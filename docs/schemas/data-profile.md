# Data Profile

A **data profile** is an assessment of whether a policy-named price field actually exists in the data, is populated, and behaves plausibly for a given snapshot. It is the second gear required for any comparison (alongside a policy interpretation).

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` (UUID) | Unique identifier |
| `country_code` | `str` (ISO 3166-1 alpha-2) | Country |
| `snapshot_date` | `date` | Which snapshot is being profiled |
| `price_type` | `str` | The national price field being assessed |
| `field_exists` | `bool` | Whether the field appears in the data |
| `population_rate` | `float` (0.0–1.0) | Fraction of records with non-null values |
| `plausibility_assessment` | `str` (enum: `plausible`, `suspect`, `implausible`) | Distribution assessment |
| `record_count` | `int` | Total records in the snapshot for this field |
| `assessed_at` | `datetime` (UTC) | When this profile was generated |
| `assessed_by` | `str` | Agent or human identifier |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `min_value` | `Decimal` | Minimum observed value |
| `max_value` | `Decimal` | Maximum observed value |
| `median_value` | `Decimal` | Median value |
| `null_count` | `int` | Number of null/missing values |
| `outlier_count` | `int` | Number of statistical outliers |
| `distribution_notes` | `str` | Human-readable distribution summary |
| `comparison_to_prior` | `str` | Drift assessment vs. previous snapshot |
| `issues` | `list[str]` | Specific issues found |

## Invariants

- `population_rate` must be between 0.0 and 1.0 inclusive
- `snapshot_date` must reference an existing snapshot partition
- A profile with `field_exists = false` must have `population_rate = 0.0`
- Profiles are per-snapshot, per-field — never aggregated across dates

## Dependencies

- Canonical Price Record (the data being profiled)
- Policy Interpretation (names which field to look for)

## Depended On By

- Comparison Candidate (requires data profiles on both sides)
