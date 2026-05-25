# Dosage Form And Route Comparability Design

## Purpose

Dosage-form normalisation is part of the comparability substrate, not a
country-delegate cleanup detail. Its job is to improve legitimate comparison
candidate recall while preserving auditability and caveats. It must prevent
two failure modes:

- false negatives: products that are comparable disappear because local form
  strings differ across countries, languages, or source protocols;
- false certainty: products enter headline comparison without recording
  route, presentation, mapping confidence, and caveats.

This layer should be conservative about final interpretation, but not overly
strict at candidate generation time. Uncertainty should usually lower identity
confidence and add caveats, not silently block a candidate, unless the route or
exposure path is clearly incompatible.

## Current Problem

Today form logic is scattered:

- CZ maps SÚKL form codes in `delegates/czechia.py`.
- IE extracts forms from PCRS product names in `delegates/ireland.py`.
- PL extracts forms from Ministry product names in `delegates/poland.py`.
- `comparison/identity.py` hard-matches final `dosage_form` strings and has
  its own small route map.

This creates brittle behaviour. For example, CZ `INJ PSO LQF` remains a raw
form string, so Enbrel presentations that should be injectable candidates do
not enter comparison. The system should instead recognise the comparable route
family and carry presentation differences as identity caveats.

## Design Principles

1. Optimise for comparability, not taxonomy purity.
   The normaliser is not a drug-dictionary classifier. It exists to decide
   whether products can fairly enter the same comparison candidate pool.

2. Split comparison-critical dimensions from presentation detail.
   A route/form family can be compatible even when device or presentation
   details differ.

3. Prefer candidate inclusion with downgraded confidence when uncertainty is
   localised to presentation.
   Do not drop products merely because one country says "solution for
   injection" and another says "pre-filled pen".

4. Keep hard exclusions simple and explicit.
   Clearly different route families or exposure paths remain blockers.

5. Make every mapping auditable.
   Each normalisation should expose the raw value, rule id, method, confidence,
   and caveat.

6. Make country expansion update this layer during ingest.
   Adding a country requires adding or validating its dosage-form and route
   alias pack as part of the ingest contract. New source languages and protocol
   abbreviations are expected data, not one-off exceptions.

## Model

Normalisation returns a structured result:

```python
class DosageFormNormalization:
    raw_value: str | None
    country_code: str
    source_field: str | None
    comparable_form_class: str | None
    route_family: str | None
    presentation_attributes: list[str]
    method: str
    confidence: str
    rule_id: str | None
    caveat: str | None
```

Examples:

```text
CZ / lekovaFormaKod = INJ PSO LQF
→ comparable_form_class = injectable
→ route_family = parenteral
→ presentation_attributes = [powder_and_solvent]
→ confidence = strong
→ rule_id = cz.sukl.inj_pso_lqf
```

```text
IE / product_name contains "Pre-filled Pen"
→ comparable_form_class = injectable
→ route_family = parenteral
→ presentation_attributes = [prefilled_pen]
→ confidence = adequate
→ rule_id = ie.pcrs.prefilled_pen
```

## Compatibility Rules

Candidate generation should use compatibility, not exact form-string equality.

Hard blockers:

- route family differs in a clinically meaningful way, such as oral vs
  parenteral, topical vs systemic, inhaled vs injectable;
- form or route cannot be inferred at all on either side;
- strength cannot be parsed or units cannot be converted under an explicit
  derivation rule.

Soft caveats:

- both sides are injectable but presentation differs, such as vial vs
  prefilled pen, syringe vs pen, powder-and-solvent vs ready-to-use solution;
- mapping confidence is adequate rather than strong;
- one side relies on product-name regex while another uses a structured source
  code;
- source language or protocol abbreviation is newly introduced but covered by
  a reviewed alias rule.

Identity confidence should be adjusted as follows:

- exact: same molecule, route family, comparable form class, strength, pack
  size, and compatible presentation attributes;
- high: same molecule, route family, comparable form class, and strength, with
  pack-size differences or minor presentation differences;
- medium: same molecule, route family, comparable form class, and strength,
  but mapping confidence or presentation alignment needs manual review;
- no candidate: hard blocker applies.

## Country Expansion Contract

Every new country delegate must pass through the dosage-form normalisation
contract during ingest:

1. Identify source fields that express form, route, device, or presentation.
2. Add country/source alias rules for structured codes and common local-language
   text patterns.
3. Map aliases only to global comparable form classes, route families, and
   presentation attributes.
4. Generate an unmapped-form distribution in the profile report.
5. Treat high-volume unmapped forms as ingest gaps before comparison artifacts
   are considered stable.
6. Add tests for representative local-language forms, abbreviations, and
   protocol-specific codes.

This keeps future countries from bypassing the shared comparison logic. Country
delegates should extract raw values; the shared normaliser should decide how
those values participate in comparison.

## Architecture

Create a shared module:

```text
src/eu_pharma_price/normalization/dosage_forms.py
```

Responsibilities:

- define global comparable form classes;
- define route families;
- define presentation attributes;
- hold global compatibility rules;
- load or define country/source alias packs;
- return `DosageFormNormalization`;
- expose route inference to `comparison/identity.py`.

Delegates should call this module when producing canonical records. The
comparison layer should consume normalised form class, route family, and
presentation attributes. The profile layer should report unmapped raw forms and
mapping confidence distribution.

## Data Flow

```text
raw source row
→ country delegate extracts raw form/route/presentation hints
→ shared dosage-form normaliser
→ canonical record + normalisation metadata
→ profile unmapped/mapping-confidence distribution
→ comparison identity compatibility matrix
→ review caveats and identity confidence
```

The canonical `dosage_form` field can continue to hold the comparable form
class for compatibility with existing artifacts. Additional metadata should be
stored either as schema fields or a sidecar artifact:

- raw dosage form;
- route family;
- presentation attributes;
- normalisation method;
- normalisation confidence;
- rule id;
- caveat.

## Enbrel Expected Behaviour

CZ `INJ PSO LQF` and IE `Powder and Solvent for Soln. for Inj.` should both
normalise to injectable/parenteral with `powder_and_solvent`. They should enter
candidate generation when molecule, strength, and price lane are compatible.

CZ injectable Enbrel and IE pre-filled pen Enbrel should also enter candidate
generation when molecule and strength match, but identity confidence should be
lower than exact if presentation attributes differ. The review caveat should
state that presentation differs.

## Non-Goals

- Do not implement a complete EDQM or SNOMED dosage-form ontology.
- Do not make every device or presentation its own primary comparison form.
- Do not create country-specific comparison categories for one drug or one
  source quirk.
- Do not ingest or stabilise France as part of this design; France remains
  deferred.

## Testing

Tests should cover:

- CZ SÚKL code aliases including `INJ SOL`, `INJ SOL ISP`, `INJ SOL PEP`,
  `INJ PSO LQF`, and representative infusion/oral/topical codes;
- IE PCRS product-name patterns for injection, pre-filled pen, syringe,
  powder-and-solvent, tablets, capsules, liquids, and patches;
- PL local-language product-name patterns for injection, tablets, capsules,
  oral liquids, and powder-and-solvent presentations;
- compatibility matrix behaviour for route-compatible presentation differences;
- hard blockers for oral vs parenteral and topical vs systemic differences;
- profile reporting of unmapped raw forms.
