"""Session ingest (protocol/README.md §3): a trimmed Clip session becomes a ride, its flags and its street data.

Checks come in the order an uploader can act on them: the log itself (422), then
whether the Clip is paired with the caller (403). A session already stored answers
with its first receipt (200). The pipeline then works on plain values, and this
service stores what it produced in one transaction (ADR 0004). Uploads are processed
one at a time (`db.locks`): each one reads what the previous ones wrote, so riders
flagging the same corner at the same moment still join one hazard.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from umi_protocol import public_key_from_uncompressed

from umi_api.clock import Clock
from umi_api.db.locks import CriticalSection
from umi_api.db.models import Activity, Device, ExposureDay, HazardConfirmation, SessionUpload
from umi_api.domain.calendar import local_day, local_midnight
from umi_api.domain.enums import ActivityType, CityHazardStatus, ConfirmationSource, HazardStatus, Period
from umi_api.domain.hazards import MERGE_RADIUS_M, status_for
from umi_api.domain.privacy import cause_mix, period_start
from umi_api.pipeline import (
    HotspotRef,
    MatchedTrack,
    OpenHazard,
    ProcessedRide,
    RideContext,
    SessionRejected,
    Upload,
    activity_id,
    add_exposure,
    build_track,
    map_match,
    process,
    read_upload,
)
from umi_api.pipeline.flags import Confirmation
from umi_api.pipeline.geometry import bbox_around
from umi_api.repositories.activities import ActivityRepository
from umi_api.repositories.devices import DeviceRepository
from umi_api.repositories.hazards import HazardRepository
from umi_api.repositories.riders import ExposureRepository
from umi_api.repositories.scores import StreetScoreRepository
from umi_api.repositories.streets import CauseTally, HotspotRepository
from umi_api.repositories.uploads import SessionUploadRepository
from umi_api.services.aggregation import AggregationService
from umi_api.services.errors import ConflictError, ForbiddenError, UnprocessableError
from umi_api.services.ride_rows import activity_row, hazard_row, pass_row
from umi_api.services.street_network import StreetNetwork
from umi_api.settings import Settings


@dataclass(frozen=True)
class IngestResult:
    receipt: SessionUpload
    # False when the session had already been uploaded: the receipt is the first one.
    created: bool


class IngestService:
    def __init__(
        self,
        session: AsyncSession,
        clock: Clock,
        network: StreetNetwork,
        settings: Settings,
        section: CriticalSection,
    ) -> None:
        """`clock` is the real one: an upload happens now, whatever moment the demo data is pinned to."""
        self._session = session
        self._clock = clock
        self._network = network
        self._section = section
        self._accept_simulated = bool(settings.accept_simulated)
        self._aggregate = bool(settings.aggregate_on_ingest)
        self._activities = ActivityRepository(session)
        self._devices = DeviceRepository(session)
        self._exposure = ExposureRepository(session)
        self._hazards = HazardRepository(session)
        self._hotspots = HotspotRepository(session)
        self._scores = StreetScoreRepository(session)
        self._uploads = SessionUploadRepository(session)

    async def ingest(self, athlete_id: str, body: bytes) -> IngestResult:
        upload = self._read(body)
        device = await self._devices.get(upload.device_id)
        if device is None or device.athlete_id != athlete_id:
            raise ForbiddenError(f"Clip {upload.device_id} is not paired with this account")
        if device.simulated and not self._accept_simulated:
            raise UnprocessableError(f"Clip {device.id} has simulated sensors, which are not accepted here")
        async with self._section.hold(self._session):
            if (stored := await self._uploads.find(upload.device_id, upload.session_id)) is not None:
                return IngestResult(stored, created=False)
            if await self._activities.session_stored(upload.device_id, upload.session_id):
                raise ConflictError("This session is already stored, without an upload receipt to answer with")
            try:
                receipt = await self._process(athlete_id, device, upload)
                await self._session.commit()
            except IntegrityError:
                # Another process stored the same session first: only possible on SQLite, served by one process.
                await self._session.rollback()
                if (stored := await self._uploads.find(upload.device_id, upload.session_id)) is None:
                    raise
                return IngestResult(stored, created=False)
        return IngestResult(receipt, created=True)

    def _read(self, body: bytes) -> Upload:
        try:
            return read_upload(body, accept_simulated=self._accept_simulated)
        except SessionRejected as exc:
            raise UnprocessableError(str(exc)) from exc

    async def _process(self, athlete_id: str, device: Device, upload: Upload) -> SessionUpload:
        now = self._clock.now()
        try:
            track = build_track(upload, now)
        except SessionRejected as exc:
            raise UnprocessableError(str(exc)) from exc
        index = await self._network.index(self._session)
        matched = map_match(track, index)
        context = await self._context(athlete_id, device, matched, now)
        ride = process(matched, index, context)
        await self._store(activity_row(context.activity_id, athlete_id, device.id, upload.session_id, ride), ride)
        device.firmware, device.hw_rev, device.last_sync_at = ride.device.firmware, ride.device.hw_rev, now
        if ride.device.battery_pct is not None:
            device.battery_pct = ride.device.battery_pct
        receipt = SessionUpload(
            activity_id=context.activity_id,
            received_at=now,
            segments_matched=ride.segments_matched,
            events=len(ride.events),
            flags_accepted=len(ride.flags.rows),
            flags_rejected=ride.flags.rejected,
        )
        self._uploads.add(receipt)
        if self._aggregate and ride.passes:
            await AggregationService(self._session, self._clock).run({p.segment_id for p in ride.passes})
        return receipt

    async def _context(self, athlete_id: str, device: Device, matched: MatchedTrack, now: datetime) -> RideContext:
        track = matched.track
        tallies = await self._hotspots.cause_tallies(period_start(now, Period.MONTH))
        hotspots = [
            HotspotRef(h.id, h.lon, h.lat, mix_published=_mix_published(tallies.get(h.id)))
            for h in await self._hotspots.all()
        ]
        around = bbox_around(((p.lon, p.lat) for p in track.points), MERGE_RADIUS_M)
        first_day, last_day = local_day(track.started_at), local_day(track.utc(track.session.duration_ms))
        pressed = await self._activities.flag_times(
            athlete_id, local_midnight(first_day), local_midnight(last_day + timedelta(days=1))
        )
        return RideContext(
            activity_id=await self._free_activity_id(activity_id(athlete_id, track.started_at)),
            public_key=public_key_from_uncompressed(device.public_key),
            hourly=await self._scores.published({sid for sid in matched.segment_ids if sid is not None}),
            hotspots=hotspots,
            open_hazards=[OpenHazard(h.id, h.kind, h.lon, h.lat) for h in await self._hazards.open_within(around)],
            flags_per_day=Counter(local_day(t) for t in pressed),
        )

    async def _free_activity_id(self, base: str) -> str:
        """`base`, or `base-2`, `base-3`... when the rider has another activity that started the same minute."""
        candidate, n = base, 1
        while await self._activities.exists(candidate):
            n += 1
            candidate = f"{base}-{n}"
        return candidate

    async def _store(self, activity: Activity, ride: ProcessedRide) -> None:
        # Flags point at the hazards they open and events at the street passes that count them,
        # so hazards go in first, then the activity, then its passes.
        for new in ride.flags.opened:
            self._hazards.add(hazard_row(new))
        await self._session.flush()
        self._activities.add(activity)
        await self._session.flush()
        passes = {row.key: pass_row(row, activity) for row in ride.passes}
        self._scores.add_passes(passes.values())
        await self._session.flush()
        for event, row in zip(activity.events, ride.events, strict=True):
            if row.pass_key is not None:
                event.segment_pass_id = passes[row.pass_key].id
        await self._confirm(activity.athlete_id, activity.type, ride.flags.confirmations)
        await self._add_exposure(activity.athlete_id, ride)

    async def _confirm(
        self, rider_key: str, activity_type: ActivityType, confirmations: Sequence[Confirmation]
    ) -> None:
        """Count the rider once per hazard, then move each hazard as far as its distinct riders take it."""
        if not confirmations:
            return
        by_hazard = {c.hazard_id: c for c in confirmations}
        existing = await self._hazards.confirmations_by(rider_key, by_hazard.keys())
        for hazard_id, c in by_hazard.items():
            row = existing.get(hazard_id)
            if row is None:
                self._hazards.add(
                    HazardConfirmation(
                        hazard_id=hazard_id,
                        rider_key=rider_key,
                        activity_type=activity_type,
                        source=c.source,
                        flag_id=c.flag_id,
                        confirmed_at=c.at,
                    )
                )
                continue
            # The latest time counts, and a press outranks a sensor match (same rule within a ride).
            if c.at > row.confirmed_at:
                row.confirmed_at, row.activity_type = c.at, activity_type
            if c.source is ConfirmationSource.FLAG and row.source is not ConfirmationSource.FLAG:
                row.source, row.flag_id = c.source, c.flag_id
        await self._session.flush()
        riders = await self._hazards.rider_counts(by_hazard.keys())
        for hazard in (await self._hazards.get_many(by_hazard.keys())).values():
            c = by_hazard[hazard.id]
            hazard.last_confirmed_at = max(hazard.last_confirmed_at, c.at)
            hazard.kind = hazard.kind or c.kind
            hazard.status = status_for(hazard.status, riders.get(hazard.id, 0))
            if hazard.status is HazardStatus.SENT_TO_CITY and hazard.city_status is None:
                hazard.city_status = CityHazardStatus.NEW

    async def _add_exposure(self, athlete_id: str, ride: ProcessedRide) -> None:
        stored = await self._exposure.day(athlete_id, ride.exposure.day)
        day = add_exposure(stored, ride.exposure)
        if stored is None:
            stored = ExposureDay(athlete_id=athlete_id, day=day.day)
            self._exposure.add(stored)
        stored.ride_min, stored.pm25, stored.db, stored.dose_ug_h = day.ride_min, day.pm25, day.db, day.dose_ug_h


def _mix_published(tally: CauseTally | None) -> bool:
    """Whether the hotspot's "why riders brake" mix is out (enough different riders answered there)."""
    return tally is not None and cause_mix(tally.answers, tally.riders) is not None
