import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.security import get_current_user, User
from core.errors import NotFoundError
from core.rate_limit import limiter
from core.security_utils import sanitize_input
from db.session import get_db
from services import chat as chat_service

router = APIRouter()


class CreateSessionRequest(BaseModel):
    title: str | None = None


class SendMessageRequest(BaseModel):
    message: str


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

    # SSE streaming response
    async def event_stream():
        async for event in chat_service.send_message(
            db=db,
            session_id=session_id,
            message=safe_message,
            project_id=project_id,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
