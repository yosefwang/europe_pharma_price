# Decision 004 — France: no openly published per-CIP price dataset; FR scope deferred until access path resolved

**Date:** 2026-05-16
**Status:** accepted (working hypothesis revision)
**Discovered during:** real-data ingestion attempt for FR.

## Context

Phase 4 produced a French PolicyInterpretation that mapped a synthesised column called `PRIX_FABRICANT_EUR` to `manufacturer_price`. That column does not exist in any French open-data publication accessible from this environment as of 2026-05-16. The investigation found:

| Source | What it contains | Per-CIP PFHT? |
|---|---|---|
| **ANSM BDPM** (`base-donnees-publique.medicaments.gouv.fr`) | CIS/CIP structural metadata, compositions, HAS opinions, generic groups, prescription conditions | **No** — explicitly excludes pricing |
| **CNAM `mediam` BDM_IT codage** (`mediam.ext.cnamts.fr/codif/bdm_it/`) | UCD pricing, CIP tarif, base de remboursement | Connection refused from this environment; the host is intermittently reachable but does not respond reliably to outbound research connections |
| **data.gouv.fr Medic'AM** | Aggregated reimbursement amounts and box volumes per CIP, monthly | **No** — pricing is implicit (amount / box count) but published values are post-rebate reimbursement, not PFHT |
| **data.gouv.fr Open Medic** | Aggregated dispensing volumes and amounts | **No** |
| **data.ameli.fr API** | Same Medic'AM data via API | **No PFHT** |

The published French regulatory price (PFHT — *prix fabricant hors taxes*) is the negotiated CEPS convention price. CEPS publishes individual pricing decisions in the *Journal officiel* but not as a single structured per-CIP dataset on data.gouv.fr.

## What this means for the substrate

### Without French data

- The Phase 4 / Phase 6 / Phase 7 IE-FR comparison candidates were generated against a synthetic `PRIX_FABRICANT_EUR` column that does not exist in real publications. Those candidates remain in the repository as artifacts of the synthetic 2024-09-01 fixture; they are not representative of any real comparison.
- For real-data ingestion, France is **not** in scope until one of the access paths below is resolved.
- The candidate pool of three a-priori-included countries (IE, PL, FR per [decisions/001](001-initial-scope.md)) effectively reduces to two (IE, PL) for real-data work in the immediate term.

### Cross-country comparisons that are still viable

- **IE ↔ PL** on `pharmacy_purchase_price` (IE Reimbursement Price ↔ PL Cena hurtowa brutto, with a VAT-handling derivation rule). This is the substrate's first real cross-country comparison.
- **PL alone** also publishes `Cena zbytu netto` (manufacturer net price), which would map to `manufacturer_price` and eventually pair with French data when accessible.

## Resolution options

Three legitimate paths to bring FR back in:

1. **Access the CNAM mediam codage system from a different network**. The system is publicly available; it is not blocked by ToS, only intermittently by network egress in this environment. A researcher running this project on an IP that can reach `mediam.ext.cnamts.fr` would get full CIP/UCD tarif data. This becomes a manual-fetch source per the project's existing `fetch_method=manual` pattern.
2. **Subscribe to or scrape the *Journal officiel* CEPS publications**. Each CEPS pricing decision is published individually. Aggregating them into a structured per-CIP dataset is a substantial scraping/parsing effort, likely outside the project's local-first scope unless a third party has already done it.
3. **Use Medic'AM / Open Medic as a proxy for publication-level prices**. This is *not* equivalent — Medic'AM amounts are post-rebate reimbursement, not PFHT — but it could support a separate comparison category (`payer_reimbursement_amount`) that explicitly does not pretend to be the published PFHT. This would need a new entry in the comparison vocabulary and a separate PolicyInterpretation, documented as a different kind of comparison.

## Decision (this PR)

For Phase 2 of real-data ingestion, **France is deferred**. The repository keeps:
- the existing synthetic FR fixture and its PolicyInterpretation in `data/policy/fr/policy_interpretations.jsonl` — clearly marked as referring to a synthetic column;
- the FR delegate code, since its parser is correct (the issue is data availability, not parser correctness);
- the FR source register entry, with `manual_refresh_reason` updated to record the access constraint.

When a researcher with FR access is available, option 1 above is the cleanest path: download the CIP tarif file manually, drop into `data/raw/fr/<date>/` with a manifest, and the existing pipeline will work.

## Stable commitments not affected

This decision does not change any §8 binding rule. It records a real-world data-availability gap, writes it to the audit trail (right here, in `decisions/`), and continues with the two-country case that does work. This is exactly the working-hypothesis layer doing its job under reality pressure — refusing to invent French data, surfacing the gap clearly, and continuing the work that can be done honestly.

## Sources

- [data.gouv.fr — datasets santé](https://www.data.gouv.fr/pages/donnees_sante)
- [Base de données publique des médicaments (ANSM)](https://base-donnees-publique.medicaments.gouv.fr/index.php/telechargement) — confirmed no pricing files
- [Medic'AM dataset](https://www.data.gouv.fr/datasets/medicam-medicaments-rembourses-par-lassurance-maladie-par-type-de-prescripteur-donnees-interregimes) — reimbursement amounts, not PFHT
- [CNAM BDM_IT codage](http://www.codage.ext.cnamts.fr/codif/bdm_it/index_tele_ucd.php?p_site=AMELI) — actual CIP/UCD tarif, blocked from this environment
- [CADA — CEPS document search](https://cada.data.gouv.fr/search?administration=Comit%C3%A9+%C3%A9conomique+des+produits+de+sant%C3%A9+%28CEPS%29) — individual pricing decisions
