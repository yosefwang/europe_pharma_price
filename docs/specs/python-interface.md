# Python Interface

The `eu_pharma_price.query` package is the recommended entry point for embedding the substrate into researcher workflows. It is a thin façade over the underlying Parquet and JSONL artifacts — every figure returned is traceable to the same evidence chain the workbench renders.

## Design

- **Read-only.** No mutation. Researchers cannot accidentally rewrite snapshots through this interface.
- **Pydantic at the boundary.** Returned objects are `ComparisonRow`, `CandidateBundle`, `EvidenceLinks` — typed dataclasses, not raw dictionaries.
- **Same artifacts as the UI.** The query layer reads the same files the workbench reads, so figures cannot diverge.
- **Deterministic.** Same inputs return identical outputs; no internal caches that lie.
- **Local.** No hosted services. Everything resolves through the repository.

## Public API

```python
from eu_pharma_price.query import (
    available_windows,
    available_molecules,
    candidates_for_molecule,
    candidate_with_evidence,
    queue_for_window,
)
```

### `available_windows() -> list[str]`

Lists snapshot window IDs for which comparison candidates exist (e.g., `["2024-09-01"]`).

### `available_molecules(window: str) -> list[str]`

Lists distinct molecule INNs in a given window's candidate set.

### `candidates_for_molecule(window: str, molecule_inn: str) -> list[ComparisonRow]`

Returns one `ComparisonRow` per candidate matching the molecule. Each row carries:

- `candidate_id`, `country_a_code`, `country_b_code`
- `comparison_category`, `snapshot_date`, `dosage_form`, `strength`
- `price_a`, `currency_a`, `price_b`, `currency_b`
- `price_per_strength_unit_a`, `price_per_strength_unit_b`, `price_ratio`
- `usability` (from current review assessment)
- `caveats` (concatenated from policy + identity + review)

### `candidate_with_evidence(window: str, candidate_id: str) -> CandidateBundle`

Returns the full evidence chain for one candidate — same 16-link structure as the Audit Trail view.

### `queue_for_window(window: str) -> list[QueueEntry]`

Returns review queue entries (non-`usable` items) for a window. Useful for researchers who need to surface what was excluded and why.

## Working with the result

```python
from eu_pharma_price.query import candidates_for_molecule

rows = candidates_for_molecule("2024-09-01", "paracetamol")
for r in rows:
    print(
        f"{r.country_a_code}/{r.country_b_code}: "
        f"ratio={r.price_ratio} usability={r.usability}"
    )
    for c in r.caveats:
        print(f"  caveat: {c}")
```

## What the interface does NOT do

- Does not perform fuzzy molecule lookup. Inputs must match canonical INN exactly (the substrate intentionally avoids guessing identity).
- Does not aggregate across snapshot windows. Each query is window-scoped.
- Does not surface anomalies as comparisons — anomalies live in their own queue.
- Does not attempt cross-currency conversion. `price_ratio` is `None` when currencies differ.
