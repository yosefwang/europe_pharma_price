# Decision 006 — Two-layer INN normalization for cross-language identity matching

**Date:** 2026-05-17
**Status:** accepted
**Discovered during:** real-data validation IE↔PL (Phase 9).

## Context

IE stores English INNs (`paracetamol`). PL stores Latinized INNs (`paracetamolum`). Exact-string INN matching yields 4 overlapping INNs across 592 (IE) + 423 (PL) unique INNs — blocking nearly all cross-country comparison candidates. Future countries (FR, DE, IT, ES) will bring further language-specific INN variants.

The project charter (§6) requires: "never compare across different molecules (INN must match)". The comparison identity layer enforces this via exact-string match. But "paracetamol" and "paracetamolum" ARE the same molecule — the mismatch is a linguistic surface difference, not a pharmacological one.

## Decision

A two-layer INN normalization module (`inn_normalizer.py`) sits in the comparison layer. It maps non-English INNs to English canonical forms before identity matching. The two layers are:

### Layer 1: Linguistic Rule Engine (deterministic, zero FP)

Language-specific transformation rules map local INN variants to English canonical stems. Rules are declared as data — adding a language = adding a rule list. No code changes.

**Initial PL rule set** (5 rules, sufficient for 95% of PL INNs):

| Rule | Pattern | Example |
|------|---------|---------|
| `acidum X-um → X-ic acid` | regex | `acidum valproicum` → `valproic acid` |
| Compound salt suffix | regex | `X-i hydrochloridum` → `X hydrochloride` |
| Compound sodium salt | regex | `natrii X-as` → `X-ate sodium` |
| `-as → -ate` | suffix | `besilas` → `besilate` |
| `-um/-i → ""` | suffix | `paracetamolum` → `paracetamol` |

Each rule carries a `description` field citing the linguistic rationale (e.g., "Latin neuter nominative -um suffix dropped in English INN convention"). Rules have a `terminal` flag to stop further processing (used for compound salts that should not undergo additional suffix stripping).

### Layer 2: Constrained Fuzzy Matching (safe fallback)

Only runs on INNs Layer 1 couldn't normalize. Uses the WHO ATC-DDD CSV (~6,000 English INN names, committed to `data/reference/who_atc_ddd.csv`) as the canonical dictionary. Five constraints bound the false-positive risk:

1. First character must match (`p` → `p*`)
2. Levenshtein distance ≤ 2
3. Length ratio between 80%–120% (65% for compound bases)
4. Only the lowest-distance candidate accepted
5. Multiple candidates at same distance → `ambiguity` → no auto-match (falls through to `method=none`, recorded as anomaly)

### Placement: Comparison Layer, Not Delegates

Delegates own "what was published in this country's publication." Cross-language normalization is a comparison concern. Raw INN strings remain in canonical records; the normalized INN and derived ATC code are comparison-phase artifacts stored on `ComparisonCandidate` records.

### ATC Enrichment

When the WHO lookup succeeds (Layer 1 exact or Layer 2 fuzzy), the candidate also receives the WHO ATC code. ATC codes serve as cross-validation: when canonical INNs differ but ATC codes match exactly, the candidate is accepted with `identity_confidence=medium` and a caveat. This covers edge cases where the linguistic transformation is partially successful.

## What this does NOT do

- Does not modify canonical records on disk (raw INN preserved).
- Does not infer therapeutic equivalence across different molecules.
- Does not require internet access at runtime (WHO CSV committed to repo).
- Does not claim INN→ATC mapping is authoritative for clinical use — it is a matching aid for the comparison layer.
- Does not set precedent for fuzzy matching on other dimensions (dosage form, route, strength remain exact-match).

## Code Location

- **Module**: `src/eu_pharma_price/comparison/inn_normalizer.py`
- **Reference data**: `data/reference/who_atc_ddd.csv` (from fabkury/atcd, MIT license)
- **Updated**: `identity.py` (new INN matching logic, ATC cross-validation)
- **Updated**: `generator.py` (normalizer integration in `_prepare_lane_rows`)

## Results (IE↔PL, 2026-05-17)

| Metric | Before | After |
|--------|--------|-------|
| INN overlap | 4 | 166 |
| PL INNs normalized | 0% | 95.9% |
| PL INNs with ATC | 0% | 91% |
| Comparison candidates | 15 | 12,515 |

## Scaling to New Languages

Adding a language (e.g., FR = French) requires:
1. Add a `LanguageRuleSet` for the language in `_LANGUAGE_RULES` (data, not code)
2. Add `COUNTRY_LANGUAGE` mapping
3. When language-specific rules don't exist yet, the normalizer falls through to Layer 2 (fuzzy), which is language-agnostic

French INN names are largely identical to English (both use INN Latin/English conventions), so the EN rule set (empty — pass-through) may suffice for most cases.

## Relationship to Charter

- **§4 Two gears**: INN normalization is part of identity matching in the comparison layer, not policy interpretation or data profiling. The two gears remain independent.
- **§4 Traceability**: Normalization method (`rule_based`/`fuzzy`/`exact`) and rule label are recorded in the identity match metadata.
- **§4 Honest comparison**: Fuzzy-matched candidates carry `identity_confidence ≤ medium` and an explicit caveat in the evidence bundle.
- **§8 Rule 1 (Never invent a value)**: The raw INN is preserved. The normalized form is a derived value with full provenance.
- **§8 Rule 9 (Local fixtures only)**: The WHO CSV snapshot is committed to the repository.
