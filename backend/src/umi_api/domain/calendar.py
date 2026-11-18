"""Barcelona time. Instants are UTC everywhere; days, weekdays and clock times are local."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")

# en-GB abbreviations as the web formats them (CLDR writes "Sept").
MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec")
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def local_day(instant: datetime) -> date:
    return instant.astimezone(MADRID).date()


def local_midnight(day: date) -> datetime:
    """The instant a Barcelona day starts, in UTC."""
    return datetime.combine(day, time.min, MADRID).astimezone(UTC)


def local_clock_time(instant: datetime) -> str:
    """HH:mm in Barcelona."""
    return instant.astimezone(MADRID).strftime("%H:%M")


def local_hour(instant: datetime) -> int:
    """0-23 in Barcelona."""
    return instant.astimezone(MADRID).hour


def local_weekday(instant: datetime) -> int:
    """0 = Monday."""
    return instant.astimezone(MADRID).weekday()


def day_month(day: date) -> str:
    """The web's short day label, e.g. "14 Sept"."""
    return f"{day.day} {MONTH_ABBR[day.month - 1]}"


def iso_utc(instant: datetime) -> str:
    """JavaScript's Date.toISOString(): UTC, milliseconds, trailing Z."""
    utc = instant.astimezone(UTC)
    return f"{utc:%Y-%m-%dT%H:%M:%S}.{utc.microsecond // 1000:03d}Z"
