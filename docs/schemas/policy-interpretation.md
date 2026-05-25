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
| `semantics` | `PolicySemantics` | Structured policy-agent decision consumed by comparison logic |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `superseded_by` | `str` (UUID, nullable) | If revised by a later interpretation |
| `adjudication_notes` | `str` | Notes on conflicting sources |
| `includes_vat` | `bool` (nullable) | Legacy/human-readable VAT note; `semantics.vat_position` is authoritative |
| `includes_margin` | `str` (nullable) | Legacy/human-readable margin note; `semantics.margin_position` is authoritative |
| `derivation_rules` | `list[PolicyDerivationRule]` | Policy-agent lane graph edges that can derive this interpreted price lane from observed national fields |
| `caveats` | `list[str]` | Known limitations of this mapping |

## PolicySemantics

`PolicySemantics` is the AI-native policy-agent output. It is not inferred by
the comparison layer from prose. Every policy interpretation must carry it.

| Field | Type | Description |
|-------|------|-------------|
| `comparison_category` | `str` | Same comparison vocabulary category as the parent interpretation |
| `vat_position` | enum | `vat_inclusive`, `vat_exclusive`, or `vat_unknown` |
| `margin_position` | enum | `no_standard_margins`, `wholesale_margin`, `wholesale_and_pharmacy_margins`, `public_retail_components`, `vat_only`, or `margin_unknown` |
| `derivation_kind` | enum | `observed`, `derived`, or `unknown` |
| `derivation_basis` | `str` (nullable) | Source of the semantic decision, e.g. policy-agent structured adjudication |
| `notes` | `list[str]` | Machine-carried caveats/notes supporting the semantic decision |

## PolicyDerivationRule

`PolicyDerivationRule` records the legally or officially supported edge in a
country's price-lane graph. It is authored by Policy Intelligence and executed
by the comparison layer only after the observed source lane passes data gating.

| Field | Type | Description |
|-------|------|-------------|
| `source_price_type` | `str` | Observed national field consumed by the derivation |
| `target_price_type` | `str` | Derived national lane; must match the parent interpretation's `price_type` |
| `source_category` | `str` (nullable) | Source lane's comparison vocabulary category |
| `target_category` | `str` | Target comparison vocabulary category; must match the parent interpretation |
| `formula_id` | `str` | Deterministic executor key, e.g. `divide_by_one_plus_markup`, `multiply_by_factor`, `tiered_pt_pvp_to_pva` |
| `formula` | `str` | Human-readable formula from the policy source |
| `parameters` | `dict` | Explicit rates, factors, tiers, caps, or fees used by the formula |
| `conditional_parameters` | `list` | Row-level conditions that select parameters, such as IE 12% markup for parenteral rows |
| `legal_basis` | `list[str]` | Statute, regulation, official method, or policy document supporting the edge |
| `confidence` | `str` | Evidence strength for the derivation rule |
| `caveats` | `list[str]` | Limits of the derivation, such as confidential rebates or product-specific exceptions |

## Invariants

- Every interpretation must have at least one source reference
- `comparison_category` must be from the project's comparison vocabulary
- `semantics.comparison_category` must match `comparison_category`
- Every `derivation_rules[].target_price_type` must match the parent `price_type`
- Every `derivation_rules[].target_category` must match the parent `comparison_category`
- `effective_from` must be explicit — no undated interpretations
- Superseded interpretations are never deleted, only marked
- An interpretation is a decision, not an assertion — it can be wrong and revisable

## Dependencies

- Source Document (the policy documents cited)

## Depended On By

- Comparison Candidate (requires policy interpretations on both sides)
