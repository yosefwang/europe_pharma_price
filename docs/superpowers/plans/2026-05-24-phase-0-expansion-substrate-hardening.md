# Phase 0 Expansion Substrate Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the enforcement layer required before new country expansion: readiness assessments, expansion tracking, country status reporting, and baseline regression guards.

**Architecture:** Phase 0 adds planning and governance artifacts around the existing policy-data substrate without changing existing comparison semantics. Readiness assessments live in a typed schema and machine-readable data file; report templates define the minimum country-completion summary; tests ensure the roadmap mechanics and six-country baseline stay intact before any new country is added.

**Tech Stack:** Python 3.13, Pydantic schemas, JSON data artifacts, Markdown reports, existing lane index and policy-derived price-lane graph, `unittest`.

---

### Task 1: Country Readiness Schema

**Files:**
- Create: `src/eu_pharma_price/schemas/expansion.py`
- Modify: `src/eu_pharma_price/schemas/__init__.py`
- Test: `tests/test_expansion_readiness.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_expansion_readiness.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eu_pharma_price.schemas.expansion import (
    CountryReadinessAssessment,
    ExpansionPhase,
    ExpansionStatus,
)


class ExpansionReadinessTests(unittest.TestCase):
    def test_ready_country_requires_source_price_meaning_identity_and_basis(self) -> None:
        assessment = CountryReadinessAssessment.model_validate({
            "country_code": "BE",
            "country_name": "Belgium",
            "phase": "phase_1",
            "status": "ready_for_country_plan",
            "official_sources": [{
                "name": "INAMI reimbursable specialties reference files",
                "url": "https://www.inami.fgov.be/",
                "source_format": "excel",
                "access_mode": "public_download",
                "legal_status": "research_use_ok",
            }],
            "observed_price_lanes": [{
                "price_type": "SPB_PRICE",
                "comparison_category": "manufacturer_price",
                "vat_position": "vat_exclusive",
                "margin_position": "no_standard_margins",
                "confidence": "high",
                "notes": ["Prix ex usine field in reference file description."],
            }],
            "derived_price_lanes": [],
            "identity_fields": ["inn", "strength", "dosage_form", "pack_size", "national_product_code"],
            "first_comparison_basis": ["manufacturer_price"],
            "blockers": [],
            "review_notes": ["Suitable first Phase 1 country."],
        })

        self.assertEqual(assessment.country_code, "BE")
        self.assertEqual(assessment.phase, ExpansionPhase.phase_1)
        self.assertEqual(assessment.status, ExpansionStatus.ready_for_country_plan)

    def test_ready_country_cannot_have_blockers(self) -> None:
        with self.assertRaisesRegex(ValueError, "ready countries cannot have blockers"):
            CountryReadinessAssessment.model_validate({
                "country_code": "AE",
                "country_name": "United Arab Emirates",
                "phase": "phase_3",
                "status": "ready_for_country_plan",
                "official_sources": [{
                    "name": "MOHAP price list",
                    "url": "https://mohap.gov.ae/",
                    "source_format": "manual",
                    "access_mode": "restricted_request",
                    "legal_status": "needs_review",
                }],
                "observed_price_lanes": [],
                "derived_price_lanes": [],
                "identity_fields": ["product_name"],
                "first_comparison_basis": ["public_retail_price"],
                "blockers": ["Price list access and licensing unresolved."],
                "review_notes": [],
            })

    def test_ready_country_requires_at_least_one_observed_lane(self) -> None:
        with self.assertRaisesRegex(ValueError, "ready countries need observed lanes"):
            CountryReadinessAssessment.model_validate({
                "country_code": "SG",
                "country_name": "Singapore",
                "phase": "excluded",
                "status": "ready_for_country_plan",
                "official_sources": [{
                    "name": "MOH subsidised drugs",
                    "url": "https://www.moh.gov.sg/",
                    "source_format": "html",
                    "access_mode": "public_download",
                    "legal_status": "research_use_ok",
                }],
                "observed_price_lanes": [],
                "derived_price_lanes": [],
                "identity_fields": ["product_name"],
                "first_comparison_basis": ["payer_reimbursement_price"],
                "blockers": [],
                "review_notes": [],
            })


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_expansion_readiness -v
```

Expected: FAIL with `ModuleNotFoundError` for `eu_pharma_price.schemas.expansion`.

- [ ] **Step 3: Implement schema**

Create `src/eu_pharma_price/schemas/expansion.py`:

```python
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
```

Modify `src/eu_pharma_price/schemas/__init__.py` to export:

```python
from .expansion import CountryReadinessAssessment
```

and add `"CountryReadinessAssessment"` to `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_expansion_readiness -v
```

Expected: all tests pass.

### Task 2: Expansion Tracker

**Files:**
- Create: `data/expansion/country_readiness.json`
- Test: `tests/test_expansion_readiness.py`

- [ ] **Step 1: Add failing tracker test**

Append to `ExpansionReadinessTests`:

```python
    def test_expansion_tracker_loads_and_keeps_us_ca_deferred(self) -> None:
        import json

        path = ROOT / "data" / "expansion" / "country_readiness.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assessments = [
            CountryReadinessAssessment.model_validate(item)
            for item in payload["countries"]
        ]
        by_code = {item.country_code: item for item in assessments}

        self.assertEqual(by_code["IE"].status.value, "baseline_complete")
        self.assertEqual(by_code["BE"].status.value, "ready_for_country_plan")
        self.assertEqual(by_code["US"].status.value, "deferred_special_substrate")
        self.assertEqual(by_code["CA"].status.value, "deferred_special_substrate")
        self.assertEqual(
            by_code["HK"].status.value,
            "excluded_from_price_comparison",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_expansion_readiness -v
```

Expected: FAIL because `data/expansion/country_readiness.json` does not exist.

- [ ] **Step 3: Create tracker**

Create `data/expansion/country_readiness.json` with these entries:

```json
{
  "countries": [
    {
      "country_code": "IE",
      "country_name": "Ireland",
      "phase": "baseline",
      "status": "baseline_complete",
      "official_sources": [],
      "observed_price_lanes": [],
      "derived_price_lanes": [],
      "identity_fields": [],
      "first_comparison_basis": ["manufacturer_price", "pharmacy_purchase_price"],
      "blockers": [],
      "review_notes": ["Existing baseline country."]
    },
    {
      "country_code": "PL",
      "country_name": "Poland",
      "phase": "baseline",
      "status": "baseline_complete",
      "official_sources": [],
      "observed_price_lanes": [],
      "derived_price_lanes": [],
      "identity_fields": [],
      "first_comparison_basis": ["manufacturer_price", "pharmacy_purchase_price", "public_retail_price"],
      "blockers": [],
      "review_notes": ["Existing baseline country."]
    },
    {
      "country_code": "CZ",
      "country_name": "Czechia",
      "phase": "baseline",
      "status": "baseline_complete",
      "official_sources": [],
      "observed_price_lanes": [],
      "derived_price_lanes": [],
      "identity_fields": [],
      "first_comparison_basis": ["manufacturer_price", "pharmacy_purchase_price"],
      "blockers": [],
      "review_notes": ["Existing baseline country."]
    },
    {
      "country_code": "ES",
      "country_name": "Spain",
      "phase": "baseline",
      "status": "baseline_complete",
      "official_sources": [],
      "observed_price_lanes": [],
      "derived_price_lanes": [],
      "identity_fields": [],
      "first_comparison_basis": ["manufacturer_price", "public_retail_price"],
      "blockers": [],
      "review_notes": ["Existing baseline country."]
    },
    {
      "country_code": "IT",
      "country_name": "Italy",
      "phase": "baseline",
      "status": "baseline_complete",
      "official_sources": [],
      "observed_price_lanes": [],
      "derived_price_lanes": [],
      "identity_fields": [],
      "first_comparison_basis": ["manufacturer_price", "public_retail_price"],
      "blockers": [],
      "review_notes": ["Existing baseline country."]
    },
    {
      "country_code": "PT",
      "country_name": "Portugal",
      "phase": "baseline",
      "status": "baseline_complete",
      "official_sources": [],
      "observed_price_lanes": [],
      "derived_price_lanes": [],
      "identity_fields": [],
      "first_comparison_basis": ["manufacturer_price", "public_retail_price"],
      "blockers": [],
      "review_notes": ["Existing baseline country."]
    },
    {
      "country_code": "BE",
      "country_name": "Belgium",
      "phase": "phase_1",
      "status": "ready_for_country_plan",
      "official_sources": [{
        "name": "INAMI/RIZIV reimbursable specialties reference files",
        "url": "https://www.inami.fgov.be/",
        "source_format": "excel",
        "access_mode": "public_download",
        "legal_status": "research_use_ok",
        "notes": ["Reference file descriptions identify ex-factory style fields."]
      }],
      "observed_price_lanes": [{
        "price_type": "SPB_PRICE",
        "comparison_category": "manufacturer_price",
        "vat_position": "vat_exclusive",
        "margin_position": "no_standard_margins",
        "confidence": "high",
        "notes": ["Expected first lane for Belgium."]
      }],
      "derived_price_lanes": [],
      "identity_fields": ["inn", "strength", "dosage_form", "pack_size", "national_product_code"],
      "first_comparison_basis": ["manufacturer_price"],
      "blockers": [],
      "review_notes": ["Recommended first Phase 1 country."]
    },
    {
      "country_code": "SE",
      "country_name": "Sweden",
      "phase": "phase_1",
      "status": "ready_for_country_plan",
      "official_sources": [{
        "name": "TLV open data",
        "url": "https://www.tlv.se/om-tlv/oppna-data.html",
        "source_format": "api",
        "access_mode": "public_api",
        "legal_status": "research_use_ok",
        "notes": ["AIP/AUP and margin rules need country-specific plan verification."]
      }],
      "observed_price_lanes": [{
        "price_type": "AIP",
        "comparison_category": "pharmacy_purchase_price",
        "vat_position": "vat_exclusive",
        "margin_position": "wholesale_margin",
        "confidence": "high",
        "notes": ["Pharmacy purchase lane."]
      }],
      "derived_price_lanes": [],
      "identity_fields": ["inn", "strength", "dosage_form", "pack_size", "national_product_code"],
      "first_comparison_basis": ["pharmacy_purchase_price", "public_retail_price"],
      "blockers": [],
      "review_notes": ["Second Phase 1 country after Belgium."]
    },
    {
      "country_code": "NZ",
      "country_name": "New Zealand",
      "phase": "phase_1",
      "status": "ready_for_country_plan",
      "official_sources": [{
        "name": "Pharmac Pharmaceutical Schedule",
        "url": "https://schedule.pharmac.govt.nz/",
        "source_format": "xml",
        "access_mode": "public_download",
        "legal_status": "research_use_ok",
        "notes": ["Manufacturer price and subsidy semantics are strong."]
      }],
      "observed_price_lanes": [{
        "price_type": "Manufacturer's Price",
        "comparison_category": "manufacturer_price",
        "vat_position": "vat_exclusive",
        "margin_position": "no_standard_margins",
        "confidence": "high",
        "notes": ["GST-exclusive manufacturer price."]
      }],
      "derived_price_lanes": [],
      "identity_fields": ["inn", "strength", "dosage_form", "pack_size", "national_product_code"],
      "first_comparison_basis": ["manufacturer_price", "payer_reimbursement_price"],
      "blockers": [],
      "review_notes": ["Third country in first Phase 1 batch."]
    },
    {
      "country_code": "US",
      "country_name": "United States",
      "phase": "deferred",
      "status": "deferred_special_substrate",
      "official_sources": [],
      "observed_price_lanes": [],
      "derived_price_lanes": [],
      "identity_fields": [],
      "first_comparison_basis": [],
      "blockers": ["Requires separate substrate design for NADAC/ASP/FUL/MFP and PBM/rebate market structure."],
      "review_notes": ["Explicitly deferred from this roadmap."]
    },
    {
      "country_code": "CA",
      "country_name": "Canada",
      "phase": "deferred",
      "status": "deferred_special_substrate",
      "official_sources": [],
      "observed_price_lanes": [],
      "derived_price_lanes": [],
      "identity_fields": [],
      "first_comparison_basis": [],
      "blockers": ["Requires separate provincial/federal substrate design."],
      "review_notes": ["Explicitly deferred from this roadmap."]
    },
    {
      "country_code": "HK",
      "country_name": "Hong Kong",
      "phase": "excluded",
      "status": "excluded_from_price_comparison",
      "official_sources": [],
      "observed_price_lanes": [],
      "derived_price_lanes": [],
      "identity_fields": [],
      "first_comparison_basis": [],
      "blockers": ["No stable public item-level price lane identified."],
      "review_notes": ["Possible future formulary intelligence, not price comparison."]
    }
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_expansion_readiness -v
```

Expected: all tests pass.

### Task 3: Country Completion Report Template

**Files:**
- Create: `docs/templates/country-expansion-report.md`
- Test: `tests/test_expansion_readiness.py`

- [ ] **Step 1: Add failing template test**

Append to `ExpansionReadinessTests`:

```python
    def test_country_report_template_requires_policy_data_and_status_sections(self) -> None:
        template = (
            ROOT / "docs" / "templates" / "country-expansion-report.md"
        ).read_text(encoding="utf-8")
        required = [
            "## Status",
            "## Sources",
            "## Observed Price Lanes",
            "## Derived Price Lanes",
            "## Comparison Basis",
            "## Validation Cohort",
            "## Open Caveats",
            "## Next Step",
        ]
        for heading in required:
            self.assertIn(heading, template)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_expansion_readiness -v
```

Expected: FAIL because `docs/templates/country-expansion-report.md` does not exist.

- [ ] **Step 3: Create template**

Create `docs/templates/country-expansion-report.md`:

```markdown
# <Country> Expansion Report

## Status

- Country:
- Phase:
- Status:
- Completed at:
- Implemented on branch:

## Sources

| Source | Format | Access | Legal/ToS status | Snapshot |
|---|---|---|---|---|

## Observed Price Lanes

| Price type | Comparison category | VAT/GST | Margins/fees | Confidence | Notes |
|---|---|---|---|---|---|

## Derived Price Lanes

| Source lane | Target lane | Formula | Legal basis | Confidence | Caveats |
|---|---|---|---|---|---|

## Comparison Basis

| Basis | Included? | Reason |
|---|---|---|

## Validation Cohort

| Molecule | Basis | Countries compared | Result | Notes |
|---|---|---|---|---|

## Open Caveats

-

## Next Step

-
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_expansion_readiness -v
```

Expected: all tests pass.

### Task 4: Baseline Regression Guard

**Files:**
- Modify: `tests/test_expansion_readiness.py`

- [ ] **Step 1: Add failing-or-passing baseline guard test**

Append to `ExpansionReadinessTests`:

```python
    def test_baseline_six_countries_are_tracked_before_expansion(self) -> None:
        import json

        path = ROOT / "data" / "expansion" / "country_readiness.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assessments = [
            CountryReadinessAssessment.model_validate(item)
            for item in payload["countries"]
        ]
        baseline = {
            item.country_code
            for item in assessments
            if item.phase.value == "baseline"
            and item.status.value == "baseline_complete"
        }

        self.assertEqual(baseline, {"IE", "PL", "CZ", "ES", "IT", "PT"})
```

- [ ] **Step 2: Run focused test**

Run:

```bash
.venv/bin/python -m unittest tests.test_expansion_readiness -v
```

Expected: all tests pass.

- [ ] **Step 3: Run existing six-country substrate test**

Run:

```bash
.venv/bin/python -m unittest tests.test_price_lane_substrate -v
```

Expected: all tests pass, including the three-drug six-country manufacturer-basis validation.

### Task 5: Documentation and Roadmap Linkage

**Files:**
- Modify: `docs/superpowers/plans/2026-05-24-global-price-expansion-roadmap.md`
- Test: `tests/test_expansion_readiness.py`

- [ ] **Step 1: Add failing documentation linkage test**

Append to `ExpansionReadinessTests`:

```python
    def test_roadmap_links_phase_0_artifacts(self) -> None:
        roadmap = (
            ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-05-24-global-price-expansion-roadmap.md"
        ).read_text(encoding="utf-8")
        self.assertIn("data/expansion/country_readiness.json", roadmap)
        self.assertIn("docs/templates/country-expansion-report.md", roadmap)
        self.assertIn("CountryReadinessAssessment", roadmap)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m unittest tests.test_expansion_readiness -v
```

Expected: FAIL if the roadmap does not name the concrete Phase 0 artifacts.

- [ ] **Step 3: Update roadmap Phase 0 section**

In `docs/superpowers/plans/2026-05-24-global-price-expansion-roadmap.md`, make the Phase 0 outputs list name:

- `src/eu_pharma_price/schemas/expansion.py`
- `data/expansion/country_readiness.json`
- `docs/templates/country-expansion-report.md`
- `tests/test_expansion_readiness.py`

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m unittest tests.test_expansion_readiness -v
```

Expected: all tests pass.

### Task 6: Full Verification

**Files:**
- All changed files.

- [ ] **Step 1: Run compile check**

Run:

```bash
.venv/bin/python -m compileall -q src tests ui scripts
```

Expected: exit code 0.

- [ ] **Step 2: Run full unit suite**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 3: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 4: Commit Phase 0**

Run:

```bash
git add docs/superpowers/plans/2026-05-24-global-price-expansion-roadmap.md docs/superpowers/plans/2026-05-24-phase-0-expansion-substrate-hardening.md src/eu_pharma_price/schemas/expansion.py src/eu_pharma_price/schemas/__init__.py tests/test_expansion_readiness.py data/expansion/country_readiness.json docs/templates/country-expansion-report.md
git commit -m "Add expansion substrate readiness layer"
```

Expected: commit succeeds.
