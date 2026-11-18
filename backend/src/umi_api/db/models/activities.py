"""Rides and runs, built from one Clip session each, and what happened during them."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from umi_api.db.base import Base, UtcDateTime, str_enum
from umi_api.domain.enums import ActivityType, BrakeCause, FlagSource, HazardKind, RideEventType

if TYPE_CHECKING:
    from umi_api.db.models.hazards import Hazard
    from umi_api.db.models.streets import StreetSegment


class Activity(Base):
    __tablename__ = "activities"
    # One activity per uploaded session: retries of the same upload find it again.
    __table_args__ = (UniqueConstraint("device_id", "session_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    session_id: Mapped[int | None] = mapped_column(Integer)
    type: Mapped[ActivityType] = mapped_column(str_enum(ActivityType))
    title: Mapped[str] = mapped_column(String(120))
    place: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    duration_s: Mapped[int] = mapped_column(Integer)
    moving_time_s: Mapped[int] = mapped_column(Integer)
    distance_m: Mapped[int] = mapped_column(Integer)
    avg_speed_kmh: Mapped[float] = mapped_column(Float)
    max_speed_kmh: Mapped[float] = mapped_column(Float)
    elevation_gain_m: Mapped[int] = mapped_column(Integer)
    comfort: Mapped[int] = mapped_column(Integer)
    safety: Mapped[int] = mapped_column(Integer)
    air: Mapped[int] = mapped_column(Integer)
    noise: Mapped[int] = mapped_column(Integer)
    # Simplified trace for thumbnails, [[lon, lat], ...].
    preview: Mapped[list[list[float]]] = mapped_column(JSON)
    kudos: Mapped[int] = mapped_column(Integer, default=0)
    kudoed_by: Mapped[list[str]] = mapped_column(JSON, default=list)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    weather_temp_c: Mapped[float] = mapped_column(Float)
    weather_condition: Mapped[str] = mapped_column(String(24))

    events: Mapped[list["RideEvent"]] = relationship(
        order_by="RideEvent.position", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )
    flags: Mapped[list["Flag"]] = relationship(
        order_by="Flag.seq", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )
    detail: Mapped["ActivityDetail | None"] = relationship(
        lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )
    segments: Mapped[list["ActivitySegment"]] = relationship(
        order_by="ActivitySegment.position", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )


class ActivityDetail(Base):
    """The heavy part of a ride report, read as a whole: the trace and the 1 Hz samples."""

    __tablename__ = "activity_details"

    activity_id: Mapped[str] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True)
    route: Mapped[list[list[float]]] = mapped_column(JSON)
    # [t (s), distance (m), speed (km/h), vibration (m/s² RMS), PM2.5 (µg/m³), noise (dB), route index]
    samples: Mapped[list[list[float]]] = mapped_column(JSON)


class ActivitySegment(Base):
    """A street segment the activity went through, scored for this pass."""

    __tablename__ = "activity_segments"

    activity_id: Mapped[str] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_id: Mapped[str] = mapped_column(ForeignKey("street_segments.id"), index=True)
    distance_m: Mapped[int] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer)
    # The street's own score at that hour when the ride was processed, same blend as `score`
    # (domain.scoring.pass_score), so the two compare.
    street_average: Mapped[int] = mapped_column(Integer)

    segment: Mapped["StreetSegment"] = relationship(lazy="raise")


class RideEvent(Base):
    __tablename__ = "ride_events"
    __table_args__ = (UniqueConstraint("activity_id", "position"),)

    # "{activity_id}-e{position}"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    activity_id: Mapped[str] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    type: Mapped[RideEventType] = mapped_column(str_enum(RideEventType))
    sample_index: Mapped[int] = mapped_column(Integer)
    lon: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    # m/s² for brakes (mean deceleration) and potholes (1 s vibration RMS), as the Clip's EVENT
    # record says (protocol/README.md §1.3); µg/m³ for PM2.5, dB(A) for noise.
    value: Mapped[float] = mapped_column(Float)
    # Clip EVENT records also carry the instantaneous peak (m/s²) and the duration.
    peak: Mapped[float | None] = mapped_column(Float)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime)
    street: Mapped[str | None] = mapped_column(String(160))
    # Hard brakes: one of the (at most 2) moments the app asks about after the ride.
    ask: Mapped[bool] = mapped_column(Boolean, default=False)
    cause: Mapped[BrakeCause | None] = mapped_column(str_enum(BrakeCause))
    cause_answered_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # Hard-brake cluster the event belongs to, set by the pipeline.
    hotspot_id: Mapped[str | None] = mapped_column(ForeignKey("brake_hotspots.id", ondelete="SET NULL"), index=True)
    # The street pass that counts the event, set by the pipeline: a cause given later re-weighs its brakes.
    segment_pass_id: Mapped[int | None] = mapped_column(ForeignKey("segment_passes.id", ondelete="SET NULL"))

    segment_pass: Mapped["SegmentPass | None"] = relationship(lazy="raise")


class Flag(Base):
    """A hazard flagged from the Clip's button, signed by the Clip (protocol/README.md §1.4)."""

    __tablename__ = "flags"
    # A replayed flag is ignored.
    __table_args__ = (UniqueConstraint("device_id", "session_id", "seq"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    activity_id: Mapped[str] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    session_id: Mapped[int | None] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer)
    sample_index: Mapped[int] = mapped_column(Integer)
    lon: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    pressed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    street: Mapped[str | None] = mapped_column(String(160))
    source: Mapped[FlagSource] = mapped_column(str_enum(FlagSource))
    # Recognised on the Clip and covered by the signature.
    keyword_kind: Mapped[HazardKind | None] = mapped_column(str_enum(HazardKind))
    keyword_confidence: Mapped[int | None] = mapped_column(Integer)
    lang: Mapped[str | None] = mapped_column(String(2))
    # Said by the rider after the ride for a flag pressed without a keyword (not signed).
    answered_kind: Mapped[HazardKind | None] = mapped_column(str_enum(HazardKind))
    kind_answered_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # Sensor snapshot at the press.
    speed_kmh: Mapped[float | None] = mapped_column(Float)
    vib_rms: Mapped[float | None] = mapped_column(Float)
    noise_db: Mapped[float | None] = mapped_column(Float)
    sig_alg: Mapped[int] = mapped_column(Integer, default=0)
    signature: Mapped[bytes | None] = mapped_column(LargeBinary(64))
    hazard_id: Mapped[str | None] = mapped_column(ForeignKey("hazards.id", ondelete="SET NULL"), index=True)

    hazard: Mapped["Hazard | None"] = relationship(lazy="raise")

    @property
    def kind(self) -> HazardKind | None:
        return self.keyword_kind or self.answered_kind


class SessionUpload(Base):
    """What processing an uploaded session produced, so a retried upload gets the same answer.

    The session itself is identified by its activity's `(device_id, session_id)`.
    """

    __tablename__ = "session_uploads"

    activity_id: Mapped[str] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(UtcDateTime)
    segments_matched: Mapped[int] = mapped_column(Integer)
    events: Mapped[int] = mapped_column(Integer)
    flags_accepted: Mapped[int] = mapped_column(Integer)
    # Bad or missing signature, outside the service area, or over the daily cap.
    flags_rejected: Mapped[int] = mapped_column(Integer)


class SegmentPass(Base):
    """One activity through one street segment in one hour: the unit street scores are recomputed from.

    A segment-hour is published only once enough distinct riders passed
    (`[privacy] segment_hour_min_riders`), so the rider is kept with each pass.
    """

    __tablename__ = "segment_passes"
    __table_args__ = (
        UniqueConstraint("activity_id", "segment_id", "hour_start"),
        Index("ix_segment_passes_segment_hour", "segment_id", "hour_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[str] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"))
    segment_id: Mapped[str] = mapped_column(ForeignKey("street_segments.id"))
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"))
    activity_type: Mapped[ActivityType] = mapped_column(str_enum(ActivityType))
    # Start of the UTC hour the pass began in.
    hour_start: Mapped[datetime] = mapped_column(UtcDateTime)
    vib_rms: Mapped[float | None] = mapped_column(Float)
    pm25: Mapped[float | None] = mapped_column(Float)
    db: Mapped[float | None] = mapped_column(Float)
    hard_brakes: Mapped[int] = mapped_column(Integer, default=0)
    # Brakes weighted by what riders said about them (domain.reports.brake_weight).
    weighted_brakes: Mapped[float] = mapped_column(Float, default=0)
