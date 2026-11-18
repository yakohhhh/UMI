"""The scored street network and what the Clips found on it."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from umi_api.db.base import Base, UtcDateTime, str_enum
from umi_api.domain.enums import ActivityType, BrakeCause, PotholeSeverity, StreetKind

if TYPE_CHECKING:
    from umi_api.db.models.city import District


class StreetSegment(Base):
    __tablename__ = "street_segments"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    from_name: Mapped[str | None] = mapped_column(String(120))
    to_name: Mapped[str | None] = mapped_column(String(120))
    district_code: Mapped[str] = mapped_column(ForeignKey("districts.code"), index=True)
    kind: Mapped[StreetKind] = mapped_column(str_enum(StreetKind))
    bike_lane: Mapped[bool] = mapped_column(Boolean)
    length_m: Mapped[int] = mapped_column(Integer)
    # [[lon, lat], ...]
    coordinates: Mapped[list[list[float]]] = mapped_column(JSON)
    comfort: Mapped[int] = mapped_column(Integer)
    safety: Mapped[int] = mapped_column(Integer)
    air: Mapped[int] = mapped_column(Integer)
    noise: Mapped[int] = mapped_column(Integer)
    passes_30d: Mapped[int] = mapped_column(Integer)
    # Change of the overall score vs the previous 30 days, in points.
    trend: Mapped[float] = mapped_column(Float)
    vib_rms: Mapped[float] = mapped_column(Float)
    # Typical PM2.5 (µg/m³) and noise (dB(A)) measured on the segment.
    pm25: Mapped[float] = mapped_column(Float)
    db: Mapped[float] = mapped_column(Float)

    district: Mapped["District"] = relationship(lazy="raise")
    hourly: Mapped[list["SegmentHourlyScore"]] = relationship(
        order_by="SegmentHourlyScore.hour", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )


class SegmentHourlyScore(Base):
    __tablename__ = "segment_hourly_scores"

    segment_id: Mapped[str] = mapped_column(ForeignKey("street_segments.id", ondelete="CASCADE"), primary_key=True)
    hour: Mapped[int] = mapped_column(Integer, primary_key=True)
    comfort: Mapped[int] = mapped_column(Integer)
    safety: Mapped[int] = mapped_column(Integer)
    air: Mapped[int] = mapped_column(Integer)
    noise: Mapped[int] = mapped_column(Integer)


class SegmentHourlyBaseline(Base):
    """The seeded hourly scores, kept apart so the published ones can always be recomputed from them.

    `umi-api aggregate` merges riders' passes into these and writes `segment_hourly_scores`.
    """

    __tablename__ = "segment_hourly_baselines"

    segment_id: Mapped[str] = mapped_column(ForeignKey("street_segments.id", ondelete="CASCADE"), primary_key=True)
    hour: Mapped[int] = mapped_column(Integer, primary_key=True)
    comfort: Mapped[int] = mapped_column(Integer)
    safety: Mapped[int] = mapped_column(Integer)
    air: Mapped[int] = mapped_column(Integer)
    noise: Mapped[int] = mapped_column(Integer)


class SegmentSurface(Base):
    """Surface figures for the city's resurfacing ranking (last 30 days)."""

    __tablename__ = "segment_surface_stats"

    segment_id: Mapped[str] = mapped_column(ForeignKey("street_segments.id", ondelete="CASCADE"), primary_key=True)
    surface_index: Mapped[float] = mapped_column(Float)
    confirmed_impacts: Mapped[int] = mapped_column(Integer)
    riders_30d: Mapped[int] = mapped_column(Integer)
    trend: Mapped[float] = mapped_column(Float)

    segment: Mapped[StreetSegment] = relationship(lazy="raise")


class Pothole(Base):
    __tablename__ = "potholes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    segment_id: Mapped[str] = mapped_column(ForeignKey("street_segments.id", ondelete="CASCADE"), index=True)
    lon: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    # Distinct Clips that felt the impact.
    confirmations: Mapped[int] = mapped_column(Integer)
    first_seen: Mapped[date] = mapped_column(Date)
    severity: Mapped[PotholeSeverity] = mapped_column(str_enum(PotholeSeverity))

    segment: Mapped[StreetSegment] = relationship(lazy="raise")


class BrakeHotspot(Base):
    """A cluster of hard brakes (> 3 m/s²), usually a junction."""

    __tablename__ = "brake_hotspots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(160))
    lon: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    district_code: Mapped[str | None] = mapped_column(ForeignKey("districts.code"))
    hard_brakes_week: Mapped[int] = mapped_column(Integer)
    hard_brakes_30d: Mapped[int] = mapped_column(Integer)
    peak_hour: Mapped[int] = mapped_column(Integer)
    trend: Mapped[float] = mapped_column(Float)
    avg_decel: Mapped[float] = mapped_column(Float)

    district: Mapped["District | None"] = relationship(lazy="raise")


class HotspotCauseAnswer(Base):
    """One rider's answer to "why did you brake?" at a hotspot; mixes are computed from these."""

    __tablename__ = "hotspot_cause_answers"
    __table_args__ = (Index("ix_hotspot_cause_answers_hotspot_time", "hotspot_id", "answered_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hotspot_id: Mapped[str] = mapped_column(ForeignKey("brake_hotspots.id", ondelete="CASCADE"))
    # Same pseudonymous key as hazard_confirmations.rider_key.
    rider_key: Mapped[str] = mapped_column(String(64))
    activity_type: Mapped[ActivityType] = mapped_column(str_enum(ActivityType))
    cause: Mapped[BrakeCause] = mapped_column(str_enum(BrakeCause))
    answered_at: Mapped[datetime] = mapped_column(UtcDateTime)
    # The rider's own brake, when the answer came from the app.
    ride_event_id: Mapped[str | None] = mapped_column(ForeignKey("ride_events.id", ondelete="CASCADE"), unique=True)
