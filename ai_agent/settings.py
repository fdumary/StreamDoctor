from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )
    service_token: SecretStr | None = Field(
        default=None, validation_alias="AI_SERVICE_TOKEN"
    )
    api_key: SecretStr | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    model: str = Field(
        default="gemini-3.5-flash-lite",
        pattern=r"^[a-zA-Z0-9._-]+$",
        max_length=100,
        validation_alias="GEMINI_MODEL",
    )
    timeout: float = Field(
        default=20, gt=0, le=90, validation_alias="VISION_TIMEOUT_SECONDS"
    )
    max_photo_bytes: int = 32 * 1024 * 1024
    max_pixels: int = 16_000_000
    max_concurrency: int = Field(default=2, ge=1, le=8)
    cache_ttl_seconds: int = 600
    cache_size: int = 100
