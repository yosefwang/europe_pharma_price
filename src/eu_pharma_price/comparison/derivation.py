"""Derivation rules for per-unit and per-strength-unit price calculations.

Every transformed numeric value must reference a DerivationRule. This
module produces the rules deterministically and applies them as pure
functions of the inputs. No mutation of canonical records.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from ..schemas.comparison import DerivationRule, RuleType
from .parsers import ParsedPackSize, ParsedStrength


@dataclass(frozen=True)
class DerivedPrice:
    price_per_unit: Decimal
    price_per_strength_unit: Decimal
    rule_per_unit: DerivationRule
    rule_per_strength_unit: DerivationRule


def _stable_uuid(seed: str) -> str:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return str(uuid.UUID(h[:32]))


def derive_per_unit_price(
    canonical_id: str,
    price_amount: Decimal,
    pack_size: ParsedPackSize,
    strength: ParsedStrength,
    snapshot_date: date,
    country_code: str,
) -> DerivedPrice:
    if pack_size.units <= 0:
        raise ValueError(f"pack_size_units must be positive, got {pack_size.units}")
    if strength.value <= 0:
        raise ValueError(f"strength value must be positive, got {strength.value}")

    price_per_unit = price_amount / Decimal(pack_size.units)
    price_per_strength_unit = price_per_unit / strength.value
    now = datetime.now(timezone.utc)

    rule_pu = DerivationRule(
        id=_stable_uuid(f"per_unit:{canonical_id}"),
        rule_type=RuleType.per_unit,
        description=(
            "Per-unit price: divide canonical price_amount by parsed "
            "pack_size_units. Pure function of inputs."
        ),
        formula="price_per_unit = price_amount / pack_size_units",
        input_fields=["price_amount", "pack_size_units"],
        output_field="price_per_unit",
        effective_from=snapshot_date,
        source_reference="docs/specs/normalisation-rules.md",
        created_at=now,
        created_by="phase-6-derivation",
        country_code=country_code,
        parameters={
            "pack_size_units": pack_size.units,
            "pack_pattern_id": pack_size.pattern_id,
        },
    )

    rule_psu = DerivationRule(
        id=_stable_uuid(f"per_strength_unit:{canonical_id}"),
        rule_type=RuleType.pack_normalisation,
        description=(
            "Price per strength unit: divide per-unit price by parsed "
            "strength value, in the strength's UCUM unit."
        ),
        formula=(
            "price_per_strength_unit = price_per_unit / strength_value"
        ),
        input_fields=["price_per_unit", "strength_value"],
        output_field="price_per_strength_unit",
        effective_from=snapshot_date,
        source_reference="docs/specs/normalisation-rules.md",
        created_at=now,
        created_by="phase-6-derivation",
        country_code=country_code,
        parameters={
            "strength_value": str(strength.value),
            "strength_unit": strength.unit,
            "strength_pattern_id": strength.pattern_id,
        },
    )

    return DerivedPrice(
        price_per_unit=price_per_unit,
        price_per_strength_unit=price_per_strength_unit,
        rule_per_unit=rule_pu,
        rule_per_strength_unit=rule_psu,
    )
