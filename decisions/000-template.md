# Decision Template

> This template defines the mandatory structure for every decision recorded in `decisions/`. A decision not recorded here did not happen (CLAUDE.md section 8, rule 11). Copy this template when creating a new decision; fill every section. Do not leave placeholders.

---

## ID

`NNN-<slug>` — zero-padded three-digit sequence number, hyphen, lowercase slug. Example: `001-initial-scope`.

## Date

ISO 8601 date the decision was first proposed: `YYYY-MM-DD`.

## Status

One of:

- **proposed** — under discussion, not yet binding on downstream work.
- **accepted** — ratified; downstream artifacts must conform. Any future change to an accepted decision is a supersession, recorded as a new decision with `supersedes` in References.
- **superseded** — no longer binding; replaced by the decision named in References.

## Context

What situation or question prompted this decision. State the problem, constraint, or ambiguity as it stood at the time. Reference specific charter sections (CLAUDE.md) or prior decisions where applicable. This section must be sufficient for a future reader to understand *why* the decision was needed without searching elsewhere.

## Decision

What was decided, stated precisely. Use declarative language. Include the concrete commitment or rule, not just the direction. If the decision establishes a boundary, say exactly where it falls. If it names exceptions, list them. If it defers something, say what and to when.

## Consequences

What follows from this decision — both the gains and the costs. Include:

- What becomes easier or possible.
- What becomes harder, excluded, or requires future work.
- Any assumptions the decision rests on that may need revisiting.

Do not omit negative consequences. A decision log that records only benefits is unreliable.

## References

- Charter sections (CLAUDE.md) this decision derives from or interacts with.
- Prior decisions (`NNN-slug`) this decision supersedes, amends, or depends on.
- External sources consulted, if any.
- The person or process that ratified the decision (e.g., "project lead", "post-validation review").
