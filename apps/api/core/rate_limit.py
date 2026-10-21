"""Rate limiting via slowapi (async-safe, per-user/per-IP).

Replaces the homegrown in-memory token bucket. Keyed on the authenticated
user id when available, falling back to client IP — so shared NATs or
proxy deployments don't collapse into one bucket.
"""

import hmac
import ipaddress

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.config import settings


def _rate_limit_key(request: Request) -> str:
    """Key on authenticated user id when present, else client IP."""
    # GlobalAuthMiddleware sets request.state.user_id
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


def local_login_rate_limit_key(request: Request) -> str:
    """Trust gateway client IPs only when relayed by our authenticated web proxy.

    The gateway overwrites X-AKGB-Client-IP and strips the proxy secret from
    incoming requests. Only the web container adds its server-only secret.
    Direct API requests and unconfigured proxies retain the socket IP limit.
    """
    secret = settings.AUTH_PROXY_SECRET
    supplied = request.headers.get("x-akgb-proxy-secret", "")
    if secret and hmac.compare_digest(secret.encode(), supplied.encode()):
        try:
            address = ipaddress.ip_address(request.headers.get("x-akgb-client-ip", ""))
            return f"ip:{address}"
        except ValueError:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["60/minute"],
    # Headers are a nice-to-have; disable when behind proxies that strip them.
    headers_enabled=True,
)
