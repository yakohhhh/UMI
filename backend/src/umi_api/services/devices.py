"""Development pairing: a simulated or devkit Clip and its rider, registered in one call.

Real Clips get their key at a factory provisioning step and are paired from the
companion app (ADR 0005); neither exists yet, so the simulator registers its
Clips here. Never available in production.
"""

from dataclasses import dataclass

from cryptography.exceptions import UnsupportedAlgorithm
from sqlalchemy.ext.asyncio import AsyncSession
from umi_protocol import load_public_key_pem, public_key_to_uncompressed

from umi_api.clock import Clock
from umi_api.db.models import Athlete, Device
from umi_api.repositories.athletes import AthleteRepository
from umi_api.repositories.devices import DeviceRepository
from umi_api.schemas.devices import DeviceRegistration
from umi_api.services.errors import ConflictError, UnprocessableError

# Development riders only give a name and a vehicle.
DEV_RIDER_CITY = "Barcelona"
DEV_RIDER_AGE = 0


@dataclass(frozen=True)
class Pairing:
    device_id: str
    athlete_id: str
    # False when the Clip was already registered with the same key.
    created: bool


class DeviceService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._athletes = AthleteRepository(session)
        self._devices = DeviceRepository(session)

    async def register_dev(self, request: DeviceRegistration) -> Pairing:
        """Upsert the rider, register the Clip and pair it with them.

        Registering again with the same key is a no-op apart from the details (firmware,
        rider's name) and may move the Clip to another rider; another key for the same
        `device_id`, or a serial another Clip uses, is a conflict.
        """
        public_key = _uncompressed_point(request.public_key_pem)
        device = await self._devices.get(request.device_id)
        if device is not None and device.public_key != public_key:
            raise ConflictError(f"Clip {request.device_id} is already registered with another key")
        same_serial = await self._devices.by_serial(request.serial)
        if same_serial is not None and same_serial.id != request.device_id:
            raise ConflictError(f"Serial {request.serial} belongs to Clip {same_serial.id}")

        athlete = await self._upsert_athlete(request)
        created = device is None
        if device is None:
            device = Device(id=request.device_id, public_key=public_key)
            self._devices.add(device)
        if device.athlete_id != athlete.id:
            device.athlete_id, device.paired_at = athlete.id, self._clock.now()
        device.serial = request.serial
        device.hw_rev = request.hw_rev
        device.firmware = request.firmware
        device.simulated = request.simulated
        await self._session.commit()
        return Pairing(device_id=device.id, athlete_id=athlete.id, created=created)

    async def _upsert_athlete(self, request: DeviceRegistration) -> Athlete:
        rider = request.athlete
        athlete = await self._athletes.get(rider.id)
        if athlete is None:
            athlete = Athlete(id=rider.id, city=DEV_RIDER_CITY, age=DEV_RIDER_AGE)
            self._athletes.add(athlete)
        words = rider.name.split()
        athlete.name = rider.name
        athlete.first_name = words[0]
        athlete.initials = "".join(word[0] for word in words[:2]).upper()
        athlete.vehicle = rider.vehicle
        return athlete


def _uncompressed_point(pem: str) -> bytes:
    try:
        return public_key_to_uncompressed(load_public_key_pem(pem.encode("ascii")))
    # A non-ASCII string raises UnicodeEncodeError, a ValueError too.
    except (ValueError, UnsupportedAlgorithm) as exc:
        raise UnprocessableError("publicKeyPem is not a P-256 public key in PEM") from exc
