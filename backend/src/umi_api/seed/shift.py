"""Make the demo look recent: dates move by whole weeks, like src/lib/mock/index.ts.

Whole weeks keep weekday patterns intact (Monday commutes stay on Mondays).
"""

from datetime import UTC, date, datetime, time, timedelta

# The moment the mock data describes: Thursday 15 Oct 2026, 19:10 Barcelona (MOCK_ANCHOR).
MOCK_ANCHOR = datetime(2026, 10, 15, 17, 10, tzinfo=UTC)
WEEK = timedelta(weeks=1)


def week_shift(now: datetime) -> timedelta:
    """Whole weeks between the anchor and `now` (never negative)."""
    return max(0, (now - MOCK_ANCHOR) // WEEK) * WEEK


def parse_instant(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def shift_day(day: str, shift: timedelta) -> date:
    """The web's shiftDay(): a YYYY-MM-DD read at noon UTC, moved, cut back to a day."""
    return (datetime.combine(date.fromisoformat(day), time(12), UTC) + shift).date()
