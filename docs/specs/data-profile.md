# Data Profile

A **data profile** assesses whether a policy-named price field actually exists in a specific snapshot, is populated, and behaves plausibly. It is the second gear of the comparison rule: a field with a policy interpretation but a bad data profile cannot enter a comparison candidate.

Profiles are produced **per snapshot** — never aggregated across dates. A field that was usable last quarter may be blocked this quarter.

## Profile Dimensions

The profiler computes the following for every policy-named field in a snapshot:

### 1. Field presence

Is the column produced by the delegate, present in `prices.parquet`?

- `true` — the field exists in the canonical output
- `false` — the field is missing entirely

If `false`, all subsequent dimensions return zero or null. The field is blocked from comparison.

### 2. Non-null rate

Fraction of canonical records where the field is non-null:

```
non_null_rate = non_null_count / record_count
```

Range: `[0.0, 1.0]`.

### 3. Value distribution

For numeric fields (e.g., `price_amount`):

- min, max, median, mean
- standard deviation
- percentiles: 5, 25, 75, 95
- outlier count using a configurable IQR threshold

For categorical fields (e.g., `dosage_form`):

- distinct value count
- top-k most frequent values

### 4. Currency consistency

Single currency in the snapshot? The profiler emits an anomaly if a snapshot mixes currencies — a rare but important failure mode.

### 5. Date coverage

- `snapshot_date` matches the directory partition?
- All canonical records share the same `snapshot_date`?
- Are any future-dated `snapshot_date` values present?

### 6. Duplicate patterns

How many groups of records share `(country_code, national_product_code, snapshot_date)`? Any group of size > 1 is a duplicate cluster — the profiler does not silently dedupe; it surfaces the count.

### 7. Unit and strength plausibility

Heuristic checks:

- `pack_size` parses as a positive integer or a recognised pattern (e.g., `30 x 10ml`)
- `strength` contains a numeric component
- `price_amount` is positive and within country-specific plausibility bounds

Implausible values increment `outlier_count` and may downgrade plausibility.

## Plausibility Assessment

Each profile carries a `plausibility_assessment` taking one of:

- `plausible` — passes all dimension checks above the configured thresholds
- `suspect` — passes presence and non-null but exhibits at least one warning-level issue
- `implausible` — fails a hard threshold (zero non-null, mixed currencies, future dates, all-zero prices)

## Comparison Gating

The data profile imposes a **second gate** on top of the policy gate:

- `field_exists = false` → blocked
- `non_null_rate < threshold` → blocked
- `plausibility_assessment = implausible` → blocked
- `plausibility_assessment = suspect` → not blocked, but downgrades `data_strength` to `weak` in the resulting comparison candidate's review

Thresholds are defined in [data-quality-thresholds.md](data-quality-thresholds.md).

## Storage

Profiles are written to:

- `data/profiles/<cc>/<snapshot_date>/data_profile.json` — machine-readable
- `reports/profiles/<cc>/<snapshot_date>.md` — human-readable

The JSON conforms to the [data-profile schema](../schemas/data-profile.md) — one entry per profiled field, plus an aggregate header for the snapshot.
