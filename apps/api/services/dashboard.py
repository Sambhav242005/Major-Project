"""Dashboard service — real DB queries for stats, activity, pipeline health."""

from datetime import datetime, timedelta
import uuid as _uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Document, Entity, EntityMention, Relationship,
    ChatSession, ChatMessage, Agent, AgentTask, AuditLog,
)


def _uuid_val(pid) -> _uuid.UUID:
    """Ensure project_id is a UUID object (required by Uuid() column type)."""
    if isinstance(pid, _uuid.UUID):
        return pid
    return _uuid.UUID(str(pid))


async def get_summary(db: AsyncSession, project_id) -> dict:
    """Get dashboard summary stats for a project."""
    pid = _uuid_val(project_id)

    # Document counts by status
    doc_stmt = (
        select(Document.status, func.count(Document.id))
        .where(Document.project_id == pid)
        .group_by(Document.status)
    )
    doc_result = await db.execute(doc_stmt)
    doc_counts = {"pending": 0, "processing": 0, "processed": 0, "failed": 0}
    for status, count in doc_result.all():
        if status in doc_counts:
            doc_counts[status] = count

    # Total documents
    total_stmt = select(func.count(Document.id)).where(Document.project_id == pid)
    total_result = await db.execute(total_stmt)
    total_docs = total_result.scalar() or 0

    # Entity count
    ent_stmt = select(func.count(Entity.id)).where(Entity.project_id == pid)
    ent_result = await db.execute(ent_stmt)
    total_entities = ent_result.scalar() or 0

    # Relationship count
    rel_stmt = select(func.count(Relationship.id)).where(Relationship.project_id == pid)
    rel_result = await db.execute(rel_stmt)
    total_relationships = rel_result.scalar() or 0

    # Chat sessions count
    chat_stmt = select(func.count(ChatSession.id)).where(ChatSession.project_id == pid)
    chat_result = await db.execute(chat_stmt)
    total_chats = chat_result.scalar() or 0

    # Active agents count
    agent_stmt = (
        select(func.count(Agent.id))
        .where(Agent.project_id == pid, Agent.status == "active")
    )
    agent_result = await db.execute(agent_stmt)
    active_agents = agent_result.scalar() or 0

    # Recent activity (last 10 audit log entries)
    activity_stmt = (
        select(AuditLog)
        .where(AuditLog.project_id == pid)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    activity_result = await db.execute(activity_stmt)
    recent_activity = [
        {
            "id": str(log.id),
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": str(log.resource_id) if log.resource_id else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in activity_result.scalars().all()
    ]

    # Failed documents (for pipeline health)
    failed_stmt = (
        select(Document)
        .where(Document.project_id == pid, Document.status == "failed")
        .order_by(Document.uploaded_at.desc())
        .limit(5)
    )
    failed_result = await db.execute(failed_stmt)
    failed_docs = [
        {
            "id": str(d.id),
            "filename": d.filename,
            "error_message": d.error_message,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        }
        for d in failed_result.scalars().all()
    ]

    return {
        "documents": doc_counts,
        "total_documents": total_docs,
        "total_entities": total_entities,
        "total_relationships": total_relationships,
        "total_chats": total_chats,
        "active_agents": active_agents,
        "recent_activity": recent_activity,
        "failed_documents": failed_docs,
        "pipeline_health": {
            "queue_depth": doc_counts["pending"] + doc_counts["processing"],
            "failed_count": doc_counts["failed"],
            "success_rate": (
                round(doc_counts["processed"] / total_docs * 100, 1)
                if total_docs > 0
                else 0
            ),
        },
    }
