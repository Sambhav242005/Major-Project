"""Initialize SQLite database with all tables."""
import asyncio
from db.session import _get_engine
from db.models import Base


async def init():
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init())
