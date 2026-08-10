from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

_engine = None
_async_session = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.DATABASE_URL, echo=settings.ENVIRONMENT == "development")
    return _engine


def _get_session_factory():
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(_get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _async_session


# Export session factory for background tasks (async_sessionmaker instance)
async_session_factory = _get_session_factory()


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    session_factory = _get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
