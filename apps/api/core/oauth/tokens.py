"""OAuth token model."""

from pydantic import BaseModel


class OAuthToken(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: float  # unix timestamp
    refresh_token: str | None = None
    scope: str | None = None
