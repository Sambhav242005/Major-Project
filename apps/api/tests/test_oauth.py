"""Tests for core/oauth.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.oauth import OAuthToken, MCPOAuthClient, create_oauth_client


# ── OAuthToken model ────────────────────────────────────────

class TestOAuthToken:
    def test_creation(self):
        token = OAuthToken(
            access_token="tok_abc",
            token_type="Bearer",
            expires_at=time.time() + 3600,
            refresh_token="ref_xyz",
            scope="read write",
        )
        assert token.access_token == "tok_abc"
        assert token.token_type == "Bearer"
        assert token.refresh_token == "ref_xyz"

    def test_is_expired(self):
        token = OAuthToken(
            access_token="t",
            token_type="Bearer",
            expires_at=time.time() - 3600,
            refresh_token=None,
            scope="",
        )
        assert token.expires_at < time.time()

    def test_is_not_expired(self):
        token = OAuthToken(
            access_token="t",
            token_type="Bearer",
            expires_at=time.time() + 3600,
            refresh_token=None,
            scope="",
        )
        assert token.expires_at > time.time()


# ── MCPOAuthClient ──────────────────────────────────────────

class TestMCPOAuthClient:
    def _make_client(self):
        return MCPOAuthClient(
            client_id="client_123",
            client_secret="secret_abc",
            token_url="https://auth.example.com/token",
            scopes=["read"],
        )

    def test_get_auth_header(self):
        client = self._make_client()
        client._token = OAuthToken(
            access_token="tok_123",
            token_type="Bearer",
            expires_at=time.time() + 3600,
            refresh_token=None,
            scope="read",
        )
        header = client.get_auth_header()
        assert header == {"Authorization": "Bearer tok_123"}

    @pytest.mark.asyncio
    async def test_get_client_credentials_token(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "cc_token",
            "token_type": "bearer",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._http_client, "post", new_callable=AsyncMock, return_value=mock_response):
            token = await client.get_client_credentials_token()
            assert token.access_token == "cc_token"
            assert token.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_exchange_code(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "auth_code_token",
            "token_type": "bearer",
            "expires_in": 3600,
            "refresh_token": "ref_new",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._http_client, "post", new_callable=AsyncMock, return_value=mock_response):
            token = await client.exchange_code("auth_code_123", "https://app/callback")
            assert token.access_token == "auth_code_token"
            assert token.refresh_token == "ref_new"

    @pytest.mark.asyncio
    async def test_refresh_token(self):
        client = self._make_client()
        client._token = OAuthToken(
            access_token="old_token",
            token_type="Bearer",
            expires_at=time.time() - 3600,
            refresh_token="ref_old",
            scope="read",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_token",
            "token_type": "bearer",
            "expires_in": 3600,
            "refresh_token": "ref_new",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._http_client, "post", new_callable=AsyncMock, return_value=mock_response):
            token = await client.refresh_token()
            assert token.access_token == "refreshed_token"
            assert token.refresh_token == "ref_new"

    @pytest.mark.asyncio
    async def test_close(self):
        client = self._make_client()
        with patch.object(client._http_client, "aclose", new_callable=AsyncMock) as mock_close:
            await client.close()
            mock_close.assert_awaited_once()


# ── create_oauth_client ─────────────────────────────────────

class TestCreateOAuthClient:
    def test_returns_client_for_valid_config(self):
        config = {
            "oauth_token_url": "https://auth.example.com/token",
            "oauth_client_id": "id",
            "oauth_client_secret": "secret",
        }
        result = create_oauth_client(config)
        assert isinstance(result, MCPOAuthClient)

    def test_returns_none_for_empty_config(self):
        assert create_oauth_client({}) is None

    def test_returns_none_for_none(self):
        assert create_oauth_client(None) is None

    def test_returns_none_missing_token_url(self):
        config = {"oauth_client_id": "id", "oauth_client_secret": "secret"}
        assert create_oauth_client(config) is None

    def test_returns_none_missing_client_id(self):
        config = {"oauth_token_url": "https://x.com/t", "oauth_client_secret": "s"}
        assert create_oauth_client(config) is None
