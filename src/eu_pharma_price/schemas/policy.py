"""Policy interpretation schema."""

from datetime import date, datetime
from enum import Enum

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ComparisonCategory(str, Enum):
    manufacturer_price = "manufacturer_price"
    pharmacy_purchase_price = "pharmacy_purchase_price"
    public_retail_price = "public_retail_price"
    payer_reimbursement_price = "payer_reimbursement_price"


class VatPosition(str, Enum):
    vat_inclusive = "vat_inclusive"
    vat_exclusive = "vat_exclusive"
    vat_unknown = "vat_unknown"


class MarginPosition(str, Enum):
    no_standard_margins = "no_standard_margins"
    wholesale_margin = "wholesale_margin"
    wholesale_and_pharmacy_margins = "wholesale_and_pharmacy_margins"
    public_retail_components = "public_retail_components"
    vat_only = "vat_only"
    margin_unknown = "margin_unknown"


class DerivationKind(str, Enum):
    observed = "observed"
    derived = "derived"
    unknown = "unknown"


class PolicyDerivationCondition(BaseModel):
    field: str | None = None
    equals: str | None = None
    contains: str | None = None
    any: list["PolicyDerivationCondition"] = Field(default_factory=list)
    all: list["PolicyDerivationCondition"] = Field(default_factory=list)


class PolicyDerivationBranch(BaseModel):
    when: PolicyDerivationCondition
    parameters: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class PolicyDerivationRule(BaseModel):
    source_price_type: str
    target_price_type: str
    source_category: ComparisonCategory | None = None
    target_category: ComparisonCategory
    formula_id: str
    formula: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    conditional_parameters: list[PolicyDerivationBranch] = Field(default_factory=list)
    legal_basis: list[str] = Field(min_length=1)
    confidence: Confidence
    caveats: list[str] = Field(default_factory=list)


class PolicySemantics(BaseModel):
    comparison_category: ComparisonCategory
    vat_position: VatPosition
    margin_position: MarginPosition
    derivation_kind: DerivationKind
    derivation_basis: str | None = None
    notes: list[str] = Field(default_factory=list)


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
    semantics: PolicySemantics
    derivation_rules: list[PolicyDerivationRule] = Field(default_factory=list)
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

    @model_validator(mode="after")
    def semantics_must_match_category(self):
        if self.semantics.comparison_category != self.comparison_category:
            raise ValueError(
                "semantics.comparison_category must match comparison_category"
            )
        for rule in self.derivation_rules:
            if rule.target_price_type != self.price_type:
                raise ValueError(
                    "derivation rule target_price_type must match policy price_type"
                )
            if rule.target_category != self.comparison_category:
                raise ValueError(
                    "derivation rule target_category must match comparison_category"
                )
        return self
