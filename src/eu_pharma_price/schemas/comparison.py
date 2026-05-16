"""Comparison candidate and derivation rule schemas."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class RuleType(str, Enum):
    per_unit = "per_unit"
    vat_exclusive = "vat_exclusive"
    vat_inclusive = "vat_inclusive"
    currency_conversion = "currency_conversion"
    pack_normalisation = "pack_normalisation"


class IdentityConfidence(str, Enum):
    exact = "exact"
    high = "high"
    medium = "medium"
    low = "low"


class DerivationRule(BaseModel):
    id: str = Field(description="UUID")
    rule_type: RuleType
    description: str
    formula: str
    input_fields: list[str] = Field(min_length=1)
    output_field: str
    effective_from: date
    effective_to: date | None = None
    source_reference: str
    created_at: datetime
    created_by: str

    parameters: dict[str, Any] | None = None
    fx_source: str | None = None
    fx_date: date | None = None
    superseded_by: str | None = None
    country_code: str | None = None
    caveats: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def fx_fields_required_for_conversion(self):
        if self.rule_type == RuleType.currency_conversion:
            if not self.fx_source:
                raise ValueError("fx_source required for currency_conversion")
            if not self.fx_date:
                raise ValueError("fx_date required for currency_conversion")
        return self


class ComparisonCandidate(BaseModel):
    id: str = Field(description="UUID")
    molecule_inn: str
    atc_code: str
    strength: str
    dosage_form: str
    country_a_code: str = Field(min_length=2, max_length=2)
    country_b_code: str = Field(min_length=2, max_length=2)
    country_a_record_id: str
    country_b_record_id: str
    country_a_policy_id: str
    country_b_policy_id: str
    country_a_profile_id: str
    country_b_profile_id: str
    comparison_category: str
    snapshot_date: date
    created_at: datetime
    created_by: str

    derivation_rule_a_id: str | None = None
    derivation_rule_b_id: str | None = None
    identity_match_method: str | None = None
    identity_confidence: IdentityConfidence | None = None
    price_ratio: Decimal | None = None
    normalisation_notes: str | None = None
    caveats: list[str] = Field(default_factory=list)

    @field_validator("country_b_code")
    @classmethod
    def no_self_comparison(cls, v: str, info) -> str:
        if info.data.get("country_a_code") == v:
            raise ValueError("cannot compare a country with itself")
        return v
