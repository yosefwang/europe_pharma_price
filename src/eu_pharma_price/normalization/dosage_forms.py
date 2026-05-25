"""Dosage-form and route comparability normalisation.

This module maps local form codes/text into comparison-oriented form classes.
It is intentionally not a full pharmaceutical ontology: it keeps route/form
compatibility broad enough to avoid losing legitimate candidates while carrying
presentation differences as confidence caps and caveats.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DosageFormNormalization:
    raw_value: str | None
    country_code: str
    source_field: str | None = None
    comparable_form_class: str | None = None
    route_family: str | None = None
    presentation_attributes: tuple[str, ...] = ()
    method: str = "unknown"
    confidence: str = "weak"
    rule_id: str | None = None
    caveat: str | None = None


@dataclass(frozen=True)
class FormCompatibility:
    compatible: bool
    confidence_cap: str | None = None
    caveat: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class _AliasRule:
    comparable_form_class: str
    route_family: str
    presentation_attributes: tuple[str, ...]
    rule_id: str
    confidence: str = "strong"


_GLOBAL_ALIASES: dict[str, _AliasRule] = {
    "tablet": _AliasRule("oral_solid", "oral", (), "global.tablet"),
    "capsule": _AliasRule("oral_solid", "oral", (), "global.capsule"),
    "injection": _AliasRule("injectable", "parenteral", (), "global.injection"),
    "infusion": _AliasRule("infusible", "parenteral", (), "global.infusion"),
    "solution": _AliasRule("solution", "unknown", (), "global.solution", "weak"),
    "oral_solution": _AliasRule("oral_liquid", "oral", (), "global.oral_solution"),
    "oral_suspension": _AliasRule("oral_liquid", "oral", (), "global.oral_suspension"),
    "suspension": _AliasRule("suspension", "unknown", (), "global.suspension", "weak"),
    "syrup": _AliasRule("oral_liquid", "oral", (), "global.syrup"),
    "gel": _AliasRule("topical_semisolid", "topical", (), "global.gel"),
    "cream": _AliasRule("topical_semisolid", "topical", (), "global.cream"),
    "ointment": _AliasRule("topical_semisolid", "topical", (), "global.ointment"),
    "transdermal_patch": _AliasRule("transdermal", "transdermal", (), "global.transdermal_patch"),
    "patch": _AliasRule("transdermal", "transdermal", (), "global.patch"),
    "drops": _AliasRule("drops", "local_or_topical", (), "global.drops", "adequate"),
    "spray": _AliasRule("spray", "local_or_topical", (), "global.spray", "adequate"),
    "powder_and_solvent_for_injection": _AliasRule(
        "injectable", "parenteral", ("powder_and_solvent",),
        "global.powder_and_solvent_for_injection",
    ),
    "powder_for_solution_for_injection": _AliasRule(
        "injectable", "parenteral", ("powder_for_solution",),
        "global.powder_for_solution_for_injection",
    ),
}


_CZ_ALIASES: dict[str, _AliasRule] = {
    "TBL NOB": _AliasRule("oral_solid", "oral", (), "cz.sukl.tbl_nob"),
    "TBL FLM": _AliasRule("oral_solid", "oral", ("film_coated",), "cz.sukl.tbl_flm"),
    "TBL ENT": _AliasRule("oral_solid", "oral", ("gastro_resistant",), "cz.sukl.tbl_ent"),
    "TBL PRO": _AliasRule("oral_solid", "oral", ("prolonged_release",), "cz.sukl.tbl_pro"),
    "TBL EFF": _AliasRule("oral_solid", "oral", ("effervescent",), "cz.sukl.tbl_eff"),
    "TBL ORD": _AliasRule("oral_solid", "oral", ("orodispersible",), "cz.sukl.tbl_ord"),
    "TBL MND": _AliasRule("oral_solid", "oral", (), "cz.sukl.tbl_mnd"),
    "TBL SLG": _AliasRule("oral_solid", "oral", ("sublingual",), "cz.sukl.tbl_slg"),
    "TBL DIS": _AliasRule("oral_solid", "oral", ("dispersible",), "cz.sukl.tbl_dis"),
    "CPS DUR": _AliasRule("oral_solid", "oral", (), "cz.sukl.cps_dur"),
    "CPS MOL": _AliasRule("oral_solid", "oral", (), "cz.sukl.cps_mol"),
    "CPS END": _AliasRule("oral_solid", "oral", ("gastro_resistant",), "cz.sukl.cps_end"),
    "INJ SOL": _AliasRule("injectable", "parenteral", ("ready_to_use",), "cz.sukl.inj_sol"),
    "INJ SOL ISP": _AliasRule(
        "injectable", "parenteral", ("prefilled_syringe",), "cz.sukl.inj_sol_isp",
    ),
    "INJ SOL PEP": _AliasRule(
        "injectable", "parenteral", ("prefilled_pen",), "cz.sukl.inj_sol_pep",
    ),
    "INJ PSO LQF": _AliasRule(
        "injectable", "parenteral", ("powder_and_solvent",), "cz.sukl.inj_pso_lqf",
    ),
    "INJ PLV SOL": _AliasRule(
        "injectable", "parenteral", ("powder_for_solution",), "cz.sukl.inj_plv_sol",
    ),
    "INJ/INF SOL": _AliasRule("injectable", "parenteral", ("ready_to_use",), "cz.sukl.inj_inf_sol"),
    "INF SOL": _AliasRule("infusible", "parenteral", ("ready_to_use",), "cz.sukl.inf_sol"),
    "INF CNC": _AliasRule("infusible", "parenteral", ("concentrate",), "cz.sukl.inf_cnc"),
    "DRM GEL": _AliasRule("topical_semisolid", "topical", (), "cz.sukl.drm_gel"),
    "OPH GTT": _AliasRule("eye_drops", "ocular", (), "cz.sukl.oph_gtt"),
    "NAS SPR": _AliasRule("nasal_spray", "nasal", (), "cz.sukl.nas_spr"),
}


_IE_PATTERNS: list[tuple[re.Pattern[str], _AliasRule]] = [
    (re.compile(r"\bpowder and solvent\b|\bpdr\.\s*&\s*solv", re.IGNORECASE),
     _AliasRule("injectable", "parenteral", ("powder_and_solvent",), "ie.pcrs.powder_and_solvent", "adequate")),
    (re.compile(r"\bpre[- ]?filled\s+pen\b|\bpen\b", re.IGNORECASE),
     _AliasRule("injectable", "parenteral", ("prefilled_pen",), "ie.pcrs.prefilled_pen", "adequate")),
    (re.compile(r"\bpre[- ]?filled\s+syr(?:inge|\.)\b|\bsyringe\b|\bsyr\.\b", re.IGNORECASE),
     _AliasRule("injectable", "parenteral", ("prefilled_syringe",), "ie.pcrs.prefilled_syringe", "adequate")),
    (re.compile(r"\bsoln\.?\s+for\s+inj\b|\binj\.?\b", re.IGNORECASE),
     _AliasRule("injectable", "parenteral", ("ready_to_use",), "ie.pcrs.injection", "adequate")),
    (re.compile(r"\bfilm coated tabs?\b|\btabs?\b", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "ie.pcrs.tablet", "adequate")),
    (re.compile(r"\bcaps?\b", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "ie.pcrs.capsule", "adequate")),
    (re.compile(r"\boral soln\b", re.IGNORECASE),
     _AliasRule("oral_liquid", "oral", (), "ie.pcrs.oral_solution", "adequate")),
    (re.compile(r"\boral susp\b", re.IGNORECASE),
     _AliasRule("oral_liquid", "oral", (), "ie.pcrs.oral_suspension", "adequate")),
    (re.compile(r"\bpatch\b", re.IGNORECASE),
     _AliasRule("transdermal", "transdermal", (), "ie.pcrs.patch", "adequate")),
    (re.compile(r"\bgel\b", re.IGNORECASE),
     _AliasRule("topical_semisolid", "topical", (), "ie.pcrs.gel", "adequate")),
    (re.compile(r"\bcream\b", re.IGNORECASE),
     _AliasRule("topical_semisolid", "topical", (), "ie.pcrs.cream", "adequate")),
    (re.compile(r"\boint\b", re.IGNORECASE),
     _AliasRule("topical_semisolid", "topical", (), "ie.pcrs.ointment", "adequate")),
]


_PL_PATTERNS: list[tuple[re.Pattern[str], _AliasRule]] = [
    (re.compile(r"\bproszek\b.*\bi\s+rozpuszczalnik\b", re.IGNORECASE),
     _AliasRule("injectable", "parenteral", ("powder_and_solvent",), "pl.mz.powder_and_solvent", "adequate")),
    (re.compile(r"\broztw[oó]r do wstrzykiwa[nń]\b|\binj\b|\bzaw\.\s*do\s*wstrz", re.IGNORECASE),
     _AliasRule("injectable", "parenteral", (), "pl.mz.injection", "adequate")),
    (re.compile(r"\btabl\b|tabletk", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "pl.mz.tablet", "adequate")),
    (re.compile(r"\bkaps\b|kapsu[lł]k", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "pl.mz.capsule", "adequate")),
    (re.compile(r"\bzawiesin|syrop|doustn", re.IGNORECASE),
     _AliasRule("oral_liquid", "oral", (), "pl.mz.oral_liquid", "adequate")),
    (re.compile(r"\bplastry?\b", re.IGNORECASE),
     _AliasRule("transdermal", "transdermal", (), "pl.mz.patch", "adequate")),
    (re.compile(r"\bkrem\b|ma[śs][ćc]|[żz]el\b", re.IGNORECASE),
     _AliasRule("topical_semisolid", "topical", (), "pl.mz.topical_semisolid", "adequate")),
]


_ES_PATTERNS: list[tuple[re.Pattern[str], _AliasRule]] = [
    (re.compile(r"\bcomprimid", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "es.nomenclator.tablet", "adequate")),
    (re.compile(r"\bc[aá]psul", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "es.nomenclator.capsule", "adequate")),
    (re.compile(r"\bsoluci[oó]n\b.*\binye", re.IGNORECASE),
     _AliasRule("injectable", "parenteral", ("ready_to_use",), "es.nomenclator.injection", "adequate")),
    (re.compile(r"\bjarabe\b|\bsuspensi[oó]n oral\b|\bsoluci[oó]n oral\b", re.IGNORECASE),
     _AliasRule("oral_liquid", "oral", (), "es.nomenclator.oral_liquid", "adequate")),
]


_IT_PATTERNS: list[tuple[re.Pattern[str], _AliasRule]] = [
    (re.compile(r"\bcpr\b|compress", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "it.aifa.tablet", "adequate")),
    (re.compile(r"\bcps\b|capsul", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "it.aifa.capsule", "adequate")),
    (re.compile(r"\buso parenterale\b|\biniett", re.IGNORECASE),
     _AliasRule("injectable", "parenteral", (), "it.aifa.injectable", "adequate")),
    (re.compile(r"\borale sosp\b|\borale soluz\b|sciroppo", re.IGNORECASE),
     _AliasRule("oral_liquid", "oral", (), "it.aifa.oral_liquid", "adequate")),
]


_PT_PATTERNS: list[tuple[re.Pattern[str], _AliasRule]] = [
    (re.compile(r"\bcomprimido", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "pt.infomed.tablet", "adequate")),
    (re.compile(r"\bc[aá]psula", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "pt.infomed.capsule", "adequate")),
    (re.compile(r"\binjet[aá]vel|perfus[aã]o", re.IGNORECASE),
     _AliasRule("injectable", "parenteral", (), "pt.infomed.injectable", "adequate")),
    (re.compile(r"\bsolu[cç][aã]o oral\b|\bsuspens[aã]o oral\b|xarope", re.IGNORECASE),
     _AliasRule("oral_liquid", "oral", (), "pt.infomed.oral_liquid", "adequate")),
]


_BE_PATTERNS: list[tuple[re.Pattern[str], _AliasRule]] = [
    (re.compile(r"\b(comprim[ée]s?|filmomhulde tabletten|tabletten)\b", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "be.inami.tablet", "adequate")),
    (re.compile(r"\b(capsules?|g[eé]lules?|gelule(?:s)?)\b", re.IGNORECASE),
     _AliasRule("oral_solid", "oral", (), "be.inami.capsule", "adequate")),
    (re.compile(r"\b(solution|suspension|po(e|è)dre)\s+(?:pour|voor)\s+(?:injection|injectie|perfusion|infusie)\b|\b(injectieflacon|ampoules?|injectable)\b", re.IGNORECASE),
     _AliasRule("injectable", "parenteral", ("ready_to_use",), "be.inami.injectable", "adequate")),
    (re.compile(r"\b(perfusion|infusie)\b", re.IGNORECASE),
     _AliasRule("infusible", "parenteral", ("ready_to_use",), "be.inami.infusion", "adequate")),
    (re.compile(r"\b(siroop|sirop|orale?\s+solution|solution\s+buvable|oral(?:e)?\s+suspension)\b", re.IGNORECASE),
     _AliasRule("oral_liquid", "oral", (), "be.inami.oral_liquid", "adequate")),
]


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value.strip()) if value else ""


def _result(
    raw_value: str | None,
    country_code: str,
    source_field: str | None,
    rule: _AliasRule,
    method: str,
) -> DosageFormNormalization:
    return DosageFormNormalization(
        raw_value=raw_value,
        country_code=country_code.upper(),
        source_field=source_field,
        comparable_form_class=rule.comparable_form_class,
        route_family=rule.route_family,
        presentation_attributes=rule.presentation_attributes,
        method=method,
        confidence=rule.confidence,
        rule_id=rule.rule_id,
        caveat=None,
    )


def normalize_dosage_form(
    raw_value: str | None,
    *,
    country_code: str,
    source_field: str | None = None,
    product_name: str | None = None,
) -> DosageFormNormalization:
    """Normalise local dosage-form hints into comparison-oriented metadata."""
    cc = country_code.upper()
    raw = _clean(raw_value)
    raw_upper = raw.upper()
    raw_lower = raw.lower()

    haystack = " ".join(part for part in [raw, product_name or ""] if part)
    if cc == "CZ" and raw_upper in _CZ_ALIASES:
        return _result(raw, cc, source_field, _CZ_ALIASES[raw_upper], "exact_alias")

    patterns = (
        _IE_PATTERNS if cc == "IE"
        else _PL_PATTERNS if cc == "PL"
        else _ES_PATTERNS if cc == "ES"
        else _IT_PATTERNS if cc == "IT"
        else _PT_PATTERNS if cc == "PT"
        else _BE_PATTERNS if cc == "BE"
        else []
    )
    for pattern, rule in patterns:
        if pattern.search(haystack):
            return _result(raw or product_name, cc, source_field, rule, "regex")

    if raw_lower in _GLOBAL_ALIASES:
        return _result(raw, cc, source_field, _GLOBAL_ALIASES[raw_lower], "exact_alias")

    return DosageFormNormalization(
        raw_value=raw or product_name,
        country_code=cc,
        source_field=source_field,
        comparable_form_class=None,
        route_family=None,
        presentation_attributes=(),
        method="unknown",
        confidence="weak",
        rule_id=None,
        caveat="dosage form could not be normalised to a comparable form class",
    )


def assess_form_compatibility(
    a: DosageFormNormalization,
    b: DosageFormNormalization,
) -> FormCompatibility:
    """Assess whether two normalised forms can enter candidate comparison."""
    if not a.comparable_form_class or not b.comparable_form_class:
        return FormCompatibility(False, reason="form_class missing on at least one side")
    if not a.route_family or not b.route_family:
        return FormCompatibility(False, reason="route_family missing on at least one side")
    if a.route_family != b.route_family:
        return FormCompatibility(
            False,
            reason=f"route_family mismatch: {a.route_family} vs {b.route_family}",
        )
    if a.comparable_form_class != b.comparable_form_class:
        return FormCompatibility(
            False,
            reason=(
                "comparable_form_class mismatch: "
                f"{a.comparable_form_class} vs {b.comparable_form_class}"
            ),
        )

    attrs_a = set(a.presentation_attributes)
    attrs_b = set(b.presentation_attributes)
    caveats: list[str] = []
    confidence_cap = "exact"
    if attrs_a != attrs_b:
        confidence_cap = "high"
        caveats.append(
            "presentation differs: "
            f"{sorted(attrs_a) or ['unspecified']} vs {sorted(attrs_b) or ['unspecified']}"
        )
    if a.confidence != "strong" or b.confidence != "strong":
        if confidence_cap == "exact":
            confidence_cap = "high"
        caveats.append(
            "dosage-form mapping confidence below strong on at least one side"
        )
    return FormCompatibility(
        True,
        confidence_cap=confidence_cap,
        caveat="; ".join(caveats) if caveats else None,
    )
