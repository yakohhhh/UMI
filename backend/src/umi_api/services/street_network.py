"""The street network as the map matcher sees it, loaded from the database once per process."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.db.models import StreetSegment
from umi_api.domain.aggregation import HourScores
from umi_api.pipeline import StreetIndex, StreetRef, Typical
from umi_api.repositories.streets import StreetRepository
from umi_api.services.errors import UnavailableError


class StreetNetwork:
    """Builds the in-memory spatial index on first use and keeps it (ADR 0004).

    Indexing ~335 segments takes milliseconds, so it happens lazily on the first
    upload rather than slowing every start-up. The network only changes when the
    database is seeded again, which needs a restart of the API to be seen here.
    """

    def __init__(self) -> None:
        self._index: StreetIndex | None = None
        self._lock = asyncio.Lock()

    async def index(self, session: AsyncSession) -> StreetIndex:
        if self._index is None:
            async with self._lock:
                if self._index is None:
                    segments = await StreetRepository(session).network()
                    if not segments:
                        raise UnavailableError("The street network is not loaded yet: run `umi-api seed`")
                    self._index = StreetIndex(street_ref(s) for s in segments)
        return self._index


def street_ref(segment: StreetSegment) -> StreetRef:
    return StreetRef(
        id=segment.id,
        name=segment.name,
        district_code=segment.district_code,
        district=segment.district.name,
        coordinates=tuple((lon, lat) for lon, lat in segment.coordinates),
        typical=Typical(
            vib_rms=segment.vib_rms,
            pm25=segment.pm25,
            db=segment.db,
            scores=HourScores(segment.comfort, segment.safety, segment.air, segment.noise),
        ),
    )
