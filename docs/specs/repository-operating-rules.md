# Repository Operating Rules

> Codified from CLAUDE.md section 8 (Binding operating rules). These rules are stable commitments derived from the charter's core principles (section 4). They survive any working-hypothesis redesign. Violating any rule corrupts the substrate.

---

## Preamble

The charter states that "the principles in section 4 and the scope in section 2 imply specific Do/Don't rules" and that "violating any of these corrupts the substrate." This document expands each rule into its operational meaning: what it requires, what it prohibits, and how compliance is verified. It does not add rules beyond those in the charter; it makes the charter's rules executable.

---

## Rule 1: Every number traces to a source file hash and a raw record

**Charter source:** CLAUDE.md section 8, rule 1. Derived from section 4 (Traceability).

**Requirement.** No numeric value — price, exchange rate, unit count, VAT percentage, dosage strength — appears in any output unless it can be traced to:

- A specific file in `data/raw/` or `data/snapshots/`, identified by its content hash (SHA-256).
- A specific raw record within that file, identified by a stable record ID assigned at parse time.
- A fetched-at timestamp recording when the source was acquired.

**Partitioning rule.** `data/raw/` holds the original source file as published — the verbatim download with its hash, URL, and fetch metadata. `data/snapshots/` holds the immutable, dated partitions that the system uses as the authoritative reference for traceability. The raw file is the evidence of what was published; the snapshot is the system's versioned, queryable copy. Every snapshot traces to a raw file; every raw file may produce one or more snapshots.

**Prohibition.** Inventing, imputing, defaulting, or hard-coding a numeric value. If a source does not provide the value, the value does not exist in the substrate. A missing value is recorded as null with a reason, not filled with a proxy.

**Verification.** Every numeric field in `data/canonical/`, `data/comparisons/`, and all downstream outputs must carry a `source_hash` and `raw_record_id` attribute. A validation pass that finds a numeric field without these attributes fails.

---

## Rule 2: Derived values carry their derivation rule and ID; as-published values are preserved

**Charter source:** CLAUDE.md section 8, rule 2. Derived from section 4 (Traceability, AI interpretation / deterministic calculation).

**Requirement.** Any value that is not the as-published raw value must carry:

- A `derivation_rule` identifier pointing to a versioned, deterministic rule (e.g., `eur_to_pln_ecb_2026_03_15`, `per_unit_from_pack_price`).
- A `derivation_id` unique to this application of the rule.
- The input values the rule was applied to, preserved in full.
- A flag distinguishing derived values from as-published values.

As-published values are preserved unchanged in `data/canonical/`. Derivation happens downstream and is always additive — the as-published value is never overwritten or discarded.

**Prohibition.** Silent transformation. A derived value that does not carry its derivation rule, derivation ID, and inputs is indistinguishable from an invented value and is treated as a violation.

**Verification.** Every field in `data/comparisons/` that is not an as-published value must have non-null `derivation_rule` and `derivation_id`. The derivation rule must resolve to a deterministic function in `src/eu_pharma_price/` that produces the same output for the same inputs.

---

## Rule 3: Policy interpretation and data profile both required, on both sides

**Charter source:** CLAUDE.md section 8, rule 3. Derived from section 4 (Two gears: policy judges the data, data reflects the policy).

**Requirement.** A comparison between country A and country B for a given molecule/strength/form is permitted only when:

- A policy interpretation exists for the relevant price field in country A, mapping it to the comparison vocabulary with provenance and effective date.
- A data profile exists for the relevant snapshot in country A, confirming the field exists, is populated, and behaves plausibly.
- The same two conditions hold for country B.

Missing either piece on either side means the comparison does not proceed. There is no override, no partial comparison, and no "best effort" mode.

**Prohibition.** Comparing prices where one side lacks a policy reading or a data profile. Marking a comparison as "usable" when either gear is absent.

**Verification.** Every row in `data/comparisons/` must reference a `policy_id` and a `profile_id` for each side. A row missing any of these four references is rejected at the comparison stage.

---

## Rule 4: When in doubt, mark for review and stop

**Charter source:** CLAUDE.md section 8, rule 4. Derived from section 4 (Honest comparison or no comparison).

**Requirement.** Any agent or process that encounters ambiguity, low confidence, inconsistent data, or a situation not covered by existing rules must:

- Mark the affected record or comparison as `needs_review`.
- Record the reason for the flag.
- Stop processing that record downstream. It does not appear in reports or the UI until a human resolves the flag.

The review queue in `data/review/` is the single place where flagged items live. A flagged item is recoverable; a silently wrong figure in a report is not.

**Prohibition.** Guessing into outputs. Selecting the higher-confidence option when multiple interpretations exist without human adjudication. Suppressing a flag to make a pipeline run green.

**Verification.** No item in `data/comparisons/` with status `needs_review` may appear in a generated report or the UI. The review queue must be queriable and must include the flagging reason and originating agent.

---

## Rule 5: Snapshots are immutable — never overwrite a dated partition

**Charter source:** CLAUDE.md section 8, rule 5. Derived from section 4 (Raw record preservation, append-only history).

**Requirement.** A snapshot is written once to `data/snapshots/` under a dated partition (e.g., `data/snapshots/ie/2026-05-16/`). Once written, no file in that partition is modified, deleted, or replaced. If a subsequent fetch produces different data, it is a new snapshot under a new date.

Schemas evolve by adding new fields or new tables, not by renaming or removing existing ones. If a field is deprecated, it is marked deprecated; its data is not deleted.

**Prohibition.** Overwriting, patching, or backdating a snapshot. Renaming a column in a canonical schema (add a new column instead). Deleting data to "clean up."

**Verification.** The Git history of `data/snapshots/` must show no modifications to files after their initial commit. A CI check should enforce that no PR modifies files under `data/snapshots/` that were committed in a prior commit.

---

## Rule 6: Currency and date are always explicit

**Charter source:** CLAUDE.md section 8, rule 6. Derived from section 4 (Traceability).

**Requirement.** No bare numeric value representing money, time, or an exchange rate may exist without:

- An explicit ISO 4217 currency code (e.g., `EUR`, `PLN`).
- An explicit ISO 8601 date or datetime with timezone awareness (no naive datetimes).
- For exchange rates: the source of the rate (e.g., ECB reference rate) and the date the rate applies.

A price without a currency is meaningless. A price without a date is unanchored. An exchange rate without a source is unsourced.

**Prohibition.** Storing a price as a bare float. Using `datetime` without timezone. Applying an exchange rate without recording which rate, from which source, on which date.

**Verification.** Pydantic models at every data boundary enforce that monetary fields carry currency, temporal fields carry timezone, and FX operations carry source and date. A record failing these constraints is rejected at the boundary.

---

## Rule 7: Country boundaries are clean — no direct cross-country joins

**Charter source:** CLAUDE.md section 8, rule 7. Derived from section 4 (Two gears) and section 5 (Agent layer).

**Requirement.** No agent, process, or query joins data from two countries directly. Cross-country reasoning goes through the comparison layer (`data/comparisons/`), which mediates via policy interpretations and the shared comparison vocabulary. A Country Delegate agent for Ireland reads only Irish data; it never reads Polish data to inform its parsing or interpretation.

The comparison layer is the sole point where data from multiple countries meets. This boundary ensures that each country's data is produced independently and that comparisons are explicit, mediated, and auditable.

**Prohibition.** A SQL join across country partitions in `data/canonical/`. A Country Delegate agent reading another country's canonical records. A Python function that takes two countries' DataFrames and merges them outside the comparison layer.

**Verification.** The comparison layer is the only module that imports or reads from more than one country's canonical data. CI enforces that no other module depends on multiple country data sources simultaneously.

---

## Rule 8: No agent has internet access at runtime

**Charter source:** CLAUDE.md section 8, rule 8. Derived from section 5 (Agent layer) and section 4 (Traceability).

**Requirement.** LLM agents (Country Delegate, Policy Intelligence, Analytics, Review) operate on data already present in the repository. Fetching data from the internet is a separate, audited step that happens outside agent runtime. The fetch step records: the URL, the timestamp, the resulting file hash, and the `robots.txt` / ToS compliance check.

Agents may reference policy documents, but only documents already fetched and stored in `data/raw/` or `data/policy/`. An agent never makes an HTTP request during its reasoning.

**Prohibition.** An agent calling `requests.get()`, `urllib`, or any network function during execution. Passing a URL to an agent and expecting it to fetch the content. Using a tool-calling pattern where the agent triggers a web fetch.

**Verification.** Agent runtime environments have no network access (enforced by sandboxing, network namespace, or dependency restriction). The fetch step is a separate script or pipeline stage, logged in the audit trail.

---

## Rule 9: Repository-local fixtures only in tests

**Charter source:** CLAUDE.md section 8, rule 9. Derived from section 4 (Traceability) and section 9 (Technology orientation: reproducibility).

**Requirement.** Tests use only data that exists within the repository. Test fixtures are committed to `tests/` (or a subdirectory) and version-controlled alongside the code they test. No test depends on an external API, a live database, a network service, or a file not present in the repository.

Reproducibility is non-negotiable: any developer, on any machine, at any time, must be able to run the full test suite and get the same results, with no network access required.

**Prohibition.** A test that calls an external API (even a mock that requires network). A test that reads from `data/raw/` production data (tests use their own fixtures). A test that depends on a specific file path outside the repository. A test marked `@pytest.mark.skipif` due to network unavailability.

**Verification.** The test suite runs successfully with network access disabled. All test fixtures are committed files under `tests/`. CI runs the suite in a network-isolated environment.

---

## Rule 10: Honor robots.txt and Terms of Service

**Charter source:** CLAUDE.md section 8, rule 10. Derived from section 4 (Honest comparison or no comparison) and section 1 (Purpose: not scraping anything not voluntarily published).

**Requirement.** Before any data source is fetched, the fetch process checks:

- The source's `robots.txt` for crawl directives. If the desired path is disallowed, the fetch does not proceed.
- The source's Terms of Service for data-use restrictions. If the ToS prohibits automated extraction or redistribution, the fetch does not proceed without explicit legal clearance, recorded in `decisions/`.

Sources that cannot be automatically fetched due to `robots.txt` or ToS restrictions are marked as "manual-refresh" and fetched by a human operator who records the fetch manually. The manual-refresh status is part of the source's metadata.

**Prohibition.** Fetching from a path disallowed by `robots.txt`. Ignoring a ToS clause that restricts automated data extraction. Circumventing rate-limiting or access controls.

**Verification.** The fetch pipeline logs the `robots.txt` check result and the ToS review status for every source. A source without a logged `robots.txt` check cannot be fetched. Manual-refresh sources carry a `manual_refresh: true` flag.

---

## Rule 11: The repository is the system of record — decisions not in decisions/ did not happen

**Charter source:** CLAUDE.md section 8, rule 11. Derived from section 4 (Raw record preservation, append-only history).

**Requirement.** Every decision that affects the system's behavior, scope, design, or rules is recorded in `decisions/` using the template in `decisions/000-template.md`. This includes:

- Scope changes (adding or removing a country).
- Policy interpretation adjudications.
- Schema changes.
- Rule exceptions or overrides.
- Validation outcomes.
- Anomaly dispositions (accommodate, exempt, exclude, accept with caveat).

A decision recorded only in a Slack thread, a meeting, a commit message, or a verbal agreement does not count. It must be in `decisions/`, with all template fields filled, or it did not happen.

**Prohibition.** Acting on a decision that is not in `decisions/`. Treating a commit message as a decision record. Skipping the decision template because the change is "minor."

**Verification.** Any PR that changes system behavior, scope, or rules must reference a decision ID in `decisions/`. CI enforces that behavior-changing PRs carry a valid decision reference.

---

## Enforcement summary

| Rule | Primary enforcement | CI check |
|---|---|---|
| 1 (Trace to source) | Pydantic model constraints on `source_hash`, `raw_record_id` | Validation pass rejects records without traceability |
| 2 (Derivation rule) | Pydantic model constraints on `derivation_rule`, `derivation_id` | Comparison layer rejects derived values without provenance |
| 3 (Both gears) | Comparison layer gate | Comparison layer rejects rows missing any of four references |
| 4 (Mark for review) | Review agent and pipeline gating | No `needs_review` item appears in reports or UI |
| 5 (Immutable snapshots) | Git history + write-once convention | CI rejects modifications to committed snapshot files |
| 6 (Explicit currency/date) | Pydantic models with typed fields | Boundary validation rejects bare numbers and naive datetimes |
| 7 (Clean country boundaries) | Module dependency structure | CI enforces single-country data access outside comparison layer |
| 8 (No runtime internet) | Agent runtime sandboxing | Test suite runs with network disabled |
| 9 (Local fixtures only) | Test fixture convention | Test suite runs with network disabled |
| 10 (robots.txt / ToS) | Fetch pipeline checks | Fetch pipeline logs compliance for every source |
| 11 (Repository is record) | Decision template in `decisions/` | CI requires decision reference for behavior-changing PRs |
