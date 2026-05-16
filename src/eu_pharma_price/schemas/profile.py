"""Data profile schema."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class PlausibilityAssessment(str, Enum):
    plausible = "plausible"
    suspect = "suspect"
    implausible = "implausible"


class DataProfile(BaseModel):
    id: str = Field(description="UUID")
    country_code: str = Field(min_length=2, max_length=2)
    snapshot_date: date
    price_type: str
    field_exists: bool
    population_rate: float = Field(ge=0.0, le=1.0)
    plausibility_assessment: PlausibilityAssessment
    record_count: int = Field(ge=0)
    assessed_at: datetime
    assessed_by: str

    min_value: Decimal | None = None
    max_value: Decimal | None = None
    median_value: Decimal | None = None
    null_count: int | None = None
    outlier_count: int | None = None
    distribution_notes: str | None = None
    comparison_to_prior: str | None = None
    issues: list[str] = Field(default_factory=list)

    @field_validator("assessed_at")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("assessed_at must be timezone-aware UTC")
        return v

    @field_validator("population_rate")
    @classmethod
    def check_field_exists_consistency(cls, v: float, info) -> float:
        if info.data.get("field_exists") is False and v != 0.0:
            raise ValueError("population_rate must be 0.0 when field_exists is False")
        return v
