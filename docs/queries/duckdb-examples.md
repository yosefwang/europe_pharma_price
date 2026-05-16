# DuckDB query examples

DuckDB reads the project's Parquet artifacts directly. These examples assume the working directory is the repository root.

## Setup

```sql
-- Direct file references — no schema migration needed.
-- All paths are relative to the repository root.
```

## List candidate windows

```sql
SELECT DISTINCT regexp_extract(filename, 'comparisons/([^/]+)/', 1) AS window
FROM glob('data/comparisons/*/candidates.parquet') AS files(filename)
ORDER BY window;
```

## Distinct molecules in a window

```sql
SELECT DISTINCT molecule_inn
FROM 'data/comparisons/2024-09-01/candidates.parquet'
ORDER BY molecule_inn;
```

## Candidates for one molecule

```sql
SELECT
  id AS candidate_id,
  country_a_code, country_b_code,
  comparison_category,
  strength, dosage_form,
  price_ratio,
  identity_confidence
FROM 'data/comparisons/2024-09-01/candidates.parquet'
WHERE LOWER(TRIM(molecule_inn)) = 'paracetamol';
```

## Join candidates with their per-strength-unit prices

The evidence bundle JSONL stores per-side derived figures. DuckDB reads JSONL natively:

```sql
SELECT
  c.id AS candidate_id,
  c.molecule_inn,
  c.country_a_code,
  c.country_b_code,
  c.price_ratio,
  e.country_a.price_per_strength_unit AS price_per_strength_unit_a,
  e.country_b.price_per_strength_unit AS price_per_strength_unit_b
FROM 'data/comparisons/2024-09-01/candidates.parquet' c
JOIN read_json_auto(
  'data/comparisons/2024-09-01/evidence_bundle.jsonl',
  format='newline_delimited'
) e
ON c.id = e.candidate_id
WHERE c.molecule_inn = 'paracetamol';
```

## Join candidates with current review usability

```sql
SELECT
  c.molecule_inn, c.country_a_code, c.country_b_code,
  r.usability,
  r.policy_strength, r.data_strength,
  r.identity_strength, r.normalisation_strength
FROM 'data/comparisons/2024-09-01/candidates.parquet' c
LEFT JOIN read_json_auto(
  'data/review/2024-09-01/review_assessments.jsonl',
  format='newline_delimited'
) r
ON r.comparison_candidate_id = c.id
ORDER BY c.molecule_inn;
```

## Find candidates with caveats from upstream

```sql
SELECT
  c.molecule_inn, c.country_a_code, c.country_b_code,
  r.usability,
  list_aggregate(r.caveats, 'string_agg', ' | ') AS combined_caveats
FROM 'data/comparisons/2024-09-01/candidates.parquet' c
JOIN read_json_auto(
  'data/review/2024-09-01/review_assessments.jsonl',
  format='newline_delimited'
) r
ON r.comparison_candidate_id = c.id
WHERE list_count(r.caveats) > 0
ORDER BY c.molecule_inn;
```

## Snapshot-level data health for a country

```sql
SELECT
  country_code, snapshot_date, snapshot_status,
  list_aggregate(profiles, 'string_agg', ', ') AS field_summary
FROM read_json_auto(
  'data/profiles/ie/2024-09-01/data_profile.json'
);
```

## All non-usable candidates across windows

```sql
SELECT
  regexp_extract(filename, 'review/([^/]+)/', 1) AS window,
  candidate_id, usability, blocking_issues, caveats
FROM read_json_auto(
  'data/review/*/queue.jsonl',
  format='newline_delimited',
  filename=true
);
```

## Hash-verify file integrity (programmatic)

DuckDB cannot directly compute file hashes, but you can list manifests:

```sql
SELECT
  files.filename,
  files.file_hash,
  files.file_size_bytes
FROM read_json_auto(
  'tests/fixtures/sources/*/*/manifest.json',
  format='auto'
), unnest(files) AS files;
```

Then verify hashes from Python or `sha256sum`.

## Caveats about querying directly

- Running aggregates over price columns silently treats canonical `price_amount` strings as text — cast explicitly: `CAST(price_amount AS DECIMAL(18,6))`.
- The substrate stores currency separately; never compute price aggregates without filtering on `price_currency` first.
- Cross-snapshot aggregation is the researcher's responsibility — the substrate does not pre-roll.
- Candidates for the same molecule across windows must be unioned manually.
