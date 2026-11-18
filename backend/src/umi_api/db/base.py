"""Declarative base and the portable column types every model uses.

Only types that behave the same on SQLite and Postgres (ADR 0004): enums are
stored as their string values, JSON is plain JSON, instants are UTC.
"""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Dialect, Enum, MetaData
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

# Deterministic constraint names, so Alembic can alter and drop them on both dialects.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UtcDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC instants on every dialect.

    SQLite has no timezone support and returns naive values; storing naive UTC
    and re-attaching UTC on the way out keeps comparisons and arithmetic exact.
    """

    impl = DateTime(timezone=False)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime: pass an aware (UTC) instant")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


def str_enum[E: StrEnum](enum: type[E]) -> Enum:
    """A StrEnum stored as its value in a VARCHAR (no native enum type to migrate)."""
    return Enum(
        enum,
        native_enum=False,
        create_constraint=False,
        # Room for values added later without a column migration.
        length=32,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
