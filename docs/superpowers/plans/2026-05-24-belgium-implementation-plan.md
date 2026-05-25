# Belgium Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Belgium as a first-class Phase 1 country on a manufacturer-price basis without weakening the existing six-country baseline.

**Architecture:** Belgium enters through the same policy-data dual-gear substrate as the existing six countries. The delegate reads the INAMI reimbursable-specialties reference file, canonicalises the observed fields into raw and canonical records, the policy layer declares `SPB_PRICE` as an observed manufacturer lane, and the comparison substrate consumes that interpretation like any other country. The first pass stays narrow: one honest observed basis, no speculative extra derivations.

**Tech Stack:** Python 3.13, Pydantic schemas, pandas/openpyxl for workbook parsing, JSON source register entries, policy interpretation JSONL, existing delegate runner and comparison substrate, `unittest`.

---

### Task 1: Belgium Source Registration and Policy Interpretation

**Files:**
- Modify: `data/sources/register.json`
- Create: `data/policy/be/policy_interpretations.jsonl`
- Test: `tests/test_new_country_delegates.py`

- [ ] **Step 1: Write the failing test**

Add a Belgium test to `tests/test_new_country_delegates.py` that builds a tiny workbook with an `SSP_PRICE_COMPARISON` sheet containing `SPB_PRICE`, `S_COD`, `S_NAM`, `S_NAM_SPECIF`, `F_ORGA`, `ATC_COD`, `SI_CONC_NOM`, `S_PREP`, `RETARD`, `VOLUME_TOTAL`, `SPB_BASE`, `SPB_PUBLIC`, and asserts that the Belgium delegate produces one canonical record with:

```python
self.assertEqual(record.country_code, "BE")
self.assertEqual(record.price_type, "SPB_PRICE")
self.assertFalse(record.price_includes_vat)
self.assertEqual(str(record.price_amount), "10.80")
self.assertEqual(record.product_name, "BELGIAN TEST 500 mg 30 tablets")
self.assertEqual(record.inn, "paracetamol")
self.assertEqual(record.atc_code, "N02BE01")
self.assertEqual(record.strength, "500 mg")
self.assertEqual(record.pack_size, "30")
self.assertEqual(record.dosage_form, "oral_solid")
self.assertEqual(record.route_of_administration, "oral")
self.assertEqual(record.manufacturer, "Test Pharma NV")
self.assertEqual(record.national_product_code, "1234567")
```

Also add a registration test:

```python
from json import loads
register = loads((ROOT / "data" / "sources" / "register.json").read_text(encoding="utf-8"))
be = next(item for item in register if item["country_code"] == "BE")
self.assertEqual(be["source_name"], "INAMI reimbursable specialties reference files")
self.assertEqual(be["fetch_method"], "manual")
self.assertEqual(be["status"], "registered")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
../../.venv/bin/python -m unittest tests.test_new_country_delegates -v
```

Expected: fail because Belgium delegate, source registration, and policy interpretation are missing.

- [ ] **Step 3: Implement the source and policy entries**

Update `data/sources/register.json` with a Belgium entry:

```json
{
  "source_id": "src-be-inami",
  "country_code": "BE",
  "source_name": "INAMI reimbursable specialties reference files",
  "source_url": "https://www.inami.fgov.be/fr/themes/soins-de-sante-cout-et-remboursement/les-prestations-de-sante-que-vous-rembourse-votre-mutualite/medicaments/remboursement-d-un-medicament/specialites-pharmaceutiques-remboursables/specialites-pharmaceutiques-remboursables-listes-et-fichiers-de-reference",
  "source_type": "excel",
  "update_frequency": "monthly",
  "fetch_method": "manual",
  "robots_txt_compliant": true,
  "tos_reviewed": true,
  "tos_permits_research": true,
  "manual_refresh_reason": "The INAMI reference file is a large monthly workbook that is saved via the public download link in the browser. The first-pass implementation will use a small workbook fixture that mirrors the published table structure.",
  "registered_at": "2026-05-24T00:00:00+00:00",
  "registered_by": "phase-0-expansion",
  "status": "registered",
  "notes": "SPB_PRICE is described by INAMI as Prix ex usine. The first pass uses manufacturer_price only."
}
```

Create `data/policy/be/policy_interpretations.jsonl` with one line:

```json
{
  "id": "be-spb-price-2026-05-24",
  "country_code": "BE",
  "price_type": "SPB_PRICE",
  "comparison_category": "manufacturer_price",
  "effective_from": "2026-05-01",
  "effective_to": null,
  "source_references": [
    "https://www.inami.fgov.be/fr/themes/soins-de-sante-cout-et-remboursement/les-prestations-de-sante-que-vous-rembourse-votre-mutualite/medicaments/remboursement-d-un-medicament/specialites-pharmaceutiques-remboursables/specialites-pharmaceutiques-remboursables-listes-et-fichiers-de-reference",
    "https://www.inami.fgov.be/SiteCollectionDocuments/liste-specialites-pharmaceutiques-remboursables-description-fichier-reference.pdf"
  ],
  "interpretation_text": "SPB_PRICE is the INAMI ex-usine price for reimbursable specialties and maps to manufacturer_price.",
  "confidence": "high",
  "authored_at": "2026-05-24T00:00:00+00:00",
  "authored_by": "be-data-ingestion",
  "superseded_by": null,
  "adjudication_notes": null,
  "includes_vat": false,
  "includes_margin": "no standard margins (manufacturer ex-usine)",
  "caveats": [
    "The first pass uses the observed ex-usine lane only.",
    "Hospital-only and reference-pricing complexity is deferred until the base lane is working."
  ],
  "semantics": {
    "comparison_category": "manufacturer_price",
    "vat_position": "vat_exclusive",
    "margin_position": "no_standard_margins",
    "derivation_kind": "observed",
    "derivation_basis": "policy-agent-structured-decision",
    "notes": [
      "SPB_PRICE is explicitly described by INAMI as Prix ex usine."
    ]
  },
  "derivation_rules": [],
  "caveats": [
    "The first pass uses the observed ex-usine lane only.",
    "Hospital-only and reference-pricing complexity is deferred until the base lane is working."
  ]
}
```

- [ ] **Step 4: Run the test again and verify it still fails only for the missing delegate**

Run:

```bash
../../.venv/bin/python -m unittest tests.test_new_country_delegates -v
```

Expected: Belgium-specific failures only, because the source and policy files now exist but the delegate does not yet.

### Task 2: Belgium Delegate

**Files:**
- Create: `src/eu_pharma_price/delegates/belgium.py`
- Modify: `src/eu_pharma_price/delegates/registry.py`
- Modify: `src/eu_pharma_price/delegates/__init__.py`
- Test: `tests/test_new_country_delegates.py`

- [ ] **Step 1: Extend the test with a failing delegate import/registration assertion**

Add:

```python
self.assertEqual(get_delegate("BE").country_code, "BE")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
../../.venv/bin/python -m unittest tests.test_new_country_delegates -v
```

Expected: failure because `BelgiumDelegate` is not implemented or not registered.

- [ ] **Step 3: Implement the delegate**

Create `src/eu_pharma_price/delegates/belgium.py`:

```python
"""Belgium country delegate (INAMI reimbursable specialties reference file)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..schemas.source import RawRecord
from .base import BaseDelegate


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


class BelgiumDelegate(BaseDelegate):
    country_code = "BE"
    default_currency = "EUR"
    price_field = "SPB_PRICE"
    price_includes_vat = False
    delimiter = ","
    decimal_separator = "."
    local_field_descriptions = {
        "SPB_PRICE": "INAMI ex-usine price for reimbursable specialties; maps to manufacturer_price.",
        "SPB_BASE": "Base de remboursement (niveau ex-usine).",
        "SPB_PUBLIC": "Public price, if present in the combined reference table.",
        "S_COD": "Unique INAMI code for each pack.",
        "S_NAM": "Specialty name.",
        "S_NAM_SPECIF": "Specific specialty name.",
        "F_ORGA": "Responsible firm.",
        "ATC_COD": "ATC code.",
        "SI_CONC_NOM": "Active-ingredient strength.",
        "S_PREP": "Injectable versus non-injectable flag.",
        "RETARD": "Retard-release flag.",
        "VOLUME_TOTAL": "Units per pack.",
    }

    def parse_csv(self, file_path: Path) -> list[dict[str, str]]:
        xls = pd.ExcelFile(file_path)
        sheet_name = "SSP_PRICE_COMPARISON" if "SSP_PRICE_COMPARISON" in xls.sheet_names else xls.sheet_names[0]
        df = xls.parse(sheet_name)
        return [
            {str(k): _clean_text(v) for k, v in row.items()}
            for row in df.to_dict(orient="records")
        ]

    def _derive_fields(self, raw_record: RawRecord) -> dict[str, Any]:
        prep = _clean_text(raw_record.raw_fields.get("S_PREP"))
        is_injectable = prep == "1"
        name = " ".join(
            _clean_text(raw_record.raw_fields.get(field))
            for field in ("S_NAM", "S_NAM_SPECIF")
            if _clean_text(raw_record.raw_fields.get(field))
        )
        strength = _clean_text(raw_record.raw_fields.get("SI_CONC_NOM"))
        pack_size = _clean_text(raw_record.raw_fields.get("VOLUME_TOTAL"))
        dosage_form = "injection" if is_injectable else "oral_solid"
        route = "parenteral" if is_injectable else "oral"
        if not pack_size and "pack" in name.lower():
            pack_size = "".join(ch for ch in name if ch.isdigit())
        return {
            "product_name": name or _clean_text(raw_record.raw_fields.get("S_NAM")),
            "inn": _clean_text(raw_record.raw_fields.get("B_LBL_FR")) or _clean_text(raw_record.raw_fields.get("B_LBL_NL")),
            "strength": strength,
            "pack_size": pack_size,
            "dosage_form": dosage_form,
            "route_of_administration": route,
            "manufacturer": _clean_text(raw_record.raw_fields.get("F_ORGA")),
            "national_product_code": _clean_text(raw_record.raw_fields.get("S_COD")),
            "atc_code": _clean_text(raw_record.raw_fields.get("ATC_COD")),
        }
```

Register the delegate in `src/eu_pharma_price/delegates/registry.py` and export it in `src/eu_pharma_price/delegates/__init__.py`.

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
../../.venv/bin/python -m unittest tests.test_new_country_delegates -v
```

Expected: Belgium delegate registration and canonicalization tests pass.

### Task 3: Belgium Country Report and Tracker Update

**Files:**
- Modify: `data/expansion/country_readiness.json`
- Create: `reports/countries/be/README.md` or the report produced by the country run
- Test: `tests/test_expansion_readiness.py`

- [ ] **Step 1: Add Belgium status to the tracker if it is implemented and validated**

Update `data/expansion/country_readiness.json` so Belgium moves from `ready_for_country_plan` to `in_progress` while the first fixture and delegate are being validated, then to `complete` once the country report exists and the cohort passes.

- [ ] **Step 2: Run the full test and verify country report format**

Use the country report template at `docs/templates/country-expansion-report.md` and populate:

- status;
- source;
- observed lane;
- derived lane: none in first pass;
- comparison basis: manufacturer_price;
- validation cohort.

- [ ] **Step 3: Run the focused Belgium regression**

Run:

```bash
../../.venv/bin/python -m unittest tests.test_new_country_delegates -v
../../.venv/bin/python -m unittest tests.test_price_lane_substrate -v
```

Expected: baseline still passes and Belgium delegate tests pass.

### Task 4: Full Verification and Commit

**Files:**
- All changed files.

- [ ] **Step 1: Run compile check**

Run:

```bash
../../.venv/bin/python -m compileall -q src tests ui scripts
```

Expected: exit code 0.

- [ ] **Step 2: Run full unit suite**

Run:

```bash
../../.venv/bin/python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 3: Run diff hygiene check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Commit Belgium**

Run:

```bash
git add data/sources/register.json data/policy/be/policy_interpretations.jsonl data/expansion/country_readiness.json docs/templates/country-expansion-report.md src/eu_pharma_price/delegates/belgium.py src/eu_pharma_price/delegates/registry.py src/eu_pharma_price/delegates/__init__.py tests/test_new_country_delegates.py
git commit -m "Add Belgium manufacturer-price delegate"
```

Expected: commit succeeds.
