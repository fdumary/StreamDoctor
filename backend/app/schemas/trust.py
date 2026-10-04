from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimestampModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", mode="before", check_fields=False)
    @classmethod
    def utc_timestamp(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class Signal(BaseModel):
    available: bool
    score: float | None
    weight: float
    reasons: list[str]
    details: dict


class TrustFlag(BaseModel):
    code: str
    reason: str
    needs_review: bool
    penalty: float


class AssessmentResponse(TimestampModel):
    id: str
    report_id: str
    scoring_version: str
    score: float
    evidence_coverage: float
    requires_review: bool
    auto_eligible: bool
    components: dict[str, Signal]
    flags: list[TrustFlag]
    reasons: list[str]
    policy: dict
    created_at: datetime
    review_status: Literal["pending", "approved", "rejected"]
    expert_verified: bool
    eligible_for_trusted_use: bool
    is_synthetic: bool


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: UUID
    request_id: UUID
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=10, max_length=3000)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Provide a review reason of at least ten characters")
        return value


class ReviewResponse(TimestampModel):
    id: str
    report_id: str
    assessment_id: str
    reviewer_id: str
    request_id: str
    decision: Literal["approved", "rejected"]
    reason: str
    created_at: datetime


class ReviewQueueItem(BaseModel):
    report_id: str
    site_id: str
    assessment_id: str
    score: float
    evidence_coverage: float
    requires_review: bool
    status: Literal["pending", "approved", "rejected"]
    is_synthetic: bool
    reasons: list[str]


class ReviewQueuePage(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    limit: int
    offset: int
