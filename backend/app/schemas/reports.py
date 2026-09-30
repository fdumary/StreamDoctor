from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.models.report import ReportStatus
from app.schemas.photos import PhotoResponse

Clarity = Literal["clear", "slightly_cloudy", "cloudy", "opaque", "unknown"]
Smell = Literal["none", "earthy", "sewage", "chemical", "other", "unknown"]
Flow = Literal["still", "slow", "moderate", "fast", "dry", "unknown"]
Foam = Literal["none", "small_patches", "extensive", "unknown"]
VisibleLife = Literal["none_observed", "plants", "animals", "both", "unknown"]
WaterColor = Literal["colorless", "brown", "green", "black", "other", "unknown"]


class ObservationFields(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    clarity: Clarity | None = None
    smell: Smell | None = None
    flow: Flow | None = None
    foam: Foam | None = None
    visible_life: VisibleLife | None = None
    water_color: WaterColor | None = None
    # Optional measured value, not inferred from photos. Unusual values remain valid.
    ph: float | None = Field(default=None, ge=0, le=14)
    notes: str = Field(default="", max_length=5000)


class ReportCreate(ObservationFields):
    site_id: UUID
    observed_at: AwareDatetime
    is_synthetic: bool = False

    @field_validator("observed_at")
    @classmethod
    def observation_time(cls, value):
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Observation time cannot be in the future (5 minute clock tolerance)")
        return value.astimezone(timezone.utc)


class ReportPatch(ObservationFields):
    observed_at: AwareDatetime | None = None
    is_synthetic: bool = False

    @field_validator("observed_at")
    @classmethod
    def observation_time(cls, value):
        if value is None:
            raise ValueError("Observation time cannot be null")
        return ReportCreate.observation_time(value)


class ReportSummary(ObservationFields):
    @field_validator("observed_at", "created_at", "updated_at", "submitted_at", mode="before")
    @classmethod
    def utc_timestamp(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    model_config = ConfigDict(from_attributes=True)
    id: str
    site_id: str
    contributor_id: str
    status: ReportStatus
    observed_at: datetime
    is_synthetic: bool
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    version: int


class ReportResponse(ReportSummary):
    photos: list[PhotoResponse]
    submitted_snapshot: dict | None


class ReportPage(BaseModel):
    items: list[ReportSummary]
    total: int
    limit: int
    offset: int
