"""MCP OAuth 2.0 client — handles OAuth2 flows for MCP connections.

Supports:
- Client Credentials flow (server-to-server)
- Authorization Code flow (user-interactive)
- Token storage and refresh
"""

import time
import logging
from datetime import datetime, timedelta

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class OAuthToken(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: float  # unix timestamp
    refresh_token: str | None = None
    scope: str | None = None


class MCPOAuthClient:
    """OAuth 2.0 client for MCP server connections."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        scopes: list[str] | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.scopes = scopes or []
        self._token: OAuthToken | None = None
        self._http_client = httpx.AsyncClient(timeout=30.0)

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

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthToken:
        """Exchange authorization code for token (Authorization Code flow)."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
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
        scopes=auth_config.get("oauth_scopes", []),
    )
