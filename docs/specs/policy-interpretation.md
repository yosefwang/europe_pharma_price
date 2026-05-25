# Policy Interpretation

A **policy interpretation** is a typed, sourced reading of what a national price field means and how it fits into the shared comparison vocabulary. Policy Intelligence (this phase) produces interpretations; the Country Delegate (Phase 3) does not.

## Why interpretation is separate from the delegate

The delegate knows the structure of a country's published files; it does *not* know how those fields fit into a cross-country comparison vocabulary. That mapping is a policy decision based on regulation, official guidance, and pricing studies — not file structure.

Separating these layers means:

- File-format changes affect only the delegate.
- Vocabulary refinement or re-adjudication affects only Policy Intelligence.
- A policy interpretation can be revised without re-running parsing.

## Required Fields

See [docs/schemas/policy-interpretation.md](../schemas/policy-interpretation.md) for the canonical schema. The interpretation produced in this phase carries every required field:

- `country_code`, `price_type` — identify which national field this interpretation covers
- `comparison_category` — the entry in the shared vocabulary
- `effective_from`, `effective_to` — the period this reading applies to
- `source_references` — at least one URL or document ID supporting the reading
- `interpretation_text` — plain-language reading
- `semantics` — structured policy-agent decision that records VAT position,
  margin position, derivation kind, and comparable lane semantics
- `derivation_rules` — for derived lanes, structured policy-agent decisions
  that describe how to derive this lane from observed national fields
- `confidence` — `high`, `medium`, or `low`
- `authored_at`, `authored_by` — provenance
- `caveats` — known limitations

## Source Reference Discipline

A policy interpretation must cite at least one **official policy source**. Acceptable kinds:

- Government regulation, statutory instrument, ministerial decree
- Pricing-authority guidance documents
- Published reimbursement methodology
- Peer-reviewed pharmacoeconomic literature describing the regime

Marketing material, press releases without citation, and commercial databases are not sufficient as the *only* source.

## Adjudication

When sources conflict (e.g., a regulation says one thing, a methodology document says another), Policy Intelligence records the conflict and adjudicates:

- The more authoritative source wins (regulation > methodology > commentary).
- The losing reading is recorded in `adjudication_notes` so future reviewers see what was considered.
- If sources cannot be reconciled cleanly, `confidence` is `low` and the interpretation is flagged for human review.

## What Policy Interpretation Does NOT Do

- **Does not modify any numeric value.** Mapping a field to a category never changes the price.
- **Does not perform unit or currency conversions.** Those are derivation rules (Phase 5).
- **Does not match products across countries.** That's the comparison layer's job.
- **Does not decide usability.** That's the Review layer (Phase 7).
- **Does not leave lane semantics to the comparison layer.** Policy
  Intelligence must emit structured `semantics`; prose fields such as
  `interpretation_text` and `includes_margin` are explanatory evidence, not
  machine-control inputs.

## Policy-Derived Lane Graph

Policy Intelligence must make a best-effort attempt to reconstruct comparable
price lanes when official law, regulation, or methodology gives a stable
formula. The output is a country-local price-lane graph:

```
manufacturer_price
  + wholesale markup
    -> pharmacy_purchase_price
      + pharmacy margin + VAT + fees
        -> public_retail_price
```

Edges can also be executed in reverse when the policy rule explicitly supports
the reverse formula. For example, IE publishes `Reimbursement Price` as an
observed pharmacy-purchase lane, but S.I. 639/2019 supplies the statutory
wholesale markup. Policy Intelligence therefore records a derivation edge from
`Reimbursement Price` to `ex-factory (derived)`, and comparison may include IE
on a manufacturer-price basis while marking the lane as `derived`.

The comparison layer may execute only the structured `derivation_rules`
attached to a policy interpretation. It must not derive prices from prose,
country code, or hard-coded assumptions.

## Storage

Interpretations are written to `data/policy/<country>/policy_interpretations.jsonl` — one JSON object per line, each conforming to the policy interpretation schema.

Reports are written to `reports/policy/<country>.md` — human-readable summary listing every interpretation, citation, and caveat.

## Gating Rule

No comparison candidate may be built from a national field that lacks a current policy interpretation. The comparison layer (Phase 6) enforces this by joining canonical records to interpretations on `(country_code, price_type)` and rejecting any row that does not match.

The current policy interpretation must include `semantics`. The comparison
layer consumes `semantics.comparison_category`, `semantics.vat_position`,
`semantics.margin_position`, and `semantics.derivation_kind` directly. It must
not infer these values from policy prose or margin descriptions.

Derived lane construction additionally requires a current policy interpretation
whose `derivation_rules` identify the observed source field, target lane,
formula, parameters, legal basis, confidence, and caveats. Missing derivation
rules mean no virtual lane is generated, even if older code has a country-level
formula.

A field with `confidence = low` does not block candidate construction, but the resulting candidate inherits `policy_strength = weak` in its review assessment, which prevents `usable` status (see [review-assessment.md](../schemas/review-assessment.md)).
