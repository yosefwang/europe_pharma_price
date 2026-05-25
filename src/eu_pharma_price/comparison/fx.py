"""ECB reference rates for currency conversion.

Every currency conversion produces a DerivationRule carrying the FX source,
date, and rate used. Rates are stored in a local append-only JSONL file so
the repository remains self-contained (per charter §8: no runtime internet).

Fetching is a separate, audited step. The fetcher writes to
data/fx/ecb_rates.jsonl; the converter reads from it.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..schemas.comparison import DerivationRule, RuleType


@dataclass(frozen=True)
class FxConversion:
    converted_amount: Decimal
    rate: Decimal
    rule: DerivationRule


def _stable_uuid(seed: str) -> str:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return str(uuid.UUID(h[:32]))


def _load_rates(repo_root: Path) -> dict[tuple[str, str], list[tuple[date, Decimal, str]]]:
    """Return {(from_ccy, to_ccy): [(date, rate, source_url), ...]} sorted by date desc."""
    rates_path = repo_root / "data" / "fx" / "ecb_rates.jsonl"
    if not rates_path.exists():
        return {}
    result: dict[tuple[str, str], list[tuple[date, Decimal, str]]] = {}
    with rates_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            key = (entry["from_ccy"], entry["to_ccy"])
            result.setdefault(key, []).append(
                (date.fromisoformat(entry["rate_date"]),
                 Decimal(str(entry["rate"])),
                 entry["source_url"])
            )
    for key in result:
        result[key].sort(key=lambda x: x[0], reverse=True)
    return result


def _find_rate(
    rates: dict[tuple[str, str], list[tuple[date, Decimal, str]]],
    from_ccy: str, to_ccy: str, rate_date: date,
) -> tuple[Decimal, str] | None:
    """Find the nearest rate on or before rate_date."""
    key = (from_ccy, to_ccy)
    entries = rates.get(key, [])
    for d, rate, source_url in entries:
        if d <= rate_date:
            return rate, source_url
    return None


def convert_currency(
    repo_root: Path,
    amount: Decimal,
    from_ccy: str,
    to_ccy: str,
    rate_date: date,
    canonical_id: str,
) -> FxConversion | None:
    """Convert amount between currencies using the nearest available ECB rate
    on or before rate_date. Returns None when no rate is available.

    The conversion always goes through EUR as the base: non-EUR pairs are
    triangulated (e.g., PLN→GBP = PLN→EUR × EUR→GBP).
    """
    if from_ccy == to_ccy:
        return None

    rates = _load_rates(repo_root)

    source_url = ""

    # EUR is the base currency in ECB rates. Every rate is expressed as
    # 1 EUR = X foreign_ccy.
    if from_ccy == "EUR":
        found = _find_rate(rates, "EUR", to_ccy, rate_date)
        if found is None:
            return None
        rate, source_url = found
    elif to_ccy == "EUR":
        found = _find_rate(rates, "EUR", from_ccy, rate_date)
        if found is None:
            return None
        rate_eur_from, source_url = found
        rate = Decimal("1") / rate_eur_from
    else:
        # Triangulate through EUR: A → EUR → B
        found_a = _find_rate(rates, "EUR", from_ccy, rate_date)
        if found_a is None:
            return None
        rate_eur_a, _ = found_a
        rate_a_eur = Decimal("1") / rate_eur_a

        found_b = _find_rate(rates, "EUR", to_ccy, rate_date)
        if found_b is None:
            return None
        rate_eur_b, source_url = found_b

        rate = rate_a_eur * rate_eur_b

    converted = (amount * rate).quantize(Decimal("0.0000000001"))
    now = datetime.now(timezone.utc)

    rule = DerivationRule(
        id=_stable_uuid(f"fx:{canonical_id}:{from_ccy}:{to_ccy}:{rate_date}"),
        rule_type=RuleType.currency_conversion,
        description=(
            f"Currency conversion: {from_ccy} → {to_ccy} at "
            f"{rate} (ECB reference rate, {rate_date})"
        ),
        formula=(
            f"converted = amount × {rate} "
            f"(1 EUR = {rates.get(('EUR', to_ccy, rate_date), (rate, ''))[0]} "
            f"{to_ccy})"
        ),
        input_fields=["price_per_strength_unit", "price_currency"],
        output_field="price_per_strength_unit_converted",
        effective_from=rate_date,
        source_reference="https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/",
        created_at=now,
        created_by="phase-6-fx",
        parameters={
            "from_ccy": from_ccy,
            "to_ccy": to_ccy,
            "rate": str(rate),
            "rate_date": rate_date.isoformat(),
        },
        fx_source=source_url,
        fx_date=rate_date,
    )
    return FxConversion(converted_amount=converted, rate=rate, rule=rule)


def store_rate(
    repo_root: Path,
    from_ccy: str,
    to_ccy: str,
    rate_date: date,
    rate: Decimal,
    source_url: str,
) -> None:
    """Append a rate to the local store (the fetch side of the boundary)."""
    fx_dir = repo_root / "data" / "fx"
    fx_dir.mkdir(parents=True, exist_ok=True)
    rates_path = fx_dir / "ecb_rates.jsonl"
    entry: dict[str, Any] = {
        "from_ccy": from_ccy,
        "to_ccy": to_ccy,
        "rate_date": rate_date.isoformat(),
        "rate": str(rate),
        "source_url": source_url,
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }
    with rates_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
