"""Shim for backward compatibility — re-exports from core.oauth package.

New code should `from core.oauth import OAuthToken, PKCEChallenge, MCPOAuthClient, create_oauth_client`
or `from core.oauth.tokens import OAuthToken` etc. This file preserves the old
`import core.oauth` / `from core.oauth import X` paths by delegating to the package.
"""

# When the package `core/oauth/__init__.py` exists, `import core.oauth`
# resolves to the package, not this file. This shim remains for tooling,
# direct file loading, and documentation symmetry.
try:
    from core.oauth.tokens import OAuthToken  # noqa: F401
    from core.oauth.pkce import PKCEChallenge  # noqa: F401
    from core.oauth.client import MCPOAuthClient  # noqa: F401
    from core.oauth.factory import create_oauth_client  # noqa: F401
    # Ensure persistence side-effects are applied
    import core.oauth.persistence  # noqa: F401
except Exception:  # pragma: no cover
    # Fallback if package not yet importable (e.g., during py_compile of shim alone)
    pass

__all__ = ["OAuthToken", "PKCEChallenge", "MCPOAuthClient", "create_oauth_client"]
