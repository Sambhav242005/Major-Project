"""Offline verification of real Supabase asymmetric JWT signatures and claims."""

import time
from unittest.mock import AsyncMock

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import Depends, FastAPI
from jose import JWTError, jwk, jwt

from core import security
from core.auth_middleware import GlobalAuthMiddleware


@pytest.fixture(params=["RS256", "ES256"])
def signing_material(request):
    algorithm = request.param
    private = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        if algorithm == "RS256"
        else ec.generate_private_key(ec.SECP256R1())
    )
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    public_jwk = jwk.construct(public_pem, algorithm=algorithm).to_dict()
    public_jwk.update(kid="test-signing-key", alg=algorithm, use="sig")
    return algorithm, private_pem, public_jwk


@pytest.fixture
def auth_setup(monkeypatch, signing_material):
    monkeypatch.setattr(security.settings, "MOCK_AUTH", False)
    monkeypatch.setattr(security.settings, "SUPABASE_URL", "https://example.supabase.co/")
    monkeypatch.setattr(security, "_fetch_jwks", AsyncMock(return_value={"keys": [signing_material[2]]}))
    return signing_material


def signed_token(material, **overrides):
    claims = {
        "sub": "e76cfad6-c9a4-44ea-a1a8-fab04fe3d162",
        "email": "member@example.com",
        "iss": "https://example.supabase.co/auth/v1",
        "aud": "authenticated",
        "exp": int(time.time()) + 300,
    }
    claims.update(overrides)
    return jwt.encode(claims, material[1], algorithm=material[0], headers={"kid": "test-signing-key"})


@pytest.mark.asyncio
async def test_real_signature_authenticates_dependency_and_middleware(auth_setup):
    app = FastAPI()
    app.add_middleware(GlobalAuthMiddleware)

    @app.get("/private")
    async def private(user=Depends(security.get_current_user)):
        return {"id": user.id, "email": user.email}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/private", headers={"Authorization": f"Bearer {signed_token(auth_setup)}"})
    assert response.status_code == 200
    assert response.json()["email"] == "member@example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides", [
    {"iss": "https://attacker.supabase.co/auth/v1"},
    {"aud": "another-audience"},
    {"exp": int(time.time()) - 120},
    {"sub": ""},
    {"sub": None},
    {"sub": "   "},
])
async def test_rejects_invalid_claims(auth_setup, overrides):
    with pytest.raises(JWTError):
        await security.decode_access_token(signed_token(auth_setup, **overrides))


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["iss", "aud", "exp", "sub"])
async def test_rejects_missing_required_claims(auth_setup, missing):
    token = signed_token(auth_setup)
    claims = jwt.get_unverified_claims(token)
    claims.pop(missing)
    token = jwt.encode(claims, auth_setup[1], algorithm=auth_setup[0], headers={"kid": "test-signing-key"})
    with pytest.raises(JWTError):
        await security.decode_access_token(token)


@pytest.mark.asyncio
async def test_rejects_symmetric_algorithm_without_fetching_keys(auth_setup):
    token = jwt.encode({"sub": "user"}, "secret", algorithm="HS256", headers={"kid": "test-signing-key"})
    with pytest.raises(JWTError, match="unsupported signing algorithm"):
        await security.decode_access_token(token)
    security._fetch_jwks.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kid", [None, "", "  ", 123])
async def test_rejects_missing_or_malformed_key_id(auth_setup, kid):
    headers = {} if kid is None else {"kid": kid}
    token = jwt.encode({"sub": "user"}, auth_setup[1], algorithm=auth_setup[0], headers=headers)
    with pytest.raises(JWTError, match="key ID"):
        await security.decode_access_token(token)
    security._fetch_jwks.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    {"kty": "oct"}, {"alg": "HS256"}, {"use": "enc"}, {"kid": "other-key"},
])
async def test_rejects_mismatched_signing_key(auth_setup, change):
    auth_setup[2].update(change)
    with pytest.raises(JWTError):
        await security.decode_access_token(signed_token(auth_setup))


@pytest.mark.asyncio
async def test_rejects_invalid_signature(auth_setup, signing_material):
    # A different private key cannot authenticate against the selected JWKS key.
    if auth_setup[0] == "RS256":
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    else:
        other = ec.generate_private_key(ec.SECP256R1())
    pem = other.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    token = signed_token((auth_setup[0], pem, auth_setup[2]))
    with pytest.raises(JWTError):
        await security.decode_access_token(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", ["", "https://keys.example.com/jwks"])
async def test_jwks_endpoint_defaults_to_supabase_project(monkeypatch, explicit):
    monkeypatch.setattr(security.settings, "SUPABASE_URL", "https://example.supabase.co/")
    monkeypatch.setattr(security.settings, "SUPABASE_JWKS_URL", explicit)
    monkeypatch.setattr(security, "_jwks_cache", None)
    urls = []

    def respond(request):
        urls.append(str(request.url))
        return httpx.Response(200, json={"keys": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(security.httpx, "AsyncClient", lambda **kwargs: client)
    assert await security._fetch_jwks() == {"keys": []}
    assert urls == [explicit or "https://example.supabase.co/auth/v1/.well-known/jwks.json"]
