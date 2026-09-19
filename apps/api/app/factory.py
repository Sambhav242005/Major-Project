"""Application factory — creates and configures the FastAPI app."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from core.auth_middleware import GlobalAuthMiddleware
from core.config import settings
from core.errors import AppError, app_error_handler
from core.rate_limit import limiter
from core.security_headers import SecurityHeadersMiddleware
from routers import agents, auth, chat, dashboard, documents, kb, mcp, meetings, projects, sharing, webhooks
from routers import system as system_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Knowledge Graph Builder API",
        version="0.1.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url=None,
    )

    app.add_exception_handler(AppError, app_error_handler)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):  # type: ignore[unused-argument]
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
        )

    # Order matters: security headers -> auth -> CORS
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(GlobalAuthMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # slowapi reads the limiter from app.state — wire it here.
    app.state.limiter = limiter

    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(documents.router, prefix="/documents", tags=["documents"])
    app.include_router(kb.router, prefix="/kb", tags=["knowledge-base"])
    app.include_router(chat.router, prefix="/chat", tags=["chat"])
    app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
    app.include_router(agents.router, prefix="/agents", tags=["agents"])
    app.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
    app.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
    app.include_router(projects.router, prefix="/projects", tags=["projects"])
    app.include_router(sharing.router, prefix="/projects/{project_id}/shares", tags=["sharing"])
    app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
    app.include_router(system_router.router)

    return app
