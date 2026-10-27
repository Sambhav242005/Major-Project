from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.security import get_current_user, User
from core.errors import NotFoundError
from core.rate_limit import limiter
from core.security_utils import sanitize_input
from core.sse import generator_sse_stream
from db.session import get_db
from services import chat as chat_service
from services.chat.request_capture import get_snapshot_for_project
from core.config import settings
from pipelines.llm_client import GenerationConfig

router = APIRouter()


class CreateSessionRequest(BaseModel):
    title: str | None = None


class GenerationSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["configured", "openai", "groq", "openrouter", "gemini", "chatgpt"] = "configured"
    model: str | None = Field(default=None, min_length=1, max_length=200)
    api_key: SecretStr | None = None

    @field_validator("model")
    @classmethod
    def clean_model(cls, value):
        if value is not None:
            value = value.strip()
            if not value or any(ord(char) < 32 for char in value):
                raise ValueError("Enter a valid model ID")
        return value

    def resolve(self) -> GenerationConfig:
        if self.provider == "configured":
            return GenerationConfig(settings.LLM_PROVIDER, self.model or settings.LLM_CHAT_MODEL,
                                    settings.LLM_BASE_URL, settings.LLM_API_KEY)
        if not self.model:
            raise HTTPException(422, "Enter a model ID for the selected provider")
        if self.provider == "chatgpt":
            if not settings.CHATGPT_CREDENTIALS_PATH:
                raise HTTPException(422, "ChatGPT is not connected on the server")
            return GenerationConfig("chatgpt", self.model)
        key = self.api_key.get_secret_value().strip() if self.api_key else ""
        if not key or any(ord(char) < 32 or ord(char) > 126 for char in key):
            raise HTTPException(422, "Enter an API key for the selected provider")
        endpoints = {
            "openai": "https://api.openai.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
        }
        return GenerationConfig("openai", self.model, endpoints[self.provider], key)


class SendMessageRequest(BaseModel):
    message: str
    generation: GenerationSelection | None = None


@router.post("/sessions")
async def create_chat_session(
    body: CreateSessionRequest | None = None,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    title = body.title if body else None
    session = await chat_service.create_session(db, user, project_id, title)
    return session


@router.get("/sessions")
async def list_chat_sessions(
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions = await chat_service.list_sessions(db, project_id)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_chat_session(
    session_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await chat_service.get_session(db, session_id, project_id)
    if not session:
        raise NotFoundError("Chat session not found")
    return session


@router.post("/sessions/{session_id}/messages")
@limiter.limit("60/minute")
async def send_message(
    request: Request,
    response: Response,
    session_id: str,
    body: SendMessageRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify session exists
    session = await chat_service.get_session(db, session_id, project_id)
    if not session:
        raise NotFoundError("Chat session not found")

    # Sanitize user input
    safe_message = sanitize_input(body.message)
    generation = body.generation.resolve() if body.generation else None

    # SSE streaming response
    return await generator_sse_stream(
        chat_service.send_message(
            db=db,
            session_id=session_id,
            message=safe_message,
            project_id=project_id,
            actor_id=user.id,
            **({"generation": generation} if generation else {}),
        )
    )


@router.get("/model-requests/{request_id}")
async def get_model_request(
    request_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read-only sanitized snapshot of what was sent to the chat model.

    Returns one request tied to a chat turn. Unknown/expired snapshots and
    snapshots owned by another project are both 404, so a caller cannot probe
    for other accounts' requests by id.
    """
    snapshot = await get_snapshot_for_project(db, request_id, project_id)
    if snapshot is None:
        raise NotFoundError("Model request snapshot not found or expired")
    return snapshot
