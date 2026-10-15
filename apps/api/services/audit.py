from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuditLog


async def write_audit_log(
    db: AsyncSession,
    project_id: UUID | str,
    actor_id: UUID | str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: UUID | str | None = None,
    meta: dict | None = None,
) -> None:
    """Write an audit event for a project action."""
    # Route and service callers use both UUID objects and serialized IDs.
    # SQLAlchemy Uuid columns require UUID objects when binding on SQLite.
    log = AuditLog(
        project_id=project_id if isinstance(project_id, UUID) else UUID(project_id),
        actor_id=actor_id if actor_id is None or isinstance(actor_id, UUID) else UUID(actor_id),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id if resource_id is None or isinstance(resource_id, UUID) else UUID(resource_id),
        meta=meta,
    )

    db.add(log)
