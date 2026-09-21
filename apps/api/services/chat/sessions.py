"""Chat session management — create/get/list_sessions."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import _user_uuid
from core.security import User
from db.models import ChatMessage, ChatSession


async def create_session(
    db: AsyncSession,
    user: User,
    project_id: str,
    title: str | None = None,
) -> dict:
    """Create a new chat session."""
    session = ChatSession(
        project_id=uuid.UUID(project_id),
        user_id=_user_uuid(user.id),
        title=title or "New Chat",
        created_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()

    return {
        "id": str(session.id),
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


async def get_session(
    db: AsyncSession,
    session_id: str,
    project_id: str,
) -> dict | None:
    """Get chat session with messages."""
    stmt = select(ChatSession).where(
        ChatSession.id == uuid.UUID(session_id),
        ChatSession.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        return None

    # Get messages
    msg_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    msg_result = await db.execute(msg_stmt)
    messages = msg_result.scalars().all()

    return {
        "id": str(session.id),
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "citations": m.citations or [],
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


async def list_sessions(
    db: AsyncSession,
    project_id: str,
) -> list[dict]:
    """List all chat sessions for a project."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.project_id == uuid.UUID(project_id))
        .order_by(ChatSession.created_at.desc())
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "title": s.title,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]
