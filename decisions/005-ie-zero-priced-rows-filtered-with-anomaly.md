# Decision 005 — IE delegate filters zero-priced rows; emits anomaly per row

**Date:** 2026-05-16
**Status:** accepted (resolution=`exempt`)
**Discovered during:** real-data validation 002.

## Context

The PCRS druglist publishes ~12.5% of rows with `Reimbursement Price = 0.00`. These are not erroneous; they are administrative markers for:

- High Tech medicines (a separate scheme — published in a different file)
- reference-priced items where the published value is held at zero
- special-claim items billed via different mechanisms

Including them as canonical records pollutes the data profile (the profiler correctly flagged the IE 2026-05-16 snapshot as `implausible` because 20% of `price_amount` values were zero, breaking the 95% positive-rate threshold). With the snapshot blocked, no cross-country candidates can be generated against IE — including the otherwise-eligible IE↔PL `pharmacy_purchase_price` comparison.

## Decision

The IE delegate filters zero-priced rows out of the canonical output and emits one `policy_gap` anomaly per filtered row instead. Concretely:

- A raw row with `Reimbursement Price` numerically equal to `0` does not produce a canonical record.
- The same row produces an anomaly with `anomaly_type=policy_gap`, `severity=low`, `title="Zero-priced row excluded from canonical"`, citing the raw record ID and the product's national code so it can still be located.
- The row remains in `raw.parquet` (the raw layer is unchanged — append-only history is preserved per the charter).

This implements the `exempt` resolution outcome from the project charter §7: handle this specific instance without changing the design or extending the comparison vocabulary. The 95% positive-rate threshold remains in force.

## Why exempt, not accommodate

`accommodate` would mean introducing a country-specific threshold override or a new "include zero" plausibility tier. Neither is justified by one country's data quirk; the threshold was set deliberately conservatively, and the fix is to keep the threshold and use the anomaly system to record what was filtered.

## What this does NOT do

- Does not change the IE PolicyInterpretation. The interpretation describes what `Reimbursement Price` *means* in the publication; that meaning is unchanged.
- Does not silently drop data. Every filtered row produces an anomaly with full provenance.
- Does not affect any other country.
- Does not establish a precedent for filtering canonical records based on price values. The exemption is specifically: **`Reimbursement Price = 0`** in IE PCRS only.

## Caveats this introduces

- The anomaly count for IE PCRS will appear inflated (~1,000+ anomalies per snapshot). The Anomaly Routing rules apply: `low` severity items go to the audit log, not the human review queue.
- A future High Tech delegate (separate snapshot) will recover the prices for these excluded rows. The two delegates together restore full coverage; the druglist alone is not a complete IE picture.

## Implementation

In `src/eu_pharma_price/delegates/ireland.py`, override `_make_canonical` to short-circuit on `price_amount == 0` with an anomaly, before the parent class's price coercion runs.
