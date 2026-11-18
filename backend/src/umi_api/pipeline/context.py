"""What the pipeline needs from the database, loaded by the caller once the track is matched."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey

from umi_api.domain.aggregation import HourScores
from umi_api.domain.enums import HazardKind


@dataclass(frozen=True)
class HotspotRef:
    id: str
    lon: float
    lat: float
    # Its "why riders brake" mix is already published (enough different riders answered).
    mix_published: bool


@dataclass(frozen=True)
class OpenHazard:
    """A hazard a new flag can still join (domain.hazards.OPEN_STATUSES)."""

    id: str
    kind: HazardKind | None
    lon: float
    lat: float


@dataclass(frozen=True)
class RideContext:
    activity_id: str
    # The paired Clip's key: flag signatures are checked against it.
    public_key: EllipticCurvePublicKey
    # Published scores per matched segment, indexed by local hour (0-23).
    hourly: Mapping[str, Sequence[HourScores]]
    hotspots: Sequence[HotspotRef]
    # Open hazards around the track.
    open_hazards: Sequence[OpenHazard]
    # Flags the rider already has per Barcelona day, for the daily cap.
    flags_per_day: Mapping[date, int]
