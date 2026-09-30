import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class ReportStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str] = mapped_column(String(36), ForeignKey("stream_sites.id"), index=True)
    contributor_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, native_enum=False, create_constraint=True, name="report_status"),
        default=ReportStatus.draft,
        index=True,
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    clarity: Mapped[str | None] = mapped_column(String(30))
    smell: Mapped[str | None] = mapped_column(String(30))
    flow: Mapped[str | None] = mapped_column(String(30))
    foam: Mapped[str | None] = mapped_column(String(30))
    visible_life: Mapped[str | None] = mapped_column(String(30))
    water_color: Mapped[str | None] = mapped_column(String(30))
    ph: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_snapshot: Mapped[dict | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version}
