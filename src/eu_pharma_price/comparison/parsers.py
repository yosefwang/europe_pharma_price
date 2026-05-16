"""Strength and pack-size parser.

The canonical record stores strength and pack_size as published. This
module produces normalised numeric values plus the DerivationRules that
document the parsing. Unparseable inputs return None — never a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ParsedStrength:
    value: Decimal
    unit: str
    pattern_id: str


@dataclass(frozen=True)
class ParsedPackSize:
    units: int
    pattern_id: str


_STRENGTH_PATTERNS = [
    ("mg", re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*mg\s*$", re.IGNORECASE)),
    ("g", re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*g\s*$", re.IGNORECASE)),
    ("ug", re.compile(
        r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mcg|µg|ug)\s*$", re.IGNORECASE,
    )),
    ("mg/ml", re.compile(
        r"^\s*([0-9]+(?:\.[0-9]+)?)\s*mg\s*/\s*ml\s*$", re.IGNORECASE,
    )),
    ("[iU]", re.compile(
        r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(?:IU|iu)\s*$", re.IGNORECASE,
    )),
    ("%", re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*$")),
]


def parse_strength(raw: str) -> ParsedStrength | None:
    if raw is None:
        return None
    for unit, pat in _STRENGTH_PATTERNS:
        m = pat.match(raw)
        if m:
            return ParsedStrength(
                value=Decimal(m.group(1)),
                unit=unit,
                pattern_id=f"strength:{unit}",
            )
    return None


_PACK_PATTERNS = [
    ("integer", re.compile(r"^\s*([0-9]+)\s*$")),
    ("integer_tablets", re.compile(
        r"^\s*([0-9]+)\s*(?:tab|tabs|tablet|tablets|caps|capsules|"
        r"tabletka|tabletki|kapsu[lł]ka|kapsu[lł]ki|comprime|comprimes|"
        r"comprimés|comprimé|gélule|gélules|gelule|gelules)\s*$",
        re.IGNORECASE,
    )),
    ("count_x_volume", re.compile(
        r"^\s*([0-9]+)\s*[xX×]\s*[0-9]+(?:\.[0-9]+)?\s*[a-zA-Z/]*\s*$",
    )),
]


def parse_pack_size(raw: str) -> ParsedPackSize | None:
    if raw is None:
        return None
    for pid, pat in _PACK_PATTERNS:
        m = pat.match(raw)
        if m:
            return ParsedPackSize(
                units=int(m.group(1)),
                pattern_id=f"pack:{pid}",
            )
    return None
