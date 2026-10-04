from datetime import datetime, timezone
from typing import Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.reports import Clarity, Foam, VisibleLife, WaterColor

VisualField = Literal["clarity", "foam", "visible_life", "water_color"]
ALLOWED_VALUES = {
    "clarity": get_args(Clarity),
    "foam": get_args(Foam),
    "visible_life": get_args(VisibleLife),
    "water_color": get_args(WaterColor),
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EvidenceRegion(StrictModel):
    x: float = Field(ge=0, le=1, strict=True)
    y: float = Field(ge=0, le=1, strict=True)
    width: float = Field(gt=0, le=1, strict=True)
    height: float = Field(gt=0, le=1, strict=True)

    @model_validator(mode="after")
    def inside_image(self):
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("Region must fit inside the image")
        return self


class Suggestion(StrictModel):
    field: VisualField
    value: str
    confidence: float | None = Field(default=None, ge=0, le=1, strict=True)
    explanation: str = Field(min_length=1, max_length=1000)
    evidence_region: EvidenceRegion | None = None

    @model_validator(mode="after")
    def validate_value(self):
        if self.value not in ALLOWED_VALUES[self.field]:
            raise ValueError("Suggestion value does not match the field enumeration")
        if not self.explanation.strip():
            raise ValueError("Explanation must not be blank")
        return self


class ProviderResult(StrictModel):
    schema_version: Literal["1.0"]
    model_name: str = Field(min_length=1, max_length=120)
    model_version: str = Field(min_length=1, max_length=120)
    is_mock: bool = Field(strict=True)
    image_usable: bool = Field(strict=True)
    limitations: list[str] = Field(max_length=10)
    suggestions: list[Suggestion] = Field(max_length=4)

    @field_validator("limitations")
    @classmethod
    def limits(cls, values):
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("Each limitation must contain 1–500 characters")
        return values

    @model_validator(mode="after")
    def consistent(self):
        names = [item.field for item in self.suggestions]
        if len(names) != len(set(names)):
            raise ValueError("Each observation field may appear at most once")
        if not self.image_usable and self.suggestions:
            raise ValueError("An unusable image must not produce suggestions")
        if not self.image_usable and not self.limitations:
            raise ValueError("Explain why the image is unusable")
        return self


class AnalysisRequest(StrictModel):
    photo_id: UUID
    request_id: UUID


class FieldDecision(StrictModel):
    field: VisualField
    action: Literal["accept", "edit", "reject"]
    value: str | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def decision_value(self):
        if self.action == "edit":
            if self.value not in ALLOWED_VALUES[self.field]:
                raise ValueError("Edited value must match the field enumeration")
        elif self.value is not None:
            raise ValueError("Only edit decisions may provide a value")
        return self


class FeedbackRequest(StrictModel):
    decisions: list[FieldDecision] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def unique_fields(self):
        names = [item.field for item in self.decisions]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate field decisions are not allowed")
        return self


class AnalysisResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    report_id: str
    evidence_photo_id: str
    photo_sha256: str
    request_id: str
    status: Literal["running", "succeeded", "failed"]
    provider: Literal["mock", "http"]
    is_mock: bool
    input_report_version: int
    input_snapshot: dict
    result: ProviderResult | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    feedback: dict | None
    feedback_at: datetime | None
    feedback_report_version: int | None
    is_stale: bool
    can_decide: bool

    @field_validator("created_at", "completed_at", "feedback_at", mode="before")
    @classmethod
    def utc_timestamp(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class AnalysisPage(StrictModel):
    items: list[AnalysisResponse]
    total: int
    limit: int
    offset: int
