# Source Document

A **source document** is the immutable record of a file fetched from a national pricing authority. It is the root of the evidence chain — every downstream artifact traces back to one or more source documents.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` (UUID) | Unique identifier for this source document |
| `country_code` | `str` (ISO 3166-1 alpha-2) | Country of origin |
| `source_url` | `str` (URL) | The URL from which the document was fetched |
| `fetched_at` | `datetime` (UTC, timezone-aware) | When the document was retrieved |
| `file_hash` | `str` (SHA-256) | Hash of the raw file content |
| `file_path` | `str` | Relative path to the stored file in `data/raw/` |
| `media_type` | `str` | MIME type of the document |
| `file_size_bytes` | `int` | Size of the raw file |
| `fetch_method` | `str` (enum: `automated`, `manual`) | How the document was obtained |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | `str` | Human-readable description of content |
| `robots_txt_compliant` | `bool` | Whether fetch respected robots.txt |
| `tos_reviewed` | `bool` | Whether terms of service were reviewed |
| `superseded_by` | `str` (UUID, nullable) | If this document has been replaced |

## Invariants

- `file_hash` must match the actual content at `file_path`
- `fetched_at` must be timezone-aware UTC
- No source document may be modified after creation (append-only)
- `country_code` must be in the project's candidate pool (32 countries)

## Dependencies

None — source documents are root artifacts.

## Depended On By

- Raw Record (extracts structured data from source documents)
