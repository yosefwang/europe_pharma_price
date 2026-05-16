# Report Generation

Comparison reports are markdown documents generated on demand from a candidate's evidence bundle. They are reproducible, citable, and explicitly link every figure to its source.

## Design Principles

- **Bilingual chrome, source-language evidence.** Section labels and explanatory copy translate; source URLs, canonical IDs, file hashes, and original-language interpretation text stay as published.
- **Snapshot-dated.** Every report names the snapshot window in its title and front matter. Re-generating from the same artifacts yields identical content (except generation timestamp).
- **No standalone numbers.** Every numeric figure carries its currency, snapshot date, and the derivation rule that produced it.
- **Caveats are first-class.** A report with caveats lists them inside a "Caveats" section that downstream readers cannot miss.
- **Audit links visible.** Each section names the canonical, raw, policy, and profile IDs supporting its figures.

## Report Structure

```
# Comparison report — <molecule> — <country_a> ↔ <country_b>

**Snapshot window:** <date>  
**Generated:** <iso8601_timestamp>  
**Candidate ID:** <uuid>  
**Usability:** <usable|usable_with_caveat|exploratory|not_comparable>

## Summary

A short prose paragraph stating the figure, the regimes compared, and the
strongest caveat in one sentence.

## Headline figures

- Country A side: <price_amount> <currency> per pack of <pack_size>; per
  strength unit: <price_per_strength_unit> <currency>/<unit>
- Country B side: <price_amount> <currency> per pack of <pack_size>; per
  strength unit: <price_per_strength_unit> <currency>/<unit>
- Price ratio (A / B): <ratio> | <reason if null>

## Why these fields are compatible

A short explanation derived from both sides' policy interpretations,
naming the comparison category and the source citations.

## Caveats

Bulleted list of every caveat from policy interpretations + identity +
review.

## Evidence chain

Two columns (A, B), each listing:
- source document (URL + file hash)
- canonical record ID
- raw record ID
- policy interpretation ID + sources
- data profile ID + plausibility
- derivation rule ID + formula

## Review assessment

Strength tuple, blocking issues (if any), rationale.
```

## Language

Reports are generated in **one language at a time**. The locale parameter selects which translations of section labels and explanatory chrome are rendered. Source citations, interpretation_text, caveat text, and IDs render in their original form regardless of locale — translating those would either lose precision or invent translations of formal regulatory language.

When a localized summary is added (a future option), it is rendered in a separate clearly-labeled "Localized summary" block — not interleaved with source evidence.

## Reports for Non-Usable Candidates

Reports can be generated for `not_comparable` candidates. The headline figures still appear (so readers see what was being compared) but a banner at the top states the candidate is not suitable for headline use, and the blocking issues are listed before the caveats. The audit chain remains complete.

This is deliberate: blocked cases are part of the substrate's value. A researcher who wants to know "did anyone try to compare X across these countries, and why didn't it work?" needs the same audit chain as someone consuming a usable comparison.

## Storage

Reports are written to:

```
reports/comparisons/<window>/<candidate_id>-<lang>.md
```

Reports are not pre-generated for every candidate. The query layer provides `generate_report(window, candidate_id, lang)` as the only producer.

## Idempotency

Re-generating a report with the same locale and the same artifacts produces byte-identical output (except the `Generated` timestamp). The IDs, hashes, and figures are functions of the artifacts.
