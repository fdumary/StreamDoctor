from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    kind: Literal["storm"]
    occurred_at: AwareDatetime
    is_synthetic: bool = False

    @field_validator("occurred_at")
    @classmethod
    def valid_time(cls, value):
        if value > datetime.now(timezone.utc) or value < datetime.now(timezone.utc) - timedelta(days=30):
            raise ValueError("Event must have occurred within the last 30 days")
        return value.astimezone(timezone.utc)


class EventResponse(BaseModel):
    id: str
    site_id: str
    kind: Literal["storm"]
    occurred_at: datetime
    is_synthetic: bool
