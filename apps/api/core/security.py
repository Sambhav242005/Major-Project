import logging

import httpx
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from jose.backends.cryptography_backend import CryptographyRSAKey
from pydantic import BaseModel

from core.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

_jwks_cache: dict | None = None


async def _fetch_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.SUPABASE_JWKS_URL)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


async def _get_signing_key(token: str):
    jwks = await _fetch_jwks()
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return CryptographyRSAKey(key_data)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token: signing key not found",
    )


class User(BaseModel):
    id: str
    email: str | None = None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    # EventSource can't send headers — fall back to ?token= query param
    actual_token = None
    if credentials:
        actual_token = credentials.credentials
    else:
        actual_token = request.query_params.get("token")

    if not actual_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Mock auth mode — accept any token, return demo user.
    # Never usable in production: config.py rejects MOCK_AUTH in prod at startup.
    if settings.MOCK_AUTH:
        logger.warning("MOCK_AUTH: accepting any token as the demo user (development only)")
        return User(id="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11", email="mock@example.com")

    try:
        signing_key = await _get_signing_key(actual_token)
        payload = jwt.decode(
            actual_token,
            signing_key,
            algorithms=["RS256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing sub claim",
            )
        return User(id=user_id, email=payload.get("email"))
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )
