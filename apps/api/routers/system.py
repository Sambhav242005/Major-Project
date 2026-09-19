"""System router — health and status endpoints."""

from fastapi import APIRouter

from core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/system/status")
async def system_status():
    """Return system configuration and service availability."""
    return {
        "auth_mode": "local" if settings.MOCK_AUTH else "supabase",
        "environment": settings.ENVIRONMENT,
        "llm": {
            "base_url": settings.LLM_BASE_URL,
            "model": settings.LLM_MODEL,
        },
        "embedding": {
            "base_url": settings.EMBEDDING_BASE_URL,
            "model": settings.EMBEDDING_MODEL,
        },
    }
