from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Status = Literal["green", "yellow", "red", "unknown"]


class Indicator(BaseModel):
    code: str
    reason: str
    severity: Literal["yellow", "red"]
    reports: int


class Verdict(BaseModel):
    status: Status
    label: str
    submitted_reports: int
    eligible_reports: int
    contributing_reports: int
    independent_contributors: int
    excluded_by_trust: int
    excluded_repeats: int
    excluded_incomplete: int
    latest_observation_at: datetime | None
    mean_trust_score: float | None
    indicators: list[Indicator]
    limitations: list[str]


class Trend(BaseModel):
    previous_status: Status
    direction: Literal["improving", "worsening", "unchanged", "insufficient_data"]


class AudienceSummary(BaseModel):
    summary: str
    actions: list[str]


class Diagnosis(BaseModel):
    site_id: str
    site_name: str
    is_synthetic: bool
    policy_version: str
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    trusted: Verdict
    unfiltered: Verdict
    trust_lens_changed: bool
    trend: Trend
    audiences: dict[str, AudienceSummary]
    possible_explanations: list[str]


class MonitoringNeed(BaseModel):
    code: str
    priority: Literal["high", "normal"]
    reason: str
    requested_fields: list[str]


class MonitoringNeeds(BaseModel):
    site_id: str
    is_synthetic: bool
    generated_at: datetime
    needs: list[MonitoringNeed]
