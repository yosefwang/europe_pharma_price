# Decision 008 — Policy semantics are structured policy-agent decisions

**Date:** 2026-05-23
**Status:** accepted
**Supersedes/amends:** 007-multinational-price-lane-substrate.

## Context

The multinational price-lane substrate originally normalised VAT/margin state
from `PolicyInterpretation.includes_vat` and free-text `includes_margin`.
That was useful as a bridge, but it placed semantic adjudication in the
comparison layer. For new countries, the intended workflow is different:
country delegates describe published data, while policy intelligence agents
read regulation and source evidence, decide what each price field means, and
write structured decisions. Comparison should consume those decisions and
cross-check them against data profiles; it should not reinterpret prose.

## Decision

`PolicyInterpretation` now carries a required `semantics` object. This object
is the machine-readable output of the policy intelligence layer and includes:

- `comparison_category`
- `vat_position`
- `margin_position`
- `derivation_kind`
- `derivation_basis`
- `notes`

The comparison layer uses `policy.semantics` as the authoritative source for
lane keys, VAT caveats, and observed-vs-derived provenance. It must not infer
these values from `interpretation_text`, `includes_margin`, or `price_type`
strings. Legacy explanatory fields may remain for human readability, but they
are not control-plane inputs.

## Consequences

Adding a country now requires the policy agent to emit structured semantics for
every comparable price field. Missing or inconsistent semantics fail policy
loading instead of silently falling back to string matching. This raises the bar
for country onboarding, but it keeps the policy-data dual gear explicit and
stable.

Existing IE, PL, CZ, ES, IT, PT, and historical FR policy interpretation files
have been backfilled with explicit semantics. Future policy updates should
write these fields directly rather than relying on backfill.

## References

- `src/eu_pharma_price/schemas/policy.py`
- `src/eu_pharma_price/normalization/price_lanes.py`
- `src/eu_pharma_price/comparison/generator.py`
- `data/policy/*/policy_interpretations.jsonl`
- `docs/schemas/policy-interpretation.md`
- `docs/specs/policy-interpretation.md`
