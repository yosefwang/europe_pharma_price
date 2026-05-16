# Raw Record

A **raw record** is a single structured row extracted verbatim from a source document. It preserves the exact field names, values, and structure as published — no interpretation, no normalisation.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` (UUID) | Unique identifier |
| `source_document_id` | `str` (UUID) | Reference to the source document |
| `country_code` | `str` (ISO 3166-1 alpha-2) | Country of origin |
| `extracted_at` | `datetime` (UTC) | When extraction occurred |
| `row_index` | `int` | Position in the source (for reproducibility) |
| `raw_fields` | `dict[str, Any]` | The verbatim key-value pairs as published |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `sheet_name` | `str` | For multi-sheet documents |
| `extraction_method` | `str` | Parser used (e.g., `pandas_excel`, `pdf_tabula`) |
| `extraction_notes` | `str` | Any issues encountered during extraction |

## Invariants

- `source_document_id` must reference an existing source document
- `raw_fields` must never be modified after creation
- No interpretation or transformation applied — values are as-published
- Field names in `raw_fields` are preserved exactly as they appear in the source

## Dependencies

- Source Document (parent)

## Depended On By

- Canonical Price Record (normalises raw records into typed fields)
