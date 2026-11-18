"""Session upload from the phone (protocol/README.md §3)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from umi_protocol.constants import FORMAT_MEDIA_TYPE

from umi_api.api.auth import CurrentAthlete
from umi_api.api.deps import IngestSectionDep, SessionDep, SettingsDep, StreetNetworkDep, WallClockDep
from umi_api.schemas.ingest import FlagCounts, IngestReceipt
from umi_api.services.ingest import IngestService

router = APIRouter(prefix="/ingest", tags=["ingest"])

# protocol/README.md §3. About 18 hours of riding at ~110 KB an hour.
MAX_SESSION_BYTES = 2 * 1024 * 1024


async def session_body(request: Request) -> bytes:
    """The raw `.umis` bytes, refused as soon as they exceed the limit (never buffered whole)."""
    media_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if media_type != FORMAT_MEDIA_TYPE:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Send the session as {FORMAT_MEDIA_TYPE}")
    too_large = HTTPException(
        status.HTTP_413_CONTENT_TOO_LARGE, detail=f"Sessions are limited to {MAX_SESSION_BYTES} bytes"
    )
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_SESSION_BYTES:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_SESSION_BYTES:
            raise too_large
    return bytes(body)


def _ingest(
    session: SessionDep,
    clock: WallClockDep,
    network: StreetNetworkDep,
    settings: SettingsDep,
    section: IngestSectionDep,
) -> IngestService:
    return IngestService(session, clock, network, settings, section)


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=IngestReceipt,
    responses={
        200: {"model": IngestReceipt, "description": "Already uploaded: the first receipt, nothing duplicated"},
        403: {"description": "The Clip is not paired with this rider"},
        409: {"description": "Already stored without a receipt (imported with the demo)"},
        413: {"description": "Larger than 2 MiB"},
        415: {"description": f"Not sent as {FORMAT_MEDIA_TYPE}"},
        422: {"description": "Not a valid v1 log, not trimmed, no TIME_SYNC, implausible, or simulated and refused"},
        503: {"description": "The street network is not loaded"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {FORMAT_MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def upload_session(
    response: Response,
    athlete_id: CurrentAthlete,
    body: Annotated[bytes, Depends(session_body)],
    ingest: Annotated[IngestService, Depends(_ingest)],
) -> IngestReceipt:
    """A trimmed session log from the rider's Clip, processed into an activity before the answer."""
    result = await ingest.ingest(athlete_id, body)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    receipt = result.receipt
    return IngestReceipt(
        activity_id=receipt.activity_id,
        segments_matched=receipt.segments_matched,
        flags=FlagCounts(accepted=receipt.flags_accepted, rejected=receipt.flags_rejected),
        events=receipt.events,
    )
