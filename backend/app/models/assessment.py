import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.report import utcnow


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (UniqueConstraint("report_id", "evidence_digest", name="uq_assessment_evidence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("reports.id"), index=True)
    scoring_version: Mapped[str] = mapped_column(String(40))
    evidence_digest: Mapped[str] = mapped_column(String(64))
    score: Mapped[float] = mapped_column(Float)
    evidence_coverage: Mapped[float] = mapped_column(Float)
    requires_review: Mapped[bool] = mapped_column(Boolean)
    auto_eligible: Mapped[bool] = mapped_column(Boolean)
    components: Mapped[dict] = mapped_column(JSON)
    flags: Mapped[list] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)
    policy: Mapped[dict] = mapped_column(JSON)
    evidence: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
