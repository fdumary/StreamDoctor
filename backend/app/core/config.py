from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./streamdoctor.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    session_ttl_minutes: int = Field(default=60, ge=1, le=1440)
    auth_rate_limit: int = Field(default=10, ge=1)
    auth_rate_window_seconds: int = Field(default=60, ge=1)

    upload_dir: Path = Path("storage/photos")
    max_photo_bytes: int = Field(default=8 * 1024 * 1024, ge=1024, le=32 * 1024 * 1024)
    max_stored_photo_bytes: int = Field(default=32 * 1024 * 1024, ge=1024)
    max_photo_pixels: int = Field(default=16_000_000, ge=1, le=40_000_000)
    max_photos_per_report: int = Field(default=5, ge=1, le=10)

    @field_validator("database_url")
    @classmethod
    def database_driver(cls, value: str) -> str:
        if value.startswith(("postgres://", "postgresql://")):
            return "postgresql+psycopg://" + value.split("://", 1)[1]
        if not value.startswith(("postgresql+psycopg://", "sqlite:///")):
            raise ValueError("Use PostgreSQL (psycopg) or SQLite for local development")
        return value

    @field_validator("cors_origins")
    @classmethod
    def explicit_origins(cls, value: list[str]) -> list[str]:
        if any(origin == "*" or not origin.startswith(("http://", "https://")) for origin in value):
            raise ValueError("CORS origins must be explicit HTTP(S) origins")
        return value

    @model_validator(mode="after")
    def production_database(self):
        if self.environment == "production" and self.database_url.startswith("sqlite"):
            raise ValueError("Production requires PostgreSQL")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
