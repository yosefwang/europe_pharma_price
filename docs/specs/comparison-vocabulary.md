# Comparison Vocabulary

The comparison vocabulary names *what kind of regulated price* a national field represents, so comparisons happen between things of compatible kind.

This vocabulary is the project's current **working hypothesis**. National pricing regimes may straddle these categories, fall outside them, or demand different cuts entirely — that is a finding to feed back through anomaly reports, not a problem to silence.

## Stable Principles (binding)

- **No category is privileged.** The system does not prefer any one kind of price; it does not require every country to map to a specific one; it does not silently bridge across categories.
- **Mappings are decisions.** Each national field's mapping to a category is a policy interpretation with provenance, an effective-date window, and an adjudication record. It can be wrong and revisable.
- **Hard exclusions.** Never compare across different molecules, different routes of administration, or therapeutically substitutable but distinct ingredients.

## Categories (working hypothesis)

| ID | Label (EN) | Label (中文) | Description |
|----|-----------|-------------|-------------|
| `manufacturer_price` | Manufacturer-side price | 厂商端价格 | Price the marketing authorisation holder receives, before wholesale and pharmacy margins, before any consumption tax (VAT, sales tax). Examples: ex-factory price, prix fabricant hors taxes. |
| `pharmacy_purchase_price` | Pharmacy purchase price | 药店采购价 | Price the pharmacy pays to acquire the product, including wholesale margin if applicable, but typically before pharmacy margin and VAT. Examples: cena hurtowa (PL), prix grossiste. |
| `public_retail_price` | Public retail price | 公开零售价 | Price the patient or public payer pays at point of dispensing, including pharmacy margin and VAT. Examples: prix public TTC, retail price. |
| `payer_reimbursement_price` | Payer reimbursement price | 支付方报销价 | Amount a public payer reimburses for a product, which may differ from any of the above (e.g., reference price, capped reimbursement). |
| `unmapped_price_concept` | Unmapped price concept | 未映射价格概念 | A national price field that does not fit any of the above categories cleanly. Such fields cannot be compared across countries; they are recorded so the gap is visible. |
| `not_comparable` | Not comparable | 不可比较 | A field that has been adjudicated as unsuitable for cross-country comparison for reasons other than missing category (e.g., legal-confidentiality publication that lacks supporting metadata). |

## Mapping Examples (working)

These are illustrative; the actual mappings live in `data/policy/<country>/policy_interpretations.jsonl`.

### Ireland

- `EX_FACTORY_PRICE_EUR` → `manufacturer_price`
  - Source: PCRS reimbursement methodology; FASPM
  - Caveat: Some packs in the PCRS list also carry `RETAIL_PRICE_EUR`; the two coexist in the same publication and must not be confused.

### Poland

- `CENA_HURTOWA_PLN` → `pharmacy_purchase_price`
  - Source: ustawa refundacyjna (Reimbursement Act); Ministry of Health methodology
  - Caveat: Includes wholesale margin per the Reimbursement Act but excludes pharmacy margin and VAT — comparison to `manufacturer_price` from another country requires a derivation rule (Phase 5).

### France

- `PRIX_FABRICANT_EUR` → `manufacturer_price`
  - Source: CEPS pricing convention; Code de la sécurité sociale
  - Caveat: Negotiated under confidential rebate arrangements; the published value is the gross convention price, not the net price after rebates.

## Adding to the Vocabulary

If a country produces a price field that does not fit existing categories, the country delegate or Policy Intelligence agent emits an anomaly report (`anomaly_type: category_ambiguity` or `policy_gap`). The resolution is one of:

- **accommodate** — extend the vocabulary by adding a category. Recorded in `decisions/`.
- **exempt** — handle this country's field specifically without extending the vocabulary.
- **exclude** — mark the field as `unmapped_price_concept` for now.
- **accept_with_caveat** — map to the closest existing category with a permanent caveat.

The vocabulary grows toward the real shape of European pharmaceutical pricing; it is not frozen.

## What the Vocabulary Does NOT Do

- It does not impose a global "fair" price concept.
- It does not require every country to have an entry in every category.
- It does not silently bridge categories — a comparison spanning categories needs an explicit policy-supported rule.
- It does not substitute for reading the underlying policy when stakes are high. The vocabulary organises comparisons; it does not pre-empt expert judgment.
