# Canonical Record Normalization

This spec defines how a country delegate maps raw fields into a canonical price record. The goal is structural normalisation only — values are preserved as published, never silently transformed.

## Normalisation Steps

### 1. Field mapping (structural only)

Each delegate maintains a mapping from source field names to canonical field names:

```yaml
# Ireland (PCRS-style)
PRODUCT_NAME -> product_name
STRENGTH -> strength
DOSAGE_FORM -> dosage_form
PACK_SIZE -> pack_size
EX_FACTORY_PRICE_EUR -> price_amount
MANUFACTURER -> manufacturer
PRODUCT_CODE -> national_product_code
```

The canonical field `price_type` is set to the source field name (e.g., `EX_FACTORY_PRICE_EUR`) — this preserves what kind of regulated price the figure represents.

### 2. Type coercion

| Source value | Canonical type | Rule |
|--------------|----------------|------|
| Numeric string in price column | `Decimal` | Parse with country-specific decimal separator |
| Date string | `date` | ISO 8601 only; reject ambiguous formats |
| Pack size string | `str` (preserved) | No interpretation — "28" stays "28", "30 x 10ml" stays "30 x 10ml" |

### 3. Currency assignment

Currency is **never** inferred. It must be explicitly declared in the delegate's configuration:

```yaml
ie:
  default_currency: EUR
pl:
  default_currency: PLN
fr:
  default_currency: EUR
```

If a source document contains multiple currencies (rare), the delegate must surface this as an anomaly and abort.

### 4. Snapshot date

The canonical record's `snapshot_date` is the snapshot directory name (e.g., `2024-06-15`), not any date inside the file. This is the date the delegate captured the source as effective.

### 5. INN and ATC enrichment (optional)

If the source includes INN or ATC fields, they are copied verbatim. The delegate does **not** look up INN/ATC from external systems — that's enrichment work for a later phase if needed.

## What is NOT canonicalisation

- **No per-unit conversion.** Pack sizes stay as-published. Per-unit prices come from derivation rules (Phase 5).
- **No VAT adjustment.** If the source publishes VAT-inclusive prices, that's recorded in `price_includes_vat` — not silently stripped.
- **No currency conversion.** PLN stays PLN; EUR stays EUR.
- **No identifier resolution across countries.** A national product code is preserved, but the delegate doesn't try to find its counterpart in another country.
- **No deduplication.** If the source has duplicate rows, the delegate emits duplicate canonical records (and may surface an anomaly).

## Lineage

For each canonical record, the delegate writes a row to `raw_to_canonical.parquet`:

| canonical_id | raw_record_id | source_document_id | snapshot_date |
|--------------|---------------|--------------------|---------------|
| `<uuid>` | `<uuid>` | `<uuid>` | `2024-06-15` |

A canonical record is permitted to derive from multiple raw records (e.g., when a source publishes one row per pack size and the delegate consolidates). When this happens, multiple rows in `raw_to_canonical.parquet` share the same `canonical_id`.

## Anomaly Triggers

A delegate emits an anomaly report (rather than producing a canonical record) when:

- A required canonical field has no source field that maps to it
- A source field contains data that cannot be type-coerced cleanly
- The same row appears multiple times with conflicting values
- The currency declared in delegate config does not match a currency hint in the source
- A new column appears in the source that the delegate's mapping does not cover

Anomaly reports follow the schema in [docs/schemas/anomaly-report.md](../schemas/anomaly-report.md).
