# Country Delegate

A **country delegate** owns one country's pricing publication regime end-to-end: fetching, parsing, normalising into canonical records, and surfacing anomalies. Delegates operate in isolation — they never read another country's data.

## Responsibilities

1. **Locate fields** in the country's published files (column names, sheets, sections).
2. **Parse sources** into raw records that preserve published values verbatim.
3. **Produce canonical records** by mapping raw fields to the canonical schema.
4. **Preserve raw-to-canonical lineage** — every canonical record links back to its raw record(s) by ID.
5. **Describe locally what each price field means** in country-local terms (without assigning cross-country meaning).
6. **Surface anomalies** when raw fields don't fit the canonical schema cleanly.

## Boundaries

- A delegate **must not** read another country's data, snapshots, or canonical artifacts.
- A delegate **must not** assign cross-country meaning. The mapping from a country's price field to a comparison category is the responsibility of Policy Intelligence (Phase 4), not the delegate.
- A delegate **must not** silently transform numeric values. All transformations must reference a derivation rule (Phase 5).
- A delegate operates only on data from `data/raw/<country_code>/<snapshot_date>/` and emits artifacts under `data/canonical/<country_code>/<snapshot_date>/`.

## Inputs

- Source documents from `data/raw/<country_code>/<snapshot_date>/` (with verified manifests)
- Country-specific parsing configuration (columns, encodings, separators)

## Outputs

| Path | Format | Description |
|------|--------|-------------|
| `data/canonical/<cc>/<date>/prices.parquet` | Parquet | Canonical price records |
| `data/canonical/<cc>/<date>/raw_to_canonical.parquet` | Parquet | Lineage: which raw record(s) produced each canonical record |
| `reports/delegate/<cc>/<date>.md` | Markdown | Human-readable summary of the run |
| `reports/anomalies/<cc>/<date>.md` | Markdown | Anomaly reports for this run (when applicable) |

## Delegate States

```
not_started → source_captured → parsed → canonicalized
                                    ↓
                              anomaly_reported
                                    ↓
                              needs_review
```

| State | Meaning |
|-------|---------|
| `not_started` | No snapshot has been processed |
| `source_captured` | A snapshot exists in `data/raw/` |
| `parsed` | Raw records have been extracted from the source |
| `canonicalized` | Canonical price records have been produced |
| `anomaly_reported` | One or more fields could not be mapped cleanly |
| `needs_review` | Manual review required before publishing |

## Local Field Description

Each delegate produces a **local field description** (part of the delegate report) that names every price-relevant field in the source and explains what it represents in country-local terms. This is *informational* — it does not establish comparability. Policy Intelligence consumes these descriptions later.

Example (Ireland):

> `EX_FACTORY_PRICE_EUR`: the manufacturer's price excluding VAT and pharmacy/wholesale margin, as published in the PCRS reimbursement list. The list also contains a `RETAIL_PRICE_EUR` column (the price paid by the patient at retail) but it is not reproduced in this fixture.

## Identity

The delegate is the only component that knows the structure of a country's source files. If the source format changes, only that country's delegate is affected.
