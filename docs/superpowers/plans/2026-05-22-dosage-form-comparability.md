# Dosage Form Comparability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared dosage-form and route comparability layer so IE, CZ, and PL ingest can map local forms into auditable comparable form classes without over-blocking valid comparison candidates.

**Architecture:** Add a focused `normalization.dosage_forms` module that returns structured mapping metadata and a compatibility assessment. Delegates call the shared normalizer when creating canonical records; identity matching consumes route/form compatibility instead of exact form-string equality. Canonical records keep `dosage_form` as the comparable form class and add optional audit metadata fields.

**Tech Stack:** Python 3.13, Pydantic schemas, pandas/parquet artifacts, `unittest`.

---

### Task 1: Shared Normalizer

**Files:**
- Create: `src/eu_pharma_price/normalization/__init__.py`
- Create: `src/eu_pharma_price/normalization/dosage_forms.py`
- Test: `tests/test_dosage_form_normalization.py`

- [ ] **Step 1: Write failing tests**

Create tests for:

```python
from eu_pharma_price.normalization.dosage_forms import (
    assess_form_compatibility,
    normalize_dosage_form,
)


def test_cz_inj_pso_lqf_maps_to_injectable_powder_and_solvent():
    result = normalize_dosage_form(
        "INJ PSO LQF", country_code="CZ", source_field="lekovaFormaKod",
    )
    assert result.comparable_form_class == "injectable"
    assert result.route_family == "parenteral"
    assert "powder_and_solvent" in result.presentation_attributes
    assert result.confidence == "strong"
    assert result.rule_id == "cz.sukl.inj_pso_lqf"


def test_ie_prefilled_pen_maps_to_injectable_with_device_attribute():
    result = normalize_dosage_form(
        None,
        country_code="IE",
        source_field="Drug Name",
        product_name="Enbrel Soln. for Inj. in Pre-filled Pen 50 mg. 4",
    )
    assert result.comparable_form_class == "injectable"
    assert result.route_family == "parenteral"
    assert "prefilled_pen" in result.presentation_attributes
    assert result.confidence == "adequate"


def test_injectable_presentations_are_compatible_with_caveat():
    a = normalize_dosage_form("INJ PSO LQF", country_code="CZ")
    b = normalize_dosage_form(
        None, country_code="IE",
        product_name="Enbrel Soln. for Inj. in Pre-filled Pen 50 mg. 4",
    )
    compatibility = assess_form_compatibility(a, b)
    assert compatibility.compatible is True
    assert compatibility.confidence_cap == "high"
    assert "presentation differs" in compatibility.caveat


def test_oral_and_parenteral_are_not_compatible():
    a = normalize_dosage_form("TBL FLM", country_code="CZ")
    b = normalize_dosage_form("INJ SOL", country_code="CZ")
    compatibility = assess_form_compatibility(a, b)
    assert compatibility.compatible is False
    assert "route_family mismatch" in compatibility.reason
```

Run: `.venv/bin/python -m unittest tests.test_dosage_form_normalization -v`
Expected: import failure because the module does not exist yet.

- [ ] **Step 2: Implement normalizer**

Implement:

```python
@dataclass(frozen=True)
class DosageFormNormalization:
    raw_value: str | None
    country_code: str
    source_field: str | None
    comparable_form_class: str | None
    route_family: str | None
    presentation_attributes: tuple[str, ...]
    method: str
    confidence: str
    rule_id: str | None
    caveat: str | None


@dataclass(frozen=True)
class FormCompatibility:
    compatible: bool
    confidence_cap: str | None
    caveat: str | None
    reason: str | None
```

Add deterministic aliases for current IE/CZ/PL forms, including CZ `INJ PSO LQF`, `INJ SOL ISP`, `INJ SOL PEP`, IE pre-filled pen/syringe/powder-and-solvent, and PL injection/tablet/capsule/powder-and-solvent patterns.

- [ ] **Step 3: Verify green**

Run: `.venv/bin/python -m unittest tests.test_dosage_form_normalization -v`
Expected: all tests pass.

### Task 2: Canonical Metadata And Delegate Integration

**Files:**
- Modify: `src/eu_pharma_price/schemas/records.py`
- Modify: `src/eu_pharma_price/delegates/czechia.py`
- Modify: `src/eu_pharma_price/delegates/ireland.py`
- Modify: `src/eu_pharma_price/delegates/poland.py`
- Test: `tests/test_dosage_form_normalization.py`
- Test: `tests/test_stabilisation_checkpoint.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert delegate helpers or sample canonical records carry:

```python
assert record.dosage_form == "injectable"
assert record.route_of_administration == "parenteral"
assert record.dosage_form_raw == "INJ PSO LQF"
assert record.dosage_form_rule_id == "cz.sukl.inj_pso_lqf"
assert "powder_and_solvent" in record.dosage_form_attributes
```

Run: `.venv/bin/python -m unittest tests.test_dosage_form_normalization tests.test_stabilisation_checkpoint -v`
Expected: failure because metadata fields and delegate integration are not present.

- [ ] **Step 2: Add optional schema fields**

Extend `CanonicalPriceRecord` with:

```python
dosage_form_raw: str | None = None
dosage_form_attributes: list[str] = Field(default_factory=list)
dosage_form_normalization_method: str | None = None
dosage_form_normalization_confidence: str | None = None
dosage_form_rule_id: str | None = None
dosage_form_caveat: str | None = None
```

- [ ] **Step 3: Integrate delegates**

Replace delegate-local final form mapping with `normalize_dosage_form(...)`. Keep existing parsing where it extracts useful raw text, but the final comparable class and route must come from the shared normalizer. For unmapped forms, keep canonicalisation possible only when the normalizer returns a comparable form class; otherwise emit the existing missing-field anomaly.

- [ ] **Step 4: Verify green**

Run: `.venv/bin/python -m unittest tests.test_dosage_form_normalization tests.test_stabilisation_checkpoint -v`
Expected: all tests pass.

### Task 3: Identity Compatibility Matrix

**Files:**
- Modify: `src/eu_pharma_price/comparison/identity.py`
- Modify: `src/eu_pharma_price/comparison/generator.py`
- Test: `tests/test_dosage_form_normalization.py`

- [ ] **Step 1: Write failing tests**

Add identity tests:

```python
def test_identity_allows_compatible_injectable_presentations_with_high_confidence():
    # same molecule, same strength, same comparable form class, different
    # presentation attributes should match with capped high confidence.


def test_identity_blocks_oral_vs_parenteral_route_family():
    # oral tablet vs injectable should not match.
```

Run: `.venv/bin/python -m unittest tests.test_dosage_form_normalization -v`
Expected: failure because identity still requires exact form equality and does not consume form metadata.

- [ ] **Step 2: Update identity matching**

Use `assess_form_compatibility(...)` inside `assess_identity`. Pass optional form attributes and normalisation confidence from generator prepared rows. Cap confidence when presentation differs or mapping confidence is not strong. Preserve hard blockers for route-family mismatch and unparseable strength.

- [ ] **Step 3: Verify green**

Run: `.venv/bin/python -m unittest tests.test_dosage_form_normalization -v`
Expected: all tests pass.

### Task 4: Profile Reporting And Artifact Regeneration

**Files:**
- Modify: `src/eu_pharma_price/profile/profiler.py`
- Regenerate: CZ/IE/PL canonical/profile/comparison/review artifacts for the existing validated snapshots only.
- Test: `tests/test_dosage_form_normalization.py`
- Test: `tests/test_stabilisation_checkpoint.py`

- [ ] **Step 1: Write failing profile test**

Add a profiler test that creates a small DataFrame or temporary parquet with mapped and unmapped form metadata, then asserts a `dosage_form_normalization` profile reports confidence distribution and unmapped forms.

Run: `.venv/bin/python -m unittest tests.test_dosage_form_normalization -v`
Expected: failure because profiler does not inspect dosage-form metadata.

- [ ] **Step 2: Implement profile summary**

Add a profile entry for `dosage_form_normalization` with distribution notes for confidence counts, rule-id coverage, and unmapped raw forms.

- [ ] **Step 3: Regenerate artifacts**

Run the existing project commands or scripts used for delegate/profile/comparison/review generation for IE `2026-05-16`, PL `2026-04-01`, and CZ `2026-05-20`. Do not ingest or stage `data/raw/fr/`.

- [ ] **Step 4: Verify Enbrel candidate recall**

Run a local query that confirms CZ Enbrel rows with `INJ PSO LQF` now produce injectable candidates against IE Enbrel where molecule and strength match, with presentation caveats rather than missing candidates.

- [ ] **Step 5: Full verification**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q src tests ui
git status --short
```

Expected: tests and compile pass; only intended files are staged/modified; `data/raw/fr/` remains untracked and unstaged.
