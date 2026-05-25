# Global Price Expansion Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans before implementing any country in this roadmap. Each country must receive its own country-specific implementation plan before code or data capture begins.

**Goal:** Expand the project from the existing six-country substrate into a broader international statutory/list-price comparison product without weakening the policy-data dual-gear architecture.

**Architecture:** The project is not a country-coverage exercise. It is an AI-native policy-and-data system: country delegates preserve published data, Policy Intelligence interprets price meaning and derivation rules, and the comparison substrate consumes only structured policy semantics and auditable derivation evidence. New countries are admitted only when they strengthen this architecture or can be represented honestly within it.

**Tech Stack:** Python 3.13, Pydantic policy/comparison schemas, pandas/parquet artifacts, country delegates, policy interpretation JSONL, policy-derived price-lane graph, existing INN/dosage-form/strength/FX normalisers, `unittest`.

---

## Operating Principles

- Keep the existing substrate intact. The six completed countries (`IE`, `PL`, `CZ`, `ES`, `IT`, `PT`) are the regression baseline.
- Do not optimise for the number of countries. Optimise for interpretable, legally grounded, apple-to-apple comparison.
- Every country must preserve the two gears:
  - data gear: official source capture, raw lineage, canonical records, data profile;
  - policy gear: structured policy interpretation, VAT/margin semantics, observed/derived distinction, derivation rules.
- Derived lanes are a feature, not a weakness, when they are grounded in binding law or official methodology.
- Derived lanes must remain transparent: source lane, formula, parameters, confidence, caveats, and legal basis must travel with every derived value.
- A country can be valuable even if it only supports one basis, such as payer reimbursement. It must not be forced into manufacturer-price comparison when the policy evidence does not support that.
- Confidential rebates, managed-entry agreements, tender net prices, and undisclosed paybacks remain out of scope. They are recorded as caveats, not guessed.
- The United States and Canada are excluded from this roadmap for now. Their systems may require a different substrate shape and should not distort the current architecture.

## Existing Baseline

The current baseline countries are:

| Country | Role in Baseline |
|---|---|
| `IE` | Observed pharmacy-purchase lane; policy-derived manufacturer lane from statutory wholesale-markup reversal |
| `PL` | Observed manufacturer, pharmacy-purchase, public-retail, and VAT-inclusive manufacturer lanes |
| `CZ` | Observed manufacturer and pharmacy/public ceiling lanes |
| `ES` | Observed public-retail lane; policy-derived manufacturer lane from conversion tiers |
| `IT` | Observed public-retail lane; policy-derived manufacturer lane from Class A share |
| `PT` | Observed public-retail lane; policy-derived manufacturer lane from Infarmed conversion tiers |

Before and after every expansion batch, run:

```bash
.venv/bin/python -m unittest tests.test_price_lane_substrate -v
.venv/bin/python -m unittest discover -s tests -v
```

The three-drug six-country manufacturer-basis validation must keep passing unless a deliberate decision document changes the baseline.

## Phase 0: Substrate Hardening Before New Countries

Phase 0 must be completed before implementing `BE`, `SE`, or any other new
country. It turns the roadmap's principles into enforceable project mechanics.

Required Phase 0 outputs:

- `src/eu_pharma_price/schemas/expansion.py` with the
  `CountryReadinessAssessment` schema;
- `data/expansion/country_readiness.json` as the machine-readable expansion
  tracker for all countries in this roadmap;
- `docs/templates/country-expansion-report.md` as the country report/status
  template that every completed country must fill;
- `tests/test_expansion_readiness.py` with readiness, tracker, report-template,
  and baseline-regression guard tests;
- documentation that country-specific plans are required before source capture,
  delegate code, or policy JSONL changes.

Phase 0 is not optional. It protects the project's main advantage: policy
intelligence and data normalisation must correspond through structured,
auditable artifacts rather than through ad hoc country-specific code.

## Country Admission Gate

No country-specific plan should start until a readiness note can answer each item below.

| Gate | Required Answer |
|---|---|
| Official source | What is the official or quasi-official source URL? |
| Source format | Is it CSV, Excel, XML, API, HTML, PDF, or manual-only? |
| Legal/ToS status | Can the data be captured and used for research/internal analysis? |
| Observed price lanes | Which published fields are actual prices? |
| Price meaning | Does each field represent manufacturer, pharmacy-purchase, public-retail, payer, acquisition, reference, or ceiling price? |
| VAT/GST | Is tax included, excluded, or unknown? |
| Margins/fees | Which wholesale, pharmacy, dispensing, service, or statutory fees are included? |
| Derived lane possibility | Is there a binding law or official method that supports a deterministic derivation? |
| Identity fields | Are INN, ATC, product code, strength, form, route, pack, and manufacturer available? |
| Confidence | Is each lane high, medium, low, or blocked? |
| Comparison basis | Which basis can the country honestly support first? |

If any of source, price meaning, or identity fields are unresolved, the country remains in policy research and does not enter implementation.

## Phase 1: High-Value, Low-Friction Expansion

These countries should be implemented first because they are likely to strengthen the existing architecture quickly.

| Order | Country | First Basis | Why It Belongs in Phase 1 |
|---:|---|---|---|
| 1 | `BE` Belgium | manufacturer_price | INAMI/RIZIV publishes ex-factory style fields; EUR; close to current EU baseline |
| 2 | `SE` Sweden | pharmacy_purchase_price, public_retail_price | TLV AIP/AUP data and pharmacy-margin rules are clear |
| 3 | `NZ` New Zealand | manufacturer_price, payer_reimbursement_price | Pharmac manufacturer price and subsidy semantics are unusually clean |
| 4 | `FI` Finland | pharmacy_purchase_price, public_retail_price | Wholesale-to-retail statutory calculation is clear |
| 5 | `CH` Switzerland | manufacturer_price, public_retail_price | FAP and PP are strong lanes; source migration must be handled carefully |
| 6 | `GR` Greece | manufacturer_price, wholesale/public-retail | Price bulletins likely expose multiple price stages |
| 7 | `BR` Brazil | manufacturer_price, public_retail_price, government ceiling | CMED PF/PMC/PMVG is a strong price-lane graph candidate |
| 8 | `FR` France | manufacturer_price, public_retail_price, reimbursement | Public medicine database/Ameli fields appear stronger than earlier assumptions |
| 9 | `IL` Israel | public/max price | Ministry price lists support maximum-price comparison |
| 10 | `CO` Colombia | reported market price, maximum sale price | SISMED and regulated maximum sale prices support Latin America coverage |

### Phase 1 Batch Rule

Implement no more than three Phase 1 countries in one branch/batch. Recommended first batch:

1. `BE`
2. `SE`
3. `NZ`

This batch tests three different patterns: observed manufacturer lane, AIP/AUP lane pair, and manufacturer plus payer subsidy.

## Phase 2: Complex but Valuable Expansion

These countries are worth doing after Phase 1 because they add important comparison bases, currencies, and payer systems, but require more policy work.

| Order | Country | First Basis | Main Risk |
|---:|---|---|---|
| 11 | `IS` Iceland | pharmacy_purchase_price, payer/public price | Need field-level interpretation of the price catalogue |
| 12 | `AU` Australia | manufacturer/PBS, pharmacy_purchase_price, payer | PBS settings and program branches are complex |
| 13 | `NO` Norway | pharmacy_purchase_price, public_retail_price | AIP/AUP clear; manufacturer derivation likely weak |
| 14 | `TW` Taiwan | payer_reimbursement_price | NHI payment standard strong; manufacturer derivation weak |
| 15 | `KR` South Korea | payer_reimbursement_price | HIRA reimbursement strong; Korean identity normalisation needed |
| 16 | `AR` Argentina | public suggested price, reference price | Inflation/update cadence and source stability need handling |
| 17 | `PE` Peru | pharmacy retail observed | Useful retail observatory, but not statutory manufacturer price |

### Phase 2 Batch Rule

Start Phase 2 only after at least one Phase 1 batch has passed full regression. Recommended first Phase 2 batch:

1. `IS`
2. `AU`
3. `NO`

This batch tests Nordic price-catalogue semantics, complex programmatic API pricing, and AIP/AUP without manufacturer derivation.

## Phase 3: Low-Priority or Adjudication-Heavy Expansion

These countries may be useful, but each needs stronger policy adjudication or source confirmation before implementation.

| Order | Country | Possible Basis | Required Before Implementation |
|---:|---|---|---|
| 18 | `LV` Latvia | manufacturer_price, public_retail_price | Confirm stable official bulk source and field descriptions |
| 19 | `LT` Lithuania | payer/reference/public price | Adjudicate reimbursed-list field meanings |
| 20 | `EE` Estonia | payer/reference/public price | Decide whether manufacturer lane is absent or unavailable |
| 21 | `AT` Austria | manufacturer/public/reimbursement | Adjudicate EKO, FAP/DAP, and effective-price relationships |
| 22 | `JP` Japan | payer_reimbursement_price | Build Japanese identity normaliser before broad comparisons |
| 23 | `DE` Germany | reimbursement/fixed amount; possibly public price | Resolve Lauer-Taxe/commercial-source constraint |
| 24 | `CL` Chile | public maximum price subset | Decide whether Cenabast subset is representative enough |
| 25 | `AE` United Arab Emirates | public_retail_price | Resolve price-list access, licensing, and automation boundaries |

Phase 3 countries should not be used to inflate headline coverage. If a country only supports a narrow or caveated basis, reports must say so directly.

## Excluded From Price Comparison

These countries/regions should not enter the price-comparison mainline unless a future source review finds stable item-level price data.

| Country/Region | Reason |
|---|---|
| `HK` Hong Kong | Public information mainly supports formulary/charge-category intelligence, not stable item-level price comparison |
| `SG` Singapore | Subsidy/formulary policy is useful, but item-level manufacturer/pharmacy/retail prices are not publicly strong enough |
| `MX` Mexico | Registration/formulary data is useful, but clean official bulk price lanes are weak |

These can become a separate formulary/subsidy intelligence module later. They should not be represented as price-comparable countries in this roadmap.

## Explicitly Deferred: United States and Canada

`US` and `CA` are high-value but excluded from this roadmap.

Reasons:

- The United States has multiple incompatible public price concepts (`NADAC`, `ASP`, `FUL`, `MFP`, WAC-like commercial concepts, PBM/rebate flows). It likely needs a special module rather than a normal country delegate.
- Canada is heavily provincial for public formularies while PMPRB operates at a different regulatory level. It likely needs a provincial/federal split before it can enter the main substrate.
- Both systems risk bending the current architecture around exceptional cases. The current roadmap should first prove the AI-native policy-data design across countries that fit the statutory/list-price substrate more cleanly.

Create a separate design document before touching either country.

## Country-Specific Plan Template

Every country-specific plan must use this structure.

```markdown
# <Country> Implementation Plan

**Goal:** Add <country> to the policy-data dual-gear price substrate on <first comparison basis>.

**Initial Basis:** <manufacturer_price | pharmacy_purchase_price | public_retail_price | payer_reimbursement_price>

**Observed Lanes:** <published fields and meanings>

**Derived Lanes:** <policy-supported transformations, or "none in first pass">

**Confidence:** <high | medium | low> with caveats

### Task 1: Source Registration and Capture
### Task 2: Delegate Parser and Canonical Records
### Task 3: Data Profile and Anomaly Routing
### Task 4: Policy Interpretation and Derivation Rules
### Task 5: Lane Index Integration
### Task 6: Validation Cohort
### Task 7: Country Report and Regression
```

The plan must include concrete tests before implementation.

## Validation Cohorts

Each new country must be validated against:

- the existing six-country baseline;
- at least one common generic oral solid molecule when available;
- at least one high-value or biologic molecule when available;
- the first intended comparison basis;
- a report section that distinguishes observed from derived rows.

Default common molecules:

- atorvastatin;
- dapagliflozin;
- metformin;
- olanzapine;
- pantoprazole;
- pembrolizumab.

Country-specific alternatives may be used when the official source lacks these products, but the substitution must be documented in the country-specific plan.

## Completion Criteria for Each Country

A country is complete only when:

- raw source snapshot and manifest exist;
- delegate produces canonical records with raw-to-canonical lineage;
- profile gates the price field;
- current policy interpretations exist for every comparable price lane;
- every derived lane is generated from `PolicyInterpretation.derivation_rules`;
- lane index includes the country on at least one honest comparison basis;
- validation cohort passes;
- full test suite passes;
- a country report states observed lanes, derived lanes, confidence, and non-comparable lanes.

## Roadmap Maintenance

After each country or batch:

- update this roadmap's country status;
- add a decision document for any major policy adjudication;
- do not delete excluded/deferred countries silently;
- keep the six-country baseline tests as the architectural regression guard.
