"""Review assessment and anomaly report schemas."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class Usability(str, Enum):
    usable = "usable"
    usable_with_caveat = "usable_with_caveat"
    exploratory = "exploratory"
    not_comparable = "not_comparable"


class Strength(str, Enum):
    strong = "strong"
    adequate = "adequate"
    weak = "weak"
    not_applicable = "not_applicable"


class ReviewAssessment(BaseModel):
    id: str = Field(description="UUID")
    comparison_candidate_id: str
    usability: Usability
    policy_strength: Strength
    data_strength: Strength
    identity_strength: Strength
    normalisation_strength: Strength
    rationale: str
    reviewed_at: datetime
    reviewed_by: str

    caveats: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    superseded_by: str | None = None
    human_override: bool = False
    override_rationale: str | None = None

    @model_validator(mode="after")
    def check_usability_constraints(self):
        if self.usability == Usability.not_comparable and not self.blocking_issues:
            raise ValueError("not_comparable requires at least one blocking_issue")
        if self.usability == Usability.usable_with_caveat and not self.caveats:
            raise ValueError("usable_with_caveat requires at least one caveat")
        strengths = [self.policy_strength, self.data_strength, self.identity_strength]
        if self.usability == Usability.usable and Strength.weak in strengths:
            raise ValueError("usable not permitted when any strength dimension is weak")
        return self


class AnomalyType(str, Enum):
    schema_mismatch = "schema_mismatch"
    distribution_outlier = "distribution_outlier"
    category_ambiguity = "category_ambiguity"
    identifier_conflict = "identifier_conflict"
    source_inconsistency = "source_inconsistency"
    policy_gap = "policy_gap"
    other = "other"


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class AnomalyStatus(str, Enum):
    open = "open"
    under_review = "under_review"
    resolved = "resolved"


class Resolution(str, Enum):
    accommodate = "accommodate"
    exempt = "exempt"
    exclude = "exclude"
    accept_with_caveat = "accept_with_caveat"


class AnomalyReport(BaseModel):
    id: str = Field(description="UUID")
    country_code: str = Field(min_length=2, max_length=2)
    anomaly_type: AnomalyType
    severity: Severity
    title: str
    description: str
    evidence: list[str] = Field(min_length=1)
    reported_at: datetime
    reported_by: str
    status: AnomalyStatus

    affected_records: list[str] = Field(default_factory=list)
    resolution: Resolution | None = None
    resolution_notes: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    decision_id: str | None = None

    @model_validator(mode="after")
    def check_resolution_constraints(self):
        if self.status == AnomalyStatus.resolved and self.resolution is None:
            raise ValueError("resolved status requires a resolution")
        return self
