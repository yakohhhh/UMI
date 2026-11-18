"""The phone's part: pair a Clip, trim each session for privacy, upload it.

Until the companion app exists the simulator plays the phone. Every session goes
through the reference ``umi_protocol.trim_session`` before it leaves (the first
and last 200 m stay on the phone, short trips are not uploaded at all), and the
trimmed bytes are posted as they are (``protocol/README.md`` §3).

Pairing uses the backend's development endpoint, which registers a simulated
Clip and its rider in one call and returns the rider's token. Network errors and
5xx answers are retried with exponential backoff; any 4xx answer is final.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx
from umi_protocol import TrimResult, trim_session
from umi_protocol.constants import FORMAT_MEDIA_TYPE

from .clip import ClipIdentity

DEVICES_PATH = "/v1/dev/devices"
SESSIONS_PATH = "/v1/ingest/sessions"


@dataclass(frozen=True, slots=True)
class Athlete:
    id: str
    name: str
    vehicle: str

    @classmethod
    def for_rider(cls, rider_id: str, vehicle: str) -> Athlete:
        number = rider_id.removeprefix("sim-")
        name = f"Sim Rider {int(number)}" if number.isdigit() else f"Sim {rider_id}"
        return cls(rider_id, name, vehicle)


@dataclass(frozen=True, slots=True)
class Pairing:
    device_id: str
    athlete_id: str
    token: str


@dataclass(frozen=True, slots=True)
class Receipt:
    """The backend's answer to an upload; ``duplicate`` when it already had the session (200)."""

    activity_id: str
    segments_matched: int
    flags_accepted: int
    flags_rejected: int
    events: int
    duplicate: bool


@dataclass(frozen=True, slots=True)
class SyncResult:
    """What the phone did with a session: ``receipt`` is ``None`` when the trim left nothing to upload."""

    trim: TrimResult
    receipt: Receipt | None


class BackendError(RuntimeError):
    """The backend could not be reached or answered with an error; ``status`` is ``None`` without an answer."""

    def __init__(self, status: int | None, detail: str) -> None:
        super().__init__(detail if status is None else f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class RequestRejectedError(BackendError):
    """A 4xx answer: retrying the same request cannot succeed."""


type Sleep = Callable[[float], Awaitable[None]]


class Phone:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        *,
        attempts: int = 5,
        backoff_s: float = 0.5,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if attempts < 1:
            raise ValueError("a request needs at least one attempt")
        self._client = client
        self._api_url = api_url.rstrip("/")
        self._attempts = attempts
        self._backoff_s = backoff_s
        self._sleep = sleep

    async def pair(self, clip: ClipIdentity, athlete: Athlete) -> Pairing:
        """Register a simulated Clip with its rider (idempotent: 201 the first time, 200 after)."""
        body = {
            "deviceId": clip.device_hex,
            "serial": clip.serial,
            "publicKeyPem": clip.public_key_pem,
            "hwRev": clip.hw_rev,
            "firmware": clip.firmware_version,
            "simulated": True,
            "athlete": {"id": athlete.id, "name": athlete.name, "vehicle": athlete.vehicle},
        }
        payload = _accepted(await self._post(DEVICES_PATH, json=body))
        try:
            return Pairing(str(payload["deviceId"]), str(payload["athleteId"]), str(payload["token"]))
        except KeyError as exc:
            raise BackendError(None, f"pairing answer without {exc}") from None

    async def sync(self, pairing: Pairing, session: bytes) -> SyncResult:
        """Trim a session as the Clip wrote it and upload what is left."""
        trim = trim_session(session)
        if trim.data is None:
            return SyncResult(trim, None)
        headers = {"Authorization": f"Bearer {pairing.token}", "Content-Type": FORMAT_MEDIA_TYPE}
        response = await self._post(SESSIONS_PATH, content=trim.data, headers=headers)
        payload = _accepted(response)
        try:
            receipt = Receipt(
                activity_id=str(payload["activityId"]),
                segments_matched=int(payload["segmentsMatched"]),
                flags_accepted=int(payload["flags"]["accepted"]),
                flags_rejected=int(payload["flags"]["rejected"]),
                events=int(payload["events"]),
                duplicate=response.status_code == httpx.codes.OK,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BackendError(None, f"unexpected upload answer {payload!r}: {exc!r}") from None
        return SyncResult(trim, receipt)

    async def _post(
        self, path: str, *, json: Any = None, content: bytes | None = None, headers: Mapping[str, str] | None = None
    ) -> httpx.Response:
        url = self._api_url + path
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.post(url, json=json, content=content, headers=headers)
            except httpx.TransportError as exc:
                error = BackendError(None, f"{url}: {exc!r}")
            else:
                if not response.is_server_error:
                    return response
                error = BackendError(response.status_code, _detail(response))
            if attempt >= self._attempts:
                raise error
            await self._sleep(self._backoff_s * 2 ** (attempt - 1))


def _accepted(response: httpx.Response) -> dict[str, Any]:
    if response.is_client_error:
        raise RequestRejectedError(response.status_code, _detail(response))
    if response.status_code not in (httpx.codes.OK, httpx.codes.CREATED):
        raise BackendError(response.status_code, _detail(response))
    payload = response.json()
    if not isinstance(payload, dict):
        raise BackendError(response.status_code, f"expected a JSON object, got {payload!r}")
    return payload


def _detail(response: httpx.Response) -> str:
    """FastAPI's ``detail`` when there is one, else the start of the body."""
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    return str(detail) if detail is not None else response.text[:200]
