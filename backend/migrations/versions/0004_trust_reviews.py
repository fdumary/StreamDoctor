"""Add explainable assessments and independent expert reviews."""

import sqlalchemy as sa
from alembic import op

revision = "0004_trust_reviews"
down_revision = "0003_ai_analysis"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("scoring_version", sa.String(40), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("evidence_coverage", sa.Float(), nullable=False),
        sa.Column("requires_review", sa.Boolean(), nullable=False),
        sa.Column("auto_eligible", sa.Boolean(), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("report_id", "evidence_digest", name="uq_assessment_evidence"),
    )
    op.create_index("ix_assessments_report_id", "assessments", ["report_id"])
    op.create_table(
        "review_cases",
        sa.Column("report_id", sa.String(36), sa.ForeignKey("reports.id"), primary_key=True),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("assessments.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_review_cases_status", "review_cases", ["status"])
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("assessments.id"), nullable=False),
        sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("report_id", name="uq_reviews_report_id"),
        sa.UniqueConstraint("request_id", name="uq_reviews_request_id"),
    )


def downgrade():
    op.drop_table("reviews")
    op.drop_table("review_cases")
    op.drop_table("assessments")
