# Review Assessment

The Review layer is the system's last gate before a candidate becomes a published comparison. It evaluates the full evidence chain end-to-end and assigns a `usability` label. No candidate reaches the substrate as a "final comparison" without passing through review.

This phase implements an **automated reviewer** that produces an initial assessment for every candidate using deterministic rules over the strength dimensions already captured upstream. Human reviewers can override an automated assessment; both records survive in the audit log.

## Review Dimensions

For each candidate, the reviewer scores four dimensions:

| Dimension | Source | `strong` | `adequate` | `weak` |
|-----------|--------|----------|------------|--------|
| `policy_strength` | confidence on both `PolicyInterpretation` records | both `high` | at least one `medium` | at least one `low` |
| `data_strength` | both `DataProfile` plausibility assessments | both `plausible` | at least one `suspect` | at least one `implausible` (already blocked upstream — should not appear) |
| `identity_strength` | `identity_confidence` on the candidate | `exact` | `high` | `medium` or `low` |
| `normalisation_strength` | derivation rules applied | both sides used `per_unit`+`pack_normalisation` with same strength unit | one side required category-bridging caveats | per-unit derivation impossible or partial |

When `derivation_rule_*_id` is `None` on either side (e.g., currency conversion deferred, normalisation skipped), `normalisation_strength` is `not_applicable`. The aggregator treats `not_applicable` as neutral.

## Final Usability Label

The reviewer maps the four-dimension tuple to one of four usability labels:

| Tuple shape | Label |
|-------------|-------|
| All `strong` (or `not_applicable` for normalisation) | `usable` |
| Any `weak` | not `usable` — falls to one of below |
| At least one `adequate`, no `weak` | `usable_with_caveat` |
| Currency mismatch leaving `price_ratio = null` | `exploratory` |
| Identity confidence `low`, OR data `weak`, OR comparison-category bridge missing | `not_comparable` |

The label rules are intentionally conservative. A candidate marked `usable` here is one the system is willing to surface as a primary headline figure; everything else carries permanent caveats or stays out of headline tables.

## Caveats Travel

Caveats originate in three places:

1. **Policy interpretation** — caveats from the cited regulation (`PolicyInterpretation.caveats`)
2. **Identity matcher** — when packs differ, when forms are unusual, when route was inferred
3. **Normalisation** — when units don't line up perfectly

The reviewer concatenates all upstream caveats into the assessment's `caveats` list. Every downstream consumer of the assessment (substrate query, generated report, UI) renders them. A caveat present in the source policy interpretation is **never silently dropped**.

## Blocking Issues

A `not_comparable` assessment must list at least one entry in `blocking_issues`. The reviewer fills this with the dimension and reason — e.g., `"data_strength=weak: country_a profile suspect"`.

## Human Override

Humans can override an automated assessment. The override creates a new `ReviewAssessment` record with:

- `human_override = true`
- `override_rationale = <reason>`
- the previous assessment's ID copied into `superseded_by` on the previous record

Both records remain in the JSONL log. The Review Queue view always shows the most recent (non-superseded) assessment as current, with previous assessments accessible through the candidate history.

In Phase 7, write actions are not yet wired into the UI — overrides are made by editing the JSONL with explicit attribution. A later phase adds workflow.

## Storage

```
data/review/<snapshot_window_id>/
├── review_assessments.jsonl   # one ReviewAssessment per line; append-only
└── queue.jsonl                # one queue entry per non-final candidate
```

`queue.jsonl` is a derived view of `review_assessments.jsonl`, regenerated each run. It contains every candidate whose current assessment is not `usable` — the human-facing list of work pending.

`reports/review/<snapshot_window_id>.md` is a human-readable summary.

## What Review Does NOT Do

- Does not modify any numeric value.
- Does not change any upstream artifact (policy, profile, candidate).
- Does not invent caveats — only propagates them.
- Does not silently exclude. A `not_comparable` is a recorded refusal; the audit chain still exists, just does not surface as a comparison.
