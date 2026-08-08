from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.errors import AppError, app_error_handler
from core.rate_limit import RateLimitMiddleware
from core.auth_middleware import GlobalAuthMiddleware
from core.security_headers import SecurityHeadersMiddleware
from routers import auth, documents, kb, chat, dashboard, agents, mcp, meetings, sharing, webhooks

app = FastAPI(
    title="AI Knowledge Graph Builder API",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

app.add_exception_handler(AppError, app_error_handler)

# Order matters: security headers -> auth -> rate limit -> CORS
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GlobalAuthMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=60, window_seconds=60)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(kb.router, prefix="/kb", tags=["knowledge-base"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
app.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
app.include_router(sharing.router, prefix="/projects/{project_id}/shares", tags=["sharing"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/system/status")
async def system_status():
    """Return system configuration and service availability."""
    import httpx

    ollama_ok = False
    ollama_model = settings.OLLAMA_MODEL
    ollama_models = []

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if r.status_code == 200:
                ollama_ok = True
                data = r.json()
                ollama_models = [m["name"] for m in data.get("models", [])]
    except Exception:
        pass

    openai_ok = bool(settings.OPENAI_API_KEY)

    return {
        "auth_mode": "local" if settings.MOCK_AUTH else "supabase",
        "environment": settings.ENVIRONMENT,
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "ollama_available": ollama_ok,
            "ollama_url": settings.OLLAMA_BASE_URL,
            "ollama_model": ollama_model,
            "ollama_models": ollama_models,
            "openai_available": openai_ok,
            "openai_model": settings.OPENAI_MODEL,
        },
    }
