"""Critical sections for work that reads shared rows and then writes from what it read.

Ingest is such work: it reads the open hazards near a ride, the rider's flags that
day and the activity ids already taken, then writes hazards, confirmations and an
activity. Two uploads processed at the same time would each miss the other's
writes, so two riders flagging the same corner at once would open two hazards,
and neither hazard would ever count both riders.
"""

import asyncio
import zlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CriticalSection:
    """Exclusive within this process and, on Postgres, across every process sharing the database."""

    def __init__(self, name: str) -> None:
        self._local = asyncio.Lock()
        # Advisory locks are keyed by integers; a checksum of the name is the same in every process.
        self._key = zlib.crc32(name.encode())

    @asynccontextmanager
    async def hold(self, session: AsyncSession) -> AsyncIterator[None]:
        """Enter the section to read and write through `session`, committing before leaving it.

        On Postgres the database lock lasts until `session`'s transaction ends: at the
        commit, or when the session closes after a request that wrote nothing.
        """
        async with self._local:
            if session.get_bind().dialect.name == "postgresql":
                # SQLite needs no more than the local lock: it is for development, served by one process.
                await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": self._key})
            yield
