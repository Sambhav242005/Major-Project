"""Public-client Sign in with ChatGPT, independent of Codex credentials.

Protocol: https://developers.openai.com/siwc/token-sharing-open-source/sign-in
Credential storage deliberately requires Unix ownership/permissions (Pi/WSL).
"""

import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import stat
import tempfile
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid

import httpx
from jose import jwk, jwt
from jose.exceptions import ExpiredSignatureError, JOSEError, JWTClaimsError

ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = ISSUER + "/api/accounts/authorize"
TOKEN_URL = ISSUER + "/api/accounts/oauth/token"
JWKS_URL = ISSUER + "/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
INITIAL_CLIENT = "dynamic_agent_client"
AGENT_NAME = "AI Knowledge Graph Builder"
_locks: dict[str, asyncio.Lock] = {}


class ChatGPTOAuthError(RuntimeError):
    """Safe diagnostic: never include HTTP bodies, callback values or tokens."""


@dataclass(repr=False)
class AuthorizationAttempt:
    redirect_uri: str
    host_id: str
    client_id: str = INITIAL_CLIENT
    expected_subject: str | None = None
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    verifier: str = field(default_factory=lambda: secrets.token_urlsafe(64))


def authorization_url(attempt: AuthorizationAttempt, previous: dict | None = None) -> str:
    redirect = urlsplit(attempt.redirect_uri)
    if redirect.scheme != "http" or redirect.hostname != "127.0.0.1" or redirect.path != "/auth/callback" or not redirect.port or redirect.query or redirect.fragment:
        raise ChatGPTOAuthError("OAuth requires an exact HTTP 127.0.0.1 loopback callback.")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(attempt.verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    params = dict(client_id=attempt.client_id, ext_agent_host_id=attempt.host_id,
                  response_type="code", redirect_uri=attempt.redirect_uri, scope=SCOPES,
                  resource=RESOURCE, state=attempt.state, nonce=attempt.nonce,
                  code_challenge_method="S256", code_challenge=challenge)
    if attempt.client_id == INITIAL_CLIENT:
        params["agent_name_hint"] = AGENT_NAME
    elif previous:
        if previous.get("client_id") != attempt.client_id or previous.get("subject") != attempt.expected_subject:
            raise ChatGPTOAuthError("Selected account does not match this sign-in attempt.")
        if previous.get("id_token"):
            params["id_token_hint"] = previous["id_token"]
        if previous.get("email"):
            params["login_hint"] = previous["email"]
    return AUTHORIZE_URL + "?" + urlencode(params)


def callback_result(attempt: AuthorizationAttempt, callback_url: str) -> tuple[str, str]:
    callback = urlsplit(callback_url)
    expected = urlsplit(attempt.redirect_uri)
    if (callback.scheme, callback.netloc, callback.path) != (expected.scheme, expected.netloc, expected.path):
        raise ChatGPTOAuthError("Unexpected OAuth callback URI.")
    params = parse_qs(callback.query, keep_blank_values=True)
    if any(len(values) != 1 for values in params.values()):
        raise ChatGPTOAuthError("Ambiguous OAuth callback parameters.")
    if not secrets.compare_digest(params.get("state", [""])[0], attempt.state):
        raise ChatGPTOAuthError("OAuth state did not match; start sign-in again.")
    if "error" in params:
        raise ChatGPTOAuthError("ChatGPT authorization was declined or failed.")
    client_id = params.get("client_id", [attempt.client_id])[0]
    if not client_id or client_id == INITIAL_CLIENT:
        raise ChatGPTOAuthError("Registration did not return an issued client ID.")
    if attempt.client_id != INITIAL_CLIENT and client_id != attempt.client_id:
        raise ChatGPTOAuthError("Returning sign-in changed the selected client ID.")
    code = params.get("code", [""])[0]
    if not code:
        raise ChatGPTOAuthError("Authorization did not return a code.")
    return code, client_id


async def _request_json(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> dict:
    try:
        response = await client.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise ChatGPTOAuthError(f"ChatGPT authorization endpoint returned HTTP {response.status_code}; sign in again if renewal failed.")
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (httpx.HTTPError, ValueError):
        raise ChatGPTOAuthError("ChatGPT authorization endpoint could not be read.") from None


async def validate_identity(client: httpx.AsyncClient, token: str, client_id: str, *, access_token: str | None = None, nonce: str | None = None, expected_subject: str | None = None) -> dict:
    stage = "token_header"
    try:
        header = jwt.get_unverified_header(token)
        stage = "signing_algorithm"
        if header.get("alg") != "RS256":
            raise ValueError
        stage = "signing_key_id"
        if not isinstance(header.get("kid"), str) or not header["kid"]:
            raise ValueError
        keys = await _request_json(client, "GET", JWKS_URL)
        stage = "signing_key_not_found"
        key = next(key for key in keys.get("keys", []) if key.get("kid") == header["kid"])
        stage = "signing_key_type"
        if key.get("kty") != "RSA" or key.get("alg", "RS256") != "RS256" or key.get("use", "sig") != "sig":
            raise ValueError
        stage = "signature_or_required_claim"
        identity = jwt.decode(token, jwk.construct(key, algorithm="RS256"), algorithms=["RS256"], issuer=ISSUER, audience=client_id,
                              access_token=access_token,
                              options={"require_exp": True, "require_iss": True, "require_aud": True, "require_sub": True})
        stage = "subject"
        if not isinstance(identity["sub"], str) or not identity["sub"].strip():
            raise ValueError
        stage = "nonce"
        if nonce is not None and (not isinstance(identity.get("nonce"), str) or not secrets.compare_digest(identity["nonce"], nonce)):
            raise ValueError
        stage = "returning_account_identity"
        if expected_subject is not None and identity["sub"] != expected_subject:
            raise ValueError
        return identity
    except ExpiredSignatureError:
        raise ChatGPTOAuthError("ChatGPT ID token validation failed [expiry].") from None
    except JWTClaimsError as error:
        # Map library messages to fixed diagnostic labels; never print claims or
        # arbitrary exception text (which could contain credential material).
        message = str(error).lower()
        if "at_hash" in message:
            stage = "access_token_hash"
        elif "issuer" in message:
            stage = "issuer"
        elif "audience" in message:
            stage = "audience"
        else:
            stage = "required_claim"
        raise ChatGPTOAuthError(f"ChatGPT ID token validation failed [{stage}].") from None
    except (JOSEError, ValueError, TypeError, KeyError, StopIteration):
        raise ChatGPTOAuthError(f"ChatGPT ID token validation failed [{stage}].") from None


def _token_record(tokens: dict, *, previous: dict | None = None) -> dict:
    scopes = tokens.get("scope")
    if scopes is None and previous is not None:
        scopes = " ".join(previous["scopes"])
    if not isinstance(scopes, str) or not {"resource.invoke", "chatgpt.tokens.use.direct"}.issubset(scopes.split()):
        raise ChatGPTOAuthError("ChatGPT plan inference permission was not granted.")
    if tokens.get("token_type", "").lower() != "bearer" or not isinstance(tokens.get("access_token"), str) or not tokens["access_token"]:
        raise ChatGPTOAuthError("Authorization returned an invalid access token record.")
    expires = tokens.get("expires_in")
    if isinstance(expires, bool) or not isinstance(expires, (int, float)) or not math.isfinite(expires) or expires <= 0:
        raise ChatGPTOAuthError("Authorization returned an invalid token expiry.")
    record = dict(previous or {})
    for name in ("access_token", "refresh_token", "id_token", "token_type"):
        if name in tokens:
            if not isinstance(tokens[name], str) or not tokens[name]:
                raise ChatGPTOAuthError("Authorization returned an invalid credential field.")
            record[name] = tokens[name]
    record.update(scopes=scopes.split(), expires_in=expires, saved_at=time.time(), expires_at=time.time() + expires)
    return record


async def complete_authorization(attempt: AuthorizationAttempt, callback_url: str, client: httpx.AsyncClient) -> dict:
    code, client_id = callback_result(attempt, callback_url)
    tokens = await _request_json(client, "POST", TOKEN_URL, data=dict(grant_type="authorization_code", client_id=client_id,
                                 code=code, code_verifier=attempt.verifier, redirect_uri=attempt.redirect_uri, resource=RESOURCE))
    if not isinstance(tokens.get("id_token"), str):
        raise ChatGPTOAuthError("Authorization did not return an ID token.")
    identity = await validate_identity(client, tokens["id_token"], client_id, access_token=tokens.get("access_token"), nonce=attempt.nonce, expected_subject=attempt.expected_subject)
    record = _token_record(tokens)
    record.update(issuer=ISSUER, subject=identity["sub"], email=identity.get("email"), client_id=client_id, ext_agent_host_id=attempt.host_id)
    return record


def _require_unix() -> None:
    if os.name != "posix":
        raise ChatGPTOAuthError("Protected credential storage requires Unix permissions. Run this login on the Pi or WSL; Windows ACL storage is not implemented.")


def _private_directory(path: Path) -> None:
    _require_unix()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ChatGPTOAuthError("Credential directory must belong to this user and have mode 0700.")


def read_private_json(path: Path) -> dict:
    _require_unix()
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "r", encoding="utf-8") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise ChatGPTOAuthError("Credential files must belong to this user and have mode 0600.")
            result = json.load(source)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (OSError, ValueError):
        raise ChatGPTOAuthError("Protected credential record could not be read.") from None


def write_private_json(path: Path, record: dict) -> None:
    _private_directory(path.parent)
    if path.exists() or path.is_symlink():
        read_private_json(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".oauth-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(record, target)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_host_id(directory: Path) -> str:
    _private_directory(directory)
    import fcntl

    descriptor = os.open(directory / "host.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ChatGPTOAuthError("Host identifier lock must be private to this user.")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return _load_host_id_locked(directory)
    finally:
        os.close(descriptor)


def _load_host_id_locked(directory: Path) -> str:
    path = directory / "host.json"
    if path.exists():
        host_id = read_private_json(path).get("ext_agent_host_id", "")
        try:
            uuid.UUID(host_id.removeprefix("urn:uuid:"))
        except (ValueError, AttributeError):
            raise ChatGPTOAuthError("Stored host identifier is invalid.") from None
        if not host_id.startswith("urn:uuid:"):
            raise ChatGPTOAuthError("Stored host identifier is invalid.")
        return host_id
    host_id = "urn:uuid:" + str(uuid.uuid4())
    write_private_json(path, {"ext_agent_host_id": host_id})
    return host_id


@asynccontextmanager
async def _session_lock(path: Path):
    _private_directory(path.parent)
    import fcntl

    lock = _locks.setdefault(str(path.absolute()), asyncio.Lock())
    async with lock:
        descriptor = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise ChatGPTOAuthError("Credential lock must be private to this user.")
            deadline = time.monotonic() + 30
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() > deadline:
                        raise ChatGPTOAuthError("Another process is renewing this ChatGPT session.") from None
                    await asyncio.sleep(0.1)
            yield
        finally:
            os.close(descriptor)


async def get_access_token(credentials_path: str | Path) -> str:
    """Return a valid token, atomically serializing rotating refreshes on this host."""
    path = Path(credentials_path).expanduser()
    async with _session_lock(path):
        record = read_private_json(path)
        if not {"resource.invoke", "chatgpt.tokens.use.direct"}.issubset(record.get("scopes", [])):
            raise ChatGPTOAuthError("Saved account has no ChatGPT plan inference permission.")
        if record.get("issuer") != ISSUER or not record.get("subject") or not record.get("client_id") or record["client_id"] == INITIAL_CLIENT:
            raise ChatGPTOAuthError("Saved ChatGPT registration is incomplete; sign in again.")
        if record.get("expires_at", 0) > time.time() + 60 and record.get("access_token"):
            return record["access_token"]
        if not record.get("refresh_token"):
            raise ChatGPTOAuthError("ChatGPT session cannot be renewed; sign in again.")
        async with httpx.AsyncClient(timeout=30) as client:
            tokens = await _request_json(client, "POST", TOKEN_URL, data=dict(grant_type="refresh_token", client_id=record["client_id"],
                                         refresh_token=record["refresh_token"], resource=RESOURCE))
            if tokens.get("id_token"):
                await validate_identity(client, tokens["id_token"], record["client_id"], access_token=tokens.get("access_token"), expected_subject=record["subject"])
            updated = _token_record(tokens, previous=record)
        write_private_json(path, updated)
        return updated["access_token"]


async def save_authorized_account(path: Path, record: dict) -> None:
    """Never replace a different registration occupying the selected account label."""
    async with _session_lock(path):
        if path.exists():
            previous = read_private_json(path)
            if (previous.get("client_id"), previous.get("subject")) != (record.get("client_id"), record.get("subject")):
                raise ChatGPTOAuthError("Account label already contains another registration; choose a new label.")
        write_private_json(path, record)
