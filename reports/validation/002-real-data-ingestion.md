# Real-Data Validation 002 — IE PCRS druglist 2026-05-16

**Snapshot:** IE, 2026-05-16
**Source:** [PCRS druglist (sspcrs.ie)](https://www.sspcrs.ie/druglist/pub) — manual download of CSV
**Performed:** 2026-05-16
**Decision:** [decisions/003-pcrs-reimbursement-price-is-pharmacy-purchase-price.md](../../decisions/003-pcrs-reimbursement-price-is-pharmacy-purchase-price.md)

## Goal

Replace the synthetic IE fixture with a real PCRS publication and observe what the pipeline does. Surface every misalignment between Phase 4 working hypotheses and reality. Record the misalignments rather than smooth them over.

## What was ingested

| Item | Value |
|---|---|
| File | `data/raw/ie/2026-05-16/pcrs-druglist.csv` |
| Size | 1,106,263 bytes |
| SHA-256 | `59d952e8dce7a0f3…` (full hash in manifest) |
| Rows | 8,023 (8,022 after header) |
| Columns published | `Code, Drug Name, Pack Size, Strength Measure, Name, Reimbursement Price, Non Proprietary Name, Ref Price, Dental, Reference Priced, INN` |

## Misalignments observed (and how each was resolved)

### 1. Column names — A-class friction (just code)

The synthetic Phase 4 fixture used `PRODUCT_CODE`, `STRENGTH`, `DOSAGE_FORM`, `EX_FACTORY_PRICE_EUR`. The real PCRS publication uses `Code`, `Strength Measure`, no `DOSAGE_FORM` column at all, and the price column is `Reimbursement Price`. Resolved by rewriting [src/eu_pharma_price/delegates/ireland.py](../../src/eu_pharma_price/delegates/ireland.py) field mapping.

### 2. The price column has different semantics — B-class friction (working hypothesis revised)

This was the largest finding of the day. The Phase 4 PolicyInterpretation mapped `EX_FACTORY_PRICE_EUR` → `manufacturer_price`. The real PCRS column is `Reimbursement Price`, and per **S.I. No. 639/2019 Article 2** this is the *ingredient cost*:

> "ingredient cost" means —
> (a) in the case of fridge items, the ex-factory price together with a wholesale mark-up of 12 per cent, and
> (b) in the case of any other drug item, the ex-factory price together with a wholesale mark-up of 8 per cent.

So the published `Reimbursement Price` is **`ex_factory × 1.08`** (or × 1.12 for fridge items), excluding VAT, excluding pharmacy mark-up and dispensing fee. This places it in `pharmacy_purchase_price`, not `manufacturer_price`.

Recorded in [decisions/003](../../decisions/003-pcrs-reimbursement-price-is-pharmacy-purchase-price.md). Updated [data/policy/ie/policy_interpretations.jsonl](../../data/policy/ie/policy_interpretations.jsonl) accordingly with full statutory citation, retained 8% / 12% wholesale markup detail, included VAT and margin metadata, and listed four caveats specific to the real publication.

**Cross-country consequence:** IE now lines up with PL's `cena hurtowa` (also a regulated wholesale price) and is **incompatible** with FR's `prix fabricant` (pure ex-factory). The previously working FR↔IE comparison (which compared a synthetic ex-factory to FR's real ex-factory) is no longer eligible because IE's real publication is one wholesale-margin step downstream. IE↔PL becomes eligible (subject to a future PL real-data ingestion).

### 3. Dosage form is buried in `Drug Name` — B-class friction

PCRS does not publish dosage form as a column. It is encoded in the product name string: `"Kalydeco Film Coated Tabs. 150 mg. 56 (A)"`, `"Augmentin Susp 600/42.9MG/5 ML 70 ML"`, `"Voltarol Gel 1% 100G"`. Resolved by adding a `_derive_fields()` hook on `BaseDelegate` (no existing delegate broken; subclasses override only when they need it) and adding a 36-pattern regex list in the IE delegate that recognises tablet / capsule / suspension / solution / injection / transdermal_patch / sachet / suppository / etc., normalising surface forms like `"Tabs."`, `"Caps"`, `"Soln"`, `"Susp"` to canonical names.

Failure rate: 1,500 / 8,023 rows (~19%) had no recognisable form — these are non-pharmaceutical PCRS items (dental, ostomy, dressings, syringes, GMS sundries) which legitimately lack a dosage form. The delegate emits `missing_required` anomalies for them, which is the correct behaviour.

### 4. Strength patterns far richer than fixture — B-class friction

Real strength values include `MG`, `G`, `MCG` (uppercase), `%`, `IU`, concentrations like `5MG/ML` and `250MG/5 ML`, IU concentrations like `100IU/ML`, and combination strengths like `500/800MG/IU` (which represent combination products outside the project scope per charter §6).

Resolved in [src/eu_pharma_price/comparison/parsers.py](../../src/eu_pharma_price/comparison/parsers.py): added case-insensitive matching, added `MG/ML` (with optional volume divisor → normalises `250MG/5 ML` → `50 mg/ml`), added `MCG/ML`, added `IU/ML`. Combination strengths `<a>/<b>UNIT` are explicitly **rejected** (return `None`) — they are combination products, and per charter §6 these never compare across countries even when the molecule "matches" because the matched names refer to a multi-ingredient aggregate. The candidate generator then emits an anomaly for them.

### 5. Zero-priced rows are 12.5% of the publication — B-class friction (recorded, not yet acted)

Roughly 1,005 rows have `Reimbursement Price = 0.0`. These are not data errors — they are real entries for High Tech medicines (which are billed under a separate scheme, not via PCRS druglist), reference-priced items where the Reimbursement Price field is held at zero for administrative reasons, and special-claim items.

The current data profiler treats these as outliers and the snapshot is marked **implausible** because only 79.83% of prices are strictly positive (below the 95% threshold). The two-gear rule then correctly **blocks comparison candidate construction** on this snapshot.

This is the system *working as intended*, and it is also a finding that the threshold should be revisited. Three possible resolutions:

- **accommodate**: introduce a per-country threshold override that for IE accepts up to 20% zero-priced rows because the publication mixes High Tech and non-High-Tech rows. This requires adding a "zero-priced row" indicator column, ideally derived by looking at `Reference Priced = Y` and the High Tech list (which is published separately).
- **exempt**: add a delegate-level filter that drops zero-priced rows before they enter canonical, recording the count in the delegate report. This is cleanest but means two snapshots ingested into the substrate per real PCRS download (the full list and the filtered list) — needs a decision.
- **accept_with_caveat**: leave the threshold at 95% positive and accept that real PCRS snapshots will always be flagged — researchers see the implausibility, understand its source, and decide manually.

No resolution implemented yet. The behaviour is correct; the threshold is honest. Decision will be filed when the next data source (PL or FR real data) reveals whether 95% positive is too strict in general or specifically wrong for IE.

### 6. PCRS provides no `dosage_form` for non-drug items — works as intended

37% of rows have empty strength (dental, ostomy, dressings, etc.). The delegate emits `Missing required canonical fields: ['strength', 'dosage_form']` anomalies for them. The pipeline does not pretend they are drugs. They simply do not enter canonical. This is the spec working correctly — anomaly count of 3,268 is honest.

## Pipeline result on real data

```
Raw rows:               8,023
Canonical records:      4,755 (59% conversion rate)
Anomalies emitted:      3,268 (all missing_required, ~37% of source rows)
Profile status:         red (price_amount: implausible — zero-rate at 20%)
Candidates generated:   0 (snapshot blocked by data gate; correct)
```

## Working hypotheses — outcome

| Hypothesis | Status |
|---|---|
| Two-gear rule (policy + data, both sides) | Reaffirmed. Real-data implausibility correctly blocks candidate construction. |
| Per-snapshot data profiles | Reaffirmed. The same field will pass profile in a future snapshot if the zero-price rows are filtered or the threshold revised. |
| Hard exclusions silent | Reaffirmed. Combination products (`500/800MG/IU`) cleanly drop without noise. |
| Caveats travel | Reaffirmed. The four PCRS-specific caveats now sit on the policy interpretation and would propagate to any review. |
| No silent transforms | Reaffirmed. The 8% wholesale markup is *documented* in the policy interpretation but **not applied as a transform** by the pipeline — researchers wishing to back out the ex-factory price from the published Reimbursement Price would need an explicit derivation rule, which is itself recorded with provenance. |
| Phase 4 IE policy interpretation (synthetic) | **Refuted by real data.** Reverted. Real interpretation cites S.I. 639/2019. |
| Comparison vocabulary handles published prices | **Partially refuted.** The 4 categories work for the IE/PL/FR cases tested today, but the existence of zero-priced reference-priced rows suggests a future need for a "reference_price" attribute layered on top of the category, not a new category itself. |

## Sources downloaded and inspected during this validation

- [S.I. No. 639/2019](https://www.irishstatutebook.ie/eli/2019/si/639/made/en/pdf) — defines `ingredient cost`
- [FASPM 2026–2029](https://www.ipha.ie/wp-content/uploads/2026/03/20260303_IPHA_FASPM_Agreement.pdf) — defines `Price` as ex-factory exclusive of VAT
- [PCRS druglist](https://www.sspcrs.ie/druglist/pub) — the data itself
- [Community Pharmacy Agreement 2025](https://www.hse.ie/eng/about/who/gmscontracts/community-pharmacy-agreement/community-pharmacy-agreement.pdf) — pharmacy fee structure (not yet ingested)
- [HSE Pharmacy Circular 04/25 (Pricing)](https://hse.ie/eng/staff/pcrs/circulars/pharmacy/pharmacy-circular-04-25-pricing.pdf) — referenced for context
- [HSE Pharmacy Circular 06/2025 (Reference Pricing)](https://hse.ie/eng/staff/pcrs/circulars/pharmacy/pharmacy-circular-06-2025-reference-price-circular-may-2025.pdf) — informs caveat about reference-priced items

## Next validation cases (recorded, not yet performed)

- IE High Tech list (PDF) — different scheme, different publication format, requires a PDF parser. Will exercise the multi-snapshot-per-country pattern.
- PL Ministry of Health real data — will let IE↔PL produce its first real cross-country candidates.
- FR Ameli/CEPS real data — will exercise the IE-PL category line vs the FR manufacturer-price line; will require either a wholesale-markup bridging derivation rule or permanent acceptance that FR↔IE/PL is not directly comparable.

## Conclusion

Real PCRS data ingestion exposed exactly the kinds of friction the project's working-hypothesis layer was designed to handle. Five A-class fixes (code), one B-class working-hypothesis revision recorded in `decisions/003`, one threshold concern noted but not yet acted on, and zero design changes to the **stable** commitments. The two-gear rule and the no-silent-transforms invariant survived contact with reality unchanged.
