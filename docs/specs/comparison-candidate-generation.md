# Comparison Candidate Generation

This spec defines how the comparison layer takes canonical records, policy interpretations, and data profiles from two countries and produces `ComparisonCandidate` artifacts.

## Two-Gear Rule (binding)

A candidate is created **only when both gears say yes on both sides**:

| Gear | Country A side | Country B side |
|------|----------------|----------------|
| **Policy** | A's price field has a current, non-blocked PolicyInterpretation | B's price field has a current, non-blocked PolicyInterpretation |
| **Data** | A's snapshot has a non-blocked DataProfile for that field | B's snapshot has a non-blocked DataProfile for that field |

Failing any gate aborts candidate creation for that pair. There is no override.

The candidate generator is the place where this rule is enforced operationally. Both gates have already been implemented as `policy.gating.blocks_comparison` and `profile.gating.is_field_blocked`; the generator must call both before constructing a `ComparisonCandidate`.

## Hard Exclusions (binding)

The matcher already enforces (see [identity-matching.md](identity-matching.md)):

- never compare across different molecules (`inn` mismatch)
- never compare across different routes of administration
- never compare across different dosage forms
- never compare combination vs. single-ingredient products

These produce no candidate and no anomaly — pruning is silent.

## Comparison-Category Rule

Both sides' policy interpretations must share the same `comparison_category`. Cross-category comparison (e.g., manufacturer price in country A vs. pharmacy purchase price in country B) is **not** generated automatically. It requires an explicit, policy-supported derivation rule that establishes how to bridge the categories — and the bridging rule itself is a future-phase concern, not Phase 6 scope.

For Phase 6, candidates are only generated when:

```
country_a_policy.comparison_category == country_b_policy.comparison_category
```

If a researcher needs cross-category comparisons later, that is added through a documented decision in `decisions/` and an explicit policy bridge rule.

## Generation Procedure

For each pair of countries (A, B) where A < B alphabetically (no double-counting):

1. Load canonical records, policy interpretations, and data profiles for both sides for the snapshot.
2. Enumerate price lanes per country via `_enumerate_price_lanes()`, which applies the two-gear rule (policy gating + data gating). Observed lanes come from canonical records. Virtual lanes are generated only from current policy `derivation_rules`, and each generated row carries its `DerivationRule` evidence.
3. Match lanes by `comparison_category`. Only same-category lanes generate candidates. Observed and derived lanes may share the same comparable basis when their policy semantics agree; the evidence bundle must preserve whether each side was `observed` or `derived`.
4. For each matched lane pair:
   a. **INN normalization**: Run both sides' raw INNs through `InnNormalizer` (two-layer pipeline: linguistic rules → constrained fuzzy). Rows whose INN cannot be normalized are dropped.
   b. Parse strength and pack size for each row. If unparseable → dropped.
   c. Build INN-blocked index on canonical INN forms for fast lookup.
   d. For each matching INN pair, run `assess_identity()` on form, route, strength, pack size.
   e. For passing pairs, compute per-unit and per-strength-unit prices via `derive_per_unit_price()`.
   f. If currencies differ, apply FX conversion via `convert_currency()` (ECB rates from `data/fx/ecb_rates.jsonl`).
   g. Compute `price_ratio` from the (possibly FX-converted) per-strength-unit prices.
   h. Construct `ComparisonCandidate` with full evidence chain (canonical IDs, policy IDs, profile IDs, derivation rule IDs, FX rule ID) plus ATC code from WHO dictionary.
5. Write candidates to:
   - `data/comparisons/<snapshot_window_id>/candidates.parquet`
   - `data/comparisons/<snapshot_window_id>/evidence_bundle.jsonl`
   - `data/comparisons/<snapshot_window_id>/derivation_rules.jsonl`
6. Write summary to `reports/comparisons/<snapshot_window_id>/candidate-summary.md`

## Candidate ≠ Final Claim

A candidate is a **proposal**. It carries everything Review (Phase 7) needs to assess usability, but it is not itself a published comparison. Candidates that survive review are what reach the substrate; candidates that fail review are recorded but flagged not-for-publication.

The generator does not assign `usability` — that is Review's responsibility.

## Snapshot Date Alignment

Both sides of a candidate must come from snapshots taken close enough in time to be reasonably comparable. The current rule is:

- Snapshots from the same calendar quarter are eligible.
- Snapshots more than one quarter apart are not paired without an explicit override.

This rule is a working hypothesis; it can be relaxed for products with known long stable prices, via a policy interpretation that asserts price stability over a longer period.

## Idempotency and Re-Generation

Re-running the generator on the same snapshot inputs produces the same candidate set (with stable IDs derived deterministically from the input record IDs). Adding a new snapshot to either country produces only new candidates — old ones are not modified.

## Storage Layout

```
data/comparisons/
└── <snapshot_window_id>/
    ├── candidates.parquet         # one row per candidate
    └── evidence_bundle.jsonl      # one line per candidate, full nested evidence
```

The snapshot_window_id is `"<latest_date_in_pair>"` for two-country candidates. When candidates span multiple pairs, separate windows are stored separately.
