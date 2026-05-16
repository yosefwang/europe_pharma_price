# Decision 002 — First end-to-end validation case

**Date:** 2026-05-16
**Status:** accepted
**Supersedes:** —

## Context

The project charter (§7) requires the system to "walk one real country pair and one real molecule end to end" before working hypotheses harden. Phase 8 of the roadmap implements this requirement.

Selection criteria from the charter:

- source availability on both sides
- clear molecule identity
- clear strength and form
- likely policy interpretability
- expected friction sufficient to test assumptions, not chosen to confirm convenient ones

## Decision

The first validation case is:

- **Country pair**: France (FR) ↔ Ireland (IE)
- **Molecule**: paracetamol (ATC N02BE01)
- **Strength**: 500 mg
- **Dosage form**: tablet (oral)
- **Pack size**: 30 tablets
- **Snapshot date**: 2024-09-01 (Q3 2024 window)
- **Comparison category**: `manufacturer_price`
- **Candidate ID**: deterministic — derived from canonical record IDs (see `data/comparisons/2024-09-01/candidates.parquet`)

## Rationale

**Why FR/IE**:
- Both countries publish manufacturer-side prices that map to the same comparison category (`manufacturer_price`), so no category-bridging derivation rule is required for the first validation. This is the simplest possible legitimate cross-country comparison and exposes only the frictions that always exist (identity matching, strength normalisation, caveat propagation), not the additional frictions of category bridging.
- Both publish in EUR, so no currency conversion is needed. Currency conversion is a separate friction worth validating later, after the simpler case is known to work.
- Both have well-documented pricing regimes (PCRS/FASPM in IE; CEPS/Code de la sécurité sociale in FR) producing high-confidence policy interpretations.

**Why paracetamol**:
- Single-ingredient, well-known INN with no ambiguity in identity matching across countries.
- Common pack sizes (28, 30, 60) — exposes the per-pack normalisation friction without complicating with combination products or unusual presentations.
- Available in both source publications.

**Frictions explicitly expected to surface**:
- Both regimes carry caveats (CEPS confidential rebates, FASPM reference pricing) — the validation tests whether caveats actually travel through review and into outputs.
- Identity match needs the strength parser to cope with `"500mg"` exactly the same in both source files. If parsing differs by even whitespace or case, the matcher should refuse rather than guess.
- Pack size 30 is the same on both sides, so `identity_confidence=exact`; this validates the happy-path label assignment.

**Frictions explicitly excluded from this first case** (left for later validations):
- Cross-currency comparison (validates: PL ↔ FR ↔ IE — three currencies if we eventually add UK)
- Cross-category comparison (validates: PL pharmacy purchase ↔ FR manufacturer)
- Suspect/implausible data path (validates: a real publication with real holes)
- Combination products and unusual dosage forms

These will be subsequent validation cases. Each picks a friction the current case does not exercise.

## Acceptance

This case is considered passed when:
1. Every artifact in the evidence chain exists and resolves.
2. Caveats from both countries' policy interpretations appear in the final review assessment and any rendered output.
3. The Audit Trail View shows all 9 evidence artifacts with no broken-link indicators.
4. The displayed `price_per_strength_unit` traces back through derivation_rule → canonical → raw → source_document.file_hash.
5. `decisions/` contains a record of every revised working hypothesis discovered during the walk.

## Outcome

The validation pass produced no design changes — the working hypotheses are reaffirmed for the FR/IE manufacturer-price case. Detailed observations are in `reports/validation/001-end-to-end.md`. Frictions that are real but not yet exercised (cross-currency, cross-category) remain to be tested in subsequent validation cases.
