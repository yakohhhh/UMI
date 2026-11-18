"""A test rider: a paired Clip and the API client that uploads its sessions and reads the rider's data."""

import itertools
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from umi_protocol.constants import FORMAT_MEDIA_TYPE

from .sessions import RideSpec, SoftwareClip, trimmed

SESSIONS = "/v1/ingest/sessions"


@dataclass
class Rider:
    athlete_id: str
    clip: SoftwareClip
    client: httpx.AsyncClient
    _sessions: Iterator[int] = field(default_factory=lambda: itertools.count(1))

    @property
    def auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer dev:{self.athlete_id}"}

    def session(self, spec: RideSpec) -> bytes:
        """The next session of this rider's Clip, trimmed as the phone uploads it."""
        return trimmed(spec, self.clip, next(self._sessions))

    async def upload(self, body: bytes) -> httpx.Response:
        headers = {**self.auth, "Content-Type": FORMAT_MEDIA_TYPE}
        return await self.client.post(SESSIONS, content=body, headers=headers)

    async def ride(self, spec: RideSpec) -> dict[str, Any]:
        """Upload the next session and return the receipt, which must be a new activity."""
        response = await self.upload(self.session(spec))
        assert response.status_code == 201, response.text
        receipt: dict[str, Any] = response.json()
        return receipt

    async def get(self, path: str, **params: str) -> Any:
        response = await self.client.get(path, headers=self.auth, params=params)
        assert response.status_code == 200, response.text
        return response.json()


# The fixtures that make them (conftest.py).
type MakeRider = Callable[..., Awaitable[Rider]]
type MakeApi = Callable[..., Awaitable[httpx.AsyncClient]]
