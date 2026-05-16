# Data Quality Thresholds

This document fixes the numeric thresholds used by the Data Health profiler to assign `plausibility_assessment` and decide whether a field is blocked from comparison.

These thresholds are **working hypotheses**. They are conservative starting points; real data is expected to push them. When a snapshot trips a threshold and the threshold itself appears wrong, the response is to file an anomaly report and propose a revision in `decisions/`, not to silence the check.

## Hard Block Thresholds (always block from comparison)

| Dimension | Threshold | Rationale |
|-----------|-----------|-----------|
| `field_exists` | must be `true` | A field that does not exist cannot be compared. |
| `non_null_rate` | ≥ 0.50 | Less than half populated is not a meaningful field. |
| `currency consistency` | exactly one currency in snapshot | Mixed currencies indicate the snapshot itself is not a single regime; comparison would fold incomparable observations together. |
| `record_count` | ≥ 1 | An empty snapshot has nothing to compare. |
| `price_amount > 0` rate | ≥ 0.95 | Bulk zero/negative prices indicate parsing or content failure. |
| `future-dated records` | == 0 | A snapshot dated 2024-06-15 with records dated 2030-01-01 is structurally broken. |

A field failing **any** of the above is recorded with `plausibility_assessment = implausible` and is **blocked** from being used in a comparison candidate.

## Soft Warning Thresholds (downgrade to suspect)

| Dimension | Threshold | Rationale |
|-----------|-----------|-----------|
| `non_null_rate` | < 0.90 | At least 10 % of the field is missing — usable but not authoritative. |
| `outlier_rate` | > 0.05 | More than 5 % of values fall outside the IQR-based outlier band. |
| `duplicate_cluster_count` | > 0 | At least one duplicate cluster exists — a small number is acceptable but worth flagging. |

A field exceeding any of the above (without hitting a hard block) is recorded with `plausibility_assessment = suspect`. Comparisons that include this field inherit `data_strength = weak`, which prevents `usable` review status (only `usable_with_caveat` or below).

## Plausible

A field that:

- has `field_exists = true`
- has `non_null_rate ≥ 0.90`
- has `outlier_rate ≤ 0.05`
- passes currency and date coverage checks
- has `duplicate_cluster_count == 0`

…is recorded with `plausibility_assessment = plausible`. Such a field is admitted to comparison candidates without data-strength penalty.

## Outlier Definition

For numeric fields, the IQR-based outlier band is:

```
lower = Q1 - 1.5 * IQR
upper = Q3 + 1.5 * IQR
where IQR = Q3 - Q1
```

A record's value is an outlier if it falls outside `[lower, upper]`.

For canonical price fields, an additional country-specific positivity floor applies: any non-null `price_amount ≤ 0` is always an outlier regardless of IQR position.

## Aggregate Snapshot Status

The profiler also records a snapshot-level status that summarises all profiled fields:

- `green` — every profiled field is `plausible`
- `yellow` — at least one field is `suspect`, none are `implausible`
- `red` — at least one field is `implausible`

The snapshot-level status drives the badge displayed in the Data Health view.

## Adjusting Thresholds

If a country's regime makes a threshold systematically wrong (e.g., a regime where 60 % populated is normal because the field is conditionally published), the response is:

1. Country delegate or profiler emits an anomaly report (`anomaly_type = distribution_outlier` or `policy_gap`)
2. The anomaly is resolved in `decisions/` with an outcome of `accommodate` (extend the threshold per country) or `accept_with_caveat` (keep the threshold, note the caveat)
3. Country-specific overrides live in `data/profiles/<cc>/thresholds.json` if needed

Do not adjust thresholds silently. Every override is a recorded decision.
