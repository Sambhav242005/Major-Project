"""Factory for MCP OAuth clients."""

from .client import MCPOAuthClient


def create_oauth_client(auth_config: dict | None) -> MCPOAuthClient | None:
    """Create an OAuth client from connection auth_config.

    Expected auth_config keys:
      - oauth_client_id: str
      - oauth_client_secret: str
      - oauth_token_url: str
      - oauth_authorize_url: str (optional — enables PKCE flow)
      - oauth_redirect_uri: str  (optional — required for PKCE)
      - oauth_scopes: list[str] (optional)
    """
    if not auth_config:
        return None

    client_id = auth_config.get("oauth_client_id")
    client_secret = auth_config.get("oauth_client_secret")
    token_url = auth_config.get("oauth_token_url")

    if not all([client_id, client_secret, token_url]):
        return None

    return MCPOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        token_url=token_url,
        authorize_url=auth_config.get("oauth_authorize_url"),
        scopes=auth_config.get("oauth_scopes", []),
        redirect_uri=auth_config.get("oauth_redirect_uri"),
    )
