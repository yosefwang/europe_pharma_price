"""Schemas for country expansion readiness and tracking."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from .policy import ComparisonCategory, Confidence, MarginPosition, VatPosition


class ExpansionPhase(str, Enum):
    baseline = "baseline"
    phase_1 = "phase_1"
    phase_2 = "phase_2"
    phase_3 = "phase_3"
    excluded = "excluded"
    deferred = "deferred"


class ExpansionStatus(str, Enum):
    baseline_complete = "baseline_complete"
    needs_research = "needs_research"
    ready_for_country_plan = "ready_for_country_plan"
    planned = "planned"
    in_progress = "in_progress"
    complete = "complete"
    blocked = "blocked"
    excluded_from_price_comparison = "excluded_from_price_comparison"
    deferred_special_substrate = "deferred_special_substrate"


class SourceFormat(str, Enum):
    csv = "csv"
    excel = "excel"
    xml = "xml"
    api = "api"
    html = "html"
    pdf = "pdf"
    manual = "manual"
    other = "other"


class SourceAccessMode(str, Enum):
    public_download = "public_download"
    public_api = "public_api"
    public_search = "public_search"
    manual_download = "manual_download"
    restricted_request = "restricted_request"
    licensed = "licensed"


class LegalStatus(str, Enum):
    research_use_ok = "research_use_ok"
    needs_review = "needs_review"
    restricted = "restricted"
    unknown = "unknown"


class ExpansionSource(BaseModel):
    name: str
    url: str
    source_format: SourceFormat
    access_mode: SourceAccessMode
    legal_status: LegalStatus
    notes: list[str] = Field(default_factory=list)


class ExpansionPriceLane(BaseModel):
    price_type: str
    comparison_category: ComparisonCategory
    vat_position: VatPosition
    margin_position: MarginPosition
    confidence: Confidence
    notes: list[str] = Field(default_factory=list)


class ExpansionDerivedLane(BaseModel):
    source_price_type: str
    target_price_type: str
    target_category: ComparisonCategory
    confidence: Confidence
    basis: str
    caveats: list[str] = Field(default_factory=list)


class CountryReadinessAssessment(BaseModel):
    country_code: str = Field(min_length=2, max_length=2)
    country_name: str
    phase: ExpansionPhase
    status: ExpansionStatus
    official_sources: list[ExpansionSource] = Field(default_factory=list)
    observed_price_lanes: list[ExpansionPriceLane] = Field(default_factory=list)
    derived_price_lanes: list[ExpansionDerivedLane] = Field(default_factory=list)
    identity_fields: list[str] = Field(default_factory=list)
    first_comparison_basis: list[ComparisonCategory] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)

    @field_validator("country_code")
    @classmethod
    def country_code_uppercase(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def ready_country_has_required_evidence(self):
        if self.status == ExpansionStatus.ready_for_country_plan:
            if self.blockers:
                raise ValueError("ready countries cannot have blockers")
            if not self.official_sources:
                raise ValueError("ready countries need official sources")
            if not self.observed_price_lanes:
                raise ValueError("ready countries need observed lanes")
            if not self.identity_fields:
                raise ValueError("ready countries need identity fields")
            if not self.first_comparison_basis:
                raise ValueError("ready countries need a first comparison basis")
        return self
