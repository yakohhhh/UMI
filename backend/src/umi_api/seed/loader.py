"""Load the web app's mock datasets into the database (`umi-api seed`).

Idempotent: rows keyed by the mocks' ids are inserted or updated, collections
the demo owns (a demo ride's events, Laia's exposure days, the panel riders)
are replaced. Running it again later moves the demo to the new week, and resets
the answers given on demo rides.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import ColumnElement, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from umi_api.db.base import Base
from umi_api.db.models import (
    Activity,
    ActivityDetail,
    ActivitySegment,
    ApiKey,
    ApiUsageDay,
    Athlete,
    AthleteBadge,
    AthleteProfile,
    AthleteRecord,
    Badge,
    BestWindow,
    BrakeHotspot,
    CityAirNoiseCell,
    CityKpi,
    CityMonthlyBrakes,
    CityOutline,
    Club,
    ClubMembership,
    DatasetSnapshot,
    Device,
    District,
    DistrictStats,
    ExposureContributor,
    ExposureDay,
    Flag,
    Follow,
    Hazard,
    HazardConfirmation,
    HotspotCauseAnswer,
    PlannedRoute,
    Pothole,
    RideEvent,
    SegmentHourlyBaseline,
    SegmentHourlyScore,
    SegmentSurface,
    Snapshot,
    StreetSegment,
)
from umi_api.db.upsert import upsert
from umi_api.domain.enums import (
    ActivityType,
    BrakeCause,
    CityHazardStatus,
    ConfirmationSource,
    FlagSource,
    HazardKind,
    HazardStatus,
    RideEventType,
)
from umi_api.domain.geo import nearest_segment_district
from umi_api.repositories.activities import ActivityRepository
from umi_api.seed import demo, panel
from umi_api.seed.mock_data import ActivityJson, FlagJson, MockData, ScoresJson
from umi_api.seed.shift import MOCK_ANCHOR, parse_instant, shift_day, week_shift

# Panel riders confirm a freshly flagged hazard within the hour.
_CONFIRMATION_GAP = timedelta(minutes=20)


@dataclass(frozen=True)
class SeedReport:
    as_of: datetime
    week_shift_days: int
    activities: int
    hazards: int
    hotspot_answers: int


@dataclass(frozen=True)
class _PlacedSegment:
    district: str
    coordinates: list[list[float]]


@dataclass(frozen=True)
class _Context:
    data: MockData
    session: AsyncSession
    shift: timedelta
    as_of: datetime
    district_codes: dict[str, str]


async def seed_demo(session: AsyncSession, data: MockData, now: datetime) -> SeedReport:
    """Write the demo in one transaction; dates move by the whole weeks between the mocks and `now`."""
    shift = week_shift(now)
    ctx = _Context(
        data=data,
        session=session,
        shift=shift,
        as_of=MOCK_ANCHOR + shift,
        district_codes={f["properties"]["name"]: f["properties"]["code"] for f in data.districts["features"]},
    )
    await _city_geography(ctx)
    await _streets(ctx)
    await _riders(ctx)
    hazards = await _hazards(ctx)
    activities = await _activities(ctx)
    await _confirmations(ctx)
    answers = await _hotspot_answers(ctx)
    await _rider_aggregates(ctx)
    await _city_aggregates(ctx)
    await _api_key(ctx)
    await upsert(
        session,
        DatasetSnapshot,
        [
            {"name": Snapshot.DEMO, "generated_at": ctx.as_of, "loaded_at": now},
            {"name": Snapshot.CITY, "generated_at": parse_instant(data.city["generatedAt"]) + shift, "loaded_at": now},
        ],
    )
    await session.commit()
    return SeedReport(
        as_of=ctx.as_of,
        week_shift_days=shift.days,
        activities=activities,
        hazards=hazards,
        hotspot_answers=answers,
    )


async def _city_geography(ctx: _Context) -> None:
    features = ctx.data.districts["features"]
    await upsert(
        ctx.session,
        District,
        [
            {"code": f["properties"]["code"], "name": f["properties"]["name"], "geometry": f["geometry"]}
            for f in features
        ],
    )
    await upsert(
        ctx.session,
        DistrictStats,
        [
            {
                "district_code": d["code"],
                **_scores(d["scores"]),
                "surface_index": d["surfaceIndex"],
                "rides_week": d["ridesWeek"],
                "km_measured": d["kmMeasured"],
                "pm25": d["pm25"],
                "db": d["db"],
            }
            for d in ctx.data.city["districts"]
        ],
    )
    await upsert(
        ctx.session,
        CityOutline,
        [
            {"id": f["properties"]["name"].lower(), "name": f["properties"]["name"], "geometry": f["geometry"]}
            for f in ctx.data.city_outline["features"]
        ],
    )


async def _streets(ctx: _Context) -> None:
    streets = ctx.data.streets
    await upsert(
        ctx.session,
        StreetSegment,
        [
            {
                "id": s["id"],
                "name": s["name"],
                "from_name": s["from"],
                "to_name": s["to"],
                "district_code": ctx.district_codes[s["district"]],
                "kind": s["kind"],
                "bike_lane": s["bikeLane"],
                "length_m": s["lengthM"],
                "coordinates": s["coordinates"],
                **_scores(s["scores"]),
                "passes_30d": s["passes30d"],
                "trend": s["trend"],
                "vib_rms": s["surface"]["vibRms"],
                "pm25": s["pm25"],
                "db": s["db"],
            }
            for s in streets
        ],
    )
    hourly = [
        {
            "segment_id": s["id"],
            "hour": hour,
            "comfort": s["hourly"]["comfort"][hour],
            "safety": s["hourly"]["safety"][hour],
            "air": s["hourly"]["air"][hour],
            "noise": s["hourly"]["noise"][hour],
        }
        for s in streets
        for hour in range(24)
    ]
    # The seeded scores are both what is published and the baseline riders' passes merge into.
    await upsert(ctx.session, SegmentHourlyBaseline, hourly)
    await upsert(ctx.session, SegmentHourlyScore, hourly)
    await upsert(
        ctx.session,
        SegmentSurface,
        [
            {
                "segment_id": r["segmentId"],
                "surface_index": r["surfaceIndex"],
                "confirmed_impacts": r["confirmedImpacts"],
                "riders_30d": r["riders30d"],
                "trend": r["trend"],
            }
            for r in ctx.data.surface_ranking
        ],
    )
    await upsert(
        ctx.session,
        Pothole,
        [
            {
                "id": p["id"],
                "segment_id": p["segmentId"],
                "lon": p["coordinates"][0],
                "lat": p["coordinates"][1],
                "confirmations": p["confirmations"],
                "first_seen": shift_day(p["firstSeen"], ctx.shift),
                "severity": p["severity"],
            }
            for p in ctx.data.potholes
        ],
    )

    placed = [_PlacedSegment(s["district"], s["coordinates"]) for s in streets]
    rows = []
    for h in ctx.data.hotspots:
        district = nearest_segment_district((h["coordinates"][0], h["coordinates"][1]), placed)
        rows.append(
            {
                "id": h["id"],
                "label": h["label"],
                "lon": h["coordinates"][0],
                "lat": h["coordinates"][1],
                "district_code": None if district is None else ctx.district_codes[district],
                "hard_brakes_week": h["hardBrakesWeek"],
                "hard_brakes_30d": h["hardBrakes30d"],
                "peak_hour": h["peakHour"],
                "trend": h["trend"],
                "avg_decel": h["avgDecel"],
            }
        )
    await upsert(ctx.session, BrakeHotspot, rows)


async def _riders(ctx: _Context) -> None:
    people = ctx.data.people["people"]
    await upsert(
        ctx.session,
        Athlete,
        [
            {
                "id": p["id"],
                "name": p["name"],
                "first_name": p["firstName"],
                "initials": p["initials"],
                "age": p["age"],
                "city": p["city"],
                "vehicle": p["vehicle"],
            }
            for p in people.values()
        ],
    )
    await upsert(
        ctx.session,
        Follow,
        [{"follower_id": a, "followee_id": b} for a, b in demo.FOLLOWS if a in people and b in people],
    )
    devices = []
    for device in demo.DEVICES:
        athlete_id = str(device["athlete_id"])
        devices.append(
            {
                **device,
                "name": "UMI Clip",
                "simulated": False,
                "paired_at": ctx.as_of - timedelta(days=365),
                "last_sync_at": _last_sync(ctx, athlete_id),
                "disabled_sensors": [],
            }
        )
    await upsert(ctx.session, Device, devices)


def _last_sync(ctx: _Context, athlete_id: str) -> datetime:
    if athlete_id == demo.LAIA:
        return ctx.as_of - demo.LAST_SYNC_BEFORE_NOW
    # Other riders synced when their last activity ended.
    ends = [
        parse_instant(a["startedAt"]) + ctx.shift + timedelta(seconds=a["durationS"])
        for a in ctx.data.activities
        if a["athleteId"] == athlete_id
    ]
    return max(ends, default=ctx.as_of - timedelta(days=1))


async def _hazards(ctx: _Context) -> int:
    """City hazards from flags.json, plus a hazard for every flag that did not join one."""
    flags = ctx.data.flags
    rows: list[dict[str, Any]] = []
    for h in flags["cityHazards"]:
        city_status = CityHazardStatus(h["status"])
        rows.append(
            {
                "id": h["id"],
                "kind": HazardKind(h["kind"]),
                "lon": h["coordinates"][0],
                "lat": h["coordinates"][1],
                "street": h["street"],
                "district_code": ctx.district_codes.get(h["district"]),
                "status": HazardStatus.FIXED if city_status is CityHazardStatus.FIXED else HazardStatus.SENT_TO_CITY,
                "city_status": city_status,
                "first_seen_at": _noon(shift_day(h["firstSeen"], ctx.shift)),
                "last_confirmed_at": _noon(shift_day(h["lastConfirmed"], ctx.shift)),
                "riders_warned": 0,
                "proof": None,
            }
        )
    by_id = {row["id"]: row for row in rows}
    for activity, flag in _demo_flags(ctx):
        pressed_at = _flag_time(ctx, activity, flag)
        joined = flags["flagHazards"].get(flag["id"])
        if joined is not None:
            # The rider's own outcome lives on the hazard they joined.
            hazard = by_id[joined]
            hazard.update(
                riders_warned=flag["ridersWarned"],
                proof=flag.get("proof"),
                first_seen_at=min(hazard["first_seen_at"], pressed_at),
            )
            continue
        rows.append(
            {
                "id": flag["id"],
                "kind": None if flag["kind"] is None else HazardKind(flag["kind"]),
                "lon": flag["coordinates"][0],
                "lat": flag["coordinates"][1],
                "street": flag["street"],
                "district_code": None,
                "status": HazardStatus(flag["status"]),
                "city_status": None,
                "first_seen_at": pressed_at,
                "last_confirmed_at": pressed_at + _CONFIRMATION_GAP * flag["confirmations"],
                "riders_warned": flag["ridersWarned"],
                "proof": flag.get("proof"),
            }
        )
    await upsert(ctx.session, Hazard, rows)
    await ctx.session.execute(
        delete(HazardConfirmation).where(HazardConfirmation.hazard_id.in_([r["id"] for r in rows]))
    )
    return len(rows)


async def _activities(ctx: _Context) -> int:
    repository = ActivityRepository(ctx.session)
    await repository.delete([a["id"] for a in ctx.data.activities])
    await ctx.session.flush()
    devices = {str(d["athlete_id"]): str(d["id"]) for d in demo.DEVICES}
    # Each Clip numbers its sessions; the oldest demo ride is session 1.
    oldest_first = sorted(ctx.data.activities, key=lambda a: a["startedAt"])
    session_ids = {a["id"]: n for n, a in enumerate(oldest_first, start=1)}
    flags = ctx.data.flags
    for a in ctx.data.activities:
        detail = ctx.data.details[a["id"]]
        started_at = parse_instant(a["startedAt"]) + ctx.shift
        device_id = devices.get(a["athleteId"])
        session_id = session_ids[a["id"]] if device_id else None
        repository.add(
            Activity(
                id=a["id"],
                athlete_id=a["athleteId"],
                device_id=device_id,
                session_id=session_id,
                type=ActivityType(a["type"]),
                title=a["title"],
                place=a["place"],
                description=a["description"],
                started_at=started_at,
                duration_s=a["durationS"],
                moving_time_s=a["movingTimeS"],
                distance_m=a["distanceM"],
                avg_speed_kmh=a["avgSpeedKmh"],
                max_speed_kmh=a["maxSpeedKmh"],
                elevation_gain_m=a["elevationGainM"],
                **_scores(a["scores"]),
                preview=a["preview"],
                kudos=a["kudos"],
                kudoed_by=a["kudoedBy"],
                comments=a["comments"],
                featured=a["featured"],
                weather_temp_c=a["weather"]["tempC"],
                weather_condition=a["weather"]["condition"],
                events=[_event(ctx, a, index) for index in range(len(a["events"]))],
                flags=[
                    _flag(ctx, a, flag, seq=seq, device_id=device_id, session_id=session_id)
                    for seq, flag in enumerate(flags["flags"].get(a["id"], []))
                ],
                detail=ActivityDetail(route=detail["route"], samples=detail["samples"]),
                segments=[
                    ActivitySegment(
                        position=position,
                        segment_id=s["segmentId"],
                        distance_m=s["distanceM"],
                        score=s["score"],
                        street_average=s["streetAverage"],
                    )
                    for position, s in enumerate(detail["segments"])
                ],
            )
        )
    await ctx.session.flush()
    return len(ctx.data.activities)


def _event(ctx: _Context, activity: ActivityJson, index: int) -> RideEvent:
    e = activity["events"][index]
    event_id = f"{activity['id']}-e{index}"
    kind = RideEventType(e["type"])
    answer = ctx.data.flags["brakeAnswers"].get(event_id) if kind is RideEventType.HARD_BRAKE else None
    cause = None if answer is None or answer["cause"] is None else BrakeCause(answer["cause"])
    occurred_at = _sample_time(ctx, activity, e["sampleIndex"])
    return RideEvent(
        id=event_id,
        position=index,
        type=kind,
        sample_index=e["sampleIndex"],
        lon=e["coordinates"][0],
        lat=e["coordinates"][1],
        value=e["value"],
        occurred_at=occurred_at,
        street=e["street"],
        ask=bool(answer and answer.get("ask", False)),
        cause=cause,
        cause_answered_at=None if cause is None else _activity_end(ctx, activity),
    )


def _flag(
    ctx: _Context, activity: ActivityJson, flag: FlagJson, *, seq: int, device_id: str | None, session_id: int | None
) -> Flag:
    kind = None if flag["kind"] is None else HazardKind(flag["kind"])
    source = FlagSource(flag["source"])
    # A keyword is said on the Clip; a press gets its kind from the rider after the ride.
    by_voice = source is FlagSource.VOICE
    return Flag(
        id=flag["id"],
        device_id=device_id,
        session_id=session_id,
        seq=seq,
        sample_index=flag["sampleIndex"],
        lon=flag["coordinates"][0],
        lat=flag["coordinates"][1],
        pressed_at=_flag_time(ctx, activity, flag),
        street=flag["street"],
        source=source,
        keyword_kind=kind if by_voice else None,
        answered_kind=None if by_voice else kind,
        kind_answered_at=None if by_voice or kind is None else _activity_end(ctx, activity),
        hazard_id=ctx.data.flags["flagHazards"].get(flag["id"], flag["id"]),
    )


async def _confirmations(ctx: _Context) -> None:
    """One row per distinct rider behind each hazard: the demo riders' own flags, then the panel."""
    rows: list[dict[str, Any]] = []
    own: dict[str, dict[str, Any]] = {}
    for activity, flag in _demo_flags(ctx):
        hazard_id = ctx.data.flags["flagHazards"].get(flag["id"], flag["id"])
        pressed_at = _flag_time(ctx, activity, flag)
        own[hazard_id] = {
            "hazard_id": hazard_id,
            "rider_key": activity["athleteId"],
            "activity_type": ActivityType(activity["type"]),
            "source": ConfirmationSource.FLAG,
            "flag_id": flag["id"],
            "confirmed_at": pressed_at,
        }
        if hazard_id == flag["id"]:
            times = [pressed_at + _CONFIRMATION_GAP * (k + 1) for k in range(flag["confirmations"])]
            rows.extend(_panel_rows(hazard_id, panel.hazard_riders(hazard_id, times, runs=0)))
    for h in ctx.data.flags["cityHazards"]:
        first, last = _noon(shift_day(h["firstSeen"], ctx.shift)), _noon(shift_day(h["lastConfirmed"], ctx.shift))
        mine = own.get(h["id"])
        times = panel.spread(first, last, h["riders"])
        if mine is not None:
            # The demo rider opened it; the panel follows.
            times = times[1:]
        riders = panel.hazard_riders(h["id"], times, runs=panel.runners(h["riders"]))
        rows.extend(_panel_rows(h["id"], riders))
    rows.extend(own.values())
    await ctx.session.execute(insert(HazardConfirmation), rows)


def _panel_rows(hazard_id: str, riders: Sequence[panel.PanelRider]) -> list[dict[str, Any]]:
    return [
        {
            "hazard_id": hazard_id,
            "rider_key": r.key,
            "activity_type": r.activity_type,
            "source": ConfirmationSource.SENSOR,
            "flag_id": None,
            "confirmed_at": r.at,
        }
        for r in riders
    ]


async def _hotspot_answers(ctx: _Context) -> int:
    hotspot_ids = [h["id"] for h in ctx.data.hotspots]
    # Imported answers are the ones not tied to a stored ride.
    await ctx.session.execute(
        delete(HotspotCauseAnswer).where(
            HotspotCauseAnswer.hotspot_id.in_(hotspot_ids), HotspotCauseAnswer.ride_event_id.is_(None)
        )
    )
    rows = [
        {
            "hotspot_id": h["id"],
            "rider_key": answer.rider.key,
            "activity_type": answer.rider.activity_type,
            "cause": answer.cause,
            "answered_at": answer.rider.at,
            "ride_event_id": None,
        }
        for h in ctx.data.hotspots
        for answer in panel.hotspot_answers(h["id"], h["hardBrakes30d"], ctx.as_of)
    ]
    if rows:
        await ctx.session.execute(insert(HotspotCauseAnswer), rows)
    return len(rows)


async def _rider_aggregates(ctx: _Context) -> None:
    laia = demo.LAIA
    await _replace(
        ctx,
        ExposureDay,
        ExposureDay.athlete_id == laia,
        [
            {
                "athlete_id": laia,
                "day": shift_day(d["date"], ctx.shift),
                "ride_min": d["rideMin"],
                "pm25": d["pm25"],
                "db": d["db"],
                "dose_ug_h": d["doseUgH"],
            }
            for d in ctx.data.exposure
        ],
    )
    await _replace(
        ctx,
        ExposureContributor,
        ExposureContributor.athlete_id == laia,
        [{"athlete_id": laia, "position": i, **c} for i, c in enumerate(demo.EXPOSURE_CONTRIBUTORS)],
    )
    await _replace(
        ctx,
        PlannedRoute,
        PlannedRoute.athlete_id == laia,
        [
            {
                "id": r["id"],
                "athlete_id": laia,
                "position": i,
                "goal": r["goal"],
                "label": r["label"],
                "duration_min": r["durationMin"],
                "distance_m": r["distanceM"],
                **_scores(r["scores"]),
                "via": r["via"],
                "highlight": r["highlight"],
                "coordinates": r["coordinates"],
            }
            for i, r in enumerate(ctx.data.routes)
        ],
    )
    await upsert(ctx.session, BestWindow, [demo.BEST_WINDOW])
    await upsert(ctx.session, AthleteProfile, [demo.PROFILE])
    await _replace(
        ctx, AthleteRecord, AthleteRecord.athlete_id == laia, [{"athlete_id": laia, **r} for r in demo.RECORDS]
    )
    await upsert(
        ctx.session,
        Badge,
        [
            {"id": badge_id, "position": i, "label": label, "description": description}
            for i, (badge_id, label, description, _, _) in enumerate(demo.BADGES)
        ],
    )
    await upsert(
        ctx.session,
        AthleteBadge,
        [
            {"athlete_id": laia, "badge_id": badge_id, "earned": earned, "progress": progress}
            for badge_id, _, _, earned, progress in demo.BADGES
        ],
    )
    await upsert(ctx.session, Club, list(demo.CLUBS))
    await upsert(
        ctx.session,
        ClubMembership,
        [{"club_id": c["id"], "athlete_id": laia, "position": i} for i, c in enumerate(demo.CLUBS)],
    )


async def _city_aggregates(ctx: _Context) -> None:
    city = ctx.data.city
    await upsert(
        ctx.session,
        CityKpi,
        [
            {
                "id": k["id"],
                "position": i,
                "label": k["label"],
                "value": k["value"],
                "unit": k["unit"],
                "delta": k["delta"],
                "delta_unit": k["deltaUnit"],
                "delta_label": k.get("deltaLabel"),
                "better": k["better"],
                "spark": k["spark"],
                "limit_value": k.get("limit"),
                "limit_label": k.get("limitLabel"),
            }
            for i, k in enumerate(city["kpis"])
        ],
    )
    await upsert(
        ctx.session,
        CityMonthlyBrakes,
        [{"month": m["month"], "hard_brakes": m["hardBrakes"], "rides": m["rides"]} for m in city["monthlyHardBrakes"]],
    )
    await upsert(
        ctx.session,
        CityAirNoiseCell,
        [
            {"weekday": d, "hour": h, "pm25": cell["pm25"], "db": cell["db"], "rides": cell["rides"]}
            for d, row in enumerate(city["airNoise"])
            for h, cell in enumerate(row)
        ],
    )


async def _api_key(ctx: _Context) -> None:
    key_id = str(demo.API_KEY["id"])
    days = [(ctx.as_of - timedelta(days=13 - i)).date() for i in range(14)]
    calls = [demo.daily_calls(i, day) for i, day in enumerate(days)]
    usage = [{"api_key_id": key_id, "day": day, "calls": n} for day, n in zip(days, calls, strict=True)]
    await upsert(
        ctx.session,
        ApiKey,
        [
            {
                **demo.API_KEY,
                "quota_used": sum(calls) + demo.EARLIER_CALLS,
                "created_at": ctx.as_of - timedelta(days=75),
                "revoked_at": None,
            }
        ],
    )
    await _replace(ctx, ApiUsageDay, ApiUsageDay.api_key_id == key_id, usage)


async def _replace(
    ctx: _Context, model: type[Base], owned_by: ColumnElement[bool], rows: Sequence[dict[str, Any]]
) -> None:
    """Replace a collection the demo owns."""
    await ctx.session.execute(delete(model).where(owned_by))
    if rows:
        await ctx.session.execute(insert(model), list(rows))


def _demo_flags(ctx: _Context) -> list[tuple[ActivityJson, FlagJson]]:
    activities = {a["id"]: a for a in ctx.data.activities}
    return [(activities[activity_id], flag) for activity_id, flags in ctx.data.flags["flags"].items() for flag in flags]


def _sample_time(ctx: _Context, activity: ActivityJson, sample_index: int) -> datetime:
    """When sample k was taken: the ride's start plus the sample's own clock (seconds)."""
    seconds = ctx.data.details[activity["id"]]["samples"][sample_index][0]
    return parse_instant(activity["startedAt"]) + ctx.shift + timedelta(seconds=seconds)


def _flag_time(ctx: _Context, activity: ActivityJson, flag: FlagJson) -> datetime:
    return _sample_time(ctx, activity, flag["sampleIndex"])


def _activity_end(ctx: _Context, activity: ActivityJson) -> datetime:
    return parse_instant(activity["startedAt"]) + ctx.shift + timedelta(seconds=activity["durationS"])


def _noon(day: date) -> datetime:
    return datetime.combine(day, time(12), UTC)


def _scores(scores: ScoresJson) -> dict[str, int]:
    return {"comfort": scores["comfort"], "safety": scores["safety"], "air": scores["air"], "noise": scores["noise"]}
