# UI Localization Specification

> **Status:** stable commitment
> **Applies to:** Workbench UI (Task 3) and all downstream UI consumers

---

## 1. Supported Locales

| Code    | Language            | Direction |
|---------|---------------------|-----------|
| `en`    | English             | LTR       |
| `zh-CN` | Simplified Chinese  | LTR       |

The default locale is `en`. The user may switch at any time; the choice persists for the session and is stored in local preferences.

No other locales are in scope. Adding a new locale requires a locale file that mirrors the `en` key structure exactly (see section 4) and a corresponding amendment to this spec.

---

## 2. Locale File Format and Location

- **Format:** JSON, UTF-8, no BOM.
- **Location:** `ui/locales/<locale-code>.json`
- **Current files:**
  - `ui/locales/en.json` — English (authoritative key set)
  - `ui/locales/zh-CN.json` — Simplified Chinese

Every key that exists in `en.json` must exist in `zh-CN.json`. The reverse is not required (a Chinese-only key is allowed but discouraged). See section 7 for fallback behavior.

---

## 3. Key Naming Convention

Keys are **hierarchical and dot-separated**, using lowercase ASCII letters, digits, and hyphens.

```
<section>.<group>.<item>
```

Examples:

| Key                              | English value                |
|----------------------------------|------------------------------|
| `nav.projectMap`                 | Project Map                  |
| `phase.p0.name`                  | Phase 0                      |
| `phase.p0.description`           | Scoping and charter          |
| `countryScope.initiallyIncluded` | Initially Included           |
| `status.stableCommitment`        | stable commitment            |
| `evidence.sourceDocument`        | source document              |
| `comparison.manufacturerSide`    | manufacturer-side price      |
| `ui.search`                      | Search                       |

**Rules:**

- Top-level segments correspond to semantic domains: `nav`, `phase`, `countryScope`, `country`, `status`, `evidence`, `comparison`, `usability`, `ui`.
- Key segments use camelCase.
- Values are plain strings, not HTML or Markdown. If a value needs interpolation (e.g., a country name), the consuming component handles it; the locale file contains the template string with a `{placeholder}` marker.

---

## 4. What Is Translated

The following categories of UI text are translated:

| Category                    | Examples                                                        |
|-----------------------------|-----------------------------------------------------------------|
| Navigation labels           | Project Map, Schema Map, Source Register, ...                   |
| Phase names and descriptions| Phase 0, Phase 1, ...                                          |
| Country scope labels        | Initially Included, Initially Excluded, Candidate Pool, ...     |
| Status labels               | stable commitment, working hypothesis, not started, ...         |
| Stable commitment labels    | (the status labels above that are marked stable commitment)     |
| Comparison category names   | manufacturer-side price, payer reimbursement price, ...         |
| Usability labels            | usable, usable with caveat, exploratory, not comparable, ...    |
| Evidence chain labels       | source document, raw record, canonical price record, ...        |
| General UI chrome           | Search, Filter, Snapshot, Date, Currency, Language, ...        |
| Country display names       | Ireland, Poland, France, ...                                   |

---

## 5. What Is NOT Translated

The following are never translated, in any locale. They are displayed exactly as stored in the data layer.

| Category         | Examples                                          | Reason                                      |
|------------------|---------------------------------------------------|---------------------------------------------|
| Stable data identifiers | ATC codes, INN identifiers, EDQM codes     | Machine-readable; translation corrupts them |
| Hashes           | SHA-256 digests of source files                   | Cryptographic values                        |
| Source IDs       | Internal identifiers for source documents         | Referential integrity                       |
| Snapshot dates   | `2025-01-15`                                      | ISO 8601; locale-independent                |
| Source excerpts  | Quoted text from official publications            | Must match the original verbatim            |
| Provenance values| Agent IDs, rule IDs, derivation chain tokens      | Auditable references                        |
| URLs             | Source publication URLs                           | Must resolve identically                    |
| Filenames        | Parquet partition paths, PDF filenames            | Filesystem references                       |
| Currency codes   | EUR, PLN, CHF, etc.                               | ISO 4217; not translated                    |

---

## 6. Glossary File

The glossary (`ui/locales/glossary.json`) serves a distinct purpose from the locale dictionaries:

- **Locale dictionaries** translate *UI chrome* — the labels, buttons, headings, and status text that make up the interface.
- **The glossary** maps *domain terms* between English and Chinese with stable identifiers. It is used when the UI needs to display a domain term in a contextual way (e.g., a tooltip explaining "ATC" or a table rendering the comparison vocabulary with bilingual labels).

Each glossary entry has:

| Field   | Type   | Required | Description                                      |
|---------|--------|----------|--------------------------------------------------|
| `id`    | string | yes      | English kebab-case identifier (e.g., `reimbursement-price`) |
| `en`    | string | yes      | English term                                     |
| `zh-CN` | string | yes      | Simplified Chinese term                          |
| `note`  | string | no       | Clarification or context                         |

The `id` field is stable across the project lifetime. It is used as a programmatic key, never shown to the user directly.

---

## 7. Fallback Behavior

When a translation key is looked up at runtime:

1. Look up the key in the active locale file (e.g., `zh-CN`).
2. If the key is present and its value is a non-empty string, use it.
3. If the key is missing or its value is empty, fall back to `en`.
4. If the key is also missing in `en`, this is a **bug** — see section 8.

**Rule: No raw translation key shall ever be visible to the user in either locale.** If a key resolves to nothing, the UI must display a fallback indicator (e.g., `[missing: nav.projectMap]`) that clearly marks the failure, not the raw key structure. This makes missing translations immediately visible during development and impossible to ship.

---

## 8. Validation

The following checks must pass before any release:

1. **JSON validity:** Both locale files and the glossary must parse as valid JSON.
2. **Key parity:** Every key in `en.json` must exist in `zh-CN.json` (extra keys in `zh-CN` are allowed but generate a warning).
3. **No empty values:** No key in either file may map to an empty string. An empty value means "not yet translated" and must be filled before merge.
4. **Glossary completeness:** Every glossary entry must have both `en` and `zh-CN` fields populated.
5. **No raw keys in rendered UI:** A visual spot-check must confirm that no rendered view shows a dot-separated key path to the user.

These checks are enforced by CI (or a pre-merge hook) once the Workbench UI build is established.

---

## 9. Adding New Keys

When a new UI feature requires a new translation key:

1. Add the key and its English value to `en.json`.
2. Add the same key with its Chinese translation to `zh-CN.json` in the same commit.
3. If the key names a domain concept, also add a glossary entry.
4. Do not merge a PR where `en.json` has keys absent from `zh-CN.json`.

---

## 10. Amendment Protocol

This spec is a **stable commitment**. Changes to sections 1 (supported locales), 5 (what is not translated), 7 (fallback behavior), or 8 (validation) require a recorded decision in `decisions/`. Changes to section 4 (what is translated) that add new categories are working hypotheses until validated.
