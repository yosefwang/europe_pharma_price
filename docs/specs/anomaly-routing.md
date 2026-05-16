# Anomaly Routing

Anomalies surface from many places in the pipeline (delegate, profiler, candidate generator, reviewer). Routing decides which humans see what, when.

## Anomaly Sources

| Origin | Typical anomaly_type | Severity heuristic |
|--------|----------------------|--------------------|
| Country delegate | `schema_mismatch` (missing required field, unparseable price) | `medium` |
| Data profiler | `distribution_outlier`, `source_inconsistency` | `medium` to `high` depending on hard/soft threshold breach |
| Candidate generator | `schema_mismatch` (unparseable strength/pack), `category_ambiguity` (cross-category pair) | `medium` |
| Reviewer | `policy_gap` (category bridge missing), `identifier_conflict` (national codes inconsistent for same INN/strength/form) | `medium` |
| Human reviewer | any type, with detailed `description` | as the human assigns |

Severities are assigned at emission time. The router does not re-score severity.

## Routing Rules

| Severity | Default queue | Decision recorded in |
|----------|---------------|----------------------|
| `critical` | Pause pipeline, alert human review | `decisions/` (mandatory) |
| `high` | Review Queue, marked `under_review` | `decisions/` (mandatory) |
| `medium` | Review Queue, marked `open` | `decisions/` (when resolution is `accommodate` or `exempt`) |
| `low` | Recorded in audit, optional review | `decisions/` (optional) |

The Review Queue is the single human-facing list. Anomaly reports are interleaved with assessment items in the queue display, distinguishable by their `anomaly_type` field.

## Resolutions

Per project charter §7, every anomaly resolves to one of:

- `accommodate` — extend the design (e.g., add a vocabulary category, extend a parser pattern). Recorded in `decisions/`.
- `exempt` — handle this specific instance without changing design. Recorded in `decisions/` for `high`/`critical`.
- `exclude` — the case is not in scope; remove from comparison surface.
- `accept_with_caveat` — surface with a permanent caveat that travels.

The system never **silently** resolves. A `resolved` status without a `resolution` field violates the schema.

## Audit Trail

Each anomaly's resolution is appended to `data/anomalies/<window>/resolutions.jsonl`. The original report is never modified — its `status` becomes `resolved` and the `resolution` is set; supersession is via a new entry.

## Read-Only in Phase 7

In this phase, the workbench surfaces anomalies and resolutions but does not allow writing them through the UI. Resolutions are added by editing `decisions/` files and the JSONL logs explicitly. A future phase wires write actions through the UI when audit storage is finalised.
