"""Run explicitly after `alembic upgrade head`; never accepts password arguments."""

import argparse
import asyncio
from getpass import getpass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings  # noqa: E402
from core.local_auth import create_account  # noqa: E402
from db.session import async_session_factory  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a real local login account without public registration")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    if settings.AUTH_PROVIDER != "local":
        print("Set AUTH_PROVIDER=local before creating local accounts.", file=sys.stderr)
        return 1
    if not sys.stdin.isatty():
        print("Run in an interactive terminal (Docker: exec -it) for a hidden password prompt.", file=sys.stderr)
        return 1
    password = getpass("New password (at least 12 characters): ")
    if password != getpass("Confirm password: "):
        print("Passwords did not match.", file=sys.stderr)
        return 1

    async def create():
        async with async_session_factory() as db:
            account = await create_account(db, args.email, password)
            await db.commit()
            return account.id

    try:
        user_id = asyncio.run(create())
        print(f"Local account created: {user_id}")
        return 0
    except ValueError as error:
        print(str(error), file=sys.stderr)
    except SQLAlchemyError:
        print("Account creation failed. Verify database connectivity and run migrations first.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
