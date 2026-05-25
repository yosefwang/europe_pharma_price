# Multinational Price-Lane Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the policy-data dual-gear layer that turns observed and derived national price fields into stable multinational comparable price lanes before any country-pair candidate generation.

**Architecture:** Country delegates keep publishing local canonical records and local field descriptions. Policy interpretations and deterministic derivation rules are elevated into a `normalization.price_lanes` layer that emits structured observed/derived lane semantics, and a `comparison.lane_index` layer builds a multinational indexed substrate keyed by price concept, VAT/margin state, INN/ATC, strength, route, form, pack, and product type. Comparisons are then query/cohort driven instead of full pairwise materialization.

**Tech Stack:** Python 3.13, Pydantic policy/comparison schemas, pandas/parquet artifacts, existing INN/dosage-form/strength/FX normalisers, `unittest`.

---

### Task 1: Price-Lane Semantics Normaliser

**Files:**
- Create: `src/eu_pharma_price/normalization/price_lanes.py`
- Modify: `src/eu_pharma_price/normalization/__init__.py`
- Test: `tests/test_price_lane_substrate.py`

- [x] **Step 1: Write failing tests**

Add tests proving observed public-retail lanes, derived ex-factory lanes, and VAT-mismatched lanes produce distinct comparable keys.

- [x] **Step 2: Run focused test and verify red**

Run: `../../.venv/bin/python -m unittest tests.test_price_lane_substrate -v`

Expected: import failure for `eu_pharma_price.normalization.price_lanes`.

- [x] **Step 3: Implement normaliser**

Create a frozen dataclass `PriceLaneSemantics` containing country, observed price type, normalized price type, comparison category, VAT position, margin position, derivation kind, policy ID, confidence, and caveats. Add `semantics_from_policy()` and `comparable_lane_key()`.

- [x] **Step 4: Run focused test and verify green**

Run: `../../.venv/bin/python -m unittest tests.test_price_lane_substrate -v`

Expected: all tests pass.

### Task 2: Multinational Lane Index

**Files:**
- Create: `src/eu_pharma_price/comparison/lane_index.py`
- Test: `tests/test_price_lane_substrate.py`

- [x] **Step 1: Write failing tests**

Add tests that build an index for IE, PL, CZ, ES, IT, and PT snapshots, then assert:
- every indexed row has policy/profile evidence;
- derived ex-factory rows retain source record and derivation rule IDs;
- IE `pharmacy_purchase_price` and PL VAT-inclusive `pharmacy_purchase_price` are not apple-to-apple;
- ES/IT/PT public-retail lanes share a comparable key;
- manufacturer ex-VAT lanes across IE/PL/CZ/ES/IT/PT share a comparable key where derived/observed policy permits.

- [x] **Step 2: Run focused test and verify red**

Run: `../../.venv/bin/python -m unittest tests.test_price_lane_substrate -v`

Expected: import failure for `eu_pharma_price.comparison.lane_index`.

- [x] **Step 3: Implement lane index**

Load canonical records, append deterministic derived price lanes, apply policy and data gates, run INN normalisation, strength/pack parsing, dosage/form metadata extraction, and product classification. Emit a pandas DataFrame with comparable lane key columns and evidence IDs.

- [x] **Step 4: Run focused test and verify green**

Run: `../../.venv/bin/python -m unittest tests.test_price_lane_substrate -v`

Expected: all tests pass.

### Task 3: Three-Drug Targeted Comparison Check

**Files:**
- Modify: `src/eu_pharma_price/comparison/lane_index.py`
- Test: `tests/test_price_lane_substrate.py`

- [x] **Step 1: Write failing targeted tests**

Select three common molecules present in the indexed substrate and assert targeted comparison rows exist only within the same comparable lane key and same identity key.

- [x] **Step 2: Implement query helper**

Add `find_comparable_rows(index, molecule, comparable_lane_key=None)` returning rows grouped by molecule/strength/form/route and comparable lane.

- [x] **Step 3: Verify targeted tests**

Run: `../../.venv/bin/python -m unittest tests.test_price_lane_substrate -v`

Expected: all tests pass.

### Task 4: Full Verification

**Files:**
- All changed files.

- [x] **Step 1: Run full unit suite**

Run: `../../.venv/bin/python -m unittest discover -s tests -v`

Expected: all tests pass.

- [x] **Step 2: Run compile check**

Run: `../../.venv/bin/python -m compileall -q src tests ui scripts`

Expected: exit code 0.

- [x] **Step 3: Inspect worktree**

Run: `git status --short --branch`

Expected: only intended source/test/docs changes and no pairwise matrix artifacts.
