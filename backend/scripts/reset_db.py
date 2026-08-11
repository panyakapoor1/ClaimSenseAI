"""Drop and recreate the public schema.

Development helper for exercising migrations against a genuinely empty
database. Refuses to run unless CLAIMSENSE_ALLOW_DB_RESET=1 is set, because the
operation is unrecoverable and the command is short enough to run by accident.

    docker compose run --rm -e CLAIMSENSE_ALLOW_DB_RESET=1 fastapi python scripts/reset_db.py
"""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> int:
    if os.getenv("CLAIMSENSE_ALLOW_DB_RESET") != "1":
        print("Refusing to reset: set CLAIMSENSE_ALLOW_DB_RESET=1 to confirm.", file=sys.stderr)
        return 1

    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            # One statement per execute: asyncpg prepares each and rejects
            # multiple commands in a single string.
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
    finally:
        await engine.dispose()

    print("Schema 'public' dropped and recreated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
