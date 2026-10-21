"""Offline public-client protocol tests; no listeners or real tokens are created."""

from contextlib import asynccontextmanager
import os
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
from jose import jwk, jwt
import pytest

from core import chatgpt_oauth as oauth


@pytest.fixture
def material():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    key = jwk.construct(public, algorithm="RS256").to_dict()
    key.update(kid="issuer-key", alg="RS256")
    return pem, key


@pytest.fixture
def attempt():
    return oauth.AuthorizationAttempt("http://127.0.0.1:54321/auth/callback", "urn:uuid:00000000-0000-0000-0000-000000000001")


def id_token(material, attempt, *, access_token=None, **overrides):
    claims = dict(iss=oauth.ISSUER, sub="account-subject", aud="oaiapp_test", exp=int(time.time()) + 300, nonce=attempt.nonce, email="user@example.com")
    claims.update(overrides)
    return jwt.encode(claims, material[0], algorithm="RS256", headers={"kid": "issuer-key"}, access_token=access_token)


def callback(attempt, **overrides):
    params = dict(state=attempt.state, code="single-use-code", client_id="oaiapp_test")
    params.update(overrides)
    return attempt.redirect_uri + "?" + urlencode(params)


def test_authorize_url_pkce_and_separate_attempts(attempt):
    params = parse_qs(urlsplit(oauth.authorization_url(attempt)).query)
    assert params["client_id"] == [oauth.INITIAL_CLIENT]
    assert params["agent_name_hint"] == [oauth.AGENT_NAME]
    assert params["code_challenge_method"] == ["S256"]
    assert params["resource"] == [oauth.RESOURCE]
    assert params["code_challenge"][0] != attempt.verifier
    assert oauth.AuthorizationAttempt(attempt.redirect_uri, attempt.host_id).state != attempt.state


def test_reauthorization_uses_selected_account_without_agent_name(attempt):
    attempt.client_id = "oaiapp_test"
    attempt.expected_subject = "account-subject"
    params = parse_qs(urlsplit(oauth.authorization_url(attempt, dict(client_id=attempt.client_id, subject=attempt.expected_subject, id_token="private-hint"))).query)
    assert "agent_name_hint" not in params
    assert params["id_token_hint"] == ["private-hint"]
    # The CLI's --no-browser path omits all token-bearing hints.
    assert "id_token_hint" not in oauth.authorization_url(attempt)


@pytest.mark.parametrize("changes", [dict(state="wrong"), dict(error="access_denied"), dict(client_id="dynamic_agent_client"), dict(client_id=""), dict(code="")])
def test_invalid_callback_rejected(attempt, changes):
    with pytest.raises(oauth.ChatGPTOAuthError):
        oauth.callback_result(attempt, callback(attempt, **changes))


def test_returning_callback_cannot_change_client(attempt):
    attempt.client_id = "oaiapp_original"
    with pytest.raises(oauth.ChatGPTOAuthError, match="changed"):
        oauth.callback_result(attempt, callback(attempt))
    assert oauth.callback_result(attempt, attempt.redirect_uri + "?" + urlencode(dict(state=attempt.state, code="code")))[1] == "oaiapp_original"


@pytest.mark.asyncio
async def test_code_exchange_uses_issued_id_exact_redirect_and_scope(material, attempt):
    requests = []

    def respond(request):
        requests.append(request)
        if str(request.url) == oauth.JWKS_URL:
            return httpx.Response(200, json={"keys": [material[1]]})
        return httpx.Response(200, json=dict(access_token="access", refresh_token="refresh", token_type="Bearer", expires_in=3600, scope=oauth.SCOPES, id_token=id_token(material, attempt, access_token="access")))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        record = await oauth.complete_authorization(attempt, callback(attempt), client)
    form = parse_qs(requests[0].content.decode())
    assert form["client_id"] == ["oaiapp_test"]
    assert form["redirect_uri"] == [attempt.redirect_uri]
    assert form["code_verifier"] == [attempt.verifier]
    assert form["resource"] == [oauth.RESOURCE]
    assert "client_secret" not in form
    assert record["subject"] == "account-subject"
    assert record["client_id"] == "oaiapp_test"


@pytest.mark.asyncio
@pytest.mark.parametrize("provided_access_token", [None, "wrong-access-token"])
async def test_identity_rejects_missing_or_wrong_access_token_hash(material, attempt, provided_access_token):
    token = id_token(material, attempt, access_token="correct-access-token")
    assert "at_hash" in jwt.get_unverified_claims(token)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"keys": [material[1]]}))) as client:
        with pytest.raises(oauth.ChatGPTOAuthError, match=r"\[access_token_hash\]") as error:
            await oauth.validate_identity(client, token, "oaiapp_test", access_token=provided_access_token, nonce=attempt.nonce)
    assert "correct-access-token" not in str(error.value)
    assert "wrong-access-token" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("changes,diagnostic", [(dict(iss="private-wrong-issuer"), "issuer"), (dict(aud="private-wrong-audience"), "audience"), (dict(nonce="private-wrong-nonce"), "nonce")])
async def test_identity_diagnostics_are_fixed_labels_not_claims(material, attempt, changes, diagnostic):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"keys": [material[1]]}))) as client:
        with pytest.raises(oauth.ChatGPTOAuthError, match=rf"\[{diagnostic}\]") as error:
            await oauth.validate_identity(client, id_token(material, attempt, **changes), "oaiapp_test", nonce=attempt.nonce)
    assert "private-wrong" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [dict(iss="https://other.example"), dict(aud="another-client"), dict(exp=1), dict(nonce="wrong"), dict(sub="")])
async def test_id_token_validation_rejects_invalid_identity(material, attempt, changes):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"keys": [material[1]]}))) as client:
        with pytest.raises(oauth.ChatGPTOAuthError):
            await oauth.validate_identity(client, id_token(material, attempt, **changes), "oaiapp_test", nonce=attempt.nonce)


@pytest.mark.asyncio
async def test_returning_identity_must_match(material, attempt):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"keys": [material[1]]}))) as client:
        with pytest.raises(oauth.ChatGPTOAuthError):
            await oauth.validate_identity(client, id_token(material, attempt), "oaiapp_test", expected_subject="another-account")


@pytest.mark.asyncio
async def test_id_token_signature_must_match_published_key(material, attempt):
    unrelated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = unrelated.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    key = jwk.construct(public, algorithm="RS256").to_dict()
    key["kid"] = "issuer-key"
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"keys": [key]}))) as client:
        with pytest.raises(oauth.ChatGPTOAuthError):
            await oauth.validate_identity(client, id_token(material, attempt), "oaiapp_test", nonce=attempt.nonce)


@pytest.mark.asyncio
async def test_save_account_cannot_overwrite_other_registration(monkeypatch, tmp_path):
    path = tmp_path / "account.json"
    path.write_text("{}")

    @asynccontextmanager
    async def unlocked(path):
        yield

    monkeypatch.setattr(oauth, "_session_lock", unlocked)
    monkeypatch.setattr(oauth, "read_private_json", lambda path: dict(client_id="other-client", subject="other-user"))
    with pytest.raises(oauth.ChatGPTOAuthError, match="another registration"):
        await oauth.save_authorized_account(path, dict(client_id="new-client", subject="new-user"))


def test_callback_scopes_cannot_authorize_missing_token_response_permission():
    with pytest.raises(oauth.ChatGPTOAuthError, match="permission"):
        oauth._token_record(dict(scope="openid profile email", access_token="access", token_type="Bearer", expires_in=3600))


@pytest.mark.asyncio
@pytest.mark.parametrize("bound_access_token", ["new-access", "wrong-access"])
async def test_refresh_rotates_credentials_together_without_scope_or_secret(monkeypatch, tmp_path, material, attempt, bound_access_token):
    saved = dict(issuer=oauth.ISSUER, subject="account-subject", client_id="oaiapp_test", ext_agent_host_id="host", email="user@example.com",
                 access_token="old-access", refresh_token="old-refresh", id_token="retained-id", scopes=oauth.SCOPES.split(), expires_at=1)
    written = []
    forms = []
    renewed_id_token = id_token(material, attempt, access_token=bound_access_token)

    @asynccontextmanager
    async def unlocked(path):
        yield

    def respond(request):
        if str(request.url) == oauth.JWKS_URL:
            return httpx.Response(200, json={"keys": [material[1]]})
        forms.append(parse_qs(request.content.decode()))
        return httpx.Response(200, json=dict(access_token="new-access", refresh_token="new-refresh", token_type="Bearer", expires_in=3600, id_token=renewed_id_token))

    real_client = httpx.AsyncClient
    monkeypatch.setattr(oauth, "_session_lock", unlocked)
    monkeypatch.setattr(oauth, "read_private_json", lambda path: dict(saved))
    monkeypatch.setattr(oauth, "write_private_json", lambda path, record: written.append(record))
    monkeypatch.setattr(oauth.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(respond)))
    if bound_access_token != "new-access":
        with pytest.raises(oauth.ChatGPTOAuthError, match=r"\[access_token_hash\]"):
            await oauth.get_access_token(tmp_path / "account.json")
        assert written == []
        return
    assert await oauth.get_access_token(tmp_path / "account.json") == "new-access"
    assert forms[0]["client_id"] == ["oaiapp_test"]
    assert forms[0]["refresh_token"] == ["old-refresh"]
    assert forms[0]["resource"] == [oauth.RESOURCE]
    assert "scope" not in forms[0] and "client_secret" not in forms[0]
    assert written[0]["refresh_token"] == "new-refresh"
    assert written[0]["id_token"] == renewed_id_token
    assert written[0]["subject"] == saved["subject"]
    assert written[0]["expires_at"] > time.time()


@pytest.mark.asyncio
async def test_error_diagnostics_never_include_endpoint_body():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(400, json={"error": "secret-token-value"}))) as client:
        with pytest.raises(oauth.ChatGPTOAuthError) as error:
            await oauth._request_json(client, "POST", oauth.TOKEN_URL)
    assert "secret-token-value" not in str(error.value)


@pytest.mark.skipif(os.name != "posix", reason="Unix permissions cannot be verified on Windows")
def test_private_storage_permissions_host_stability_and_symlink_rejection(tmp_path):
    directory = tmp_path / "private"
    host_id = oauth.load_host_id(directory)
    assert oauth.load_host_id(directory) == host_id
    target = directory / "account.json"
    oauth.write_private_json(target, {"private": "test"})
    assert target.stat().st_mode & 0o777 == 0o600
    assert directory.stat().st_mode & 0o777 == 0o700
    linked = directory / "linked.json"
    linked.symlink_to(target)
    with pytest.raises(oauth.ChatGPTOAuthError):
        oauth.read_private_json(linked)
    target.chmod(0o644)
    with pytest.raises(oauth.ChatGPTOAuthError):
        oauth.read_private_json(target)


@pytest.mark.skipif(os.name == "posix", reason="Windows fail-closed branch")
def test_windows_storage_fails_closed(tmp_path):
    with pytest.raises(oauth.ChatGPTOAuthError, match="Pi or WSL"):
        oauth.write_private_json(tmp_path / "account.json", {"token": "test"})
