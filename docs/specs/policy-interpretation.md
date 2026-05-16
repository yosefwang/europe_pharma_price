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

## Storage

Interpretations are written to `data/policy/<country>/policy_interpretations.jsonl` — one JSON object per line, each conforming to the policy interpretation schema.

Reports are written to `reports/policy/<country>.md` — human-readable summary listing every interpretation, citation, and caveat.

## Gating Rule

No comparison candidate may be built from a national field that lacks a current policy interpretation. The comparison layer (Phase 6) enforces this by joining canonical records to interpretations on `(country_code, price_type)` and rejecting any row that does not match.

A field with `confidence = low` does not block candidate construction, but the resulting candidate inherits `policy_strength = weak` in its review assessment, which prevents `usable` status (see [review-assessment.md](../schemas/review-assessment.md)).
