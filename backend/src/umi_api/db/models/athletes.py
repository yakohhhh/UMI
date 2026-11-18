"""Riders, who they follow, their Clips, and the profile figures computed for them."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from umi_api.db.base import Base, UtcDateTime, str_enum
from umi_api.domain.enums import ScoreDimension


class Athlete(Base):
    __tablename__ = "athletes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    first_name: Mapped[str] = mapped_column(String(60))
    initials: Mapped[str] = mapped_column(String(4))
    age: Mapped[int] = mapped_column(Integer)
    city: Mapped[str] = mapped_column(String(120))
    vehicle: Mapped[str] = mapped_column(String(40))
    weekly_goal_km: Mapped[float] = mapped_column(Float, default=40)


class Follow(Base):
    __tablename__ = "follows"

    follower_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    followee_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)


class Device(Base):
    """A Clip. Flags are accepted only from a Clip paired with the uploading rider (ADR 0005)."""

    __tablename__ = "devices"

    # u64 burnt in at provisioning, as 16 lowercase hex digits.
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    athlete_id: Mapped[str | None] = mapped_column(ForeignKey("athletes.id", ondelete="SET NULL"), index=True)
    paired_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # Uncompressed P-256 point (65 bytes) registered at provisioning; verifies flag signatures.
    public_key: Mapped[bytes] = mapped_column(LargeBinary(65))
    serial: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(60), default="UMI Clip")
    hw_rev: Mapped[int] = mapped_column(Integer, default=0)
    firmware: Mapped[str] = mapped_column(String(16))
    # Simulated sensor drivers (devkit or simulator); refused in production.
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    battery_pct: Mapped[int | None] = mapped_column(Integer)
    last_sync_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # Settings mirrored to the Clip over BLE (Settings characteristic).
    voice_keywords: Mapped[bool] = mapped_column(Boolean, default=False)
    keyword_languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    chirp: Mapped[bool] = mapped_column(Boolean, default=True)
    warn_ahead: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled_sensors: Mapped[list[str]] = mapped_column(JSON, default=list)


class AthleteProfile(Base):
    """Profile figures computed offline for a rider (totals, contributions, trust).

    `earlier_*` carry the outcomes of flags and answers older than the stored
    activities; live outcomes are added on top at query time.
    """

    __tablename__ = "athlete_profiles"

    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    member_since: Mapped[date] = mapped_column(Date)
    distance_km: Mapped[float] = mapped_column(Float)
    rides: Mapped[int] = mapped_column(Integer)
    runs: Mapped[int] = mapped_column(Integer)
    hours: Mapped[int] = mapped_column(Integer)
    streets_mapped: Mapped[int] = mapped_column(Integer)
    streets_improved: Mapped[int] = mapped_column(Integer)
    potholes_confirmed: Mapped[int] = mapped_column(Integer)
    segments_first: Mapped[int] = mapped_column(Integer)
    streak_days: Mapped[int] = mapped_column(Integer)
    # [{"name": street, "passes": n}], most ridden first.
    top_streets: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    # Private reliability, 0-10, no leaderboard.
    trust_level: Mapped[int] = mapped_column(Integer)
    trust_next: Mapped[str] = mapped_column(Text)
    trust_perks: Mapped[list[str]] = mapped_column(JSON)
    earlier_riders_warned: Mapped[int] = mapped_column(Integer, default=0)
    earlier_verified: Mapped[int] = mapped_column(Integer, default=0)
    earlier_fixed: Mapped[int] = mapped_column(Integer, default=0)
    earlier_causes_given: Mapped[int] = mapped_column(Integer, default=0)


class AthleteRecord(Base):
    __tablename__ = "athlete_records"

    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(60))
    value: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(String(160))
    achieved_on: Mapped[date] = mapped_column(Date)


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(160))


class AthleteBadge(Base):
    __tablename__ = "athlete_badges"

    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    badge_id: Mapped[str] = mapped_column(ForeignKey("badges.id", ondelete="CASCADE"), primary_key=True)
    earned: Mapped[bool] = mapped_column(Boolean)
    # 0..1 towards a badge not earned yet.
    progress: Mapped[float | None] = mapped_column(Float)

    badge: Mapped[Badge] = relationship(lazy="raise")


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    challenge: Mapped[str] = mapped_column(String(120))
    progress: Mapped[float] = mapped_column(Float)
    goal: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    member_count: Mapped[int] = mapped_column(Integer)


class ClubMembership(Base):
    __tablename__ = "club_memberships"

    club_id: Mapped[str] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), primary_key=True)
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    # Order the rider sees their clubs in.
    position: Mapped[int] = mapped_column(Integer)

    club: Mapped[Club] = relationship(lazy="raise")


class BestWindow(Base):
    """Best time slot today on the rider's usual route, from the hourly forecasts."""

    __tablename__ = "best_windows"

    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(String(80))
    time_window: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text)
    metric: Mapped[ScoreDimension] = mapped_column(str_enum(ScoreDimension))
    score: Mapped[int] = mapped_column(Integer)
