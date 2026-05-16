# 001-initial-scope

---

## ID

`001-initial-scope`

## Date

2026-05-16

## Status

accepted

## Context

CLAUDE.md section 2 commits the project to a candidate pool of 32 countries (30 EEA member states plus the United Kingdom and Switzerland) but recognises that actual scope is a subset. The charter distinguishes three categories:

1. **A priori included** — committed from the start; the system must handle these.
2. **A priori excluded** — explicitly out of scope initially; inclusion requires a deliberate decision.
3. **Everything else** — enters actual scope when agent assessment supports it and a human confirms; leaves when assessment fails or the source becomes unmaintainable (criteria per CLAUDE.md sections 5 and 6).

This decision records the rationale for the first two categories. The third is governed by ongoing assessment, not by this document, but the criteria for entry and exit reference the same logic applied here.

## Decision

### A priori included: Ireland, Poland, France

**Ireland.** The Health Service Executive (HSE) publishes a single, authoritative price list for reimbursable medicines under the Framework Agreement on the Supply and Pricing of Medicines (FASPM). The list is machine-readable (CSV/PDF), published by the single payer, and reflects the reimbursement price the state actually pays. There is one regulated price field per presentation, one publisher, one regime. This makes Ireland the clearest possible starting point: the policy reading is straightforward (FASPM reimbursement price), the data source is structured and freely available, and the identity of the price concept is unambiguous.

**Poland.** The Office for Registration of Medicinal Products, Medical Devices and Biocidal Products maintains the Rejestr Produktow Leczniczych (Register of Medicinal Products). The register is publicly accessible, structured (searchable database with downloadable results), and carries multiple regulated price fields including the official wholesale price and the pharmacy retail price set by the Minister of Health. The primary challenge is language — the register is in Polish — but the data itself is well-structured and the price fields are clearly delineated in the regulatory framework. Poland also represents a meaningful policy contrast with Ireland: different pricing mechanism, different regulatory tradition, different income level. This contrast is valuable for testing whether the two-gear comparison approach survives real heterogeneity.

**France.** The Base de donnees publique des medicaments (public medicines database), maintained by the Agence nationale de securite du medicament (ANSM) with data from the Comite economique des produits de sante (CEPS), publishes multiple regulated price fields per presentation: prix d'achat de l'etablissement (hospital purchase price), prix de vente au public (public retail price), taux de remboursement (reimbursement rate), and honoraires de dispensation (dispensing fee). The data is freely downloadable, transparently sourced from official decrees, and carries explicit dates of effect. France's multi-field regime tests the system's ability to select the right comparison anchor rather than the only available price, and its transparency regime provides a strong basis for policy interpretation.

### A priori excluded: Germany

**Germany.** The Lauer-Taxe — the authoritative price list for the German statutory health insurance (GKV) market — is published by Noweda, a private wholesale cooperative, under licensing restrictions. The statutory prices it contains are not freely downloadable; access requires a paid subscription or a specific contractual relationship. The freiwillige Selbstbeschränkung (voluntary price moratorium) prices and the Festbetrage (reference price ceilings) are set by public bodies but published through the Lauer-Taxe infrastructure. Inclusion of Germany would therefore require either (a) a legal review of whether the project's use of Lauer-Taxe data complies with Noweda's licensing terms, or (b) an alternative data path that reconstructs German reimbursement prices from official gazette notices (BAnz) and G-SPC resolutions — a substantially more complex and fragile pipeline. For initial validation, this legal and technical overhead is out of scope. Germany remains a high-value candidate for future inclusion; the obstacle is legal and logistical, not conceptual.

### Everything else

Countries not named above enter actual scope through the process described in CLAUDE.md sections 5 and 6: a Country Delegate agent assesses source availability, structure, and licensing; a Policy Intelligence agent assesses interpretability; a human confirms. A country leaves actual scope when its source becomes unmaintainable, its data fails profiling, or its policy reading cannot be sustained. Each entry and exit is recorded as a decision in this directory.

## Consequences

**Gains:**

- Three countries that span the spectrum from simple single-price regime (Ireland) through multi-field structured regime (France) to different-language structured regime (Poland). This breadth tests the two-gear comparison model against genuine variation rather than easy cases.
- All three sources are freely accessible, published by public authorities or under public mandate, and machine-readable or semi-structured. No legal ambiguity about data use.
- The Ireland-Poland pair provides a strong test of cross-regime comparison (single payer vs. ministerial price-setting; English vs. Polish; one price field vs. multiple).

**Costs:**

- No DACH (Germany-Austria-Switzerland) country in initial scope. Germany is the largest pharmaceutical market in Europe; its absence limits the policy relevance of early comparisons. This is an acknowledged gap, accepted in exchange for avoiding the legal review that inclusion would require.
- No Southern European country in initial scope. Italy and Spain are large markets with complex pricing regimes; their absence means the system is not tested against Mediterranean pricing structures in validation. Inclusion candidates for Phase 2+.
- Poland's Polish-language source requires translation-aware parsing. This is a real cost but also a design test: if the system cannot handle a non-English official source, it cannot serve 30+ EEA countries.

**Assumptions that may need revisiting:**

- That the HSE price list remains freely available and machine-readable. If HSE changes its publication format or access policy, Ireland's inclusion may need reassessment.
- That the Rejestr's structure is stable enough for automated parsing. If the register redesigns its interface, the Polish Country Delegate pipeline breaks and must be rebuilt.
- That France's multi-field regime is as interpretable as it appears from the outside. If the relationship between CEPS decisions and the published database is less direct than assumed, the policy reading for French price fields may need significant revision.

## References

- CLAUDE.md section 2 (Scope) — the constitutional basis for this decision.
- CLAUDE.md sections 5 and 6 (Agent layer, Comparison vocabulary) — the criteria for future scope entry and exit.
- CLAUDE.md section 8, rule 11 (Repository is the system of record) — the requirement that this decision be recorded here.
- HSE FASPM price list: https://www.hse.ie/eng/staff/pcrs/pcrs-publications/drug-reimbursement/
- Rejestr Produktow Leczniczych: https://rejestrproduktowleczniczych.mpips.gov.pl/
- Base de donnees publique des medicaments: https://base-donnees-publique.medicaments.gouv.fr/
- Ratified by: project lead, at project inception.
