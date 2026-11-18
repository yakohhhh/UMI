"""Engine and session factory."""

from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        if make_url(url).get_backend_name() == "sqlite":
            # SQLite ignores foreign keys (and their ON DELETE) unless asked, per connection.
            event.listen(self.engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
        # Objects stay readable after commit: responses are built from them.
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def ping(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()


def _enable_sqlite_foreign_keys(connection: Any, _record: Any) -> None:
    # aiosqlite wraps the DB-API connection; the pragma goes through its cursor.
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
