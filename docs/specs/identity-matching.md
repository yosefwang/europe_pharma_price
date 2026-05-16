# Identity Matching

This spec defines how the comparison layer decides that two canonical price records — one from each country — refer to comparable products.

Identity matching does **not** establish therapeutic equivalence. Two products with the same INN, strength, route, and form are matched as comparable *for pricing purposes*. The substrate explicitly does not infer that one is clinically substitutable for the other.

## Hard Exclusions (binding)

The following exclusions are stable commitments from the project charter (§6). The matcher refuses any candidate that violates any of them:

1. **Never match across different molecules.** INN must be identical (case- and whitespace-normalised).
2. **Never match across different routes of administration.** A tablet and an injection are never comparable.
3. **Never match across different dosage forms.** Even within the same route (oral tablet vs. oral capsule), the matcher does not silently bridge.
4. **Never infer therapeutic equivalence across distinct ingredients.** A single-ingredient and a combination product are not matched.

A row that violates any hard exclusion is dropped — no candidate is produced. The matcher does not emit anomaly reports for hard-exclusion drops; that pruning is expected and noisy.

## Soft Match Dimensions

Within the hard exclusions, the matcher scores a candidate pair on:

| Dimension | Required | Description |
|-----------|----------|-------------|
| `inn` | yes | International Nonproprietary Name |
| `dosage_form` | yes | Normalised dosage form (EDQM standard term preferred when available) |
| `route_of_administration` | inferred from form | When `route_of_administration` is null, the matcher infers conservatively from `dosage_form` |
| `strength_per_unit` | yes (after normalisation) | The strength of one administered unit, computed from `strength` |
| `pack_size_units` | yes (after normalisation) | Number of administered units per pack, from `pack_size` |
| `national_product_code` | no | Different countries use different codes (CIP13, EAN, PCRS) — these are not directly cross-referenceable |

`strength_per_unit` and `pack_size_units` are produced by the strength/pack parser ([normalisation-rules.md](normalisation-rules.md)) and carry their own DerivationRule provenance.

## Identity Confidence

Each match is assigned a confidence:

- **`exact`** — INN, form, route, strength_per_unit (in same UCUM unit), and pack_size_units all match exactly.
- **`high`** — INN, form, route, and strength_per_unit match; pack_size_units differ but per-unit normalisation makes the comparison meaningful.
- **`medium`** — INN, route, strength_per_unit match, but form differs in a way that pricing literature commonly treats as comparable (e.g., immediate-release vs. delayed-release of the same molecule). This requires explicit policy support.
- **`low`** — INN matches, but at least one other dimension is uncertain. Candidate generated but reaches review with `identity_strength = weak`.

Anything below `low` is dropped, not generated.

## Tie-Breaking and Multiple Matches

When a single product in country A maps to multiple products in country B (different manufacturers, different brand names, identical INN/form/strength), the matcher emits **one candidate per matched pair**. Aggregation across brands is not the matcher's job; downstream review or analysis decides whether to aggregate.

## What Identity Matching Does NOT Do

- Does not modify any numeric value.
- Does not look up INN/ATC from external systems.
- Does not perform fuzzy matching on product names — matches happen on parsed structured fields, not on `product_name` strings.
- Does not match across molecules even when therapeutic substitution exists in clinical practice. That's a clinical determination, outside the substrate's scope.
