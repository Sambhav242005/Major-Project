"""TDD tests for audit logging."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from db.models import AuditLog
from services.audit import write_audit_log


@pytest.mark.asyncio
async def test_write_audit_log_adds_entry():
    db = MagicMock()

    project_id = uuid4()
    actor_id = uuid4()
    resource_id = uuid4()

    await write_audit_log(
        db=db,
        project_id=project_id,
        actor_id=actor_id,
        action="project.created",
        resource_type="project",
        resource_id=resource_id,
        meta={"name": "Test Project"},
    )

    db.add.assert_called_once()

    log = db.add.call_args.args[0]

    assert isinstance(log, AuditLog)
    assert log.project_id == project_id
    assert log.actor_id == actor_id
    assert log.action == "project.created"
    assert log.resource_type == "project"
    assert log.resource_id == resource_id
    assert log.meta == {"name": "Test Project"}