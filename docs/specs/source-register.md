# Source Register

The **source register** is the authoritative list of all known pricing data sources across in-scope countries. Each entry describes where a source lives, what it contains, and its current capture status.

## Purpose

- Enumerate all known national pricing publication endpoints
- Track capture status (registered → captured → verified)
- Record robots.txt/ToS compliance decisions
- Identify manual-refresh sources that cannot be automated

## Registry Entry Fields

| Field | Type | Description |
|-------|------|-------------|
| `source_id` | `str` (UUID) | Unique identifier |
| `country_code` | `str` (ISO 3166-1 alpha-2) | Country |
| `source_name` | `str` | Human-readable name (e.g., "PCRS Reimbursement List") |
| `source_url` | `str` (URL) | Publication endpoint |
| `source_type` | `str` (enum: `excel`, `csv`, `pdf`, `html`, `api`, `other`) | Format of published data |
| `update_frequency` | `str` (enum: `daily`, `weekly`, `monthly`, `quarterly`, `annual`, `irregular`, `unknown`) | How often the source is updated |
| `fetch_method` | `str` (enum: `automated`, `manual`) | Whether capture can be automated |
| `robots_txt_compliant` | `bool` | Whether automated fetch respects robots.txt |
| `tos_reviewed` | `bool` | Whether terms of service have been reviewed |
| `tos_permits_research` | `bool` (nullable) | Whether ToS permits academic research use |
| `manual_refresh_reason` | `str` (nullable) | Why manual fetch is required (if applicable) |
| `registered_at` | `datetime` (UTC) | When this source was added to the register |
| `registered_by` | `str` | Who registered it |
| `notes` | `str` (nullable) | Additional context |

## Source States

```
registered → captured → hash_verified
                ↓
         hash_mismatch (requires investigation)

registered → pending_manual_refresh (manual sources)
registered → blocked (robots.txt or ToS prohibits)
```

- **registered**: source is known but no snapshot exists yet
- **captured**: at least one snapshot has been taken
- **hash_verified**: captured file hash matches manifest
- **hash_mismatch**: captured file hash does not match (anomaly)
- **pending_manual_refresh**: source requires manual download
- **blocked**: robots.txt or ToS prohibits automated capture

## Invariants

- Every source in the register must have `robots_txt_compliant` and `tos_reviewed` set before first capture
- A source with `tos_permits_research = false` cannot be captured
- A source with `fetch_method = manual` enters `pending_manual_refresh` until a human provides the file
- Source IDs are stable — never reused, never changed

## File Location

The source register lives at `data/sources/register.json` as a JSON array of registry entries.
