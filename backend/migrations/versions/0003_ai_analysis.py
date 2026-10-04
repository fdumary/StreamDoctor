"""Persist photo analyses, input evidence, and volunteer decisions."""

import sqlalchemy as sa
from alembic import op

revision = "0003_ai_analysis"
down_revision = "0002_reports"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("evidence_photo_id", sa.String(36), nullable=False),
        sa.Column("photo_sha256", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("active_report_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.Column("input_report_version", sa.Integer(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.BigInteger(), nullable=False),
        sa.Column("feedback", sa.JSON(), nullable=True),
        sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feedback_report_version", sa.Integer(), nullable=True),
        sa.UniqueConstraint("report_id", "request_id", name="uq_ai_report_request"),
        sa.UniqueConstraint("active_report_id", name="uq_ai_analyses_active_report_id"),
    )
    op.create_index("ix_ai_analyses_report_id", "ai_analyses", ["report_id"])


def downgrade():
    op.drop_table("ai_analyses")
