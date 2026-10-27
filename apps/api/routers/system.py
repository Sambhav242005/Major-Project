"""System router — health and status endpoints."""

import importlib.util
import shutil
from pathlib import Path

from fastapi import APIRouter

from core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/system/status")
async def system_status():
    """Report configured capabilities without pretending to probe providers."""
    credential_present = bool(settings.LLM_API_KEY)
    if settings.LLM_PROVIDER == "chatgpt":
        credential_present = False
        if settings.CHATGPT_CREDENTIALS_PATH:
            from core.chatgpt_oauth import ChatGPTOAuthError, read_private_json
            try:
                record = read_private_json(Path(settings.CHATGPT_CREDENTIALS_PATH))
                credential_present = bool(record.get("access_token") and record.get("refresh_token"))
            except ChatGPTOAuthError:
                pass
    configured = bool(settings.LLM_CHAT_MODEL and (
        credential_present or (settings.LLM_PROVIDER == "openai" and settings.LLM_BASE_URL)
    ))
    return {
        "auth_mode": "mock" if settings.MOCK_AUTH else settings.AUTH_PROVIDER,
        "environment": settings.ENVIRONMENT,
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_CHAT_MODEL,
            "configured": configured,
            "credential_present": credential_present,
            "readiness": "configured" if configured else "missing_credentials",
            "connectivity": "not_checked",
        },
        "embedding": {
            "provider": settings.EMBEDDING_PROVIDER,
            "model": settings.EMBEDDING_MODEL,
            "configured": bool(settings.EMBEDDING_MODEL),
            "connectivity": "not_checked",
        },
        "capabilities": {
            "document_retry": True,
            "meetings_recording": bool(shutil.which("ffmpeg") and shutil.which("flac") and importlib.util.find_spec("speech_recognition")),
            "meetings_history": True,
            "meetings_sync": False,
            "meetings_bot": False,
            "mcp_protocol": True,
            "mcp_connection_management": True,
            "mcp_connection_check": True,
            "webhooks": True,
            # Server-connected ChatGPT availability for the chat model selector.
            "chatgpt": bool(settings.CHATGPT_CREDENTIALS_PATH),
        },
    }
