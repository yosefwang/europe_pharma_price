# Review Assessment

A **review assessment** is the final quality gate for a comparison candidate. It evaluates the full evidence chain end-to-end and assigns a usability label. No comparison reaches output without passing review.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` (UUID) | Unique identifier |
| `comparison_candidate_id` | `str` (UUID) | The candidate being reviewed |
| `usability` | `str` (enum: `usable`, `usable_with_caveat`, `exploratory`, `not_comparable`) | Final assessment |
| `policy_strength` | `str` (enum: `strong`, `adequate`, `weak`) | Strength of policy evidence |
| `data_strength` | `str` (enum: `strong`, `adequate`, `weak`) | Strength of data evidence |
| `identity_strength` | `str` (enum: `strong`, `adequate`, `weak`) | Confidence in product identity match |
| `normalisation_strength` | `str` (enum: `strong`, `adequate`, `weak`, `not_applicable`) | Quality of any normalisation |
| `rationale` | `str` | Plain-language explanation of the assessment |
| `reviewed_at` | `datetime` (UTC) | When the review was performed |
| `reviewed_by` | `str` | Reviewer identifier (agent or human) |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `caveats` | `list[str]` | Specific caveats that travel with the comparison |
| `blocking_issues` | `list[str]` | Issues that prevent usability |
| `recommendations` | `list[str]` | Suggested improvements |
| `superseded_by` | `str` (UUID, nullable) | If re-reviewed |
| `human_override` | `bool` | Whether a human overrode the initial assessment |
| `override_rationale` | `str` | Reason for override |

## Invariants

- `comparison_candidate_id` must reference an existing comparison candidate
- `usability = not_comparable` requires at least one entry in `blocking_issues`
- `usability = usable_with_caveat` requires at least one entry in `caveats`
- A review with any `weak` strength dimension cannot be `usable` (only `usable_with_caveat` or lower)
- Reviews are append-only — superseded reviews are preserved

## Dependencies

- Comparison Candidate (the full evidence bundle)

## Depended On By

- Output reports and the queryable substrate (only reviewed candidates appear)
