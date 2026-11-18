"""Districts, the city outline and the City Insights aggregates."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from umi_api.db.base import Base, UtcDateTime, str_enum
from umi_api.domain.enums import KpiDirection


class District(Base):
    __tablename__ = "districts"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    # GeoJSON Polygon or MultiPolygon.
    geometry: Mapped[dict[str, object]] = mapped_column(JSON)

    stats: Mapped["DistrictStats | None"] = relationship(lazy="raise")


class DistrictStats(Base):
    __tablename__ = "district_stats"

    district_code: Mapped[str] = mapped_column(ForeignKey("districts.code", ondelete="CASCADE"), primary_key=True)
    comfort: Mapped[int] = mapped_column(Integer)
    safety: Mapped[int] = mapped_column(Integer)
    air: Mapped[int] = mapped_column(Integer)
    noise: Mapped[int] = mapped_column(Integer)
    surface_index: Mapped[float] = mapped_column(Float)
    rides_week: Mapped[int] = mapped_column(Integer)
    km_measured: Mapped[float] = mapped_column(Float)
    pm25: Mapped[float] = mapped_column(Float)
    db: Mapped[float] = mapped_column(Float)


class CityOutline(Base):
    __tablename__ = "city_outlines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    geometry: Mapped[dict[str, object]] = mapped_column(JSON)


class CityKpi(Base):
    __tablename__ = "city_kpis"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(80))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(24))
    delta: Mapped[float] = mapped_column(Float)
    delta_unit: Mapped[str] = mapped_column(String(8))
    # What the delta compares against, e.g. "vs last winter" (the web defaults to "vs prev.").
    delta_label: Mapped[str | None] = mapped_column(String(40))
    better: Mapped[KpiDirection] = mapped_column(str_enum(KpiDirection))
    # Last 12 weeks, oldest first.
    spark: Mapped[list[float]] = mapped_column(JSON)
    limit_value: Mapped[float | None] = mapped_column(Float)
    limit_label: Mapped[str | None] = mapped_column(String(40))


class CityMonthlyBrakes(Base):
    __tablename__ = "city_monthly_brakes"

    # YYYY-MM
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    hard_brakes: Mapped[int] = mapped_column(Integer)
    rides: Mapped[int] = mapped_column(Integer)


class CityAirNoiseCell(Base):
    __tablename__ = "city_air_noise"

    # 0 = Monday
    weekday: Mapped[int] = mapped_column(Integer, primary_key=True)
    hour: Mapped[int] = mapped_column(Integer, primary_key=True)
    pm25: Mapped[float] = mapped_column(Float)
    db: Mapped[float] = mapped_column(Float)
    rides: Mapped[int] = mapped_column(Integer)


class Snapshot(StrEnum):
    # The rider demo: its "now" is the moment the mock data describes.
    DEMO = "demo"
    # The City Insights aggregates.
    CITY = "city"


class DatasetSnapshot(Base):
    """When a bulk-loaded dataset was generated, and when it was loaded."""

    __tablename__ = "dataset_snapshots"

    name: Mapped[Snapshot] = mapped_column(str_enum(Snapshot), primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(UtcDateTime)
    loaded_at: Mapped[datetime] = mapped_column(UtcDateTime)
