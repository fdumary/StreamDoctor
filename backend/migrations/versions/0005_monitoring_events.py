"""Record reviewer-confirmed monitoring events."""

import sqlalchemy as sa
from alembic import op

revision = "0005_monitoring_events"
down_revision = "0004_trust_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "monitoring_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("stream_sites.id"), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("created_by", "request_id", name="uq_monitoring_request"),
    )
    op.create_index("ix_monitoring_events_site_id", "monitoring_events", ["site_id"])
    op.create_index("ix_monitoring_events_occurred_at", "monitoring_events", ["occurred_at"])


def downgrade():
    op.drop_table("monitoring_events")
