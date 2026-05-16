# CLAUDE.md

> **Project charter for `eu-pharma-prices`.** This is the constitutional layer: purpose, principles, scope, commitments. It does *not* specify implementation. Execution plans, schemas, agent prompts, and code-level decisions are produced by downstream work (in `docs/specs/`, `decisions/`, and code) under the constraints this charter sets.
>
> **How to use this document.** Treat sections marked *stable commitment* as binding — changing them is a deliberate amendment, recorded in `decisions/`. Treat sections marked *working hypothesis* as the project's current best guess — they exist to be tested against real data and revised when reality pushes back. When a downstream artifact and this charter disagree, the rule depends on which kind of section: stable commitments override the artifact, working hypotheses are amended by it.
>
> **The discipline this charter tries to keep.** Direction without micromanagement. Abstraction without vagueness. No checklist that pretends to enumerate the future. No design choice frozen before real data has had a chance to argue with it.

---

## 1. Purpose *(stable commitment)*

A **comparable data substrate** for the published reimbursement prices of medicines across European national health systems, supporting policy research by researchers and academics — including the project's own authors — doing comparative work.

The substrate exists to answer one shape of question, repeated across many molecules and many country pairs:

> *"How does the published reimbursement price of `<molecule, strength, form>` in country A compare with the published price in country B, and what is the evidence behind that comparison?"*

A good answer always names: which national price field on each side, the policy reading that says those fields can be compared, the data behind that reading, and the caveats that travel with the figure.

The system does **not** flatten national price concepts into a single global standard. Every country publishes a different family of regulated prices for valid policy reasons — that non-uniformity is a fact about the world the system represents, not a defect it normalises away.

**Not in purpose:** clinical decision support, real-time market intelligence, scraping anything not voluntarily published, comparison of net negotiated rebated prices (which are not published), inference of therapeutic equivalence across different molecules.

## 2. Scope *(stable commitment, with the working choices noted)*

**Candidate pool:** the 30 EEA member states plus the United Kingdom and Switzerland — 32 countries. This is an outer limit, not a target. Extending beyond it is a deliberate amendment in `decisions/`.

**Actual scope:** a subset of the candidate pool, smaller than the pool. The system aims to say useful things about countries it includes; it does not aim to include everyone.

**A priori included:** Ireland, Poland, France. Committed from the start; rationale in `decisions/`.

**A priori excluded:** Germany. Rationale in `decisions/`.

**Everything else:** enters actual scope when the agents' assessment supports it and a human confirms. Leaves actual scope when assessment later fails or the source becomes unmaintainable. The criteria are described in §5 and §6.

## 3. Audience and deliverables

**Audience *(stable commitment)*:** policy researchers, academics, and the project's own authors. Not clinicians, not the general public, not HTA bodies or government procurement. Reproducibility and citability matter more than presentation polish.

**Deliverables.** Four peer products, each a different view onto the same underlying artifacts:

- a queryable data substrate — immutable dated snapshots plus the policy, profile, comparison, and audit artifacts they depend on;
- comparison reports — on demand, for a chosen molecule and country pair or cohort, citable to a snapshot date;
- a Python interface — for embedding the substrate into researchers' own analyses;
- an interactive UI — for browsing comparisons without writing code, with audit links as first-class navigation.

These four are peers. None is the "real" deliverable that the others lead up to; all consume the same tables. Sequencing among them is driven by real research need.

The specific formats (markdown vs HTML reports, REST vs Python library, web app vs notebook) are *working hypotheses* — what matters is the four functions exist and serve the same substrate.

---

## 4. Core principles *(stable commitments)*

These are the principles the system is organised around. Their phrasing here is binding; their implementation is open.

### Two gears: policy judges the data, data reflects the policy

Every comparison rests on two independent pieces of evidence, both required.

- **Policy interpretation** — for each country and each price field, a reading derived from official sources that says what the field means and how it relates to fields in other countries. Typed, ID'd, sourced, datable, adjudicable.
- **Data profile** — for each country and each snapshot, an assessment of whether the field the policy reading names actually exists, is populated, and behaves plausibly. Typed, ID'd, sourced, datable.

A comparison is permitted only when both gears say yes, for both sides. There is no override.

### Traceability

Every figure in every output traces, end to end, to:
- the published document it came from, with hash and fetched-at timestamp;
- the policy reading that interpreted it;
- the data profile that admitted it;
- any numeric transformation applied, with its rule and inputs preserved.

A figure for which any link is missing does not appear. The audit trail is built in from day one, not retrofitted.

### AI interpretation, deterministic calculation

LLM agents are first-class reasoning components for tasks that require reading policy documents and saying what they mean. Numeric transformation — currency, per-unit, VAT, identity matching on structured features — is plain code. The boundary is strict and one-directional: agents never modify numeric values; code never invents semantic interpretation.

### Raw record preservation, append-only history

The raw record as published is never lost. Snapshots are immutable. Schemas evolve by adding, not by renaming or removing. The repository — Git, on GitHub — is the system's record; a decision not in the repository did not happen.

### Honest comparison or no comparison

When evidence is weak, the system says so. When fields don't fit, it surfaces that rather than forcing them in. When in doubt, it marks for review and stops. A row in a review queue is recoverable; a silently wrong figure in a report is not.

---

## 5. The agent layer *(working hypothesis)*

The system is AI-native: agents do the interpretation work, deterministic code does the calculation work, the boundary is enforced. The specific division of agent responsibilities below is the *current best guess* — it will be revised as real data exposes which seams are well-placed and which are not.

**Working roles:**

- **Country Delegate** — owns one country's publication regime: locates fields, parses sources, produces canonical records, preserves raw records, describes locally what each price field is and means. Does not assign cross-country meaning.
- **Policy Intelligence** — reads each country's delegate output plus official policy material, produces typed policy interpretations mapping national fields to a shared comparison vocabulary. Adjudicates between sources.
- **Analytics** — profiles snapshots, checks that policy-named fields actually exist and are usable in data.
- **Secretariat** — joins canonical rows across countries, resolves anchors through policy interpretations, applies deterministic normalisation, produces comparison candidates with full evidence.
- **Review** — assesses candidates end-to-end, assigns usability, refuses to let weak evidence become a headline.

**Seams the project does not yet know are well-placed:** whether Policy Intelligence is best as one central agent or one per country; whether the delegate / policy boundary belongs where it currently sits; whether Review is a distinct agent or a deterministic pass. Real data will inform these.

**What stays stable across any future redesign:** the interpretation/calculation split, country-boundary cleanliness (no agent reads another country's data without going through the comparison layer), no internet access at agent runtime (fetching is a separate audited step).

---

## 6. Comparison vocabulary *(working hypothesis)*

The system needs a vocabulary for *what kind of regulated price* a national field represents, so that comparisons happen between things of compatible kind. The current working vocabulary describes positions in the supply chain: manufacturer-side, payer reimbursement, pharmacy purchase, public retail. Real publication regimes may straddle these, fall outside them, or demand different cuts entirely — that is a finding to feed back, not a problem to silence.

Whatever the vocabulary turns out to be, two principles are stable:

- **No category is privileged.** The system does not prefer one kind of price over another, does not require every country to map to a specific one, and does not silently bridge across categories without an explicit policy-supported rule.
- **Mappings are decisions, not assertions.** Each national field's mapping to a category is a policy interpretation with provenance, an effective-date window, and an adjudication record. It can be wrong and revisable.

Comparisons receive a **usability assessment** combining policy strength, data strength, identity strength, and normalisation strength. The current working scheme uses a small set of labels (roughly: usable, usable-with-caveat, exploratory, not-comparable); the exact granularity is open. **Hard exclusions are stable**: never compare across different molecules, different routes of administration, or therapeutically substitutable but distinct ingredients.

---

## 7. How the system evolves

### First end-to-end validation

Before the working hypotheses harden, the system must walk one real country pair and one real molecule end to end — every traceability link resolved, reviewed by a human, friction recorded. The choice of pair and molecule belongs to the execution phase, recorded in `decisions/`, chosen to surface real frictions rather than confirm convenient ones.

Until this validation is met, the working-hypothesis sections of this charter are notional. After it is met, they are revised in the same commit as the design changes that arose.

Subsequent validations are chosen for the friction they are expected to produce, not for completeness. Each may revise the working layer of the charter.

### Anomaly surfacing

Some findings will not fit the system's current assumptions — a price-like thing that is not quite a price, a field that maps to several categories at once or to none cleanly, a distribution plausible for one country but unlike anything seen before, an identifier scheme that breaks expected normalisation. Many such surprises cannot be anticipated; listing them would defeat the purpose.

A finding of the form *"this does not fit, and it seems important"* is a first-class output of the system. Any agent may produce an **anomaly report** alongside its normal output. The agent surfaces; it does not act. Reports route to humans, who decide among legitimate outcomes — accommodate (extend the design), exempt (handle this instance specifically), exclude (this case is not a fit), or accept with caveat (include with a permanent qualification) — each recorded in `decisions/`.

This mechanism is what allows the system to grow toward the real shape of European pharmaceutical pricing rather than away from it. The format of reports and the exact set of outcomes are working hypotheses; the principle is stable.

### Self-healing within limits

The system is allowed to detect, diagnose, and propose. It is never allowed to silently change the meaning of data. Retries, fallback parsing, downgrades to `needs_review`, pull requests proposing rule changes — fine without approval. Applying a schema mapping, changing a derivation rule, accepting a low-confidence match, backfilling history — requires human approval. Every action is in the audit log.

---

## 8. Binding operating rules *(stable commitments)*

The principles in §4 and the scope in §2 imply specific Do/Don't rules. Violating any of these corrupts the substrate.

1. **Never invent a value.** Every number traces to a source file hash and a raw record.
2. **Never silently transform.** Derived values carry their derivation rule and ID; as-published values are preserved.
3. **Never compare without both gears.** Policy interpretation and data profile both required, on both sides.
4. **When in doubt, mark for review and stop.** Don't guess into outputs.
5. **Snapshots are immutable.** Never overwrite a dated partition.
6. **Currency and date are always explicit.** No bare numbers, no naive datetimes, no FX without source and date.
7. **Country boundaries are clean.** Cross-country reasoning goes through the comparison layer, not direct joins.
8. **No agent has internet access at runtime.** Fetching is a separate, audited step.
9. **Repository-local fixtures only in tests.** Reproducibility is non-negotiable.
10. **Honor `robots.txt` and ToS.** Manual-refresh sources are marked.
11. **The repository is the system of record.** Decisions live in `decisions/`; a decision not there did not happen.

These survive any working-hypothesis redesign.

---

## 9. Technology orientation

**Stable commitments:**

- **Local-first, no cloud.** State of the system = state of the repository. No hosted services, queues, or managed databases.
- **Python** as the language. **Pydantic** at every data boundary; no untyped dicts crossing module lines.
- **DuckDB + Parquet** as the storage and query layer. Snapshots are dated Parquet partitions; analytics are DuckDB over them.
- **LangGraph + Anthropic Claude** as the agent runtime. Models pinned per agent. Temperature 0 for parsing, matching, and schema-drift tasks.
- **Git on GitHub** as the canonical record.

**Working choices** (libraries for HTTP, PDF, in-memory data, testing, linting) are picked at the implementation layer in `docs/specs/`, revisable when friction warrants. The orientation is: minimum sufficient set, no speculative dependencies, add the second time a need arises rather than the first.

**Tools explicitly outside scope** until a validation case demonstrates need: cloud infrastructure, vector databases, alternative agent frameworks, heavy scraping frameworks.

---

## 10. Known limitations *(stable commitments, surface, do not paper over)*

- Confidential negotiated rebate prices are not published — the dataset reflects published list prices, not net prices.
- Some authorities publish only confidential assessments — affected countries document the gap.
- Therapeutic equivalence across different molecules is a clinical/regulatory determination, outside scope.
- The system represents published price concepts, not negotiated outcomes — findings complement, never replace, formal reference-pricing exercises.
- Whatever the comparison vocabulary turns out to be, it is coarse by design — it organises comparisons; it does not substitute for reading the underlying policy when stakes are high.

---

## 11. Glossary

**ATC** — WHO Anatomical Therapeutic Chemical classification ·
**BENELUXA** — joint pharmaceutical policy initiative: BE, NL, LU, AT, IE ·
**EDQM Standard Terms** — European controlled vocabulary for dosage forms, routes, containers ·
**EEA** — European Economic Area: the 27 EU member states plus Iceland, Liechtenstein, Norway. In-scope set = these 30 + UK + Switzerland ·
**FASPM** — Framework Agreement on the Supply and Pricing of Medicines (Ireland) ·
**INN** — International Nonproprietary Name ·
**UCUM** — Unified Code for Units of Measure
