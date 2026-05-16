# End-to-End Validation 001 — FR/IE Paracetamol 500mg

**Case selected by:** [decisions/002-first-validation-case.md](../../decisions/002-first-validation-case.md)
**Snapshot window:** 2024-09-01
**Candidate ID:** see `data/comparisons/2024-09-01/candidates.parquet` (filter molecule_inn = "paracetamol")
**Performed:** 2026-05-16

## Goal

Walk one real comparison path through every artifact and UI surface, verify every link resolves, and record friction discovered along the way.

## What was walked

Candidate proposing comparison of:

- **Country A:** France — `PRIX_FABRICANT_EUR` 2.10 EUR per 30-tablet pack of paracetamol 500mg (Sanofi)
- **Country B:** Ireland — `EX_FACTORY_PRICE_EUR` 2.85 EUR per 30-tablet pack of paracetamol 500mg (Acme Pharma)
- **Comparison category:** `manufacturer_price` (both sides)
- **Identity confidence:** `exact` (INN, form, route, strength, pack all match)
- **Per-strength-unit prices:** FR 0.000140 EUR/mg vs IE 0.000190 EUR/mg
- **Price ratio (FR/IE):** 0.7368 — FR list price approximately 26% lower than IE on this basis

## The 16 links walked

For each side (A=FR, B=IE), the chain runs candidate → review → derivation rule → data profile → policy interpretation → canonical record → raw record → source document, with file-hash verification at the leaf:

| # | Link | Resolved | Note |
|---|------|----------|------|
| 1 | comparison candidate | ✓ | persisted in `data/comparisons/2024-09-01/candidates.parquet` |
| 2 | review assessment | ✓ | usability = `usable`, all four strengths = `strong` |
| 3 | derivation rule (FR) | ✓ | `pack_normalisation`: `price_per_strength_unit = price_per_unit / 500` |
| 4 | data profile (FR) | ✓ | plausibility = `plausible`, non-null rate = 1.0 |
| 5 | policy interpretation (FR) | ✓ | confidence = `high`, sources = CEPS / Code de la sécurité sociale |
| 6 | canonical record (FR) | ✓ | one row in `data/canonical/fr/2024-09-01/prices.parquet` |
| 7 | raw record (FR) | ✓ | row_index=0 in `data/canonical/fr/2024-09-01/raw.parquet` |
| 8 | source document (FR) | ✓ | manifest in `tests/fixtures/sources/fr/2024-09-01/manifest.json` |
| 9 | file hash (FR) | ✓ | sha256 of `q3-list.csv` matches manifest |
| 10 | derivation rule (IE) | ✓ | same formula as FR |
| 11 | data profile (IE) | ✓ | plausibility = `plausible`, non-null rate = 1.0 |
| 12 | policy interpretation (IE) | ✓ | confidence = `high`, sources = PCRS / FASPM |
| 13 | canonical record (IE) | ✓ | one row in `data/canonical/ie/2024-09-01/prices.parquet` |
| 14 | raw record (IE) | ✓ | row_index=0 in `data/canonical/ie/2024-09-01/raw.parquet` |
| 15 | source document (IE) | ✓ | manifest in `tests/fixtures/sources/ie/2024-09-01/manifest.json` |
| 16 | file hash (IE) | ✓ | sha256 of `q3-list.csv` matches manifest |

The walker is in [src/eu_pharma_price/audit/trail.py](../../src/eu_pharma_price/audit/trail.py); the Audit Trail view in the workbench renders the same chain interactively.

## Frictions observed

### Caveats successfully traveled

The FR policy interpretation carries two caveats:
- "Confidential CEPS rebates may apply; the published value reflects the gross convention price, not the net realised price."
- "For products under référence aux comparateurs européens, this published value is itself influenced by reference pricing and should not be treated as independently observed."

The IE policy interpretation carries:
- "PCRS publication also contains a RETAIL_PRICE_EUR column for some packs; do not confuse these."
- "Ireland participates in BENELUXA reference-pricing arrangements; net prices may differ."

All four caveats appear in the review assessment's `caveats` list and are visible in the Review Queue and Comparison Candidate views in both English and Chinese (the caveat **text** stays in source language; only the surrounding labels translate). This validates a key working hypothesis — caveats travel.

### Cross-currency case revealed by adjacent walk

The FR/IE pair shares EUR. In adjacent test runs the generator correctly leaves `price_ratio = null` when an EUR record meets a PLN record, and `comparison_category` mismatch (PL `pharmacy_purchase_price` vs FR/IE `manufacturer_price`) caused the IE/PL and FR/PL pairs to be skipped silently. Both refusal paths are correct per the charter, but the user has no clear UI surface to see *why* a candidate they expected was not produced. **Frictio noted; not a design change for Phase 8.**

### Pack-size parser is forgiving in good ways and silent in bad ways

The Polish CSV contains `tabletka` (Polish for "tablet") in `POSTAC` — accepted. French `comprimé` accepted. English `tablet` accepted. Capsule variants similarly. But the parser would silently fail on a row with `pack_size = "30 caps"` if `caps` weren't already in the regex — a regression risk when adding a new country. **Working hypothesis added below.**

### Identity matching enforces hard exclusions correctly

Synthetic test in `tests` confirmed that:
- `paracetamol tablet` vs `paracetamol injection` → no match (route mismatch)
- `paracetamol tablet` vs `ibuprofen tablet` → no match (INN mismatch)

These pruning paths are silent (no anomaly), as specified.

### Price ratio is not the headline

The 26% gap in headline form (`FR 26% lower than IE`) is meaningless on its own — both prices are gross convention prices, both regimes have known confidential rebates, and reference-pricing relationships flow from IE's BENELUXA participation and from FR's référence aux comparateurs européens. The Review Queue surfaces these as caveats, but the displayed `price_ratio` carries no warning glyph in the table. **Working hypothesis added below.**

## Working hypotheses revised

### Reaffirmed without change

- **Two-gear rule** (policy + data, both sides). Held cleanly through this case.
- **Per-snapshot data profiles**. Held — one snapshot, one profile, no aggregation.
- **Hard exclusions are silent**. Held — no spurious anomaly noise.
- **Caveats travel**. Held — all four upstream caveats reached review.
- **No silent transforms**. Held — every numeric value derived through a documented `DerivationRule`.

### Revised — add caveat-density indicator near `price_ratio`

The Review Queue distinguishes `usable_with_caveat` from `usable`, but the Comparison Candidate table renders only the bare ratio without a caveat-count badge. A reader skimming the table could miss that two of four upstream sources qualified the figure. The working hypothesis updated for a future phase: **Comparison Candidate view should render a caveat-count badge next to every `price_ratio` whenever the underlying review carries any caveat, regardless of usability label.** Not implemented in Phase 8; recorded for future work.

### Revised — pack-size parser should fail loudly on unknown forms when expanding country scope

Current behaviour: an unrecognised pack-size pattern returns `None` and the candidate generator emits a `schema_mismatch` anomaly. This is correct. But the *test fixture coverage* for new countries should explicitly include at least one row whose `pack_size` differs from existing patterns, to force the failure mode into review during onboarding rather than during use. Recorded in `decisions/` for future phases as a country-onboarding checklist item.

### Revised — the working comparison vocabulary is too narrow for the PL case

PL publishes `cena_hurtowa` (wholesale price) which mapped to `pharmacy_purchase_price`. Comparing PL to FR/IE manufacturer prices requires either:
1. an explicit policy-supported derivation that subtracts a wholesale margin (currently not implemented; would require Polish wholesale-margin regulation as a source);
2. a separate vocabulary category that better describes the regulatory shape;
3. a permanent caveat that anchors the comparison and acknowledges the bridge.

For now option 3 is the working approach; the system *correctly* refuses to produce candidates and the Comparison Candidate report `candidate-summary.md` records the skip with a reason. This was originally listed as "working hypothesis open" in `comparison-vocabulary.md`; the validation case confirms the vocabulary's coarseness is real friction, not a hypothetical concern.

## Design changes implemented in Phase 8

None. The validation pass is *non-mutating*: it walks existing artifacts, observes friction, and records observations. Frictions worth design changes are noted above and will be implemented in subsequent phases or specific decisions; nothing is silently rewritten as a result of this validation.

## Verifications performed

| Check | Result |
|-------|--------|
| Every link in the chain resolves | ✓ 16/16 |
| File hashes match manifest values | ✓ both sides |
| Caveats reach review assessment | ✓ 4/4 |
| `price_ratio` reproducible from canonical price + derivation rules | ✓ FR 2.10/(30·500) ≈ 0.000140; IE 2.85/(30·500) ≈ 0.000190; ratio ≈ 0.7368 |
| UI explains why fields are compatible | ✓ Comparison Candidate view shows shared `comparison_category=manufacturer_price` and identity-match dimensions |
| Audit Trail bilingual labels | ✓ — labels switch EN ↔ 中文; IDs and source URLs remain canonical |

## Conclusion

The system passes its first end-to-end validation for the simplest legitimate case (same-currency, same-category, single-ingredient, common-strength). The two-gear rule, traceability invariants, hard exclusions, and caveat propagation behave as the charter and specs require. Real frictions surfaced (caveat-density visibility, vocabulary coarseness for PL) and are recorded as future-work items rather than retrofitted into this validation pass.

The four working hypotheses above remain working — none has been promoted to a stable commitment; none has been refuted. They will be tested again in subsequent validation cases that exercise the frictions this one deliberately avoided.
