# Identity Matching

This spec defines how the comparison layer decides that two canonical price records — one from each country — refer to comparable products.

Identity matching does **not** establish therapeutic equivalence. Two products with the same INN, strength, route, and form are matched as comparable *for pricing purposes*. The substrate explicitly does not infer that one is clinically substitutable for the other.

## INN Normalization

INN values from different countries may use different linguistic conventions for the same molecule. The matcher uses a two-layer normalization pipeline ([`inn_normalizer.py`](../../src/eu_pharma_price/comparison/inn_normalizer.py)) to map non-English INN variants to English canonical forms:

1. **Layer 1 (Linguistic rules)**: Language-specific suffix-stripping rules (e.g., Latin `-um` → `""`, `acidum X-um` → `X-ic acid`). Deterministic, zero false-positive risk. Each rule carries provenance.

2. **Layer 2 (Constrained fuzzy matching)**: Safe fallback against the WHO ATC-DDD dictionary (~6,000 English INN names). Constrained by: first-character match, Levenshtein distance ≤ 2, length ratio 80-120%, single-winner rule. Ambiguous matches are not auto-resolved.

Normalization happens in the comparison layer, not delegates. Raw INN strings are preserved on canonical records. The normalized (canonical) INN is used for identity matching. The normalization method (`exact`/`rule_based`/`fuzzy`) is recorded in the `identity_match_method` field.

When both sides receive ATC codes from the WHO dictionary, ATC codes serve as cross-validation: if canonical INNs differ but ATC codes match exactly, the candidate is accepted with `identity_confidence=medium`.

See [decisions/006](../../decisions/006-inn-normalization-two-layer.md) for the full rationale, design, and scaling plan.

## Hard Exclusions (binding)

The following exclusions are stable commitments from the project charter (§6). The matcher refuses any candidate that violates any of them:

1. **Never match across different molecules.** INN must be identical **after normalization** (case- and whitespace-normalised canonical form).
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
- Does not look up INN/ATC from external systems at runtime — the WHO ATC-DDD dictionary is committed to the repository as a local snapshot.
- Does not perform unconstrained fuzzy matching — Layer 2 fuzzy matching is bounded by first-char, edit distance ≤ 2, and length-ratio constraints.
- Does not match across molecules even when therapeutic substitution exists in clinical practice. That's a clinical determination, outside the substrate's scope.
- Does not modify raw INN on canonical records — normalization is a comparison-phase operation.
