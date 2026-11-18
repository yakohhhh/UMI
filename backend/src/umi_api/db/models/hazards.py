"""Hazards riders flag, and the distinct riders behind each one."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from umi_api.db.base import Base, UtcDateTime, str_enum
from umi_api.domain.enums import ActivityType, CityHazardStatus, ConfirmationSource, HazardKind, HazardStatus

if TYPE_CHECKING:
    from umi_api.db.models.city import District


class Hazard(Base):
    """A place riders flagged, merged within `[reports] hazard_merge_radius_m`.

    A hazard opened by a flag takes that flag's id. Its rider count is never
    stored: it is counted from `hazard_confirmations` whenever it decides what
    gets published (ADR 0006).
    """

    __tablename__ = "hazards"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    # None until a rider says what it was.
    kind: Mapped[HazardKind | None] = mapped_column(str_enum(HazardKind))
    lon: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    street: Mapped[str | None] = mapped_column(String(160))
    district_code: Mapped[str | None] = mapped_column(ForeignKey("districts.code"))
    status: Mapped[HazardStatus] = mapped_column(str_enum(HazardStatus), index=True)
    # Set once the hazard is sent to the city; follows the city's IRIS ticket.
    city_status: Mapped[CityHazardStatus | None] = mapped_column(str_enum(CityHazardStatus))
    first_seen_at: Mapped[datetime] = mapped_column(UtcDateTime)
    last_confirmed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    # Riders whose route or map showed the hazard while it was live.
    riders_warned: Mapped[int] = mapped_column(Integer, default=0)
    # What the sensors saw after a fix or expiry, e.g. "Comfort 52 → 81 since the repair".
    proof: Mapped[str | None] = mapped_column(Text)

    district: Mapped["District | None"] = relationship(lazy="raise")


class HazardConfirmation(Base):
    """One distinct rider who flagged or confirmed a hazard (the latest time counts)."""

    __tablename__ = "hazard_confirmations"
    __table_args__ = (UniqueConstraint("hazard_id", "rider_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hazard_id: Mapped[str] = mapped_column(ForeignKey("hazards.id", ondelete="CASCADE"))
    # Pseudonymous rider key: the athlete id for app riders, an opaque key for
    # bulk-imported panels. Only ever counted, never returned by the API.
    rider_key: Mapped[str] = mapped_column(String(64))
    activity_type: Mapped[ActivityType] = mapped_column(str_enum(ActivityType))
    source: Mapped[ConfirmationSource] = mapped_column(str_enum(ConfirmationSource))
    flag_id: Mapped[str | None] = mapped_column(ForeignKey("flags.id", ondelete="SET NULL"))
    confirmed_at: Mapped[datetime] = mapped_column(UtcDateTime)
