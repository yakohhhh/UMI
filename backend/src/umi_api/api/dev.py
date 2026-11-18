"""Development-only endpoints; the router is not mounted in production (404)."""

from fastapi import APIRouter, Response, status

from umi_api.api.auth import dev_token
from umi_api.api.deps import SessionDep, WallClockDep
from umi_api.schemas.devices import DevicePairing, DeviceRegistration
from umi_api.services.devices import DeviceService

router = APIRouter(prefix="/dev", tags=["development"])


@router.post(
    "/devices",
    status_code=status.HTTP_201_CREATED,
    response_model=DevicePairing,
    responses={
        200: {"model": DevicePairing, "description": "Already registered with the same key"},
        409: {"description": "Registered with another key, or the serial belongs to another Clip"},
        422: {"description": "Invalid body or public key"},
    },
)
async def register_device(
    registration: DeviceRegistration, response: Response, session: SessionDep, clock: WallClockDep
) -> DevicePairing:
    """Register a simulated or devkit Clip, create or update its rider, and pair them.

    Returns the rider's development token, for uploads (`Authorization: Bearer <token>`).
    """
    pairing = await DeviceService(session, clock).register_dev(registration)
    if not pairing.created:
        response.status_code = status.HTTP_200_OK
    return DevicePairing(
        device_id=pairing.device_id, athlete_id=pairing.athlete_id, token=dev_token(pairing.athlete_id)
    )
