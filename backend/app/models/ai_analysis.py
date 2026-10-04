import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.report import utcnow


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (UniqueConstraint("report_id", "request_id", name="uq_ai_report_request"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("reports.id"), index=True)

    evidence_photo_id: Mapped[str] = mapped_column(String(36))
    photo_sha256: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(36))

    active_report_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    provider: Mapped[str] = mapped_column(String(20))
    is_mock: Mapped[bool] = mapped_column(Boolean)
    input_report_version: Mapped[int] = mapped_column(Integer)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[int] = mapped_column(BigInteger)
    feedback: Mapped[dict | None] = mapped_column(JSON)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    feedback_report_version: Mapped[int | None] = mapped_column(Integer)
