"""Session ingest: upload receipts, the street scores' seeded baseline, and the street
pass each ride event counts in.

Until now `segment_hourly_scores` only ever held the seeded values, so they become the
baseline that `umi-api aggregate` merges riders' passes into.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-18 12:23:51.466510+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "segment_hourly_baselines",
        sa.Column("segment_id", sa.String(length=16), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("comfort", sa.Integer(), nullable=False),
        sa.Column("safety", sa.Integer(), nullable=False),
        sa.Column("air", sa.Integer(), nullable=False),
        sa.Column("noise", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["segment_id"],
            ["street_segments.id"],
            name=op.f("fk_segment_hourly_baselines_segment_id_street_segments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("segment_id", "hour", name=op.f("pk_segment_hourly_baselines")),
    )
    op.execute(
        "INSERT INTO segment_hourly_baselines (segment_id, hour, comfort, safety, air, noise) "
        "SELECT segment_id, hour, comfort, safety, air, noise FROM segment_hourly_scores"
    )
    op.create_table(
        "session_uploads",
        sa.Column("activity_id", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("segments_matched", sa.Integer(), nullable=False),
        sa.Column("events", sa.Integer(), nullable=False),
        sa.Column("flags_accepted", sa.Integer(), nullable=False),
        sa.Column("flags_rejected", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            name=op.f("fk_session_uploads_activity_id_activities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("activity_id", name=op.f("pk_session_uploads")),
    )
    with op.batch_alter_table("ride_events") as batch_op:
        batch_op.add_column(sa.Column("segment_pass_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_ride_events_segment_pass_id_segment_passes"),
            "segment_passes",
            ["segment_pass_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("ride_events") as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_ride_events_segment_pass_id_segment_passes"), type_="foreignkey")
        batch_op.drop_column("segment_pass_id")
    op.drop_table("session_uploads")
    op.drop_table("segment_hourly_baselines")
