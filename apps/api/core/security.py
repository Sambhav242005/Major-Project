import logging

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwk, jwt, JWTError
from jose.exceptions import JWKError
from pydantic import BaseModel

from core.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

_jwks_cache: dict | None = None
_jwks_cache_ts: float | None = None
_JWKS_TTL_SECONDS = 3600
_SIGNING_ALGORITHMS = {"RS256": "RSA", "ES256": "EC"}


async def _fetch_jwks() -> dict:
    import time

    global _jwks_cache, _jwks_cache_ts
    if _jwks_cache is not None and _jwks_cache_ts is not None:
        if time.monotonic() - _jwks_cache_ts < _JWKS_TTL_SECONDS:
            return _jwks_cache
    async with httpx.AsyncClient(timeout=5.0) as client:
        jwks_url = settings.SUPABASE_JWKS_URL or (
            settings.SUPABASE_URL.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        )
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_ts = time.monotonic()
        return _jwks_cache


async def _get_signing_key(token: str):
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    algorithm = unverified_header.get("alg")
    if not isinstance(kid, str) or not kid.strip():
        raise JWTError("missing or invalid signing key ID")
    if not isinstance(algorithm, str) or algorithm not in _SIGNING_ALGORITHMS:
        raise JWTError("unsupported signing algorithm")

    jwks = await _fetch_jwks()
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            if key_data.get("kty") != _SIGNING_ALGORITHMS[algorithm]:
                raise JWTError("signing key type does not match algorithm")
            if key_data.get("alg", algorithm) != algorithm:
                raise JWTError("signing key algorithm does not match token")
            if key_data.get("use", "sig") != "sig":
                raise JWTError("signing key is not intended for signatures")
            try:
                return jwk.construct(key_data, algorithm=algorithm)
            except (ValueError, TypeError, JWKError) as exc:
                raise JWTError("invalid signing key") from exc
    raise JWTError("signing key not found")


async def decode_access_token(token: str) -> dict:
    """Validate the configured provider consistently for both auth entry points."""
    if settings.AUTH_PROVIDER == "local":
        from core.local_auth import validate_local_access_token

        return await validate_local_access_token(token)
    if settings.AUTH_PROVIDER != "supabase":
        raise JWTError("Unsupported authentication provider")
    signing_key = await _get_signing_key(token)
    payload = jwt.decode(
        token,
        signing_key,
        algorithms=list(_SIGNING_ALGORITHMS),
        audience="authenticated",
        issuer=settings.SUPABASE_URL.rstrip("/") + "/auth/v1",
        options={"require_exp": True, "require_iss": True, "require_aud": True},
    )
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise JWTError("missing sub claim")
    return payload


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
        payload = await decode_access_token(actual_token)
        return User(id=payload["sub"], email=payload.get("email"))
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )
