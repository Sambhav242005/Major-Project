"""Provision persistent per-webhook secrets without rotating configured senders."""

import secrets

from sqlalchemy import Text, cast, select, update

from db.models import InboundWebhook


async def ensure_inbound_webhook_secrets(session_factory) -> int:
    """Fill absent/invalid secrets, preserving config and concurrent changes.

    Return only the number created. Secret values must never be logged.
    A compare-and-swap prevents simultaneous workers from rotating each other's
    generated keys, including on SQLite where FOR UPDATE is ignored.
    """
    table = InboundWebhook.__table__
    config_text = cast(table.c.config, Text)
    created = 0
    async with session_factory() as db:
        async with db.begin():
            rows = (await db.execute(select(table.c.id, table.c.config, config_text))).all()
            for identifier, config, snapshot in rows:
                if config is None:
                    config = {}
                if not isinstance(config, dict):
                    raise ValueError("Inbound webhook config must be a JSON object")
                existing = config.get("secret")
                if isinstance(existing, str) and existing.strip():
                    continue
                unchanged = config_text.is_(None) if snapshot is None else config_text == snapshot
                result = await db.execute(
                    update(table)
                    .where(table.c.id == identifier, unchanged)
                    .values(config={**config, "secret": secrets.token_urlsafe(32)})
                    .returning(table.c.id)
                )
                if result.scalar_one_or_none() is not None:
                    created += 1
    return created
