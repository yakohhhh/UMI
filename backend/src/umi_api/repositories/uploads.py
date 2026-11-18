from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.db.models import Activity, SessionUpload


class SessionUploadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(self, device_id: str, session_id: int) -> SessionUpload | None:
        """The receipt of a session already processed, found by the Clip's own identifiers."""
        query = (
            select(SessionUpload)
            .join(Activity, Activity.id == SessionUpload.activity_id)
            .where(Activity.device_id == device_id, Activity.session_id == session_id)
        )
        return await self._session.scalar(query)

    def add(self, upload: SessionUpload) -> None:
        self._session.add(upload)
