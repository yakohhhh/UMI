"""What a processed ride stores: pipeline values mapped onto the models, nothing decided here."""

from umi_api.db.models import (
    Activity,
    ActivityDetail,
    ActivitySegment,
    Flag,
    Hazard,
    RideEvent,
    SegmentPass,
)
from umi_api.domain.enums import HazardStatus
from umi_api.pipeline import ProcessedRide
from umi_api.pipeline.events import EventRow
from umi_api.pipeline.flags import FlagRow, NewHazard
from umi_api.pipeline.passes import PassRow

# The temperature comes from the Clip's own sensor; a weather service would say more (follow-up).
MEASURED_CONDITION = "measured by the Clip"
# SAMPLE records carry no altitude in protocol v1.
NO_ELEVATION_M = 0


def activity_row(activity_id: str, athlete_id: str, device_id: str, session_id: int, ride: ProcessedRide) -> Activity:
    """The activity with its report, segments, events and flags (events not linked to their passes yet)."""
    s = ride.summary
    return Activity(
        id=activity_id,
        athlete_id=athlete_id,
        device_id=device_id,
        session_id=session_id,
        type=s.type,
        title=s.title,
        place=s.place,
        description=None,
        started_at=s.started_at,
        duration_s=s.duration_s,
        moving_time_s=s.moving_time_s,
        distance_m=s.distance_m,
        avg_speed_kmh=s.avg_speed_kmh,
        max_speed_kmh=s.max_speed_kmh,
        elevation_gain_m=NO_ELEVATION_M,
        comfort=s.scores.comfort,
        safety=s.scores.safety,
        air=s.scores.air,
        noise=s.scores.noise,
        preview=s.preview,
        kudos=0,
        kudoed_by=[],
        comments=0,
        featured=False,
        weather_temp_c=s.temp_c,
        weather_condition=MEASURED_CONDITION,
        detail=ActivityDetail(route=s.route, samples=s.samples),
        segments=[
            ActivitySegment(
                position=row.position,
                segment_id=row.segment_id,
                distance_m=row.distance_m,
                score=row.score,
                street_average=row.street_average,
            )
            for row in ride.segments
        ],
        events=[_event(row) for row in ride.events],
        flags=[_flag(row, device_id, session_id) for row in ride.flags.rows],
    )


def hazard_row(new: NewHazard) -> Hazard:
    return Hazard(
        id=new.id,
        kind=new.kind,
        lon=new.lon,
        lat=new.lat,
        street=new.street,
        district_code=new.district_code,
        status=HazardStatus.PENDING,
        first_seen_at=new.first_seen_at,
        last_confirmed_at=new.first_seen_at,
        riders_warned=0,
    )


def pass_row(row: PassRow, activity: Activity) -> SegmentPass:
    return SegmentPass(
        activity_id=activity.id,
        segment_id=row.segment_id,
        athlete_id=activity.athlete_id,
        activity_type=activity.type,
        hour_start=row.hour_start,
        vib_rms=row.vib_rms,
        pm25=row.pm25,
        db=row.db,
        hard_brakes=row.hard_brakes,
        weighted_brakes=row.weighted_brakes,
    )


def _event(row: EventRow) -> RideEvent:
    return RideEvent(
        id=row.id,
        position=row.position,
        type=row.type,
        sample_index=row.sample_index,
        lon=row.lon,
        lat=row.lat,
        value=row.value,
        peak=row.peak,
        duration_ms=row.duration_ms,
        occurred_at=row.occurred_at,
        street=row.street,
        ask=row.ask,
        hotspot_id=row.hotspot_id,
    )


def _flag(row: FlagRow, device_id: str, session_id: int) -> Flag:
    return Flag(
        id=row.id,
        device_id=device_id,
        session_id=session_id,
        seq=row.seq,
        sample_index=row.sample_index,
        lon=row.lon,
        lat=row.lat,
        pressed_at=row.pressed_at,
        street=row.street,
        source=row.source,
        keyword_kind=row.keyword_kind,
        keyword_confidence=row.keyword_confidence,
        lang=row.lang,
        speed_kmh=row.speed_kmh,
        vib_rms=row.vib_rms,
        noise_db=row.noise_db,
        sig_alg=row.sig_alg,
        signature=row.signature,
        hazard_id=row.hazard_id,
    )
