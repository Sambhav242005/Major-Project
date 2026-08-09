"""Tests for core/oauth.py — MCP 2026-07-28 aligned."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.oauth import OAuthToken, MCPOAuthClient, PKCEChallenge, create_oauth_client


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


# ── PKCEChallenge ───────────────────────────────────────────

class TestPKCEChallenge:
    def test_creates_verifier_and_challenge(self):
        pkce = PKCEChallenge()
        assert len(pkce.code_verifier) > 40
        assert len(pkce.code_challenge) > 40
        assert pkce.code_verifier != pkce.code_challenge

    def test_challenge_is_s256(self):
        import hashlib, base64
        pkce = PKCEChallenge()
        digest = hashlib.sha256(pkce.code_verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert pkce.code_challenge == expected

    def test_auth_url_contains_pkce_params(self):
        pkce = PKCEChallenge()
        url = pkce.auth_url(
            authorize_url="https://auth.example.com/authorize",
            client_id="client_123",
            redirect_uri="https://app/callback",
        )
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert "client_id=client_123" in url
        assert "redirect_uri=https" in url

    def test_auth_url_with_scope_and_state(self):
        pkce = PKCEChallenge()
        url = pkce.auth_url(
            authorize_url="https://auth.example.com/authorize",
            client_id="c",
            redirect_uri="https://app/callback",
            scope=["read", "write"],
            state="my_state",
        )
        assert "scope=read write" in url
        assert "state=my_state" in url


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
    async def test_exchange_code_with_pkce(self):
        client = self._make_client()
        client._pkce = PKCEChallenge()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "pkce_token",
            "token_type": "bearer",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._http_client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            token = await client.exchange_code("pkce_code", "https://app/callback")
            assert token.access_token == "pkce_token"
            # Verify code_verifier was sent in the POST data
            _, kwargs = mock_post.call_args
            assert "code_verifier" in kwargs.get("data", {})

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

    def test_create_authorization_url(self):
        client = MCPOAuthClient(
            client_id="c",
            client_secret="s",
            token_url="https://auth.example.com/token",
            authorize_url="https://auth.example.com/authorize",
            redirect_uri="https://app/callback",
            scopes=["read"],
        )
        url = client.create_authorization_url(state="proj:conn")
        assert "code_challenge=" in url
        assert "state=proj%3Aconn" in url or "state=proj:conn" in url

    def test_create_authorization_url_requires_authorize_url(self):
        client = self._make_client()
        with pytest.raises(ValueError, match="authorize_url required"):
            client.create_authorization_url()

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

    def test_includes_authorize_url_when_provided(self):
        config = {
            "oauth_token_url": "https://auth.example.com/token",
            "oauth_client_id": "id",
            "oauth_client_secret": "secret",
            "oauth_authorize_url": "https://auth.example.com/authorize",
            "oauth_redirect_uri": "https://app/callback",
        }
        result = create_oauth_client(config)
        assert result.authorize_url == "https://auth.example.com/authorize"
        assert result.redirect_uri == "https://app/callback"
