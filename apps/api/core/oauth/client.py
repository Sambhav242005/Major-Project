"""MCP OAuth 2.0 client — HTTP flows (Client Credentials, Auth Code + PKCE, refresh)."""

import logging
import time

import httpx

from .pkce import PKCEChallenge
from .tokens import OAuthToken

logger = logging.getLogger(__name__)


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

    # --- Header ---

    def get_auth_header(self) -> dict[str, str]:
        """Get the Authorization header for API calls."""
        if not self._token:
            raise ValueError("No token available. Call get_client_credentials_token() first.")
        return {"Authorization": f"{self._token.token_type} {self._token.access_token}"}

    async def close(self):
        """Close the HTTP client."""
        await self._http_client.aclose()
