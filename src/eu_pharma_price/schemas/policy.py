"""Policy interpretation schema."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ComparisonCategory(str, Enum):
    manufacturer_price = "manufacturer_price"
    pharmacy_purchase_price = "pharmacy_purchase_price"
    public_retail_price = "public_retail_price"
    payer_reimbursement_price = "payer_reimbursement_price"


class PolicyInterpretation(BaseModel):
    id: str = Field(description="UUID")
    country_code: str = Field(min_length=2, max_length=2)
    price_type: str
    comparison_category: ComparisonCategory
    effective_from: date
    effective_to: date | None = None
    source_references: list[str] = Field(min_length=1)
    interpretation_text: str
    confidence: Confidence
    authored_at: datetime
    authored_by: str

    superseded_by: str | None = None
    adjudication_notes: str | None = None
    includes_vat: bool | None = None
    includes_margin: str | None = None
    caveats: list[str] = Field(default_factory=list)

    @field_validator("authored_at")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("authored_at must be timezone-aware UTC")
        return v

    @field_validator("source_references")
    @classmethod
    def must_have_sources(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("at least one source reference is required")
        return v
