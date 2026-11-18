"""The seeded demo the end-to-end tests run against, and the API's address in-process."""

from datetime import UTC, datetime

from umi_api.seed.shift import MOCK_ANCHOR, week_shift

# The demo is seeded as if today were SEEDED_AT; its "now" is the mocks' moment moved by whole weeks.
SEEDED_AT = datetime(2026, 11, 18, 18, 0, tzinfo=UTC)
DEMO_NOW = MOCK_ANCHOR + week_shift(SEEDED_AT)
API_URL = "http://umi.test"
