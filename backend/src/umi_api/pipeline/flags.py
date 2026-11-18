"""Stage 6: flags, which ones to keep and which hazard each one opens or joins.

A flag the rider undid with a double press (FLAG_UNDO) is ignored altogether.
Any other flag is kept only if
- its signature verifies against the paired Clip's key (ADR 0005): an unsigned
  or forged flag is dropped, whatever the environment;
- it was pressed inside the service area;
- the rider has not reached `MAX_FLAGS_PER_RIDER_DAY` flags that Barcelona day.
Each dropped flag counts as rejected; the ride itself is never refused for one.

A kept flag joins the nearest open hazard of a compatible kind within
`[reports] hazard_merge_radius_m`, or opens one that takes the flag's id. A
pothole the Clip felt (EVENT) that close to an open pothole hazard confirms it
too: Clips passing "with the same sensor signature" count as riders.
"""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime

from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from umi_protocol import Flag, Lang, haversine_m, verify_flag
from umi_protocol import FlagSource as WireFlagSource
from umi_protocol import HazardKind as WireHazardKind
from umi_protocol.constants import BUTTON_KEYWORD_MIN_CONFIDENCE

from umi_api.domain.calendar import local_day
from umi_api.domain.enums import ConfirmationSource, FlagSource, HazardKind, RideEventType
from umi_api.domain.hazards import MERGE_RADIUS_M, kinds_compatible
from umi_api.domain.plausibility import MAX_FLAGS_PER_RIDER_DAY, in_service_area
from umi_api.pipeline.context import OpenHazard
from umi_api.pipeline.events import EventRow
from umi_api.pipeline.matching import MatchedTrack, StreetIndex
from umi_api.pipeline.ride import ReportSampling
from umi_api.pipeline.track import Track

# Wire codes to the API's names (domain.enums keeps the names in step with the protocol).
_KEYWORDS: dict[int, HazardKind] = {WireHazardKind[kind.name]: kind for kind in HazardKind}
_SOURCES: dict[int, FlagSource] = {WireFlagSource[source.name]: source for source in FlagSource}


@dataclass(frozen=True)
class FlagCheck:
    accepted: tuple[Flag, ...]
    rejected: int


@dataclass(frozen=True)
class FlagRow:
    id: str
    seq: int
    point: int
    sample_index: int
    lon: float
    lat: float
    pressed_at: datetime
    street: str | None
    source: FlagSource
    # The keyword recognised on the Clip (signed), None for a press without one.
    keyword_kind: HazardKind | None
    keyword_confidence: int | None
    lang: str | None
    speed_kmh: float | None
    vib_rms: float | None
    noise_db: float | None
    sig_alg: int
    signature: bytes
    hazard_id: str


@dataclass(frozen=True)
class NewHazard:
    id: str
    kind: HazardKind | None
    lon: float
    lat: float
    street: str | None
    district_code: str | None
    first_seen_at: datetime


@dataclass(frozen=True)
class Confirmation:
    """The rider flagged a hazard, or their Clip felt it."""

    hazard_id: str
    at: datetime
    source: ConfirmationSource
    flag_id: str | None
    # What the flag says the hazard is, to name one that does not say yet.
    kind: HazardKind | None


@dataclass(frozen=True)
class FlagOutcome:
    rows: tuple[FlagRow, ...]
    rejected: int
    opened: tuple[NewHazard, ...]
    confirmations: tuple[Confirmation, ...]


def check_flags(track: Track, public_key: EllipticCurvePublicKey, flags_per_day: Mapping[date, int]) -> FlagCheck:
    header = track.session.header
    per_day = Counter(flags_per_day)
    accepted: list[Flag] = []
    rejected = 0
    for flag in track.session.flags:
        day = local_day(track.utc(flag.t_ms))
        if (
            not verify_flag(public_key, header.device_id, header.session_id, flag)
            or not in_service_area(flag.lon, flag.lat)
            or per_day[day] >= MAX_FLAGS_PER_RIDER_DAY
        ):
            rejected += 1
            continue
        per_day[day] += 1
        accepted.append(flag)
    return FlagCheck(tuple(accepted), rejected)


def place_flags(
    activity_id: str,
    matched: MatchedTrack,
    *,
    index: StreetIndex,
    sampling: ReportSampling,
    check: FlagCheck,
    events: Sequence[EventRow],
    open_hazards: Sequence[OpenHazard],
) -> FlagOutcome:
    track = matched.track
    hazards = list(open_hazards)
    rows: list[FlagRow] = []
    opened: list[NewHazard] = []
    confirmations: list[Confirmation] = []
    for flag in check.accepted:
        point = track.nearest(flag.t_ms)
        segment_id = matched.segment_ids[point]
        street = index.street(segment_id) if segment_id is not None else index.nearest(flag.lon, flag.lat)
        flag_id = f"{activity_id}-f{flag.seq}"
        pressed_at = track.utc(flag.t_ms)
        kind = _keyword(flag)
        joined = _nearest(flag.lon, flag.lat, (h for h in hazards if kinds_compatible(h.kind, kind)))
        if joined is None:
            joined = OpenHazard(flag_id, kind, flag.lon, flag.lat)
            hazards.append(joined)
            opened.append(
                NewHazard(
                    id=flag_id,
                    kind=kind,
                    lon=flag.lon,
                    lat=flag.lat,
                    street=None if street is None else street.name,
                    district_code=None if street is None else street.district_code,
                    first_seen_at=pressed_at,
                )
            )
        elif joined.kind is None and kind is not None:
            hazards[hazards.index(joined)] = replace(joined, kind=kind)
        confirmations.append(Confirmation(joined.id, pressed_at, ConfirmationSource.FLAG, flag_id, kind))
        rows.append(
            FlagRow(
                id=flag_id,
                seq=flag.seq,
                point=point,
                sample_index=sampling.sample_of(point),
                lon=flag.lon,
                lat=flag.lat,
                pressed_at=pressed_at,
                street=None if street is None else street.name,
                source=_SOURCES.get(flag.source, FlagSource.PRESS),
                keyword_kind=kind,
                keyword_confidence=flag.confidence if kind is not None else None,
                lang=Lang(flag.lang).name.lower() if flag.lang in Lang and flag.lang != Lang.NONE else None,
                speed_kmh=flag.speed_kmh,
                vib_rms=flag.vib_mps2,
                noise_db=flag.noise_dba,
                sig_alg=int(flag.sig_alg),
                signature=flag.signature,
                hazard_id=joined.id,
            )
        )
    potholes = [h for h in open_hazards if h.kind is HazardKind.POTHOLE]
    for event in events:
        if event.type is RideEventType.POTHOLE and (felt := _nearest(event.lon, event.lat, potholes)) is not None:
            confirmations.append(Confirmation(felt.id, event.occurred_at, ConfirmationSource.SENSOR, None, None))
    return FlagOutcome(tuple(rows), check.rejected, tuple(opened), _one_per_hazard(confirmations))


def _one_per_hazard(confirmations: Sequence[Confirmation]) -> tuple[Confirmation, ...]:
    """The rider confirms each hazard once per ride, however often they pressed there.

    The latest time counts; a press outranks a sensor match (it says the rider saw it),
    and the first kind a flag gave names the hazard.
    """

    def rank(c: Confirmation) -> tuple[bool, datetime]:
        return c.source is ConfirmationSource.FLAG, c.at

    merged: dict[str, Confirmation] = {}
    for c in confirmations:
        seen = merged.get(c.hazard_id)
        if seen is None:
            merged[c.hazard_id] = c
        else:
            kept = max(seen, c, key=rank)
            merged[c.hazard_id] = replace(kept, at=max(seen.at, c.at), kind=seen.kind or c.kind)
    return tuple(merged.values())


def _keyword(flag: Flag) -> HazardKind | None:
    """The kind the Clip recognised; a keyword under the confidence threshold says nothing (checked here too)."""
    if flag.confidence < BUTTON_KEYWORD_MIN_CONFIDENCE:
        return None
    return _KEYWORDS.get(flag.kind)


def _nearest(lon: float, lat: float, hazards: Iterable[OpenHazard]) -> OpenHazard | None:
    distance, nearest = min(
        ((haversine_m(lat, lon, h.lat, h.lon), h) for h in hazards), key=lambda dh: dh[0], default=(0.0, None)
    )
    return nearest if nearest is not None and distance <= MERGE_RADIUS_M else None
