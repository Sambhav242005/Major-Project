"""Password-based self-hosted authentication using standard-library PBKDF2."""

import base64
import hashlib
import hmac
import secrets
import time
import uuid

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.local_auth import LocalAccount

ISSUER = "akgb-local"
ITERATIONS = 600_000
# A nonexistent user still incurs the same PBKDF2 work as a real account.
_DUMMY_HASH = "pbkdf2_sha256$600000$MDAwMDAwMDAwMDAwMDAwMA==$" + base64.urlsafe_b64encode(bytes(32)).decode()


def normalize_email(email: str) -> str:
    email = email.strip().casefold()
    if len(email) > 320 or email.count("@") != 1 or any(char.isspace() for char in email):
        raise ValueError("Provide a valid email address.")
    local, domain = email.split("@")
    if not local or not domain or "." not in domain:
        raise ValueError("Provide a valid email address.")
    return email


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 1024:
        raise ValueError("Passwords must contain between 12 and 1024 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return "$".join(("pbkdf2_sha256", str(ITERATIONS), base64.urlsafe_b64encode(salt).decode(), base64.urlsafe_b64encode(digest).decode()))


def verify_password(password: str, encoded: str) -> bool:
    if not isinstance(password, str) or len(password) > 1024:
        return False
    try:
        scheme, count, salt_encoded, digest_encoded = encoded.split("$")
        iterations = int(count)
        if scheme != "pbkdf2_sha256" or not ITERATIONS <= iterations <= 2_000_000:
            return False
        salt = base64.b64decode(salt_encoded, altchars=b"-_", validate=True)
        expected = base64.b64decode(digest_encoded, altchars=b"-_", validate=True)
        if len(salt) < 16 or len(expected) != 32:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _secret() -> str:
    secret = settings.LOCAL_AUTH_SECRET
    if len(secret) < 32:
        raise JWTError("Local authentication signing secret is not configured")
    return secret


def create_access_token(user_id: uuid.UUID, email: str) -> tuple[str, int]:
    now = int(time.time())
    expires = now + settings.LOCAL_AUTH_TOKEN_TTL_SECONDS
    token = jwt.encode(dict(sub=str(user_id), email=email, iss=ISSUER, aud="authenticated", iat=now, exp=expires), _secret(), algorithm="HS256")
    return token, expires


def decode_local_access_token(token: str) -> dict:
    payload = jwt.decode(token, _secret(), algorithms=["HS256"], issuer=ISSUER, audience="authenticated",
                         options={"require_exp": True, "require_iss": True, "require_aud": True, "require_sub": True})
    try:
        uuid.UUID(payload["sub"])
    except (ValueError, TypeError, AttributeError):
        raise JWTError("Invalid local account subject") from None
    return payload


async def validate_local_access_token(token: str) -> dict:
    """Require an existing enabled account on every authenticated request."""
    from db.session import async_session_factory

    payload = decode_local_access_token(token)
    async with async_session_factory() as db:
        account = await db.get(LocalAccount, uuid.UUID(payload["sub"]))
        if account is None or not account.active:
            raise JWTError("Local account is disabled or no longer exists")
        payload["email"] = account.email
    return payload


async def authenticate(db: AsyncSession, email: str, password: str) -> LocalAccount | None:
    try:
        email = normalize_email(email)
    except ValueError:
        email = ""
    account = (await db.execute(select(LocalAccount).where(LocalAccount.email == email))).scalar_one_or_none()
    # Password derivation is CPU-bound; keep it off the ASGI event loop.
    import asyncio

    valid = await asyncio.to_thread(verify_password, password, account.password_hash if account else _DUMMY_HASH)
    if account is None or not valid or not account.active:
        return None
    return account


async def create_account(db: AsyncSession, email: str, password: str) -> LocalAccount:
    from db.models import Profile
    import asyncio

    email = normalize_email(email)
    existing = (await db.execute(select(LocalAccount.id).where(LocalAccount.email == email))).scalar_one_or_none()
    if existing is not None:
        raise ValueError("A local account already exists for this email.")
    password_hash = await asyncio.to_thread(hash_password, password)
    user_id = uuid.uuid4()
    db.add(Profile(id=user_id, full_name=email))
    await db.flush()
    account = LocalAccount(id=user_id, email=email, password_hash=password_hash)
    db.add(account)
    await db.flush()
    return account
