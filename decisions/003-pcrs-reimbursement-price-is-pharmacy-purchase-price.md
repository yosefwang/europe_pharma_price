# Decision 003 — PCRS "Reimbursement Price" is pharmacy purchase price, not manufacturer price

**Date:** 2026-05-16
**Status:** accepted
**Supersedes:** the IE PolicyInterpretation written in Phase 4 (which incorrectly mapped `EX_FACTORY_PRICE_EUR` to `manufacturer_price`).
**Discovered during:** real-data ingestion of `data/raw/ie/0_search_results_20260516-110015.csv` (PCRS druglist, downloaded from sspcrs.ie).

## Context

Phase 4 produced an Irish PolicyInterpretation that mapped a synthesised column called `EX_FACTORY_PRICE_EUR` to comparison category `manufacturer_price`. That column does not exist in the real PCRS publication. The real PCRS druglist publishes a column called **`Reimbursement Price`** — and that column is *not* the ex-factory price. It is the **ingredient cost** as legally defined in Irish statutory instrument.

## Authoritative source

**Statutory Instrument No. 639/2019** — *Public Service Pay and Pensions Act 2017 (Payments to Community Pharmacy Contractors) Regulations 2019* — defines `ingredient cost` in Article 2:

> "ingredient cost" means —
> (a) in the case of fridge items, the ex-factory price together with a wholesale mark-up of 12 per cent, and
> (b) in the case of any other drug item, the ex-factory price together with a wholesale mark-up of 8 per cent.

That is, the column the PCRS publishes is:

```
PCRS_Reimbursement_Price = ex_factory_price × 1.08    (non-fridge items)
PCRS_Reimbursement_Price = ex_factory_price × 1.12    (fridge items)
```

The **Framework Agreement on the Supply and Pricing of Medicines (FASPM) 2026–2029** (clause defining "Price") states the underlying ex-factory figure is the price-to-wholesaler exclusive of VAT. So the PCRS Reimbursement Price excludes VAT, includes wholesale mark-up, and excludes pharmacy mark-up and dispensing fees (those are paid separately under the GMS / DPS / LTI schemes, per the same S.I.).

## Decision

The PCRS `Reimbursement Price` column is mapped to **`pharmacy_purchase_price`** in the project's comparison vocabulary, *not* `manufacturer_price` and *not* `payer_reimbursement_price`. Rationale:

- It includes a regulated wholesale mark-up, so it is not a manufacturer-side figure.
- It is the price at which a pharmacy effectively procures stock (modulo retention payments and other adjustments), so it lines up with `pharmacy_purchase_price` as defined in [docs/specs/comparison-vocabulary.md](../docs/specs/comparison-vocabulary.md).
- It is *not* the amount the HSE reimburses to the patient or to the pharmacy in total. The total reimbursement to a pharmacy under GMS = ingredient cost + dispensing fee + (other fees). The published `Reimbursement Price` is the ingredient cost component only.

This places IE in the same comparison category as Poland's `CENA_HURTOWA_PLN` (which is also a regulated wholesale price including a wholesale margin). It places IE in a *different* category from France's `PRIX_FABRICANT_EUR`, which is pure ex-factory.

## Consequences for previously generated artifacts

The Phase 4 / Phase 6 / Phase 7 artifacts on the synthetic 2024-09-01 fixtures used the incorrect IE PolicyInterpretation. They are not re-generated automatically — they are correct *as artifacts* for the synthetic fixtures (which had a column literally named `EX_FACTORY_PRICE_EUR`), but the synthetic fixtures themselves no longer represent the real Irish regime. Real-data ingestion produces a new snapshot window with the corrected semantics; the synthetic artifacts are kept for traceability of how the system evolved.

The real-data validation report `reports/validation/002-real-data-ingestion.md` records this change.

## Outcome for cross-country candidate generation

- **IE ↔ PL**: now eligible for direct comparison (both `pharmacy_purchase_price`).
- **IE ↔ FR**: now blocked by category mismatch (`pharmacy_purchase_price` vs `manufacturer_price`) — would require an explicit derivation rule that adjusts FR ex-factory by the IE 8% wholesale mark-up to bridge categories. That bridge is **not** added in this phase; it is recorded as an open working hypothesis.
- **PL ↔ FR**: same blockage as before — category mismatch, no bridging rule.

This is the correct outcome under the project's two-gear rule. The previous FR-IE candidates that compared a real manufacturer ex-factory to a synthetic "ex-factory" column were technically valid for the synthetic data but did not represent a real regulatory comparison. Real data revealed this; the system refused to silently keep producing them.

## What changed in the codebase

1. `src/eu_pharma_price/delegates/ireland.py` — field mapping rewritten for real PCRS columns; dosage form extracted from `Drug Name`; pack size handled with quoted CSV.
2. `data/policy/ie/policy_interpretations.jsonl` — interpretation rewritten with corrected category and S.I. 639/2019 citation.
3. `src/eu_pharma_price/comparison/parsers.py` — strength parser extended for MG/ML, MCG, %, IU, and unparseable combinations now emit anomalies (the 500/800MG/IU style is left intentionally unparseable in this phase).
4. `data/sources/register.json` — IE source URL corrected to the real sspcrs.ie endpoint; `fetch_method` set to `manual` per the SPA-protected download flow.

## Sources

- [S.I. No. 639/2019](https://www.irishstatutebook.ie/eli/2019/si/639/made/en/pdf)
- [FASPM 2026–2029](https://www.ipha.ie/wp-content/uploads/2026/03/20260303_IPHA_FASPM_Agreement.pdf)
- [HSE PCRS druglist (download portal)](https://www.sspcrs.ie/druglist/pub)
