"""PKCE challenge for Authorization Code flow."""

import base64
import hashlib
import secrets


class PKCEChallenge:
    """PKCE code_verifier + code_challenge (S256) for Authorization Code flow."""

    def __init__(self):
        self.code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(self.code_verifier.encode("ascii")).digest()
        self.code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def auth_url(
        self,
        authorize_url: str,
        client_id: str,
        redirect_uri: str,
        scope: list[str] | None = None,
        state: str | None = None,
    ) -> str:
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
        }
        if scope:
            params["scope"] = " ".join(scope)
        if state:
            params["state"] = state
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{authorize_url}?{qs}"
