# Anomaly Report

An **anomaly report** surfaces a finding that does not fit the system's current assumptions. It is a first-class output — any agent may produce one when it encounters something unexpected. The agent surfaces; it does not act.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` (UUID) | Unique identifier |
| `country_code` | `str` (ISO 3166-1 alpha-2) | Country where the anomaly was found |
| `anomaly_type` | `str` (enum: `schema_mismatch`, `distribution_outlier`, `category_ambiguity`, `identifier_conflict`, `source_inconsistency`, `policy_gap`, `other`) | Classification |
| `severity` | `str` (enum: `critical`, `high`, `medium`, `low`) | Impact assessment |
| `title` | `str` | Short description |
| `description` | `str` | Detailed explanation of what was found |
| `evidence` | `list[str]` | References to supporting artifacts (IDs or URLs) |
| `reported_at` | `datetime` (UTC) | When the anomaly was detected |
| `reported_by` | `str` | Agent or human identifier |
| `status` | `str` (enum: `open`, `under_review`, `resolved`) | Current status |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `affected_records` | `list[str]` (UUIDs) | Records impacted by this anomaly |
| `resolution` | `str` (enum: `accommodate`, `exempt`, `exclude`, `accept_with_caveat`, nullable) | How it was resolved |
| `resolution_notes` | `str` | Explanation of resolution decision |
| `resolved_at` | `datetime` (UTC, nullable) | When resolved |
| `resolved_by` | `str` (nullable) | Who resolved it |
| `decision_id` | `str` (nullable) | Reference to decision record in `decisions/` |

## Invariants

- `evidence` must contain at least one reference
- `status = resolved` requires `resolution` to be set
- Anomaly reports are never deleted — they are resolved or remain open
- Resolution decisions must be recorded in `decisions/` for `critical` and `high` severity

## Dependencies

- Any artifact that triggered the anomaly

## Depended On By

- Human review process (anomalies route to humans for decision)
- Decision records in `decisions/`
