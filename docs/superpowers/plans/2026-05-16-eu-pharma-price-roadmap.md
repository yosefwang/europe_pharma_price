# EU Pharma Price Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first, auditable substrate for comparing published European medicine reimbursement prices, with a bilingual research workbench that exposes each phase's deliverables as they are produced.

**Architecture:** The system advances along three coordinated tracks: Data / Evidence, Workbench UI, and Localization. Data artifacts are repository-local, append-only, typed at boundaries, and queryable through DuckDB + Parquet; the Workbench presents those artifacts as evidence chains and review surfaces from Phase 0 onward; Localization is a separate cross-cutting module for English and Simplified Chinese UI text while preserving source evidence in its original language.

**Tech Stack:** Python, Pydantic, DuckDB, Parquet, LangGraph + Anthropic Claude for interpretation agents, Git/GitHub as system of record, a local web UI for the Research Audit Workbench, and locale dictionaries for `en` and `zh-CN`.

---

## Binding Constraints From README

- No comparison appears unless policy interpretation and data profile both admit it for both sides.
- Every number traces to a source document hash, fetched-at timestamp, raw record, policy interpretation, data profile, and derivation rule where applicable.
- Agents interpret policy and schema drift; deterministic code performs numeric transformation.
- Snapshots are immutable and append-only.
- Country delegates do not read other countries' data.
- Fetching is a separate audited step; agents do not have internet access at runtime.
- Repository-local fixtures are required for tests.
- UI is a peer deliverable from the beginning, not a final presentation layer.
- UI localization is its own track, supporting English and Simplified Chinese.

## Tracks

### Data / Evidence Track

Owns schemas, source capture, raw records, canonical records, policy interpretations, data profiles, comparison candidates, review assessments, anomaly reports, reports, and queryable tables.

### Workbench Track

Owns a local Research Audit Workbench that exposes each phase's artifact in a navigable, elegant, researcher-oriented interface. The first useful screen is the workbench itself, not a landing page.

Core surfaces:

- Project Map
- Schema Map
- Source Register
- Country Workspace
- Policy Mapping View
- Data Health View
- Comparison Candidate View
- Review Queue
- Audit Trail View
- Comparison Workbench

### Localization Track

Owns bilingual UI text and domain vocabulary. Stable data identifiers, hashes, source IDs, snapshot dates, source excerpts, and provenance values are not translated or rewritten.

Core locale artifacts:

- `ui/locales/en.json`
- `ui/locales/zh-CN.json`
- `ui/locales/glossary.json`
- `docs/specs/ui-localization.md`

## Workbench Product Direction

The UI should feel like a refined research instrument: quiet, dense, precise, and built for audit. The main visual memory should be the evidence chain: each comparison is shown as a sequence of required links, with missing or weak evidence visible immediately. The UI should use compact navigation, stable panels, structured tables, status chips, timelines, and side-by-side evidence views. Decoration should never obscure traceability.

Primary layout:

- Left navigation: phases, countries, review queue, comparison lens.
- Top controls: snapshot selector, country selector, molecule search, language switcher.
- Main panel: phase-specific artifact view.
- Right provenance panel: currently selected object's source, IDs, status, caveats, and links.
- Review drawer or page: anomalies, weak evidence, and human decisions.

## Phase 0: Repository Governance And Workbench Shell

**Goal:** Establish the repository as the system of record and provide a bilingual UI shell that can display project status before data exists.

**Data / Evidence Artifacts**

- Create `decisions/000-template.md`.
- Create `decisions/001-initial-scope.md`.
- Create `docs/specs/000-end-to-end-validation.md`.
- Create `docs/specs/repository-operating-rules.md`.
- Create top-level directories: `data/`, `data/raw/`, `data/snapshots/`, `data/canonical/`, `data/policy/`, `data/profiles/`, `data/comparisons/`, `data/review/`, `reports/`, `tests/`, `src/eu_pharma_price/`, and `ui/`.

**Workbench Artifacts**

- Create Workbench shell with:
  - Project Map
  - phase roadmap
  - country scope summary
  - artifact status panel
  - empty provenance panel
- The Project Map must show Ireland, Poland, and France as initially included, and Germany as initially excluded.
- The Project Map must distinguish stable commitments from working hypotheses.

**Localization Artifacts**

- Create `docs/specs/ui-localization.md`.
- Create initial locale dictionaries:
  - `ui/locales/en.json`
  - `ui/locales/zh-CN.json`
  - `ui/locales/glossary.json`
- Include translations for navigation, phase names, country scope labels, status labels, and stable commitment labels.

**Human Verification**

- Open the Workbench and switch between English and Chinese.
- Confirm the Project Map shows:
  - included: Ireland, Poland, France
  - excluded: Germany
  - phase roadmap from Phase 0 through Phase 9
  - no source, comparison, or profile data yet
- Open `decisions/001-initial-scope.md` and confirm scope decisions are written down.

**Completion Criteria**

- A decision not recorded in `decisions/` is visibly absent from the Workbench.
- The UI shell works with no data files beyond governance documents and locale dictionaries.
- No UI text appears as a raw translation key in either language.

## Phase 1: Data Contracts And Schema Map

**Goal:** Define the typed artifact contracts that enforce traceability and the two-gear comparison rule before any live data is processed.

**Data / Evidence Artifacts**

- Create schema specifications:
  - `docs/schemas/source-document.md`
  - `docs/schemas/raw-record.md`
  - `docs/schemas/canonical-price-record.md`
  - `docs/schemas/policy-interpretation.md`
  - `docs/schemas/data-profile.md`
  - `docs/schemas/derivation-rule.md`
  - `docs/schemas/comparison-candidate.md`
  - `docs/schemas/review-assessment.md`
  - `docs/schemas/anomaly-report.md`
- Create Python Pydantic model modules later during implementation:
  - `src/eu_pharma_price/schemas/source.py`
  - `src/eu_pharma_price/schemas/records.py`
  - `src/eu_pharma_price/schemas/policy.py`
  - `src/eu_pharma_price/schemas/profile.py`
  - `src/eu_pharma_price/schemas/comparison.py`
  - `src/eu_pharma_price/schemas/review.py`
- Add schema-level tests later under `tests/schemas/`.

**Workbench Artifacts**

- Add Schema Map view.
- Display artifact types as nodes:
  - Source Document
  - Raw Record
  - Canonical Price Record
  - Policy Interpretation
  - Data Profile
  - Derivation Rule
  - Comparison Candidate
  - Review Assessment
  - Anomaly Report
- Display required dependencies:
  - Comparison Candidate requires policy interpretations, data profiles, canonical records, source documents, and derivation rules when transformed values exist.
  - Review Assessment requires comparison candidate evidence bundle.

**Localization Artifacts**

- Add bilingual names and descriptions for all schema artifact types.
- Add glossary entries for:
  - policy interpretation / 政策解释
  - data profile / 数据画像
  - comparison candidate / 比较候选
  - review assessment / 审阅评估
  - anomaly report / 异常报告
  - derivation rule / 派生规则
  - source document / 来源文档

**Human Verification**

- Open Schema Map.
- Select `Comparison Candidate`.
- Confirm the UI shows that comparison is impossible without both policy interpretation and data profile.
- Switch language and confirm artifact IDs remain stable while labels change.

**Completion Criteria**

- Schemas can express "honest comparison or no comparison."
- No schema permits a bare price without currency, date, source reference, and raw record reference.
- No schema permits a transformed numeric value without a derivation rule.

## Phase 2: Source Register And Immutable Raw Capture

**Goal:** Capture published source documents as immutable, auditable raw inputs.

**Data / Evidence Artifacts**

- Create source registry specs:
  - `docs/specs/source-register.md`
  - `docs/specs/snapshot-layout.md`
- For each source captured later, write:
  - `data/raw/<country>/<snapshot_date>/manifest.json`
  - original source file under the same snapshot directory
  - hash, fetched-at timestamp, URL, source type, robots/ToS status, and manual-refresh status
- Add repository-local source fixtures for tests under `tests/fixtures/sources/`.

**Workbench Artifacts**

- Add Source Register view.
- Display countries, source documents, snapshot dates, hash values, fetched-at timestamps, source type, robots/ToS status, and manual-refresh status.
- Add empty and blocked states:
  - no source registered
  - source pending manual refresh
  - source captured but not parsed
  - hash mismatch detected

**Localization Artifacts**

- Add translations for source statuses:
  - registered
  - captured
  - pending manual refresh
  - blocked by robots or terms
  - hash verified
  - hash mismatch
- Keep URLs, hashes, filenames, and timestamps untranslated.

**Human Verification**

- Open Source Register.
- Select a captured source.
- Confirm source metadata is visible in both languages.
- Confirm the hash and fetched-at timestamp remain identical across languages.

**Completion Criteria**

- Re-running a source capture does not overwrite an existing dated snapshot.
- Every source file can be verified by hash.
- Tests use repository-local fixtures and do not require network access.

## Phase 3: Country Delegate Workspace

**Goal:** Parse each country independently into canonical records while preserving raw provenance and surfacing anomalies.

**Data / Evidence Artifacts**

- Create country delegate specs:
  - `docs/specs/country-delegate.md`
  - `docs/specs/canonical-record-normalization.md`
- Produce per-country artifacts later:
  - `data/canonical/<country>/<snapshot_date>/prices.parquet`
  - `data/canonical/<country>/<snapshot_date>/raw_to_canonical.parquet`
  - `reports/delegate/<country>/<snapshot_date>.md`
  - `reports/anomalies/<country>/<snapshot_date>.md` when needed
- Initial country delegates:
  - Ireland
  - Poland
  - France

**Workbench Artifacts**

- Add Country Workspace.
- Display source documents, raw rows, canonical records, raw-to-canonical links, delegate report summary, and anomaly summary for one country at a time.
- Add row-level provenance: selecting a canonical record opens its source document, raw record ID, hash, and parsed fields in the right panel.
- Prevent cross-country joins in this workspace.

**Localization Artifacts**

- Add translations for delegate statuses:
  - not started
  - source captured
  - parsed
  - canonicalized
  - anomaly reported
  - needs review
- Add glossary entries for:
  - raw record / 原始记录
  - canonical price record / 规范价格记录
  - country delegate / 国家代理

**Human Verification**

- Open Country Workspace for Ireland.
- Select a canonical record.
- Confirm the UI shows the raw record and source document it came from.
- Switch to Poland or France and confirm no other country's rows appear in the selected country's workspace.

**Completion Criteria**

- Every canonical record traces to at least one raw record.
- Delegate output does not assign cross-country meaning.
- Ambiguous fields produce anomaly reports instead of silent mappings.

## Phase 4: Policy Mapping View

**Goal:** Interpret national price fields into shared comparison vocabulary with provenance and caveats.

**Data / Evidence Artifacts**

- Create policy specs:
  - `docs/specs/policy-interpretation.md`
  - `docs/specs/comparison-vocabulary.md`
- Produce:
  - `data/policy/<country>/policy_interpretations.jsonl`
  - `reports/policy/<country>.md`
- Each policy interpretation must include:
  - national field name
  - shared comparison category
  - policy source references
  - effective date window
  - confidence or strength assessment
  - adjudication status
  - caveats

**Workbench Artifacts**

- Add Policy Mapping View.
- Display national field to shared vocabulary mapping.
- Show source citations, effective date window, confidence, caveats, and adjudication state.
- Add visual indication when a field is not comparable or needs review.

**Localization Artifacts**

- Add bilingual terms for comparison categories:
  - manufacturer-side price
  - payer reimbursement price
  - pharmacy purchase price
  - public retail price
  - unmapped price concept
  - not comparable
- Source excerpts remain in source language; UI explanations are localized.

**Human Verification**

- Select a national price field.
- Confirm the UI shows why the field maps to a comparison category or why it cannot be mapped.
- Switch language and confirm the source citation and source ID remain unchanged.

**Completion Criteria**

- Every comparable field has a policy interpretation ID.
- No comparison candidate can be built from a field without a usable policy interpretation.
- Policy interpretation does not modify numeric values.

## Phase 5: Data Health View

**Goal:** Profile whether policy-named fields actually exist and behave plausibly in each snapshot.

**Data / Evidence Artifacts**

- Create profile specs:
  - `docs/specs/data-profile.md`
  - `docs/specs/data-quality-thresholds.md`
- Produce:
  - `data/profiles/<country>/<snapshot_date>/data_profile.json`
  - `reports/profiles/<country>/<snapshot_date>.md`
- Profile dimensions:
  - field presence
  - non-null rate
  - value distribution
  - currency consistency
  - date coverage
  - duplicate patterns
  - unit and strength plausibility

**Workbench Artifacts**

- Add Data Health View.
- Display field-level status, distributions, missingness, currency/date checks, and whether the policy-named field is usable for comparison.
- Add explicit state for "policy permits this field, but data profile does not."

**Localization Artifacts**

- Add translations for data profile statuses:
  - usable
  - usable with caveat
  - exploratory
  - not usable
  - needs review
  - blocked by missing field
  - blocked by implausible distribution
- Numeric formatting follows locale display conventions, while raw values remain inspectable.

**Human Verification**

- Open Data Health View for a country and snapshot.
- Select a policy-named field.
- Confirm the UI shows whether data admits comparison.
- Confirm that a blocked field cannot appear as comparison-ready.

**Completion Criteria**

- Data profile status is snapshot-specific.
- A policy-usable field with insufficient data is blocked.
- Weak data is routed to review or anomaly outputs.

## Phase 6: Comparison Candidate View

**Goal:** Generate comparison candidates only when both policy and data evidence admit comparison.

**Data / Evidence Artifacts**

- Create comparison specs:
  - `docs/specs/comparison-candidate-generation.md`
  - `docs/specs/identity-matching.md`
  - `docs/specs/normalisation-rules.md`
- Produce:
  - `data/comparisons/<snapshot_date>/candidates.parquet`
  - `data/comparisons/<snapshot_date>/evidence_bundle.jsonl`
  - `reports/comparisons/<snapshot_date>/candidate-summary.md`
- Candidate generation must enforce hard exclusions:
  - never compare different molecules
  - never compare different routes of administration
  - never infer therapeutic equivalence across distinct ingredients

**Workbench Artifacts**

- Add Comparison Candidate View.
- Display molecule, strength, form, route, country pair, national fields, price values, policy status, data profile status, identity status, normalization status, and caveats.
- Show the evidence chain as required links:
  - source document
  - raw record
  - canonical record
  - policy interpretation
  - data profile
  - derivation rule
  - candidate

**Localization Artifacts**

- Add translations for evidence chain link labels and candidate statuses.
- Add bilingual display names for deterministic normalisation rules.
- Keep rule IDs, source IDs, and candidate IDs untranslated.

**Human Verification**

- Open a comparison candidate.
- Confirm every evidence chain link is present.
- Confirm a candidate with missing policy or missing data profile cannot appear.
- Switch language and confirm the evidence chain points to the same IDs.

**Completion Criteria**

- No candidate exists without both gears on both country sides.
- Every transformed number has derivation rule provenance.
- Candidate generation stops at candidate status; it does not publish final claims.

## Phase 7: Review Queue

**Goal:** Assess candidates end-to-end and prevent weak evidence from becoming a headline.

**Data / Evidence Artifacts**

- Create review specs:
  - `docs/specs/review-assessment.md`
  - `docs/specs/anomaly-routing.md`
- Produce:
  - `data/review/<snapshot_date>/review_assessments.jsonl`
  - `data/review/<snapshot_date>/queue.jsonl`
  - `reports/review/<snapshot_date>.md`
- Review dimensions:
  - policy strength
  - data strength
  - identity strength
  - normalisation strength
  - final usability label
  - caveats
  - human decision record when applicable

**Workbench Artifacts**

- Add Review Queue.
- Display candidates needing review, anomaly reports, blocked comparisons, decisions, caveats, and history.
- Add filters by country pair, molecule, status, evidence weakness, and snapshot.
- Add read-only decision history in the first implementation; write actions can be added after audit storage is defined.

**Localization Artifacts**

- Add translations for review labels:
  - usable
  - usable with caveat
  - exploratory
  - not comparable
  - needs human review
  - accepted with caveat
  - excluded
  - accommodated by design change
  - exempted for this instance
- Caveat text written by humans should store original language and optional localized summary separately.

**Human Verification**

- Open Review Queue.
- Confirm weak evidence appears in queue and not in final comparison outputs.
- Select an item and confirm policy, data, identity, and normalisation evidence are visible together.
- Switch language and confirm review labels translate while evidence IDs remain stable.

**Completion Criteria**

- Every candidate is either assessed or queued.
- No unreviewed weak evidence appears as a final comparison.
- Caveats travel with all downstream outputs.

## Phase 8: First End-To-End Validation

**Goal:** Walk one real country pair and one real molecule through every artifact and UI surface, recording friction and design changes.

**Data / Evidence Artifacts**

- Create:
  - `decisions/002-first-validation-case.md`
  - `reports/validation/001-end-to-end.md`
  - one complete evidence bundle for the selected country pair and molecule
- Select the validation case by scoring available records after Phase 3:
  - source availability
  - clear molecule identity
  - clear strength and form
  - likely policy interpretability
  - expected friction sufficient to test assumptions
- Record the final selected pair and molecule in `decisions/002-first-validation-case.md`.

**Workbench Artifacts**

- Add Audit Trail View.
- Display the complete path:
  - source document
  - raw record
  - canonical record
  - policy interpretation
  - data profile
  - derivation rule
  - comparison candidate
  - review assessment
  - report output
- Add broken-link indicators for any missing evidence.

**Localization Artifacts**

- Audit Trail View must be fully bilingual.
- Source evidence remains in original language.
- UI explanations and status labels switch between English and Chinese.

**Human Verification**

- Open the selected validation comparison.
- Trace the final displayed number back to source hash and raw record.
- Confirm the UI explains why the compared national fields are compatible.
- Confirm any caveat appears in both languages.

**Completion Criteria**

- One real comparison path is complete end to end.
- README working hypotheses are revised or reaffirmed based on observed friction.
- All design changes caused by validation are recorded in the repository.

## Phase 9: Research Comparison Workbench

**Goal:** Mature the Workbench into a bilingual comparison platform while preserving its audit-first nature.

**Data / Evidence Artifacts**

- Create:
  - `docs/specs/python-interface.md`
  - `docs/specs/report-generation.md`
  - `docs/specs/workbench-query-interface.md`
  - query examples for DuckDB and Python
  - comparison report templates
- Produce:
  - Python query interface
  - DuckDB query examples
  - on-demand comparison reports
  - UI comparison search and browse workflows

**Workbench Artifacts**

- Add Comparison Workbench.
- Support:
  - molecule search
  - country pair selection
  - snapshot selection
  - evidence-aware comparison cards
  - report preview
  - exportable audit bundle references
- Keep audit links first-class beside every price and conclusion.

**Localization Artifacts**

- Full bilingual UI coverage.
- Bilingual report chrome and labels.
- Original source excerpts remain in source language.
- Optional localized summaries must be marked as summaries, not source evidence.

**Human Verification**

- Query a molecule and country pair in English.
- Switch to Chinese and confirm the same comparison and evidence chain appear.
- Open the report and confirm snapshot date, source hashes, policy interpretations, data profiles, derivation rules, and review assessment are visible.

**Completion Criteria**

- Python, report, DuckDB, and UI outputs consume the same underlying artifacts.
- Every displayed figure is citable to a snapshot date and evidence bundle.
- The Workbench remains useful for blocked and not-comparable cases, not only successful comparisons.

## Cross-Phase Verification Rules

- Every phase must leave at least one human-readable artifact and one Workbench surface.
- Every Workbench surface must have English and Chinese coverage before the phase is complete.
- Every artifact shown in the UI must expose stable IDs in the provenance panel.
- Locale switching must not change selected artifact IDs, source hashes, snapshot dates, or evidence chain topology.
- Any generated report must state the snapshot date.
- Any anomaly or weak evidence must be routable to Review Queue.
- Tests must use repository-local fixtures.
- Network access is permitted only in the audited fetching step, never in agent runtime tests.

## Suggested Commit Sequence

- Phase 0 commit: `chore: establish governance and workbench shell`
- Phase 1 commit: `feat: define evidence schemas and schema map`
- Phase 2 commit: `feat: add source register and raw capture audit`
- Phase 3 commit: `feat: add country delegate workspace`
- Phase 4 commit: `feat: add policy mapping artifacts`
- Phase 5 commit: `feat: add data health profiles`
- Phase 6 commit: `feat: add comparison candidates`
- Phase 7 commit: `feat: add review queue`
- Phase 8 commit: `feat: validate first end-to-end comparison`
- Phase 9 commit: `feat: complete research comparison workbench`

## Self-Review

- Spec coverage: The plan covers README purpose, scope, two-gear rule, traceability, AI interpretation versus deterministic calculation, immutable snapshots, country boundaries, anomaly surfacing, local-first storage, Python/Pydantic/DuckDB/Parquet orientation, and UI as a peer deliverable.
- UI coverage: The Workbench appears in every phase and exposes phase deliverables as user-verifiable surfaces.
- Localization coverage: English and Simplified Chinese are required from Phase 0, with glossary-managed domain terms and stable untranslated IDs.
- Placeholder scan: The plan does not rely on unassigned implementation details for validation. The first validation case is selected by a defined scoring rule after country delegate data exists and is then recorded in a decision file.
- Type consistency: Artifact names are consistent across phases: source document, raw record, canonical price record, policy interpretation, data profile, derivation rule, comparison candidate, review assessment, and anomaly report.
