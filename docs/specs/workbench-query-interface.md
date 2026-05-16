# Workbench Query Interface

The Comparison Workbench view is the researcher-facing search and browse surface. It is a peer to the Python query interface — both consume the same artifacts.

## Search Workflow

1. **Pick a snapshot window.** Defaults to the most recent.
2. **Search by molecule.** Free-text input matches against `molecule_inn` exactly (no fuzzy matching — exact INN, case-insensitive).
3. **Filter by country pair (optional).** Multiple selections allowed.
4. **Filter by usability (optional).** Defaults to `usable | usable_with_caveat`. Researchers wanting to see blocked cases switch to "all".
5. **Result table.** Each row is one candidate. Columns: molecule, strength, form, country pair, comparison category, price ratio, usability badge, caveat-count badge.

## Comparison Card

Selecting a candidate opens an "evidence-aware card" showing:

- Headline price figures for both sides, with currency, pack, per-strength-unit value
- Comparison category and a one-paragraph compatibility explanation
- All caveats (bulleted, no truncation)
- Strength tuple from review (four mini-badges)
- Six-link audit chain per side, identical to Audit Trail view
- "Open report" button that renders the markdown report inline
- "Open audit trail" link that navigates to the dedicated Audit Trail view

## Blocked-Case Display

When a candidate's review usability is `not_comparable` or `exploratory`, the card adds a banner at top:

- For `not_comparable`: a red banner naming the blocking issues. The audit chain remains visible — researchers can still see *why* the comparison was refused.
- For `exploratory`: an amber banner explaining the limitation (typically currency mismatch).

This is the workbench's most important property for research use: refused comparisons are findings, not voids.

## Localization

- Labels, banners, badges: switched between English and Chinese via the global locale.
- Source URLs, canonical IDs, file hashes, raw values, interpretation text, caveat text: rendered as-is in their original form.
- Country names: localized.
- Comparison category: localized (already in `policy.category.*`).

## Stable IDs in Provenance Panel

The right-hand provenance panel always shows:
- `candidate_id`
- `snapshot_window`
- `current_review_id`

These IDs do not change when the locale switches.

## Export

A future iteration will add an "export audit bundle" button that writes a zipped directory of every artifact in the chain plus the generated markdown report. For Phase 9, the underlying data is already available in the repository — the query interface enumerates the IDs; researchers can copy them out manually.
