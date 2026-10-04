from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VALUES = {
    "clarity": ("clear", "slightly_cloudy", "cloudy", "opaque", "unknown"),
    "foam": ("none", "small_patches", "extensive", "unknown"),
    "visible_life": ("none_observed", "plants", "animals", "both", "unknown"),
    "water_color": ("colorless", "brown", "green", "black", "other", "unknown"),
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Region(StrictModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def within_image(self):
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("Evidence region must fit within the image")
        return self


class Suggestion(StrictModel):
    field: Literal["clarity", "foam", "visible_life", "water_color"]
    value: str
    explanation: str = Field(min_length=1, max_length=1000)
    evidence_region: Region | None = None

    @model_validator(mode="after")
    def valid_observation(self):
        if self.value not in VALUES[self.field] or not self.explanation.strip():
            raise ValueError("Invalid visual observation")
        return self


class VisionResult(StrictModel):
    image_usable: bool = Field(strict=True)
    limitations: list[str] = Field(min_length=1, max_length=8)
    suggestions: list[Suggestion] = Field(max_length=4)

    @model_validator(mode="after")
    def consistent(self):
        fields = [item.field for item in self.suggestions]
        if len(fields) != len(set(fields)):
            raise ValueError("Duplicate observation field")
        if not self.image_usable and self.suggestions:
            raise ValueError("Unusable images cannot contain suggestions")
        if any(not text.strip() or len(text) > 500 for text in self.limitations):
            raise ValueError("Invalid limitation")
        return self
