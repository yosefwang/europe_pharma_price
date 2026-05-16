# 000-end-to-end-validation

> Spec for the first end-to-end validation. Derives from CLAUDE.md section 7 (How the system evolves), first end-to-end validation subsection.

---

## Purpose

Before the working-hypothesis sections of the charter (CLAUDE.md sections 5, 6, and the working choices within section 9) harden into design commitments, the system must prove it can walk one real country pair and one real molecule through every artifact and UI surface — with every traceability link resolved, every policy reading grounded in a source, every data profile backed by a snapshot, and every numeric derivation carrying its rule and inputs. A human must review the result and record the friction encountered.

This is not a demonstration. It is a stress test. The validation is chosen to surface real frictions, not to confirm convenient assumptions.

## What the validation must exercise

The validation must walk one country pair and one molecule through the complete pipeline:

1. **Raw data acquisition.** A snapshot of each country's official price source is fetched, hashed, and stored in `data/raw/` with a fetched-at timestamp. The fetch is recorded as an audited step.

2. **Canonical record production.** Each country's Country Delegate agent parses the raw snapshot into canonical records in `data/canonical/`, preserving the raw record, assigning IDs, and describing each price field's local meaning without assigning cross-country significance.

3. **Policy interpretation.** The Policy Intelligence agent reads each country's delegate output alongside official policy material, produces typed policy interpretations in `data/policy/` mapping national price fields to the comparison vocabulary. Each interpretation carries provenance, an effective-date window, and an adjudication record.

4. **Data profiling.** The Analytics agent profiles each snapshot in `data/profiles/`, confirming that the fields the policy reading names actually exist, are populated, and behave plausibly. Fields that fail profiling are flagged, not silently dropped.

5. **Comparison production.** The Secretariat agent joins canonical rows across the two countries through policy interpretations, applies deterministic normalisation (currency, per-unit, VAT), and produces comparison candidates in `data/comparisons/` with full evidence chains.

6. **Review and usability assessment.** The Review agent assesses each comparison candidate for usability, combining policy strength, data strength, identity strength, and normalisation strength. Weak candidates are marked for review, not forced into outputs.

7. **Report generation.** A comparison report is produced from the reviewed comparison, citable to a snapshot date, naming the national price fields, the policy reading, the data, and the caveats.

8. **Python interface.** The same substrate is queryable through the Python interface, returning the same artifacts with the same traceability links.

9. **Interactive UI.** The comparison is browsable in the UI, with audit links as first-class navigation: every figure links to its policy interpretation, its data profile, its raw record hash, and its derivation rule.

## How the country pair and molecule are chosen

The pair and molecule are **not** predetermined. They are chosen after Phase 3 (when at least two countries have canonical records and initial policy readings) by scoring candidates against five criteria:

| Criterion | What it measures |
|---|---|
| **Source availability** | Can the raw source be fetched, parsed, and hashed without exceptional effort? Is it freely accessible and machine-readable? |
| **Clear molecule identity** | Does the molecule have an unambiguous INN and ATC code? Can it be matched across the two countries without relying on brand names or fuzzy matching? |
| **Clear strength and form** | Is the strength expressed in a single, comparable unit (e.g., mg, mL) and the dosage form in a standardised vocabulary (e.g., EDQM Standard Terms)? No ambiguous combinations, no extended-release qualifiers that differ between countries. |
| **Likely policy interpretability** | Do both countries publish price fields that plausibly map to the same comparison-vocabulary category? Is there at least one candidate pair of fields where the policy reading can be grounded in official sources for both sides? |
| **Expected friction** | Does the candidate present at least one known or suspected difficulty — language difference, multi-field selection ambiguity, currency normalisation, VAT treatment, identifier mismatch — that would test the system's ability to handle real complexity rather than the easiest possible case? |

The scoring is qualitative, not numerical. The goal is to pick a candidate that is tractable enough to complete end-to-end but difficult enough to expose assumptions. A candidate that is easy on all five criteria is less valuable than one that scores well on four and introduces friction on the fifth.

The choice is recorded in `decisions/` as a formal decision (using the template in `decisions/000-template.md`), naming the pair, the molecule, the score on each criterion, and the reasoning behind the selection.

## What counts as "met"

The validation is met when:

- Every artifact listed in the pipeline above exists for the chosen pair and molecule, is populated, and is internally consistent.
- Every figure in the comparison report, the Python interface output, and the UI trace end-to-end to a source file hash, a raw record, a policy interpretation, a data profile, and (where applicable) a derivation rule with its inputs.
- A human has reviewed the full chain and found no missing links, no ungrounded assertions, and no silent transformations.
- All frictions encountered during the validation are recorded in `decisions/`.
- The working-hypothesis sections of the charter (sections 5, 6, working choices in section 9) are revised in the same commit as the design changes that arose from the validation.

## What happens before validation is met

Until this validation is met:

- The working-hypothesis sections of the charter (CLAUDE.md sections 5, 6, working choices within section 9) are **notional** — they describe the current best guess, not a binding commitment.
- Downstream specs may reference these sections, but they must flag such references as contingent on validation.
- No working-hypothesis section may be treated as a stable commitment for the purpose of blocking alternative designs that emerge during validation.

## Subsequent validations

After the first validation is met, subsequent validations are chosen for the friction they are expected to produce, not for completeness. Each subsequent validation may revise the working layer of the charter. Each is recorded in `decisions/` with its own entry, referencing this spec.

## References

- CLAUDE.md section 7, first end-to-end validation subsection — the constitutional requirement for this validation.
- CLAUDE.md section 4, Traceability — the traceability standard the validation must prove.
- CLAUDE.md section 4, AI interpretation, deterministic calculation — the boundary the validation must respect.
- CLAUDE.md section 4, Honest comparison or no comparison — the honesty standard the validation must demonstrate.
- CLAUDE.md section 8, rules 1-11 — the binding operating rules the validation must satisfy.
- `decisions/000-template.md` — the template for recording the pair/molecule choice.
