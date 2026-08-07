"""Global auth middleware — enforces JWT on all routes by default.

Public routes are whitelisted. All others require valid Bearer token.
In MOCK_AUTH mode, accepts any Bearer token with a mock user.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.config import settings


# Routes that don't require auth
PUBLIC_ROUTES = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/mock-login",
}

# Route prefixes that don't require auth
PUBLIC_PREFIXES = (
    "/auth/",
)


class GlobalAuthMiddleware(BaseHTTPMiddleware):
    """Enforces JWT authentication on all routes except whitelisted public ones.

    In MOCK_AUTH mode, accepts any Bearer token and assigns a mock user.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public routes
        if path in PUBLIC_ROUTES or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
            )

        token = auth_header[7:]  # strip "Bearer "

        # Mock auth mode — accept any token
        if settings.MOCK_AUTH:
            request.state.user_id = "mock-user-001"
            request.state.user_email = "mock@example.com"
            return await call_next(request)

        # Real auth mode — validate JWT
        try:
            from core.security import _get_signing_key
            from jose import jwt, JWTError

            signing_key = await _get_signing_key(token)
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience="authenticated",
            )

            if not payload.get("sub"):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid token: missing sub claim"},
                )

            request.state.user_id = payload["sub"]
            request.state.user_email = payload.get("email")

        except JWTError as e:
            return JSONResponse(
                status_code=401,
                content={"detail": f"Invalid token: {e}"},
            )
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication failed"},
            )

        return await call_next(request)
