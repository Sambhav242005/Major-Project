"""OAuth package — re-exports for backward compatibility."""

from .client import MCPOAuthClient
from .factory import create_oauth_client
from .pkce import PKCEChallenge
from .tokens import OAuthToken

# Ensure persistence methods are attached
import core.oauth.persistence  # noqa: F401

__all__ = ["OAuthToken", "PKCEChallenge", "MCPOAuthClient", "create_oauth_client"]
