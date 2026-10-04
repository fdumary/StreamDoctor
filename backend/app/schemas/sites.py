from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SiteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    is_demo: bool = False

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value


class SiteResponse(SiteCreate):
    @field_validator("created_at", mode="before")
    @classmethod
    def utc_timestamp(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class SitePage(BaseModel):
    items: list[SiteResponse]
    total: int
    limit: int
    offset: int
