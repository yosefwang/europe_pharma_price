# Decision 007 — Multinational price-lane substrate before pairwise comparison

**Date:** 2026-05-23
**Status:** accepted
**Depends on:** 003-PCRS-reimbursement-price-is-pharmacy-purchase-price; 006-INN-normalization-two-layer.

## Context

The project now has real canonical snapshots for IE, PL, CZ, ES, IT, and PT. IE/PL/CZ were already usable on `main`; ES/PT/IT add countries whose observed publications are mostly public retail or reimbursement-list prices rather than direct manufacturer ex-factory prices.

A naive country-pair generator scales poorly and, more importantly, hides the policy-data question that determines whether two rows are comparable: what exact price concept did each country publish, does it include VAT, does it include wholesale/pharmacy margins, and can a deterministic policy-supported derivation produce a lane with the same meaning?

The project charter requires the dual-gear model: policy interpretation and data/profile evidence must agree before comparison. A cross-country comparison must therefore be assembled from explicit price semantics, not from country-pair special cases.

## Decision

The comparison architecture uses a multinational price-lane substrate before any pairwise or report-level output.

Each country delegate continues to publish local canonical records using the fields and price labels in the national source. The comparison layer then builds indexed price lanes by:

1. applying the data-profile gate for the snapshot;
2. looking up the active `PolicyInterpretation` for each published or derived `price_type`;
3. appending only deterministic policy-supported derived lanes, such as IE/ES/IT/PT ex-factory manufacturer lanes;
4. normalising lane semantics into `(comparison_category, vat_position, margin_position)`;
5. normalising identity dimensions through the existing INN, strength, pack, dosage-form, route, and product-type normalisers;
6. normalising numeric price to per-strength-unit and, when needed, EUR with an auditable FX derivation rule.

A lane is apple-to-apple comparable only when the lane key and identity key align. Observed and derived provenance is retained as evidence but is not itself a blocker: an observed CZ or PL manufacturer ex-VAT lane may compare with a derived IE/ES/IT/PT manufacturer ex-VAT lane when the policy interpretation and derivation rule support that meaning.

The project must not materialise a full country-pair matrix as the primary integration mechanism. Pairwise candidates or reports may be generated later as views over the lane substrate for a specific cohort, molecule, lane key, or review question.

## Consequences

This makes ES/PT/IT integration part of the same global comparison system as IE/PL/CZ. It prevents accidental comparison between superficially similar but semantically different prices, such as IE VAT-exclusive pharmacy purchase price and PL VAT-inclusive wholesale price.

It also makes derived prices auditable: a derived lane carries source record and derivation rule evidence, while the canonical national publication remains unchanged.

The cost is that every country price field needs a maintained policy interpretation for VAT and margin state. If a country publishes a price whose VAT or margin components cannot be established, that lane remains blocked or marked unknown rather than being forced into a comparison.

The first implemented substrate covers IE, PL, CZ, ES, IT, and PT and validates atorvastatin 20 mg, olanzapine 10 mg, and pantoprazole 40 mg as six-country manufacturer ex-VAT comparison cohorts.

## References

- `src/eu_pharma_price/normalization/price_lanes.py`
- `src/eu_pharma_price/comparison/lane_index.py`
- `src/eu_pharma_price/comparison/price_lane_derivation.py`
- `tests/test_price_lane_substrate.py`
- `docs/specs/comparison-vocabulary.md`
- `docs/specs/normalisation-rules.md`
