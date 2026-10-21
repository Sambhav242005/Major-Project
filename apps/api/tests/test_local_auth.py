"""Real local passwords, signed sessions and profile foreign-key integration."""

import time
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from jose import JWTError, jwt
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core import local_auth, security
from core.auth_middleware import GlobalAuthMiddleware
from core.config import settings
from core.deps import _ensure_user_and_project
from core.rate_limit import limiter
from db.local_auth import LocalAccount
from db.models import Profile
from db.session import Base, get_db
from routers.auth import router


@pytest.fixture(autouse=True)
def auth_config(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "local")
    monkeypatch.setattr(settings, "LOCAL_AUTH_SECRET", "test-local-secret-with-more-than-32-characters")
    monkeypatch.setattr(settings, "LOCAL_AUTH_TOKEN_TTL_SECONDS", 3600)
    monkeypatch.setattr(settings, "MOCK_AUTH", False)


@pytest_asyncio.fixture
async def db(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enforce_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("db.session.async_session_factory", factory)
    async with factory() as session:
        yield session
    await engine.dispose()


def test_password_hash_uses_random_salt_and_verifies():
    first = local_auth.hash_password("a strong test password")
    second = local_auth.hash_password("a strong test password")
    assert first != second
    assert "a strong test password" not in first
    assert first.startswith("pbkdf2_sha256$600000$")
    assert local_auth.verify_password("a strong test password", first)
    assert not local_auth.verify_password("wrong password", first)
    assert not local_auth.verify_password("password", "malformed hash")


@pytest.mark.parametrize("password", ["short", "a" * 1025])
def test_rejects_invalid_new_password_length(password):
    with pytest.raises(ValueError):
        local_auth.hash_password(password)


@pytest.mark.asyncio
async def test_account_creation_normalizes_email_and_preserves_profile_identity(db):
    account = await local_auth.create_account(db, "  Member@Example.COM ", "a strong test password")
    assert account.email == "member@example.com"
    profile = (await db.execute(select(Profile).where(Profile.id == account.id))).scalar_one()
    assert profile.id == account.id
    user = security.User(id=str(account.id), email=account.email)
    project = await _ensure_user_and_project(db, user)
    assert isinstance(project, uuid.UUID)
    assert await local_auth.authenticate(db, " MEMBER@example.com ", "a strong test password") is account
    assert await local_auth.authenticate(db, account.email, "wrong password") is None
    assert await local_auth.authenticate(db, "missing@example.com", "a strong test password") is None
    account.active = False
    await db.flush()
    assert await local_auth.authenticate(db, account.email, "a strong test password") is None
    with pytest.raises(ValueError, match="already exists"):
        await local_auth.create_account(db, "MEMBER@EXAMPLE.COM", "another strong password")


@pytest.mark.asyncio
async def test_local_jwt_does_not_fetch_supabase_keys(monkeypatch, db):
    fetch = AsyncMock(side_effect=AssertionError("Local JWT must not contact Supabase"))
    monkeypatch.setattr(security, "_fetch_jwks", fetch)
    account = await local_auth.create_account(db, "member@example.com", "a strong test password")
    await db.commit()
    user_id = account.id
    token, expires = local_auth.create_access_token(user_id, "member@example.com")
    payload = await security.decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["exp"] == expires
    fetch.assert_not_awaited()


@pytest.mark.parametrize("overrides", [
    {"iss": "another-issuer"}, {"aud": "another-audience"}, {"exp": 1},
    {"sub": ""}, {"sub": "not-a-uuid"}, {"sub": None},
])
def test_local_jwt_rejects_invalid_claims(overrides):
    claims = dict(sub=str(uuid.uuid4()), iss=local_auth.ISSUER, aud="authenticated", exp=int(time.time()) + 300)
    claims.update(overrides)
    token = jwt.encode(claims, settings.LOCAL_AUTH_SECRET, algorithm="HS256")
    with pytest.raises(JWTError):
        local_auth.decode_local_access_token(token)


@pytest.mark.parametrize("missing", ["sub", "exp", "iss", "aud"])
def test_local_jwt_rejects_missing_claims(missing):
    claims = dict(sub=str(uuid.uuid4()), iss=local_auth.ISSUER, aud="authenticated", exp=int(time.time()) + 300)
    claims.pop(missing)
    with pytest.raises(JWTError):
        local_auth.decode_local_access_token(jwt.encode(claims, settings.LOCAL_AUTH_SECRET, algorithm="HS256"))


def test_local_jwt_rejects_wrong_key_and_algorithm():
    claims = dict(sub=str(uuid.uuid4()), iss=local_auth.ISSUER, aud="authenticated", exp=int(time.time()) + 300)
    for key, algorithm in [("other-secret-of-sufficient-length", "HS256"), (settings.LOCAL_AUTH_SECRET, "HS384")]:
        with pytest.raises(JWTError):
            local_auth.decode_local_access_token(jwt.encode(claims, key, algorithm=algorithm))


@pytest.mark.asyncio
async def test_supabase_provider_rejects_local_token(monkeypatch):
    token, _ = local_auth.create_access_token(uuid.uuid4(), "member@example.com")
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabase")
    with pytest.raises(JWTError):
        await security.decode_access_token(token)


@pytest.mark.asyncio
async def test_login_route_and_authenticated_me_with_real_password_and_session(db, monkeypatch):
    account = await local_auth.create_account(db, "member@example.com", "a strong test password")
    await db.commit()
    app = FastAPI()
    app.state.limiter = limiter
    app.add_middleware(GlobalAuthMiddleware)
    app.include_router(router, prefix="/auth")

    @app.get("/private")
    async def private():
        return {"ok": True}

    async def session_override():
        yield db

    app.dependency_overrides[get_db] = session_override
    # Isolation from rate-limit counts in other in-process app tests.
    monkeypatch.setattr(limiter, "enabled", False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/local-login", json={"email": account.email, "password": "a strong test password"})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        data = response.json()
        assert data["user"]["id"] == str(account.id)
        assert data["session"]["user"] == data["user"]
        token = data["session"]["access_token"]
        assert "password" not in response.text
        me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200 and me.json()["id"] == str(account.id)
        assert (await client.get("/private", headers={"Authorization": f"Bearer {token}"})).status_code == 200
        denied = await client.post("/auth/local-login", json={"email": account.email, "password": "wrong password"})
        assert denied.status_code == 401
        assert (await client.post("/auth/signup", json={})).status_code == 403
        account.active = False
        await db.commit()
        assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401
        assert (await client.get("/private", headers={"Authorization": f"Bearer {token}"})).status_code == 401
        monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabase")
        assert (await client.post("/auth/local-login", json={"email": account.email, "password": "a strong test password"})).status_code == 403


@pytest.mark.asyncio
async def test_local_login_enforces_ten_attempts_per_minute(db, monkeypatch):
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(router, prefix="/auth")

    async def session_override():
        yield db

    app.dependency_overrides[get_db] = session_override
    monkeypatch.setattr(limiter, "enabled", True)
    # Password correctness is tested above; isolate this test to the rate boundary.
    monkeypatch.setattr(local_auth, "authenticate", AsyncMock(return_value=None))
    transport = httpx.ASGITransport(app=app, client=("198.51.100.241", 3422))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        statuses = []
        for _ in range(11):
            response = await client.post("/auth/local-login", json={"email": "member@example.com", "password": "wrong password"})
            statuses.append(response.status_code)
    assert statuses == [401] * 10 + [429]
