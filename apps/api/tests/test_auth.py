"""TDD tests for authentication — JWT validation, user extraction."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException

from core.security import get_current_user, User


# --- Test: Valid token returns User ---

@pytest.mark.asyncio
@patch("core.security._get_signing_key")
@patch("core.security.jwt.decode")
async def test_valid_token_returns_user(mock_decode, mock_get_key):
    mock_get_key.return_value = MagicMock()
    mock_decode.return_value = {"sub": "user-123", "email": "test@example.com"}

    credentials = MagicMock()
    credentials.credentials = "valid-token"

    user = await get_current_user(credentials)

    assert user.id == "user-123"
    assert user.email == "test@example.com"


# --- Test: Missing sub claim raises 401 ---

@pytest.mark.asyncio
@patch("core.security._get_signing_key")
@patch("core.security.jwt.decode")
async def test_missing_sub_raises_401(mock_decode, mock_get_key):
    mock_get_key.return_value = MagicMock()
    mock_decode.return_value = {"email": "test@example.com"}  # no sub

    credentials = MagicMock()
    credentials.credentials = "token-no-sub"

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == 401
    assert "missing sub claim" in exc_info.value.detail


# --- Test: Expired token raises 401 ---

@pytest.mark.asyncio
@patch("core.security._get_signing_key")
@patch("core.security.jwt.decode")
async def test_expired_token_raises_401(mock_decode, mock_get_key):
    from jose import JWTError

    mock_get_key.return_value = MagicMock()
    mock_decode.side_effect = JWTError("Signature has expired")

    credentials = MagicMock()
    credentials.credentials = "expired-token"

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == 401


# --- Test: Malformed token raises 401 ---

@pytest.mark.asyncio
@patch("core.security._get_signing_key")
@patch("core.security.jwt.decode")
async def test_malformed_token_raises_401(mock_decode, mock_get_key):
    from jose import JWTError

    mock_get_key.return_value = MagicMock()
    mock_decode.side_effect = JWTError("Not enough segments")

    credentials = MagicMock()
    credentials.credentials = "not-a-jwt"

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)

    assert exc_info.value.status_code == 401
