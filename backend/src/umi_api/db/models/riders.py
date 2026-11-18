"""Per-rider aggregates: daily exposure and planned routes."""

from datetime import date

from sqlalchemy import JSON, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from umi_api.db.base import Base, str_enum
from umi_api.domain.enums import RouteGoal


class ExposureDay(Base):
    __tablename__ = "exposure_days"

    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    # Local (Barcelona) day.
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    ride_min: Mapped[int] = mapped_column(Integer)
    # Ride-weighted means; None on days without a ride.
    pm25: Mapped[float | None] = mapped_column(Float)
    db: Mapped[float | None] = mapped_column(Float)
    dose_ug_h: Mapped[float] = mapped_column(Float)


class ExposureContributor(Base):
    """Streets that contribute most to the rider's PM2.5 dose (last 90 days)."""

    __tablename__ = "exposure_contributors"

    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    street: Mapped[str] = mapped_column(String(120))
    share: Mapped[float] = mapped_column(Float)
    pm25: Mapped[float] = mapped_column(Float)
    minutes_week: Mapped[int] = mapped_column(Integer)


class PlannedRoute(Base):
    """Alternatives for the rider's usual trip, scored at the 08:00 peak."""

    __tablename__ = "planned_routes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    goal: Mapped[RouteGoal] = mapped_column(str_enum(RouteGoal))
    label: Mapped[str] = mapped_column(String(40))
    duration_min: Mapped[int] = mapped_column(Integer)
    distance_m: Mapped[int] = mapped_column(Integer)
    comfort: Mapped[int] = mapped_column(Integer)
    safety: Mapped[int] = mapped_column(Integer)
    air: Mapped[int] = mapped_column(Integer)
    noise: Mapped[int] = mapped_column(Integer)
    via: Mapped[list[str]] = mapped_column(JSON)
    highlight: Mapped[str] = mapped_column(String(160))
    coordinates: Mapped[list[list[float]]] = mapped_column(JSON)
