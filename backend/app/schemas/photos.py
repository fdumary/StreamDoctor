from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class PhotoMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["own", "open_license", "synthetic"] = "own"
    attribution: str | None = Field(default=None, max_length=500)
    license_name: str | None = Field(default=None, max_length=200)
    source_url: HttpUrl | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_credit(self):
        if self.source == "open_license" and not (
            self.attribution
            and self.attribution.strip()
            and self.license_name
            and self.license_name.strip()
            and self.source_url
        ):
            raise ValueError("Open-license photos require attribution, license_name, and source_url")
        return self


class PhotoResponse(BaseModel):
    @field_validator("created_at", mode="before")
    @classmethod
    def utc_timestamp(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    model_config = ConfigDict(from_attributes=True)
    id: str
    report_id: str
    original_sha256: str
    stored_sha256: str
    byte_size: int
    width: int
    height: int
    content_type: str
    source: str
    attribution: str | None
    license_name: str | None
    source_url: str | None
    created_at: datetime
    download_path: str
