from typing import Annotated

from pydantic import Field

from umi_api.schemas.base import ApiModel

# Rider ids end up in activity, event and flag ids, which have room for this much.
RiderId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")]


class DevAthlete(ApiModel):
    id: RiderId
    name: Annotated[str, Field(min_length=1, max_length=120, pattern=r"\S")]
    vehicle: Annotated[str, Field(min_length=1, max_length=40)]


class DeviceRegistration(ApiModel):
    """A Clip and its rider, as the simulator (or a devkit) registers them in development."""

    # u64 burnt in at provisioning, 16 lowercase hex digits (protocol/README.md §1.1).
    device_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
    serial: Annotated[str, Field(min_length=1, max_length=32)]
    # SubjectPublicKeyInfo PEM of the Clip's P-256 key.
    public_key_pem: Annotated[str, Field(max_length=1024)]
    hw_rev: Annotated[int, Field(ge=0, le=255)]
    firmware: Annotated[str, Field(pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}$")]
    simulated: bool
    athlete: DevAthlete


class DevicePairing(ApiModel):
    device_id: str
    athlete_id: str
    # Bearer token acting as the rider (development only).
    token: str
