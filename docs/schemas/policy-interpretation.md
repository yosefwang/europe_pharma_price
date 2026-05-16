# Policy Interpretation

A **policy interpretation** is a typed, sourced reading of what a national price field means and how it relates to fields in other countries. It is one of the two gears required for any comparison (the other being a data profile).

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` (UUID) | Unique identifier |
| `country_code` | `str` (ISO 3166-1 alpha-2) | Country this interpretation covers |
| `price_type` | `str` | The national price field being interpreted |
| `comparison_category` | `str` | Position in the comparison vocabulary (e.g., `manufacturer_price`, `pharmacy_purchase_price`, `public_retail_price`, `payer_reimbursement_price`) |
| `effective_from` | `date` | Start of the period this interpretation covers |
| `effective_to` | `date` (nullable) | End of period (null = still current) |
| `source_references` | `list[str]` | URLs or document IDs supporting this reading |
| `interpretation_text` | `str` | The actual reading in plain language |
| `confidence` | `str` (enum: `high`, `medium`, `low`) | Strength of evidence |
| `authored_at` | `datetime` (UTC) | When this interpretation was produced |
| `authored_by` | `str` | Agent or human identifier |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `superseded_by` | `str` (UUID, nullable) | If revised by a later interpretation |
| `adjudication_notes` | `str` | Notes on conflicting sources |
| `includes_vat` | `bool` (nullable) | Whether the interpreted price field includes VAT |
| `includes_margin` | `str` (nullable) | What margins are included |
| `caveats` | `list[str]` | Known limitations of this mapping |

## Invariants

- Every interpretation must have at least one source reference
- `comparison_category` must be from the project's comparison vocabulary
- `effective_from` must be explicit — no undated interpretations
- Superseded interpretations are never deleted, only marked
- An interpretation is a decision, not an assertion — it can be wrong and revisable

## Dependencies

- Source Document (the policy documents cited)

## Depended On By

- Comparison Candidate (requires policy interpretations on both sides)
