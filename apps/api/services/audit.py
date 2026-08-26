from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuditLog


async def write_audit_log(
    db: AsyncSession,
    project_id: UUID,
    actor_id: UUID,
    action: str,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    meta: dict | None = None,
) -> None:
    """Write an audit event for a project action."""
    log = AuditLog(
        project_id=project_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        meta=meta,
    )

    db.add(log)