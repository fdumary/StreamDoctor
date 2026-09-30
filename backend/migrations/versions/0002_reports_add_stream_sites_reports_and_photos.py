"""Add stream sites reports and photos
Revision ID: 0002_reports
Revises: 0001_accounts
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_reports"
down_revision = "0001_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stream_sites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name=op.f("ck_stream_sites_latitude_range")),
        sa.CheckConstraint(
            "longitude >= -180 AND longitude <= 180", name=op.f("ck_stream_sites_longitude_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stream_sites")),
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=False),
        sa.Column("contributor_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "submitted", name="report_status", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clarity", sa.String(length=30), nullable=True),
        sa.Column("smell", sa.String(length=30), nullable=True),
        sa.Column("flow", sa.String(length=30), nullable=True),
        sa.Column("foam", sa.String(length=30), nullable=True),
        sa.Column("visible_life", sa.String(length=30), nullable=True),
        sa.Column("water_color", sa.String(length=30), nullable=True),
        sa.Column("ph", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_snapshot", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contributor_id"], ["users.id"], name=op.f("fk_reports_contributor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["stream_sites.id"], name=op.f("fk_reports_site_id_stream_sites")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_reports_contributor_id"), ["contributor_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_reports_observed_at"), ["observed_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_reports_site_id"), ["site_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_reports_status"), ["status"], unique=False)

    op.create_table(
        "photos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("original_sha256", sa.String(length=64), nullable=False),
        sa.Column("stored_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("attribution", sa.String(length=500), nullable=True),
        sa.Column("license_name", sa.String(length=200), nullable=True),
        sa.Column("source_url", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], name=op.f("fk_photos_report_id_reports")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_photos")),
        sa.UniqueConstraint("report_id", "original_sha256", name="uq_photos_report_original"),
        sa.UniqueConstraint("storage_key", name=op.f("uq_photos_storage_key")),
    )
    with op.batch_alter_table("photos", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_photos_original_sha256"), ["original_sha256"], unique=False)
        batch_op.create_index(batch_op.f("ix_photos_report_id"), ["report_id"], unique=False)


def downgrade():
    with op.batch_alter_table("photos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_photos_report_id"))
        batch_op.drop_index(batch_op.f("ix_photos_original_sha256"))

    op.drop_table("photos")
    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reports_status"))
        batch_op.drop_index(batch_op.f("ix_reports_site_id"))
        batch_op.drop_index(batch_op.f("ix_reports_observed_at"))
        batch_op.drop_index(batch_op.f("ix_reports_contributor_id"))

    op.drop_table("reports")
    op.drop_table("stream_sites")
