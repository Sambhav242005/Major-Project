"""DB persistence for OAuth tokens — attaches load/save to MCPOAuthClient."""

import logging
import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .tokens import OAuthToken

logger = logging.getLogger(__name__)


async def _load_token_from_db(
    self, db: AsyncSession, connection_id: str
) -> OAuthToken | None:
    """Load persisted token from DB. Returns None if not found or expired."""
    from db.models import MCPAuthToken

    stmt = (
        select(MCPAuthToken)
        .where(MCPAuthToken.connection_id == connection_id)
        .order_by(MCPAuthToken.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if not row:
        return None

    token = OAuthToken(
        access_token=row.access_token,
        token_type=row.token_type,
        expires_at=row.expires_at.timestamp(),
        refresh_token=row.refresh_token,
        scope=row.scope,
    )

    # If expired but has refresh token, try refreshing
    if token.expires_at <= time.time() + 60 and token.refresh_token:
        self._token = token
        try:
            refreshed = await self.refresh_token()
            await self.save_token_to_db(db, connection_id)
            return refreshed
        except Exception:
            logger.warning("Token refresh failed during DB load")
            return None

    self._token = token
    return token


async def _save_token_to_db(self, db: AsyncSession, connection_id: str) -> None:
    """Persist current token to DB."""
    if not self._token:
        return

    from db.models import MCPAuthToken

    old = await db.execute(
        select(MCPAuthToken).where(MCPAuthToken.connection_id == connection_id)
    )
    for row in old.scalars().all():
        await db.delete(row)

    token_row = MCPAuthToken(
        connection_id=connection_id,
        access_token=self._token.access_token,
        token_type=self._token.token_type,
        refresh_token=self._token.refresh_token,
        expires_at=datetime.fromtimestamp(self._token.expires_at),
        scope=self._token.scope,
    )
    db.add(token_row)
    await db.flush()


def _attach_persistence():
    """Monkey-patch persistence methods onto MCPOAuthClient."""
    from .client import MCPOAuthClient

    MCPOAuthClient.load_token_from_db = _load_token_from_db
    MCPOAuthClient.save_token_to_db = _save_token_to_db


_attach_persistence()
