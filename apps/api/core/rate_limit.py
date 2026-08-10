"""Rate limiting via slowapi (async-safe, per-user/per-IP).

Replaces the homegrown in-memory token bucket. Keyed on the authenticated
user id when available, falling back to client IP — so shared NATs or
proxy deployments don't collapse into one bucket.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _rate_limit_key(request: Request) -> str:
    """Key on authenticated user id when present, else client IP."""
    # GlobalAuthMiddleware sets request.state.user (see core.auth_middleware)
    user = getattr(request.state, "user", None)
    if user and getattr(user, "id", None):
        return f"user:{user.id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["60/minute"],
    # Headers are a nice-to-have; disable when behind proxies that strip them.
    headers_enabled=True,
)
