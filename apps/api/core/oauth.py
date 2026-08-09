"""MCP OAuth 2.0 client — handles OAuth2 flows for MCP connections.

Supports (MCP 2026-07-28 aligned):
- Client Credentials flow (server-to-server)
- Authorization Code + PKCE flow (user-interactive, production-grade)
- Token persistence to DB (survives restarts)
- Token refresh
"""

import hashlib
import base64
import os
import secrets
import time
import logging
from datetime import datetime, timedelta

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class OAuthToken(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: float  # unix timestamp
    refresh_token: str | None = None
    scope: str | None = None


class PKCEChallenge:
    """PKCE code_verifier + code_challenge (S256) for Authorization Code flow."""

    def __init__(self):
        self.code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(self.code_verifier.encode("ascii")).digest()
        self.code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def auth_url(self, authorize_url: str, client_id: str, redirect_uri: str,
                 scope: list[str] | None = None, state: str | None = None) -> str:
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
        }
        if scope:
            params["scope"] = " ".join(scope)
        if state:
            params["state"] = state
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{authorize_url}?{qs}"


class MCPOAuthClient:
    """OAuth 2.0 client for MCP server connections."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        authorize_url: str | None = None,
        scopes: list[str] | None = None,
        redirect_uri: str | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.authorize_url = authorize_url
        self.scopes = scopes or []
        self.redirect_uri = redirect_uri
        self._token: OAuthToken | None = None
        self._pkce: PKCEChallenge | None = None
        self._http_client = httpx.AsyncClient(timeout=30.0)

    # --- Client Credentials ---

    async def get_client_credentials_token(self) -> OAuthToken:
        """Get token using Client Credentials flow (server-to-server)."""
        if self._token and self._token.expires_at > time.time() + 60:
            return self._token

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scopes:
            data["scope"] = " ".join(self.scopes)

        try:
            resp = await self._http_client.post(self.token_url, data=data)
            resp.raise_for_status()
            token_data = resp.json()

            self._token = OAuthToken(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=time.time() + token_data.get("expires_in", 3600),
                scope=token_data.get("scope"),
            )
            return self._token

        except httpx.HTTPStatusError as e:
            logger.error(f"OAuth client credentials failed: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"OAuth client credentials error: {e}")
            raise

    # --- Authorization Code + PKCE ---

    def create_authorization_url(self, state: str | None = None) -> str:
        """Start PKCE flow — returns the URL the user should visit."""
        if not self.authorize_url:
            raise ValueError("authorize_url required for PKCE flow")
        if not self.redirect_uri:
            raise ValueError("redirect_uri required for PKCE flow")

        self._pkce = PKCEChallenge()
        return self._pkce.auth_url(
            authorize_url=self.authorize_url,
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=self.scopes or None,
            state=state,
        )

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthToken:
        """Exchange authorization code for token (Authorization Code flow)."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self._pkce:
            data["code_verifier"] = self._pkce.code_verifier

        try:
            resp = await self._http_client.post(self.token_url, data=data)
            resp.raise_for_status()
            token_data = resp.json()

            self._token = OAuthToken(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=time.time() + token_data.get("expires_in", 3600),
                refresh_token=token_data.get("refresh_token"),
                scope=token_data.get("scope"),
            )
            return self._token

        except httpx.HTTPStatusError as e:
            logger.error(f"OAuth code exchange failed: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"OAuth code exchange error: {e}")
            raise

    # --- Token Refresh ---

    async def refresh_token(self) -> OAuthToken:
        """Refresh an expired token."""
        if not self._token or not self._token.refresh_token:
            raise ValueError("No refresh token available")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._token.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            resp = await self._http_client.post(self.token_url, data=data)
            resp.raise_for_status()
            token_data = resp.json()

            self._token = OAuthToken(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=time.time() + token_data.get("expires_in", 3600),
                refresh_token=token_data.get("refresh_token", self._token.refresh_token),
                scope=token_data.get("scope"),
            )
            return self._token

        except httpx.HTTPStatusError as e:
            logger.error(f"OAuth token refresh failed: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"OAuth token refresh error: {e}")
            raise

    # --- DB Persistence ---

    async def load_token_from_db(self, db: AsyncSession, connection_id: str) -> OAuthToken | None:
        """Load persisted token from DB. Returns None if not found or expired."""
        from db.models import MCPAuthToken

        stmt = (
            select(MCPAuthToken)
            .where(MCPAuthToken.connection_id == connection_id)
            .order_by(MCPAuthToken.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None

        token = OAuthToken(
            access_token=row.access_token,
            token_type=row.token_type,
            expires_at=row.expires_at.timestamp(),
            refresh_token=row.refresh_token,
            scope=row.scope,
        )

        # If expired but has refresh token, try refreshing
        if token.expires_at <= time.time() + 60 and token.refresh_token:
            self._token = token
            try:
                refreshed = await self.refresh_token()
                await self.save_token_to_db(db, connection_id)
                return refreshed
            except Exception:
                logger.warning("Token refresh failed during DB load")
                return None

        self._token = token
        return token

    async def save_token_to_db(self, db: AsyncSession, connection_id: str) -> None:
        """Persist current token to DB."""
        if not self._token:
            return

        from db.models import MCPAuthToken

        # Upsert: delete old tokens for this connection, insert new
        old = await db.execute(
            select(MCPAuthToken).where(MCPAuthToken.connection_id == connection_id)
        )
        for row in old.scalars().all():
            await db.delete(row)

        token_row = MCPAuthToken(
            connection_id=connection_id,
            access_token=self._token.access_token,
            token_type=self._token.token_type,
            refresh_token=self._token.refresh_token,
            expires_at=datetime.fromtimestamp(self._token.expires_at),
            scope=self._token.scope,
        )
        db.add(token_row)
        await db.flush()

    # --- Header ---

    def get_auth_header(self) -> dict[str, str]:
        """Get the Authorization header for API calls."""
        if not self._token:
            raise ValueError("No token available. Call get_client_credentials_token() first.")
        return {"Authorization": f"{self._token.token_type} {self._token.access_token}"}

    async def close(self):
        """Close the HTTP client."""
        await self._http_client.aclose()


def create_oauth_client(auth_config: dict | None) -> MCPOAuthClient | None:
    """Create an OAuth client from connection auth_config.

    Expected auth_config keys:
      - oauth_client_id: str
      - oauth_client_secret: str
      - oauth_token_url: str
      - oauth_authorize_url: str (optional — enables PKCE flow)
      - oauth_redirect_uri: str  (optional — required for PKCE)
      - oauth_scopes: list[str] (optional)
    """
    if not auth_config:
        return None

    client_id = auth_config.get("oauth_client_id")
    client_secret = auth_config.get("oauth_client_secret")
    token_url = auth_config.get("oauth_token_url")

    if not all([client_id, client_secret, token_url]):
        return None

    return MCPOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        token_url=token_url,
        authorize_url=auth_config.get("oauth_authorize_url"),
        scopes=auth_config.get("oauth_scopes", []),
        redirect_uri=auth_config.get("oauth_redirect_uri"),
    )
