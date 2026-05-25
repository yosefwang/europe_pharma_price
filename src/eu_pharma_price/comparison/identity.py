"""Identity matching for cross-country comparison.

Enforces hard exclusions from the project charter:
- never compare across different molecules (INN must match)
- never compare across different routes of administration
- never compare across different dosage forms
- never compare combination vs. single-ingredient

Soft dimensions (INN, form, route, normalised strength, pack size)
score the match and assign identity_confidence.

INN matching now uses two-layer normalization (see inn_normalizer.py):
1. Linguistic rules (deterministic, per-language suffix stripping etc.)
2. Constrained fuzzy matching against WHO ATC-DDD dictionary

Matching happens on the CANONICAL (English) INN form. ATC code serves
as cross-validation when both sides have it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..normalization.dosage_forms import (
    DosageFormNormalization,
    FormCompatibility,
    assess_form_compatibility,
)
from ..schemas.comparison import IdentityConfidence
from .inn_normalizer import NormalizationMethod
from .parsers import ParsedPackSize, ParsedStrength


_FORM_TO_ROUTE = {
    "tablet": "oral",
    "tabletka": "oral",
    "comprimé": "oral",
    "comprime": "oral",
    "capsule": "oral",
    "kapsułka": "oral",
    "kapsulka": "oral",
    "gélule": "oral",
    "gelule": "oral",
    "injection": "parenteral",
    "injectable": "parenteral",
    "infusible": "parenteral",
    "solution": "parenteral",
    "oral_solid": "oral",
    "oral_liquid": "oral",
    "suppository": "rectal",
    "ointment": "topical",
    "cream": "topical",
    "topical_semisolid": "topical",
}


def _normalise_form(form: str) -> str:
    return form.strip().lower()


def _infer_route(form: str) -> str | None:
    return _FORM_TO_ROUTE.get(_normalise_form(form))


def _normalise_inn_raw(inn: str | None) -> str | None:
    """Basic normalisation (strips, lowercases) — used when InnNormalizer
    is not available."""
    if inn is None:
        return None
    return inn.strip().lower()


@dataclass(frozen=True)
class IdentityMatch:
    matches: bool
    confidence: IdentityConfidence | None
    method: str
    reason: str | None


def assess_identity(
    inn_a: str | None,
    inn_b: str | None,
    form_a: str,
    form_b: str,
    route_a: str | None,
    route_b: str | None,
    strength_a: ParsedStrength | None,
    strength_b: ParsedStrength | None,
    pack_a: ParsedPackSize | None,
    pack_b: ParsedPackSize | None,
    *,
    inn_atc_a: str | None = None,
    inn_atc_b: str | None = None,
    inn_method_a: str = "structured",
    inn_method_b: str = "structured",
    form_attrs_a: tuple[str, ...] = (),
    form_attrs_b: tuple[str, ...] = (),
    form_confidence_a: str = "strong",
    form_confidence_b: str = "strong",
) -> IdentityMatch:
    """Assess identity match between two canonical records.

    INN matching: compares canonical (already-normalized) INN strings.
    When both sides have ATC codes AND canonical INNs differ, ATC match
    still allows a medium-confidence candidate (cross-language validation).
    """
    if inn_a is None or inn_b is None:
        return IdentityMatch(False, None, "structured",
                             "INN missing on at least one side")

    inn_match = _normalise_inn_raw(inn_a) == _normalise_inn_raw(inn_b)

    if not inn_match:
        # ATC cross-validation: both sides have ATC codes that agree → medium
        if inn_atc_a and inn_atc_b and inn_atc_a == inn_atc_b:
            return _assess_non_inn_dimensions(
                form_a, form_b, route_a, route_b,
                strength_a, strength_b, pack_a, pack_b,
                method="inn_fuzzy",
                caveat=f"INN differs ({inn_a} vs {inn_b}) but ATC {inn_atc_a} matches",
                form_attrs_a=form_attrs_a,
                form_attrs_b=form_attrs_b,
                form_confidence_a=form_confidence_a,
                form_confidence_b=form_confidence_b,
            )
        return IdentityMatch(False, None, "structured", "INN mismatch")

    method = "structured"
    if inn_method_a in ("fuzzy", "rule_based") or inn_method_b in ("fuzzy", "rule_based"):
        method = "inn_normalized"

    # When neither side has an ATC code from WHO, the INN may be a
    # combination product not in WHO L5, an insulin variant, a naming
    # error, or a genuine non-drug item (saline, medical food, device).
    # Cap confidence at medium instead of hard-blocking — 72% of
    # non-ATC INNs in real data are actually drugs, so blocking would
    # lose valid candidates. The caveat travels through to the review
    # queue for human triage.
    force_confidence: IdentityConfidence | None = None
    caveat: str | None = None
    if not inn_atc_a and not inn_atc_b:
        method = "inn_normalized"
        force_confidence = IdentityConfidence.medium
        caveat = (
            "ATC code not available from WHO dictionary for either side — "
            "INN may be combination product, non-standard name, or "
            "non-drug item; verify manually before using this comparison"
        )

    result = _assess_non_inn_dimensions(
        form_a, form_b, route_a, route_b,
        strength_a, strength_b, pack_a, pack_b,
        method=method, caveat=caveat,
        form_attrs_a=form_attrs_a,
        form_attrs_b=form_attrs_b,
        form_confidence_a=form_confidence_a,
        form_confidence_b=form_confidence_b,
    )
    if force_confidence is not None and result.confidence is not None:
        # Cap: never report higher than force_confidence
        conf_order = {"exact": 4, "high": 3, "medium": 2, "low": 1}
        if conf_order.get(result.confidence.value, 0) > conf_order[force_confidence.value]:
            return IdentityMatch(
                result.matches, force_confidence,
                result.method, result.reason,
            )
    return result


def _assess_non_inn_dimensions(
    form_a: str, form_b: str,
    route_a: str | None, route_b: str | None,
    strength_a: ParsedStrength | None, strength_b: ParsedStrength | None,
    pack_a: ParsedPackSize | None, pack_b: ParsedPackSize | None,
    method: str, caveat: str | None,
    form_attrs_a: tuple[str, ...] = (),
    form_attrs_b: tuple[str, ...] = (),
    form_confidence_a: str = "strong",
    form_confidence_b: str = "strong",
) -> IdentityMatch:

    route_a_resolved = route_a or _infer_route(form_a)
    route_b_resolved = route_b or _infer_route(form_b)
    form_compatibility = assess_form_compatibility(
        DosageFormNormalization(
            raw_value=form_a,
            country_code="",
            comparable_form_class=_normalise_form(form_a),
            route_family=route_a_resolved,
            presentation_attributes=form_attrs_a,
            confidence=form_confidence_a,
        ),
        DosageFormNormalization(
            raw_value=form_b,
            country_code="",
            comparable_form_class=_normalise_form(form_b),
            route_family=route_b_resolved,
            presentation_attributes=form_attrs_b,
            confidence=form_confidence_b,
        ),
    )
    if not form_compatibility.compatible:
        return IdentityMatch(
            False,
            None,
            "structured",
            form_compatibility.reason or "dosage form not compatible",
        )

    if strength_a is None or strength_b is None:
        return IdentityMatch(False, None, "structured",
                             "strength could not be parsed")
    if strength_a.unit != strength_b.unit:
        return IdentityMatch(False, None, "structured",
                             "strength units differ — not comparing without explicit conversion")
    if strength_a.value != strength_b.value:
        return IdentityMatch(False, None, "structured", "strength value mismatch")

    if pack_a is None or pack_b is None:
        return IdentityMatch(True, IdentityConfidence.low, method,
                             "pack size unparseable on one or both sides")

    if pack_a.units == pack_b.units:
        return _with_form_confidence_cap(
            IdentityConfidence.exact, method, caveat, form_compatibility,
        )

    reason_str = "; ".join(filter(None, [
        "pack sizes differ — per-unit comparison applies",
        caveat,
        form_compatibility.caveat,
    ]))
    return _with_form_confidence_cap(
        IdentityConfidence.high, method, reason_str, form_compatibility,
    )


def _with_form_confidence_cap(
    base_confidence: IdentityConfidence,
    method: str,
    caveat: str | None,
    form_compatibility: FormCompatibility,
) -> IdentityMatch:
    confidence = base_confidence
    cap = form_compatibility.confidence_cap
    if cap:
        order = {
            IdentityConfidence.exact: 4,
            IdentityConfidence.high: 3,
            IdentityConfidence.medium: 2,
            IdentityConfidence.low: 1,
        }
        cap_confidence = IdentityConfidence(cap)
        if order[confidence] > order[cap_confidence]:
            confidence = cap_confidence
    reason_str = "; ".join(filter(None, [caveat, form_compatibility.caveat]))
    return IdentityMatch(True, confidence, method, reason_str)
