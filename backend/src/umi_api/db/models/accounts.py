"""City API keys and their usage."""

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from umi_api.db.base import Base, UtcDateTime


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # City Insights account (an organisation, not a rider).
    account: Mapped[str] = mapped_column(String(64), index=True)
    # Shown in full in the console (reveal / copy). Hashing at rest is a follow-up.
    token: Mapped[str] = mapped_column(String(64), unique=True)
    plan: Mapped[str] = mapped_column(String(120))
    rate_limit_per_s: Mapped[int] = mapped_column(Integer)
    monthly_quota: Mapped[int] = mapped_column(Integer)
    # Calls counted against the quota since the last monthly reset.
    quota_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class ApiUsageDay(Base):
    __tablename__ = "api_usage_days"

    api_key_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id", ondelete="CASCADE"), primary_key=True)
    # UTC day.
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    calls: Mapped[int] = mapped_column(Integer)
