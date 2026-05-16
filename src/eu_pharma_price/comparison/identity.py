"""Identity matching for cross-country comparison.

Enforces hard exclusions from the project charter:
- never compare across different molecules (INN must match)
- never compare across different routes of administration
- never compare across different dosage forms
- never compare combination vs. single-ingredient

Soft dimensions (INN, form, route, normalised strength, pack size)
score the match and assign identity_confidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas.comparison import IdentityConfidence
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
    "solution": "parenteral",
    "suppository": "rectal",
    "ointment": "topical",
    "cream": "topical",
}


def _normalise_form(form: str) -> str:
    return form.strip().lower()


def _infer_route(form: str) -> str | None:
    return _FORM_TO_ROUTE.get(_normalise_form(form))


def _normalise_inn(inn: str | None) -> str | None:
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
) -> IdentityMatch:
    if inn_a is None or inn_b is None:
        return IdentityMatch(False, None, "structured",
                             "INN missing on at least one side")
    if _normalise_inn(inn_a) != _normalise_inn(inn_b):
        return IdentityMatch(False, None, "structured", "INN mismatch")

    nf_a = _normalise_form(form_a)
    nf_b = _normalise_form(form_b)
    if nf_a != nf_b:
        # Allow some forms that share a route to potentially match if external
        # policy says so — but for Phase 6, dosage_form mismatch is a hard
        # exclusion as specified in the charter.
        return IdentityMatch(False, None, "structured", "dosage_form mismatch")

    route_a_resolved = route_a or _infer_route(form_a)
    route_b_resolved = route_b or _infer_route(form_b)
    if route_a_resolved is None or route_b_resolved is None:
        return IdentityMatch(False, None, "structured",
                             "route_of_administration could not be inferred")
    if route_a_resolved != route_b_resolved:
        return IdentityMatch(False, None, "structured",
                             "route_of_administration mismatch")

    if strength_a is None or strength_b is None:
        return IdentityMatch(False, None, "structured",
                             "strength could not be parsed")
    if strength_a.unit != strength_b.unit:
        return IdentityMatch(False, None, "structured",
                             "strength units differ — not comparing without explicit conversion")
    if strength_a.value != strength_b.value:
        return IdentityMatch(False, None, "structured", "strength value mismatch")

    if pack_a is None or pack_b is None:
        # Pack size unparseable on at least one side — record as low confidence
        return IdentityMatch(True, IdentityConfidence.low, "structured",
                             "pack size unparseable on one or both sides")

    if pack_a.units == pack_b.units:
        return IdentityMatch(True, IdentityConfidence.exact, "structured", None)

    return IdentityMatch(True, IdentityConfidence.high, "structured",
                         "pack sizes differ — per-unit comparison applies")
