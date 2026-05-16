# Comparison Candidate

A **comparison candidate** is a proposed price comparison between two countries for a specific molecule. It is the central artifact of the system — the point where both gears (policy interpretation + data profile) must align on both sides before a comparison is permitted.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` (UUID) | Unique identifier |
| `molecule_inn` | `str` | International Nonproprietary Name |
| `atc_code` | `str` | ATC classification |
| `strength` | `str` | Strength being compared |
| `dosage_form` | `str` | Dosage form being compared |
| `country_a_code` | `str` (ISO 3166-1 alpha-2) | First country |
| `country_b_code` | `str` (ISO 3166-1 alpha-2) | Second country |
| `country_a_record_id` | `str` (UUID) | Canonical price record for country A |
| `country_b_record_id` | `str` (UUID) | Canonical price record for country B |
| `country_a_policy_id` | `str` (UUID) | Policy interpretation for country A |
| `country_b_policy_id` | `str` (UUID) | Policy interpretation for country B |
| `country_a_profile_id` | `str` (UUID) | Data profile for country A |
| `country_b_profile_id` | `str` (UUID) | Data profile for country B |
| `comparison_category` | `str` | The shared category being compared |
| `snapshot_date` | `date` | Effective date of comparison |
| `created_at` | `datetime` (UTC) | When this candidate was generated |
| `created_by` | `str` | Agent or process identifier |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `derivation_rule_a_id` | `str` (UUID, nullable) | If country A value was transformed |
| `derivation_rule_b_id` | `str` (UUID, nullable) | If country B value was transformed |
| `identity_match_method` | `str` | How product identity was established |
| `identity_confidence` | `str` (enum: `exact`, `high`, `medium`, `low`) | Confidence in identity match |
| `price_ratio` | `Decimal` (nullable) | A/B price ratio (if calculable) |
| `normalisation_notes` | `str` | Notes on any normalisation applied |
| `caveats` | `list[str]` | Known limitations of this comparison |

## Invariants

- Both `country_a_policy_id` and `country_b_policy_id` must exist and be current
- Both `country_a_profile_id` and `country_b_profile_id` must exist with `field_exists = true` and `plausibility_assessment != implausible`
- `country_a_code != country_b_code` — no self-comparisons
- `comparison_category` must match on both policy interpretations
- Never compare across different molecules (INN must match)
- Never compare across different routes of administration
- If `derivation_rule_a_id` or `derivation_rule_b_id` is set, the corresponding derivation rule must exist
- `snapshot_date` must be explicit

## Dependencies

- Canonical Price Record (both sides)
- Policy Interpretation (both sides)
- Data Profile (both sides)
- Source Document (transitive, both sides)
- Derivation Rule (when transformed values exist)

## Depended On By

- Review Assessment (evaluates the candidate end-to-end)
