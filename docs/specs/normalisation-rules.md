# Normalisation Rules

Numeric transformations applied to canonical price records before comparison. Every transformation references a `DerivationRule` ID — there are no silent numeric transformations anywhere in the substrate.

## Strength Parsing

The canonical record stores `strength` as published (e.g., `"500mg"`, `"5 mg/ml"`, `"100 IU"`). The strength parser splits this into:

- `strength_value` — `Decimal`
- `strength_unit` — UCUM-conformant unit code (e.g., `mg`, `g`, `mg/ml`, `[iU]`)

Supported patterns (working hypothesis):

- `"<n>mg"` / `"<n> mg"` — milligrams
- `"<n>g"` — grams  
- `"<n>mcg"` / `"<n>µg"` — micrograms (normalised to UCUM `ug`)
- `"<n> mg/ml"` — concentration
- `"<n> IU"` — international units
- `"<n>%"` — percentage strength

When the strength string does not match any supported pattern, the parser returns `None` and the candidate generator emits an anomaly (`anomaly_type: schema_mismatch`) instead of producing a candidate.

## Pack Size Parsing

`pack_size` is also stored as published. The parser splits it into:

- `pack_size_value` — `int` (number of administered units per pack)
- `pack_size_pattern` — the pattern that matched (for audit)

Supported patterns:

- `"<n>"` — bare integer (e.g., `"28"` → 28 tablets)
- `"<n> tab"` / `"<n> tablets"` — explicit unit count
- `"<n> x <m>"` — `<n>` units of `<m>`-something each (currently only `n` is taken for unit count; the second factor is preserved in raw)

When a pack size does not match a supported pattern, the parser returns `None` and the candidate generator emits an anomaly.

## Per-Unit Price Derivation

Once strength and pack size are parsed, the `per_unit` derivation rule produces:

```
price_per_unit = price_amount / pack_size_value
price_per_strength_unit = price_per_unit / strength_value
```

`price_per_strength_unit` is in the strength's natural unit (e.g., EUR per mg). For comparison across countries with the same currency, this can be compared directly. For comparison across currencies, an additional `currency_conversion` rule is needed (Phase 7+ scope).

Each derived value carries a `DerivationRule` ID with:
- `rule_type = per_unit` or `pack_normalisation`
- `formula` = the literal formula above
- `input_fields` = `["price_amount", "pack_size_value", "strength_value"]`
- `output_field` = `"price_per_unit"` or `"price_per_strength_unit"`
- `effective_from` = the snapshot date
- `source_reference` = `"docs/specs/normalisation-rules.md"`

## Currency Handling (deferred)

Currency conversion is **out of scope for Phase 6**. Candidates are only generated between countries sharing a currency, OR with `price_ratio` left null when currencies differ. Cross-currency comparison requires a separate `currency_conversion` derivation rule with explicit FX source and date — added in a later phase or by ad hoc decision.

## Hard Exclusion: No Form-Crossing Normalisation

Even when normalisation produces compatible numbers, the matcher's hard exclusions still apply. A tablet and an injection of the same molecule at the same per-mg price are not comparable; the comparison layer rejects the pair before any normalisation is considered.

## Idempotency

All normalisation rules are pure functions of their inputs:

- Same `(price_amount, pack_size, strength)` → same `(price_per_unit, price_per_strength_unit)` every time
- No round-tripping through floats: `Decimal` throughout
- Rules do not mutate canonical records

Re-running the candidate generator on the same snapshot produces identical artifacts (modulo timestamps and UUIDs, which the generator can be configured to keep stable across runs by hashing inputs).

## When Normalisation Disagrees

If a country publishes `strength = "500mg"` but the actual per-tablet content is `250mg` (this happens with combination products listed under a non-INN aggregate name), the parser cannot detect the discrepancy from the data alone. This is a **policy interpretation** matter — Policy Intelligence may flag specific products, and the resulting policy interpretation is what triggers the matcher to drop or downgrade. The normalisation layer trusts canonical strength as published.
