"""Startup secret provisioning uses isolated storage and never rotates senders."""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models import InboundWebhook
from services.webhooks.provisioning import ensure_inbound_webhook_secrets


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'webhooks.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(InboundWebhook.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def insert(sessions, config):
    identifier = uuid.uuid4()
    async with sessions() as db:
        db.add(InboundWebhook(id=identifier, project_id=uuid.uuid4(), name="test",
                              slug=str(identifier), handler="trigger_agent", config=config))
        await db.commit()
    return identifier


async def configs(sessions):
    async with sessions() as db:
        return dict((await db.execute(select(InboundWebhook.id, InboundWebhook.config))).all())


async def test_secrets_persist_are_distinct_and_do_not_rotate(sessions):
    configured = await insert(sessions, {"secret": "sender-configured", "agent_id": "keep"})
    missing = [await insert(sessions, config) for config in
               [None, {"agent_id": "keep"}, {"secret": ""}, {"secret": 42}, {"secret": "  "}]]
    assert await ensure_inbound_webhook_secrets(sessions) == len(missing)
    first = await configs(sessions)
    assert first[configured] == {"secret": "sender-configured", "agent_id": "keep"}
    assert first[missing[1]]["agent_id"] == "keep"
    keys = [first[identifier]["secret"] for identifier in missing]
    assert len(set(keys)) == len(missing)
    assert all(len(key) == 43 for key in keys)  # token_urlsafe(32): 256 random bits
    assert await ensure_inbound_webhook_secrets(sessions) == 0
    assert await configs(sessions) == first


async def test_concurrent_startup_winner_is_not_overwritten(sessions):
    identifier = await insert(sessions, {"agent_id": "keep"})
    async with sessions() as stale:
        execute = stale.execute
        async def interleave(statement, *args, **kwargs):
            result = await execute(statement, *args, **kwargs)
            if statement.is_select:
                assert await ensure_inbound_webhook_secrets(sessions) == 1
            return result
        stale.execute = interleave
        # The first reader's snapshot becomes stale before its conditional write.
        assert await ensure_inbound_webhook_secrets(lambda: stale) == 0
    assert (await configs(sessions))[identifier]["agent_id"] == "keep"
    assert await ensure_inbound_webhook_secrets(sessions) == 0


async def test_provision_failure_rolls_back(sessions):
    identifier = await insert(sessions, {})
    await insert(sessions, ["invalid config"])
    with pytest.raises(ValueError, match="JSON object"):
        await ensure_inbound_webhook_secrets(sessions)
    assert (await configs(sessions))[identifier] == {}


async def test_startup_provisions_before_scheduler_and_fails_closed(monkeypatch):
    from app.factory import create_app
    from services.webhooks import dispatch, provisioning
    from core.config import settings

    events = []
    async def provision(_):
        events.append("provision")
    async def scheduler(_):
        events.append("scheduler")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(provisioning, "ensure_inbound_webhook_secrets", provision)
    monkeypatch.setattr(dispatch, "run_retry_scheduler", scheduler)
    app = create_app()
    async with app.router.lifespan_context(app):
        import asyncio
        await asyncio.sleep(0)
    assert events == ["provision", "scheduler"]
    failure = AsyncMock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr(provisioning, "ensure_inbound_webhook_secrets", failure)
    events.clear()
    with pytest.raises(RuntimeError, match="database unavailable"):
        async with app.router.lifespan_context(app):
            pass
    assert events == []


async def test_application_engine_hides_generated_secret_in_sql_logs(tmp_path, monkeypatch, caplog):
    import logging
    import db.session as application_db
    from core.config import settings

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'logs.db'}")
    monkeypatch.setattr(application_db, "_engine", None)
    monkeypatch.setattr(application_db, "_async_session", None)
    factory = application_db._get_session_factory()
    engine = application_db._get_engine()
    engine.echo = True  # Exercise diagnostic logging even when explicitly enabled.
    try:
        caplog.set_level(logging.INFO, logger="sqlalchemy.engine")
        async with engine.begin() as connection:
            await connection.run_sync(InboundWebhook.__table__.create)
        identifier = await insert(factory, {})
        assert await ensure_inbound_webhook_secrets(factory) == 1
        secret = (await configs(factory))[identifier]["secret"]
        assert secret not in caplog.text
        assert "SQL parameters hidden" in caplog.text
    finally:
        await engine.dispose()
