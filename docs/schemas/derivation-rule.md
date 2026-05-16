# Derivation Rule

A **derivation rule** documents a numeric transformation applied to a canonical price value. Every derived value (per-unit price, VAT-exclusive price, currency-converted price) must reference a derivation rule — no silent transformations.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` (UUID) | Unique identifier |
| `rule_type` | `str` (enum: `per_unit`, `vat_exclusive`, `vat_inclusive`, `currency_conversion`, `pack_normalisation`) | Kind of transformation |
| `description` | `str` | Plain-language explanation of the rule |
| `formula` | `str` | Mathematical formula (e.g., `price_amount / pack_size`) |
| `input_fields` | `list[str]` | Field names consumed |
| `output_field` | `str` | Field name produced |
| `effective_from` | `date` | When this rule became applicable |
| `effective_to` | `date` (nullable) | End of applicability (null = current) |
| `source_reference` | `str` | Justification (policy doc, regulation, etc.) |
| `created_at` | `datetime` (UTC) | When this rule was created |
| `created_by` | `str` | Author identifier |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `parameters` | `dict[str, Any]` | Rule-specific parameters (e.g., VAT rate, FX rate) |
| `fx_source` | `str` | For currency conversions: source of exchange rate |
| `fx_date` | `date` | Date of the exchange rate used |
| `superseded_by` | `str` (UUID, nullable) | If replaced by updated rule |
| `country_code` | `str` (nullable) | If rule is country-specific |
| `caveats` | `list[str]` | Known limitations |

## Invariants

- Every derived numeric value in the system must reference a derivation rule
- `formula` must be deterministic — same inputs always produce same output
- For currency conversions: `fx_source` and `fx_date` are mandatory
- Rules are never applied retroactively without explicit audit record
- Parameters (VAT rates, FX rates) are explicit, never implicit

## Dependencies

- Canonical Price Record (input values)
- Source Document (for policy justification references)

## Depended On By

- Comparison Candidate (when transformed values are compared)
