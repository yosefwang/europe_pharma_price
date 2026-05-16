# Canonical Price Record

A **canonical price record** is a typed, structured representation of a single medicine's price as published by a national authority. It maps raw fields to a known schema but preserves the original values — transformations (per-unit, VAT-exclusive) are separate derivation rules.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` (UUID) | Unique identifier |
| `raw_record_id` | `str` (UUID) | Reference to the raw record |
| `source_document_id` | `str` (UUID) | Transitive reference to source |
| `country_code` | `str` (ISO 3166-1 alpha-2) | Country |
| `snapshot_date` | `date` | The effective date of this price observation |
| `product_name` | `str` | Product name as published |
| `inn` | `str` (nullable) | International Nonproprietary Name |
| `atc_code` | `str` (nullable) | ATC classification code |
| `strength` | `str` | Strength as published (e.g., "500mg") |
| `dosage_form` | `str` | Dosage form as published |
| `pack_size` | `str` | Pack size as published |
| `price_amount` | `Decimal` | The numeric price value |
| `price_currency` | `str` (ISO 4217) | Currency code |
| `price_type` | `str` | National price field name (as published) |
| `price_includes_vat` | `bool` (nullable) | Whether VAT is included |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `manufacturer` | `str` | Marketing authorisation holder |
| `national_product_code` | `str` | Country-specific product identifier |
| `route_of_administration` | `str` | Route (EDQM standard term preferred) |
| `unit_of_measure` | `str` (UCUM) | Unit for strength |
| `notes` | `str` | Any relevant notes from the source |

## Invariants

- `price_amount` must never be bare: always accompanied by `price_currency` and `snapshot_date`
- `price_currency` must be a valid ISO 4217 code
- `snapshot_date` must be explicit — no inferred dates
- `raw_record_id` must reference an existing raw record
- No transformed values in this record — use derivation rules for unit conversions, VAT adjustments

## Dependencies

- Raw Record (parent)
- Source Document (transitive)

## Depended On By

- Comparison Candidate (uses canonical records from two countries)
- Derivation Rule (transforms canonical values)
- Data Profile (assesses field completeness)
