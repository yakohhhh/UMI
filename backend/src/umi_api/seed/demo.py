"""Demo values the web mocks hard-code in src/lib/api.ts rather than in a JSON file.

The backend stores them in tables (a Clip, a profile, a City API key...), so
they are written here once, next to where the seed reads them.
"""

import math
from datetime import date, timedelta

from umi_api.domain.enums import ScoreDimension
from umi_api.domain.numbers import js_round

LAIA = "laia"
MARC = "marc"
FOLLOWS = ((LAIA, MARC), (MARC, LAIA))

# The demo Clips. Public keys are real P-256 points; seeded flags are unsigned
# (sig_alg none), like devkit builds, so no private key is needed anywhere.
DEVICES = (
    {
        "id": "c10a2b3c4d000412",
        "athlete_id": LAIA,
        "serial": "UMI-C1-0412-BCN",
        "public_key": bytes.fromhex(
            "04ea1c9921869cd5a33cb78a04825ff64c4afe772a97bd37c287b49b0710bc5172"
            "e69f8550d95ec6d196a67f8a8cebf063bc2b2de6e2b835e1e9b0d9ca23759b2a"
        ),
        "firmware": "1.4.2",
        "hw_rev": 1,
        "battery_pct": 82,
        # Laia opted in to voice keywords (off by default on a new Clip).
        "voice_keywords": True,
        "keyword_languages": ["ca", "es", "en"],
        "chirp": True,
        "warn_ahead": True,
    },
    {
        "id": "c10a2b3c4d000733",
        "athlete_id": MARC,
        "serial": "UMI-C1-0733-BCN",
        "public_key": bytes.fromhex(
            "0465ab20b580eb80d4a411051ded302f504d7f59f5a10ec101983f61498e07f870"
            "6323f0dacb11195494ac0283ce53f30432c091c23d66216ba0280faa97842ead"
        ),
        "firmware": "1.4.2",
        "hw_rev": 1,
        "battery_pct": 64,
        "voice_keywords": True,
        "keyword_languages": ["es", "en"],
        "chirp": True,
        "warn_ahead": False,
    },
)
# Laia's Clip synced a few minutes before the demo's "now".
LAST_SYNC_BEFORE_NOW = timedelta(minutes=6)

BEST_WINDOW = {
    "athlete_id": LAIA,
    "title": "Today's best window",
    "time_window": "18:00–19:30",
    "detail": "Cleanest air on your way home: PM2.5 around 9 µg/m³ on Pg. de Sant Joan once the sea breeze sets in.",
    "metric": ScoreDimension.AIR,
    "score": 84,
}

EXPOSURE_CONTRIBUTORS = (
    {"street": "Avinguda Diagonal", "share": 0.36, "pm25": 15.8, "minutes_week": 52},
    {"street": "Passeig de Sant Joan", "share": 0.22, "pm25": 12.9, "minutes_week": 41},
    {"street": "Travessera de Gràcia", "share": 0.17, "pm25": 13.6, "minutes_week": 28},
    {"street": "Carrer de la Llacuna", "share": 0.09, "pm25": 10.4, "minutes_week": 19},
)

PROFILE = {
    "athlete_id": LAIA,
    "member_since": date(2025, 11, 3),
    "distance_km": 1846,
    "rides": 412,
    "runs": 6,
    "hours": 131,
    "streets_mapped": 186,
    "streets_improved": 23,
    "potholes_confirmed": 14,
    "segments_first": 9,
    "streak_days": 9,
    "top_streets": [
        {"name": "Passeig de Sant Joan", "passes": 168},
        {"name": "Avinguda Diagonal", "passes": 151},
        {"name": "Carrer del Consell de Cent", "passes": 77},
        {"name": "Carrer de la Llacuna", "passes": 64},
    ],
    "trust_level": 7,
    "trust_next": "3 more verified flags to reach Street steward",
    "trust_perks": [
        "Passing Clips re-check your flags first, so they're verified sooner",
        "Early access to new keyword languages",
    ],
    # Older flags and answers (before the rides in the feed) count towards the impact totals.
    "earlier_riders_warned": 2140,
    "earlier_verified": 17,
    "earlier_fixed": 2,
    "earlier_causes_given": 41,
}

RECORDS = (
    {
        "id": "longest",
        "label": "Longest ride",
        "value": "38.4 km",
        "detail": "Seafront to Montgat and back",
        "achieved_on": date(2026, 6, 14),
    },
    {
        "id": "calm",
        "label": "Calmest week",
        "value": "Overall 81",
        "detail": "12 rides on green axes",
        "achieved_on": date(2026, 9, 21),
    },
    {
        "id": "fast",
        "label": "Fastest commute",
        "value": "13m 08s",
        "detail": "Gràcia → 22@, Sunday morning",
        "achieved_on": date(2026, 5, 10),
    },
)

# (id, label, description, earned, progress)
BADGES = (
    ("cartographer", "Street cartographer", "Measured 150 different street segments", True, None),
    ("calm", "Calm commuter", "20 commutes with an overall score above 70", True, None),
    ("pothole", "Pothole hunter", "10 of your pothole flags verified by other riders", True, None),
    ("fixed", "Fixed it", "3 of your flags repaired by the city", True, None),
    ("steward", "Street steward", "Trust level 8: clear a hazard on your commute alone", False, 0.7),
    ("early", "Early bird", "Rode before 7:30 on 15 days", True, None),
    ("clean", "Clean air month", "A month under 10 µg/m³ average", False, 0.62),
    ("century", "2,000 km", "Ride 2,000 km with UMI", False, 0.92),
)

CLUBS = (
    {
        "id": "gracia",
        "name": "Gràcia Riders",
        "challenge": "October distance",
        "progress": 1240,
        "goal": 2000,
        "unit": "km",
        "member_count": 86,
    },
    {
        "id": "calm",
        "name": "Calm Commute Challenge",
        "challenge": "Rides scoring 70+ overall",
        "progress": 12,
        "goal": 20,
        "unit": "rides",
        "member_count": 412,
    },
    {
        "id": "22",
        "name": "22@ Bike to Work",
        "challenge": "Office rides this week",
        "progress": 318,
        "goal": 400,
        "unit": "rides",
        "member_count": 204,
    },
)

CITY_ACCOUNT = "ajuntament-bcn"
API_KEY = {
    "id": "bcn-pilot",
    "account": CITY_ACCOUNT,
    "token": "umi_live_bcn_9f2c4e7a1d6b8e03c5a7",
    "plan": "City pilot · Ajuntament de Barcelona",
    "rate_limit_per_s": 20,
    "monthly_quota": 250_000,
}
# Calls before the 14 days the console charts.
EARLIER_CALLS = 41_280


def daily_calls(index: int, day: date) -> int:
    """Synthetic City API traffic for the 14-day chart (index 0 = oldest day)."""
    weekend = day.weekday() >= 5
    return js_round((2100 if weekend else 5400) + math.sin(index * 1.7) * 900 + index * 60)
