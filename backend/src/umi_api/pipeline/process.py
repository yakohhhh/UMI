"""Stages 4-9 on a matched track: everything a ride writes, as plain values for the caller to store."""

from dataclasses import dataclass

from umi_api.domain.enums import RideEventType
from umi_api.pipeline.context import RideContext
from umi_api.pipeline.device import DeviceStatus, device_status
from umi_api.pipeline.events import EventRow, ride_events
from umi_api.pipeline.exposure import ExposureDayValues, ride_exposure
from umi_api.pipeline.flags import FlagOutcome, check_flags, place_flags
from umi_api.pipeline.matching import MatchedTrack, StreetIndex
from umi_api.pipeline.passes import PassRow, segment_passes
from umi_api.pipeline.readings import readings
from umi_api.pipeline.ride import ReportSampling, RideSummary, SegmentRow, segment_rows, summarize


@dataclass(frozen=True)
class ProcessedRide:
    summary: RideSummary
    segments: tuple[SegmentRow, ...]
    events: tuple[EventRow, ...]
    flags: FlagOutcome
    passes: tuple[PassRow, ...]
    # The ride alone; the caller adds it to the day already stored (exposure.add_exposure).
    exposure: ExposureDayValues
    device: DeviceStatus
    segments_matched: int


def process(matched: MatchedTrack, index: StreetIndex, context: RideContext) -> ProcessedRide:
    track = matched.track
    values = readings(matched, index, context.hourly)
    sampling = ReportSampling.for_points(len(track.points))
    # Flags first: a flag pressed right after a hard brake means the app does not ask about it.
    check = check_flags(track, context.public_key, context.flags_per_day)
    events = ride_events(
        context.activity_id,
        matched,
        index=index,
        sampling=sampling,
        hotspots=context.hotspots,
        flag_times_ms=[f.t_ms for f in check.accepted],
    )
    brakes = [e.point for e in events if e.type is RideEventType.HARD_BRAKE]
    summary = summarize(matched, values, index, sampling, hard_brakes=len(brakes))
    return ProcessedRide(
        summary=summary,
        segments=tuple(segment_rows(matched, values)),
        events=tuple(events),
        flags=place_flags(
            context.activity_id,
            matched,
            index=index,
            sampling=sampling,
            check=check,
            events=events,
            open_hazards=context.open_hazards,
        ),
        passes=tuple(segment_passes(matched, values, brakes)),
        exposure=ride_exposure(track, values, summary.moving_time_s),
        device=device_status(track.session),
        segments_matched=matched.segments_matched,
    )
