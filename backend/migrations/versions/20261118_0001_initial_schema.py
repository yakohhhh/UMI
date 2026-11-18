"""Initial schema: riders and Clips, activities and what happened during them, hazards,
the scored street network, City Insights aggregates and City API keys.

Hand-checked after autogenerate: instants are naive UTC DATETIME/TIMESTAMP columns
(the models' UtcDateTime), enums are VARCHAR(32) without a native type, JSON is plain JSON,
so the same revision runs on SQLite and Postgres.

Revision ID: 0001
Revises:
Create Date: 2026-11-18 11:27:30.522828+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("account", sa.String(length=64), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("plan", sa.String(length=120), nullable=False),
        sa.Column("rate_limit_per_s", sa.Integer(), nullable=False),
        sa.Column("monthly_quota", sa.Integer(), nullable=False),
        sa.Column("quota_used", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
        sa.UniqueConstraint("token", name=op.f("uq_api_keys_token")),
    )
    op.create_index(op.f("ix_api_keys_account"), "api_keys", ["account"], unique=False)
    op.create_table(
        "athletes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("first_name", sa.String(length=60), nullable=False),
        sa.Column("initials", sa.String(length=4), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("vehicle", sa.String(length=40), nullable=False),
        sa.Column("weekly_goal_km", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_athletes")),
    )
    op.create_table(
        "badges",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=160), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_badges")),
    )
    op.create_table(
        "city_air_noise",
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("pm25", sa.Float(), nullable=False),
        sa.Column("db", sa.Float(), nullable=False),
        sa.Column("rides", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("weekday", "hour", name=op.f("pk_city_air_noise")),
    )
    op.create_table(
        "city_kpis",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
        sa.Column("delta_unit", sa.String(length=8), nullable=False),
        sa.Column("delta_label", sa.String(length=40), nullable=True),
        sa.Column("better", sa.Enum("up", "down", name="kpidirection", native_enum=False, length=32), nullable=False),
        sa.Column("spark", sa.JSON(), nullable=False),
        sa.Column("limit_value", sa.Float(), nullable=True),
        sa.Column("limit_label", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_city_kpis")),
    )
    op.create_table(
        "city_monthly_brakes",
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("hard_brakes", sa.Integer(), nullable=False),
        sa.Column("rides", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("month", name=op.f("pk_city_monthly_brakes")),
    )
    op.create_table(
        "city_outlines",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("geometry", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_city_outlines")),
    )
    op.create_table(
        "clubs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("challenge", sa.String(length=120), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("goal", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clubs")),
    )
    op.create_table(
        "dataset_snapshots",
        sa.Column("name", sa.Enum("demo", "city", name="snapshot", native_enum=False, length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_dataset_snapshots")),
    )
    op.create_table(
        "districts",
        sa.Column("code", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("geometry", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_districts")),
        sa.UniqueConstraint("name", name=op.f("uq_districts_name")),
    )
    op.create_table(
        "api_usage_days",
        sa.Column("api_key_id", sa.String(length=32), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["api_key_id"], ["api_keys.id"], name=op.f("fk_api_usage_days_api_key_id_api_keys"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("api_key_id", "day", name=op.f("pk_api_usage_days")),
    )
    op.create_table(
        "athlete_badges",
        sa.Column("athlete_id", sa.String(length=64), nullable=False),
        sa.Column("badge_id", sa.String(length=32), nullable=False),
        sa.Column("earned", sa.Boolean(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["athlete_id"], ["athletes.id"], name=op.f("fk_athlete_badges_athlete_id_athletes"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["badge_id"], ["badges.id"], name=op.f("fk_athlete_badges_badge_id_badges"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("athlete_id", "badge_id", name=op.f("pk_athlete_badges")),
    )
    op.create_table(
        "athlete_profiles",
        sa.Column("athlete_id", sa.String(length=64), nullable=False),
        sa.Column("member_since", sa.Date(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("rides", sa.Integer(), nullable=False),
        sa.Column("runs", sa.Integer(), nullable=False),
        sa.Column("hours", sa.Integer(), nullable=False),
        sa.Column("streets_mapped", sa.Integer(), nullable=False),
        sa.Column("streets_improved", sa.Integer(), nullable=False),
        sa.Column("potholes_confirmed", sa.Integer(), nullable=False),
        sa.Column("segments_first", sa.Integer(), nullable=False),
        sa.Column("streak_days", sa.Integer(), nullable=False),
        sa.Column("top_streets", sa.JSON(), nullable=False),
        sa.Column("trust_level", sa.Integer(), nullable=False),
        sa.Column("trust_next", sa.Text(), nullable=False),
        sa.Column("trust_perks", sa.JSON(), nullable=False),
        sa.Column("earlier_riders_warned", sa.Integer(), nullable=False),
        sa.Column("earlier_verified", sa.Integer(), nullable=False),
        sa.Column("earlier_fixed", sa.Integer(), nullable=False),
        sa.Column("earlier_causes_given", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["athlete_id"], ["athletes.id"], name=op.f("fk_athlete_profiles_athlete_id_athletes"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("athlete_id", name=op.f("pk_athlete_profiles")),
    )
    op.create_table(
        "athlete_records",
        sa.Column("athlete_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("value", sa.String(length=60), nullable=False),
        sa.Column("detail", sa.String(length=160), nullable=False),
        sa.Column("achieved_on", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["athlete_id"], ["athletes.id"], name=op.f("fk_athlete_records_athlete_id_athletes"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("athlete_id", "id", name=op.f("pk_athlete_records")),
    )
    op.create_table(
        "best_windows",
        sa.Column("athlete_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("time_window", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column(
            "metric",
            sa.Enum("comfort", "safety", "air", "noise", name="scoredimension", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["athlete_id"], ["athletes.id"], name=op.f("fk_best_windows_athlete_id_athletes"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("athlete_id", name=op.f("pk_best_windows")),
    )
    op.create_table(
        "brake_hotspots",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("district_code", sa.String(length=2), nullable=True),
        sa.Column("hard_brakes_week", sa.Integer(), nullable=False),
        sa.Column("hard_brakes_30d", sa.Integer(), nullable=False),
        sa.Column("peak_hour", sa.Integer(), nullable=False),
        sa.Column("trend", sa.Float(), nullable=False),
        sa.Column("avg_decel", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["district_code"], ["districts.code"], name=op.f("fk_brake_hotspots_district_code_districts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brake_hotspots")),
    )
    op.create_table(
        "club_memberships",
        sa.Column("club_id", sa.String(length=32), nullable=False),
        sa.Column("athlete_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["athlete_id"], ["athletes.id"], name=op.f("fk_club_memberships_athlete_id_athletes"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["club_id"], ["clubs.id"], name=op.f("fk_club_memberships_club_id_clubs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("club_id", "athlete_id", name=op.f("pk_club_memberships")),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("athlete_id", sa.String(length=64), nullable=True),
        sa.Column("paired_at", sa.DateTime(), nullable=True),
        sa.Column("public_key", sa.LargeBinary(length=65), nullable=False),
        sa.Column("serial", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("hw_rev", sa.Integer(), nullable=False),
        sa.Column("firmware", sa.String(length=16), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column("battery_pct", sa.Integer(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("voice_keywords", sa.Boolean(), nullable=False),
        sa.Column("keyword_languages", sa.JSON(), nullable=False),
        sa.Column("chirp", sa.Boolean(), nullable=False),
        sa.Column("warn_ahead", sa.Boolean(), nullable=False),
        sa.Column("disabled_sensors", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["athlete_id"], ["athletes.id"], name=op.f("fk_devices_athlete_id_athletes"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        sa.UniqueConstraint("serial", name=op.f("uq_devices_serial")),
    )
    op.create_index(op.f("ix_devices_athlete_id"), "devices", ["athlete_id"], unique=False)
    op.create_table(
        "district_stats",
        sa.Column("district_code", sa.String(length=2), nullable=False),
        sa.Column("comfort", sa.Integer(), nullable=False),
        sa.Column("safety", sa.Integer(), nullable=False),
        sa.Column("air", sa.Integer(), nullable=False),
        sa.Column("noise", sa.Integer(), nullable=False),
        sa.Column("surface_index", sa.Float(), nullable=False),
        sa.Column("rides_week", sa.Integer(), nullable=False),
        sa.Column("km_measured", sa.Float(), nullable=False),
        sa.Column("pm25", sa.Float(), nullable=False),
        sa.Column("db", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["district_code"],
            ["districts.code"],
            name=op.f("fk_district_stats_district_code_districts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("district_code", name=op.f("pk_district_stats")),
    )
    op.create_table(
        "exposure_contributors",
        sa.Column("athlete_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("street", sa.String(length=120), nullable=False),
        sa.Column("share", sa.Float(), nullable=False),
        sa.Column("pm25", sa.Float(), nullable=False),
        sa.Column("minutes_week", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_exposure_contributors_athlete_id_athletes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("athlete_id", "position", name=op.f("pk_exposure_contributors")),
    )
    op.create_table(
        "exposure_days",
        sa.Column("athlete_id", sa.String(length=64), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("ride_min", sa.Integer(), nullable=False),
        sa.Column("pm25", sa.Float(), nullable=True),
        sa.Column("db", sa.Float(), nullable=True),
        sa.Column("dose_ug_h", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["athlete_id"], ["athletes.id"], name=op.f("fk_exposure_days_athlete_id_athletes"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("athlete_id", "day", name=op.f("pk_exposure_days")),
    )
    op.create_table(
        "follows",
        sa.Column("follower_id", sa.String(length=64), nullable=False),
        sa.Column("followee_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["followee_id"], ["athletes.id"], name=op.f("fk_follows_followee_id_athletes"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["follower_id"], ["athletes.id"], name=op.f("fk_follows_follower_id_athletes"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("follower_id", "followee_id", name=op.f("pk_follows")),
    )
    op.create_table(
        "hazards",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "roadworks",
                "pothole",
                "blocked_lane",
                "obstacle",
                "danger",
                name="hazardkind",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("street", sa.String(length=160), nullable=True),
        sa.Column("district_code", sa.String(length=2), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "verified",
                "sent_to_city",
                "fixed",
                "expired",
                name="hazardstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "city_status",
            sa.Enum("new", "sent_to_iris", "scheduled", "fixed", name="cityhazardstatus", native_enum=False, length=32),
            nullable=True,
        ),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_confirmed_at", sa.DateTime(), nullable=False),
        sa.Column("riders_warned", sa.Integer(), nullable=False),
        sa.Column("proof", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["district_code"], ["districts.code"], name=op.f("fk_hazards_district_code_districts")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hazards")),
    )
    op.create_index(op.f("ix_hazards_status"), "hazards", ["status"], unique=False)
    op.create_table(
        "planned_routes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("athlete_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "goal",
            sa.Enum("fastest", "calmest", "cleanest", name="routegoal", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("comfort", sa.Integer(), nullable=False),
        sa.Column("safety", sa.Integer(), nullable=False),
        sa.Column("air", sa.Integer(), nullable=False),
        sa.Column("noise", sa.Integer(), nullable=False),
        sa.Column("via", sa.JSON(), nullable=False),
        sa.Column("highlight", sa.String(length=160), nullable=False),
        sa.Column("coordinates", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["athlete_id"], ["athletes.id"], name=op.f("fk_planned_routes_athlete_id_athletes"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planned_routes")),
    )
    op.create_index(op.f("ix_planned_routes_athlete_id"), "planned_routes", ["athlete_id"], unique=False)
    op.create_table(
        "street_segments",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("from_name", sa.String(length=120), nullable=True),
        sa.Column("to_name", sa.String(length=120), nullable=True),
        sa.Column("district_code", sa.String(length=2), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "arterial",
                "boulevard",
                "street",
                "green",
                "promenade",
                "seafront",
                name="streetkind",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("bike_lane", sa.Boolean(), nullable=False),
        sa.Column("length_m", sa.Integer(), nullable=False),
        sa.Column("coordinates", sa.JSON(), nullable=False),
        sa.Column("comfort", sa.Integer(), nullable=False),
        sa.Column("safety", sa.Integer(), nullable=False),
        sa.Column("air", sa.Integer(), nullable=False),
        sa.Column("noise", sa.Integer(), nullable=False),
        sa.Column("passes_30d", sa.Integer(), nullable=False),
        sa.Column("trend", sa.Float(), nullable=False),
        sa.Column("vib_rms", sa.Float(), nullable=False),
        sa.Column("pm25", sa.Float(), nullable=False),
        sa.Column("db", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["district_code"], ["districts.code"], name=op.f("fk_street_segments_district_code_districts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_street_segments")),
    )
    op.create_index(op.f("ix_street_segments_district_code"), "street_segments", ["district_code"], unique=False)
    op.create_table(
        "activities",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("athlete_id", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(length=16), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.Enum("ride", "run", name="activitytype", native_enum=False, length=32), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("place", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("moving_time_s", sa.Integer(), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("avg_speed_kmh", sa.Float(), nullable=False),
        sa.Column("max_speed_kmh", sa.Float(), nullable=False),
        sa.Column("elevation_gain_m", sa.Integer(), nullable=False),
        sa.Column("comfort", sa.Integer(), nullable=False),
        sa.Column("safety", sa.Integer(), nullable=False),
        sa.Column("air", sa.Integer(), nullable=False),
        sa.Column("noise", sa.Integer(), nullable=False),
        sa.Column("preview", sa.JSON(), nullable=False),
        sa.Column("kudos", sa.Integer(), nullable=False),
        sa.Column("kudoed_by", sa.JSON(), nullable=False),
        sa.Column("comments", sa.Integer(), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("weather_temp_c", sa.Float(), nullable=False),
        sa.Column("weather_condition", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(
            ["athlete_id"], ["athletes.id"], name=op.f("fk_activities_athlete_id_athletes"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name=op.f("fk_activities_device_id_devices"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activities")),
        sa.UniqueConstraint("device_id", "session_id", name=op.f("uq_activities_device_id_session_id")),
    )
    op.create_index(op.f("ix_activities_athlete_id"), "activities", ["athlete_id"], unique=False)
    op.create_index(op.f("ix_activities_started_at"), "activities", ["started_at"], unique=False)
    op.create_table(
        "potholes",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("segment_id", sa.String(length=16), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("confirmations", sa.Integer(), nullable=False),
        sa.Column("first_seen", sa.Date(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("low", "medium", "high", name="potholeseverity", native_enum=False, length=32),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["segment_id"],
            ["street_segments.id"],
            name=op.f("fk_potholes_segment_id_street_segments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_potholes")),
    )
    op.create_index(op.f("ix_potholes_segment_id"), "potholes", ["segment_id"], unique=False)
    op.create_table(
        "segment_hourly_scores",
        sa.Column("segment_id", sa.String(length=16), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("comfort", sa.Integer(), nullable=False),
        sa.Column("safety", sa.Integer(), nullable=False),
        sa.Column("air", sa.Integer(), nullable=False),
        sa.Column("noise", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["segment_id"],
            ["street_segments.id"],
            name=op.f("fk_segment_hourly_scores_segment_id_street_segments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("segment_id", "hour", name=op.f("pk_segment_hourly_scores")),
    )
    op.create_table(
        "segment_surface_stats",
        sa.Column("segment_id", sa.String(length=16), nullable=False),
        sa.Column("surface_index", sa.Float(), nullable=False),
        sa.Column("confirmed_impacts", sa.Integer(), nullable=False),
        sa.Column("riders_30d", sa.Integer(), nullable=False),
        sa.Column("trend", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["segment_id"],
            ["street_segments.id"],
            name=op.f("fk_segment_surface_stats_segment_id_street_segments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("segment_id", name=op.f("pk_segment_surface_stats")),
    )
    op.create_table(
        "activity_details",
        sa.Column("activity_id", sa.String(length=64), nullable=False),
        sa.Column("route", sa.JSON(), nullable=False),
        sa.Column("samples", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            name=op.f("fk_activity_details_activity_id_activities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("activity_id", name=op.f("pk_activity_details")),
    )
    op.create_table(
        "activity_segments",
        sa.Column("activity_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.String(length=16), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("street_average", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            name=op.f("fk_activity_segments_activity_id_activities"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["segment_id"], ["street_segments.id"], name=op.f("fk_activity_segments_segment_id_street_segments")
        ),
        sa.PrimaryKeyConstraint("activity_id", "position", name=op.f("pk_activity_segments")),
    )
    op.create_index(op.f("ix_activity_segments_segment_id"), "activity_segments", ["segment_id"], unique=False)
    op.create_table(
        "flags",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("activity_id", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(length=16), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("sample_index", sa.Integer(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("pressed_at", sa.DateTime(), nullable=False),
        sa.Column("street", sa.String(length=160), nullable=True),
        sa.Column("source", sa.Enum("press", "voice", name="flagsource", native_enum=False, length=32), nullable=False),
        sa.Column(
            "keyword_kind",
            sa.Enum(
                "roadworks",
                "pothole",
                "blocked_lane",
                "obstacle",
                "danger",
                name="hazardkind",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("keyword_confidence", sa.Integer(), nullable=True),
        sa.Column("lang", sa.String(length=2), nullable=True),
        sa.Column(
            "answered_kind",
            sa.Enum(
                "roadworks",
                "pothole",
                "blocked_lane",
                "obstacle",
                "danger",
                name="hazardkind",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("kind_answered_at", sa.DateTime(), nullable=True),
        sa.Column("speed_kmh", sa.Float(), nullable=True),
        sa.Column("vib_rms", sa.Float(), nullable=True),
        sa.Column("noise_db", sa.Float(), nullable=True),
        sa.Column("sig_alg", sa.Integer(), nullable=False),
        sa.Column("signature", sa.LargeBinary(length=64), nullable=True),
        sa.Column("hazard_id", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["activity_id"], ["activities.id"], name=op.f("fk_flags_activity_id_activities"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name=op.f("fk_flags_device_id_devices"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["hazard_id"], ["hazards.id"], name=op.f("fk_flags_hazard_id_hazards"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flags")),
        sa.UniqueConstraint("device_id", "session_id", "seq", name=op.f("uq_flags_device_id_session_id_seq")),
    )
    op.create_index(op.f("ix_flags_activity_id"), "flags", ["activity_id"], unique=False)
    op.create_index(op.f("ix_flags_hazard_id"), "flags", ["hazard_id"], unique=False)
    op.create_table(
        "ride_events",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("activity_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "hard_brake", "pothole", "pm_spike", "noise_peak", name="rideeventtype", native_enum=False, length=32
            ),
            nullable=False,
        ),
        sa.Column("sample_index", sa.Integer(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("peak", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("street", sa.String(length=160), nullable=True),
        sa.Column("ask", sa.Boolean(), nullable=False),
        sa.Column(
            "cause",
            sa.Enum(
                "pedestrian",
                "animal",
                "vehicle",
                "car_door",
                "lane_blocked",
                "surface",
                "roadworks",
                "junction",
                "just_me",
                name="brakecause",
                native_enum=False,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("cause_answered_at", sa.DateTime(), nullable=True),
        sa.Column("hotspot_id", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["activity_id"], ["activities.id"], name=op.f("fk_ride_events_activity_id_activities"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["hotspot_id"],
            ["brake_hotspots.id"],
            name=op.f("fk_ride_events_hotspot_id_brake_hotspots"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ride_events")),
        sa.UniqueConstraint("activity_id", "position", name=op.f("uq_ride_events_activity_id_position")),
    )
    op.create_index(op.f("ix_ride_events_hotspot_id"), "ride_events", ["hotspot_id"], unique=False)
    op.create_table(
        "segment_passes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.String(length=64), nullable=False),
        sa.Column("segment_id", sa.String(length=16), nullable=False),
        sa.Column("athlete_id", sa.String(length=64), nullable=False),
        sa.Column(
            "activity_type", sa.Enum("ride", "run", name="activitytype", native_enum=False, length=32), nullable=False
        ),
        sa.Column("hour_start", sa.DateTime(), nullable=False),
        sa.Column("vib_rms", sa.Float(), nullable=True),
        sa.Column("pm25", sa.Float(), nullable=True),
        sa.Column("db", sa.Float(), nullable=True),
        sa.Column("hard_brakes", sa.Integer(), nullable=False),
        sa.Column("weighted_brakes", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            name=op.f("fk_segment_passes_activity_id_activities"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"], ["athletes.id"], name=op.f("fk_segment_passes_athlete_id_athletes"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["segment_id"], ["street_segments.id"], name=op.f("fk_segment_passes_segment_id_street_segments")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_segment_passes")),
        sa.UniqueConstraint(
            "activity_id", "segment_id", "hour_start", name=op.f("uq_segment_passes_activity_id_segment_id_hour_start")
        ),
    )
    op.create_index("ix_segment_passes_segment_hour", "segment_passes", ["segment_id", "hour_start"], unique=False)
    op.create_table(
        "hazard_confirmations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hazard_id", sa.String(length=80), nullable=False),
        sa.Column("rider_key", sa.String(length=64), nullable=False),
        sa.Column(
            "activity_type", sa.Enum("ride", "run", name="activitytype", native_enum=False, length=32), nullable=False
        ),
        sa.Column(
            "source", sa.Enum("flag", "sensor", name="confirmationsource", native_enum=False, length=32), nullable=False
        ),
        sa.Column("flag_id", sa.String(length=80), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["flag_id"], ["flags.id"], name=op.f("fk_hazard_confirmations_flag_id_flags"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["hazard_id"], ["hazards.id"], name=op.f("fk_hazard_confirmations_hazard_id_hazards"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hazard_confirmations")),
        sa.UniqueConstraint("hazard_id", "rider_key", name=op.f("uq_hazard_confirmations_hazard_id_rider_key")),
    )
    op.create_table(
        "hotspot_cause_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hotspot_id", sa.String(length=32), nullable=False),
        sa.Column("rider_key", sa.String(length=64), nullable=False),
        sa.Column(
            "activity_type", sa.Enum("ride", "run", name="activitytype", native_enum=False, length=32), nullable=False
        ),
        sa.Column(
            "cause",
            sa.Enum(
                "pedestrian",
                "animal",
                "vehicle",
                "car_door",
                "lane_blocked",
                "surface",
                "roadworks",
                "junction",
                "just_me",
                name="brakecause",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
        sa.Column("ride_event_id", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["hotspot_id"],
            ["brake_hotspots.id"],
            name=op.f("fk_hotspot_cause_answers_hotspot_id_brake_hotspots"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ride_event_id"],
            ["ride_events.id"],
            name=op.f("fk_hotspot_cause_answers_ride_event_id_ride_events"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hotspot_cause_answers")),
        sa.UniqueConstraint("ride_event_id", name=op.f("uq_hotspot_cause_answers_ride_event_id")),
    )
    op.create_index(
        "ix_hotspot_cause_answers_hotspot_time", "hotspot_cause_answers", ["hotspot_id", "answered_at"], unique=False
    )


def downgrade() -> None:
    op.drop_table("hotspot_cause_answers")
    op.drop_table("hazard_confirmations")
    op.drop_table("segment_passes")
    op.drop_table("ride_events")
    op.drop_table("flags")
    op.drop_table("activity_segments")
    op.drop_table("activity_details")
    op.drop_table("segment_surface_stats")
    op.drop_table("segment_hourly_scores")
    op.drop_table("potholes")
    op.drop_table("activities")
    op.drop_table("street_segments")
    op.drop_table("planned_routes")
    op.drop_table("hazards")
    op.drop_table("follows")
    op.drop_table("exposure_days")
    op.drop_table("exposure_contributors")
    op.drop_table("district_stats")
    op.drop_table("devices")
    op.drop_table("club_memberships")
    op.drop_table("brake_hotspots")
    op.drop_table("best_windows")
    op.drop_table("athlete_records")
    op.drop_table("athlete_profiles")
    op.drop_table("athlete_badges")
    op.drop_table("api_usage_days")
    op.drop_table("districts")
    op.drop_table("dataset_snapshots")
    op.drop_table("clubs")
    op.drop_table("city_outlines")
    op.drop_table("city_monthly_brakes")
    op.drop_table("city_kpis")
    op.drop_table("city_air_noise")
    op.drop_table("badges")
    op.drop_table("athletes")
    op.drop_table("api_keys")
