"""Stage 5: what happened during the ride, and which hard brakes the app asks about afterwards.

Hard brakes and potholes are detected on the Clip (EVENT records). PM2.5 spikes
and noise peaks are derived here (protocol/README.md §1.3): readings at or above
`[detection] pm_spike_ugm3` / `noise_peak_dba` form an episode until they stay
below for `EPISODE_GAP_MS`, and each episode is one event at its peak. An EVENT
recorded twice (same kind, same time) counts once; one that happened away from
the plausible track (dropped fixes, outside the service area) is left out.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from umi_protocol import Air, Event, EventKind, haversine_m
from umi_protocol.constants import DETECTION_NOISE_PEAK_DBA, DETECTION_PM_SPIKE_UGM3

from umi_api.domain.enums import RideEventType
from umi_api.domain.numbers import round_to
from umi_api.domain.plausibility import in_service_area
from umi_api.domain.reports import FLAG_EXPLAINS_BRAKE_S, HOTSPOT_RADIUS_M, BrakeCandidate, pick_questions
from umi_api.pipeline.context import HotspotRef
from umi_api.pipeline.matching import MatchedTrack, StreetIndex
from umi_api.pipeline.passes import PassKey, pass_key
from umi_api.pipeline.ride import ReportSampling

EPISODE_GAP_MS = 120_000
# An event further than this in time from any kept fix happened where the track was dropped.
MAX_EVENT_GAP_MS = 5_000

# Kinds a newer Clip may add are left out until the app can show them.
_CLIP_KINDS: dict[int, RideEventType] = {
    EventKind.HARD_BRAKE: RideEventType.HARD_BRAKE,
    EventKind.POTHOLE: RideEventType.POTHOLE,
}
_TYPE_ORDER = {kind: rank for rank, kind in enumerate(RideEventType)}


@dataclass(frozen=True)
class EventRow:
    id: str
    position: int
    type: RideEventType
    t_ms: int
    # Track point and ride report sample the event is drawn at.
    point: int
    sample_index: int
    lon: float
    lat: float
    # m/s² for brakes (mean deceleration) and potholes (1 s RMS), µg/m³ for PM2.5, dB(A) for noise.
    value: float
    peak: float | None
    duration_ms: int | None
    occurred_at: datetime
    street: str | None
    # The segment pass that counts it, when the event fell in one.
    pass_key: PassKey | None
    hotspot_id: str | None
    ask: bool


@dataclass(frozen=True)
class _Detected:
    type: RideEventType
    t_ms: int
    value: float
    peak: float | None = None
    duration_ms: int | None = None
    position: tuple[float, float] | None = None


def ride_events(
    activity_id: str,
    matched: MatchedTrack,
    *,
    index: StreetIndex,
    sampling: ReportSampling,
    hotspots: Sequence[HotspotRef],
    flag_times_ms: Sequence[int],
) -> list[EventRow]:
    """Events in time order; `flag_times_ms` are the ride's accepted flags (they explain brakes)."""
    track = matched.track
    pm25 = ((a.t_ms, a.pm25_ugm3) for a in track.session.of_type(Air))
    noise = ((p.t_ms, p.noise_dba) for p in track.points)
    detected = sorted(
        [
            *_clip_events(track.session.of_type(Event)),
            *_episodes(pm25, DETECTION_PM_SPIKE_UGM3, RideEventType.PM_SPIKE),
            *_episodes(noise, DETECTION_NOISE_PEAK_DBA, RideEventType.NOISE_PEAK),
        ],
        key=lambda e: (e.t_ms, _TYPE_ORDER[e.type]),
    )
    rows: list[EventRow] = []
    for event in detected:
        point = track.nearest(event.t_ms)
        fix = track.points[point]
        if abs(fix.t_ms - event.t_ms) > MAX_EVENT_GAP_MS:
            continue
        lon, lat = event.position if event.position and in_service_area(*event.position) else (fix.lon, fix.lat)
        segment_id = matched.segment_ids[point]
        run = matched.run_at(point)
        hotspot = _hotspot(lon, lat, hotspots) if event.type is RideEventType.HARD_BRAKE else None
        rows.append(
            EventRow(
                id=f"{activity_id}-e{len(rows)}",
                position=len(rows),
                type=event.type,
                t_ms=event.t_ms,
                point=point,
                sample_index=sampling.sample_of(point),
                lon=lon,
                lat=lat,
                value=event.value,
                peak=event.peak,
                duration_ms=event.duration_ms,
                occurred_at=track.utc(event.t_ms),
                street=None if segment_id is None else index.street(segment_id).name,
                pass_key=None if run is None else pass_key(track, run),
                hotspot_id=None if hotspot is None else hotspot.id,
                ask=False,
            )
        )
    asked = set(pick_questions(_brake_candidates(rows, hotspots, flag_times_ms)))
    return [replace(row, ask=True) if row.position in asked else row for row in rows]


def _clip_events(events: Iterable[Event]) -> list[_Detected]:
    detected: dict[tuple[int, int], _Detected] = {}
    for e in events:
        kind = _CLIP_KINDS.get(e.kind)
        if kind is None or e.value_mps2 is None or (e.kind, e.t_ms) in detected:
            continue
        detected[e.kind, e.t_ms] = _Detected(
            type=kind,
            t_ms=e.t_ms,
            value=round_to(e.value_mps2, 1),
            peak=None if e.peak_mps2 is None else round_to(e.peak_mps2, 2),
            duration_ms=e.duration_ms,
            position=(e.lon, e.lat),
        )
    return list(detected.values())


def _episodes(readings: Iterable[tuple[int, float | None]], threshold: float, kind: RideEventType) -> list[_Detected]:
    peaks: list[_Detected] = []
    last_above: int | None = None
    for t_ms, value in readings:
        if value is None or value < threshold:
            continue
        if last_above is not None and t_ms - last_above <= EPISODE_GAP_MS:
            if value > peaks[-1].value:
                peaks[-1] = _Detected(kind, t_ms, round_to(value, 1))
        else:
            peaks.append(_Detected(kind, t_ms, round_to(value, 1)))
        last_above = t_ms
    return peaks


def _hotspot(lon: float, lat: float, hotspots: Sequence[HotspotRef]) -> HotspotRef | None:
    distance, nearest = min(
        ((haversine_m(lat, lon, h.lat, h.lon), h) for h in hotspots), key=lambda dh: dh[0], default=(0.0, None)
    )
    return nearest if nearest is not None and distance <= HOTSPOT_RADIUS_M else None


def _brake_candidates(
    rows: Sequence[EventRow], hotspots: Sequence[HotspotRef], flag_times_ms: Sequence[int]
) -> list[BrakeCandidate]:
    published = {h.id for h in hotspots if h.mix_published}
    explains_ms = FLAG_EXPLAINS_BRAKE_S * 1000
    return [
        BrakeCandidate(
            key=row.position,
            decel_mps2=row.value,
            t_s=row.t_ms / 1000,
            hotspot_id=row.hotspot_id,
            hotspot_published=row.hotspot_id in published,
            explained=any(0 <= t - row.t_ms <= explains_ms for t in flag_times_ms),
        )
        for row in rows
        if row.type is RideEventType.HARD_BRAKE
    ]
