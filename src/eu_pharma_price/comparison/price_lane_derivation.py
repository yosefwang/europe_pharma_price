"""Policy-driven price lane derivations.

Observed country delegates publish the price lanes present in source data.
This module adds virtual, auditable lanes when policy research gives a stable
formula for deriving a global comparison category, e.g. ex-factory price from a
published public retail price. It does not mutate canonical parquet files.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Callable

import pandas as pd

from ..policy.gating import load_interpretations
from ..schemas.comparison import DerivationRule, RuleType
from ..schemas.policy import (
    PolicyDerivationCondition,
    PolicyDerivationRule,
    PolicyInterpretation,
)

DERIVED_EX_FACTORY_PRICE_TYPE = "ex-factory (derived)"


@dataclass(frozen=True)
class PolicyDerivationEdge:
    country_code: str
    policy_interpretation_id: str
    source_price_type: str
    target_price_type: str
    source_category: str | None
    target_category: str
    formula_id: str
    formula: str
    legal_basis: tuple[str, ...]
    confidence: str
    caveats: tuple[str, ...]


@dataclass(frozen=True)
class PolicyDerivationGraph:
    edges: list[PolicyDerivationEdge] = field(default_factory=list)

    def by_country(self) -> dict[str, list[PolicyDerivationEdge]]:
        out: dict[str, list[PolicyDerivationEdge]] = {}
        for edge in self.edges:
            out.setdefault(edge.country_code, []).append(edge)
        return out


def _stable_uuid(seed: str) -> str:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return str(uuid.UUID(h[:32]))


def build_policy_derivation_graph(
    repo_root: Path,
    countries: list[str] | tuple[str, ...] | None = None,
) -> PolicyDerivationGraph:
    """Return a policy-derived lane graph for audit/reporting.

    The graph is intentionally policy-only: it does not inspect canonical
    records or calculate prices. It answers which derived lanes policy
    intelligence authorises, with formula and legal-basis provenance.
    """
    if countries is None:
        policy_root = repo_root / "data" / "policy"
        countries = sorted(
            path.name.upper()
            for path in policy_root.iterdir()
            if path.is_dir()
        ) if policy_root.exists() else []

    edges: list[PolicyDerivationEdge] = []
    for country in countries:
        for policy in load_interpretations(repo_root, country):
            for rule in policy.derivation_rules:
                edges.append(PolicyDerivationEdge(
                    country_code=policy.country_code.upper(),
                    policy_interpretation_id=policy.id,
                    source_price_type=rule.source_price_type,
                    target_price_type=rule.target_price_type,
                    source_category=(
                        rule.source_category.value
                        if rule.source_category is not None
                        else None
                    ),
                    target_category=rule.target_category.value,
                    formula_id=rule.formula_id,
                    formula=rule.formula,
                    legal_basis=tuple(rule.legal_basis),
                    confidence=rule.confidence.value,
                    caveats=tuple(rule.caveats),
                ))
    return PolicyDerivationGraph(edges=edges)


def _as_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).replace(",", ".").strip()
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP).normalize()


def _matches_condition(row: pd.Series, condition: PolicyDerivationCondition) -> bool:
    if condition.any:
        return any(_matches_condition(row, child) for child in condition.any)
    if condition.all:
        return all(_matches_condition(row, child) for child in condition.all)
    if condition.field is None:
        return False
    value = row.get(condition.field)
    if value is None:
        return False
    text = str(value).strip().lower()
    if condition.equals is not None:
        return text == str(condition.equals).strip().lower()
    if condition.contains is not None:
        return str(condition.contains).strip().lower() in text
    return False


def _parameters_for_row(
    row: pd.Series,
    rule: PolicyDerivationRule,
) -> tuple[dict, list[str]]:
    parameters = dict(rule.parameters)
    notes: list[str] = []
    for branch in rule.conditional_parameters:
        if _matches_condition(row, branch.when):
            parameters.update(branch.parameters)
            notes.extend(branch.notes)
            break
    return parameters, notes


def _decimal_parameter(parameters: dict, *names: str) -> Decimal | None:
    for name in names:
        if name in parameters:
            return _as_decimal(parameters[name])
    return None


def _derive_from_policy_rule(
    row: pd.Series,
    rule: PolicyDerivationRule,
) -> tuple[Decimal | None, dict, list[str]]:
    amount = _as_decimal(row.get("price_amount"))
    if amount is None or amount <= 0:
        return None, {}, []
    parameters, notes = _parameters_for_row(row, rule)
    formula_id = rule.formula_id

    if formula_id == "multiply_by_factor":
        factor = _decimal_parameter(parameters, "factor")
        if factor is None:
            return None, {}, []
        return amount * factor, {"factor": str(factor)}, notes

    if formula_id == "divide_by_divisor":
        divisor = _decimal_parameter(parameters, "divisor")
        if divisor is None or divisor == 0:
            return None, {}, []
        return amount / divisor, {"divisor": str(divisor)}, notes

    if formula_id == "divide_by_one_plus_markup":
        markup = _decimal_parameter(parameters, "markup", "default_markup")
        if markup is None:
            return None, {}, []
        return (
            amount / (Decimal("1") + markup),
            {"markup": str(markup)},
            notes,
        )

    if formula_id == "subtract_fixed_fee_then_divide":
        fixed_fee = _decimal_parameter(parameters, "fixed_fee")
        coefficient = _decimal_parameter(parameters, "coefficient")
        if fixed_fee is None or coefficient is None or coefficient == 0:
            return None, {}, []
        derived = (amount - fixed_fee) / coefficient
        if derived <= 0:
            return None, {}, []
        return (
            derived,
            {"fixed_fee": str(fixed_fee), "coefficient": str(coefficient)},
            notes,
        )

    if formula_id == "tiered_pt_pvp_to_pva":
        for tier in parameters.get("tiers", []):
            lower = _as_decimal(tier.get("lower"))
            upper = _as_decimal(tier.get("upper"))
            coefficient = _as_decimal(tier.get("coefficient"))
            fixed_fee = _as_decimal(tier.get("fixed_fee"))
            if lower is None or coefficient is None or fixed_fee is None:
                continue
            if coefficient == 0:
                continue
            derived = (amount - fixed_fee) / coefficient
            if derived < lower:
                continue
            if upper is not None and derived > upper:
                continue
            return (
                derived,
                {
                    "tier": str(tier.get("id")),
                    "tier_lower": str(lower),
                    "tier_upper": str(upper) if upper is not None else None,
                    "coefficient": str(coefficient),
                    "fixed_fee": str(fixed_fee),
                    "vat_rate": str(tier.get("vat_rate", "")),
                },
                notes,
            )
        return None, {}, []

    if formula_id == "tiered_es_pvp_to_pva":
        for tier in parameters.get("tiers", []):
            max_pvp = _as_decimal(tier.get("max_pvp"))
            divisor = _as_decimal(tier.get("divisor"))
            vat_rate = _as_decimal(tier.get("vat_rate"))
            fixed_margin = _as_decimal(tier.get("fixed_margin"))
            if max_pvp is not None and amount > max_pvp:
                continue
            if divisor is not None:
                derived = amount / divisor
                params = {"tier": str(tier.get("id")), "divisor": str(divisor)}
            elif vat_rate is not None and fixed_margin is not None:
                derived = (amount / (Decimal("1") + vat_rate)) - fixed_margin
                params = {
                    "tier": str(tier.get("id")),
                    "vat_rate": str(vat_rate),
                    "fixed_margin": str(fixed_margin),
                }
            else:
                continue
            if derived <= 0:
                return None, {}, []
            return derived, params, notes
        return None, {}, []

    return None, {}, []


def _derive_price_lanes_from_policies(
    df: pd.DataFrame,
    country_code: str,
    snapshot_date: date,
    policies: list[PolicyInterpretation],
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=list(df.columns))
    rows: list[pd.Series] = []
    cc = country_code.upper()
    existing_price_types = set(df["price_type"].astype(str))
    for policy in policies:
        if policy.country_code.upper() != cc:
            continue
        for policy_rule in policy.derivation_rules:
            if policy_rule.target_price_type in existing_price_types:
                continue
            source = df[df["price_type"] == policy_rule.source_price_type]
            for _, row in source.iterrows():
                amount, rule_params, notes = _derive_from_policy_rule(row, policy_rule)
                if amount is None:
                    continue
                source_id = str(row["id"])
                rule_id = _stable_uuid(
                    f"price_lane:{cc}:{source_id}:{policy_rule.target_price_type}:"
                    f"{policy.id}"
                )
                params = {
                    **rule_params,
                    "source_record_id": source_id,
                    "source_price_type": policy_rule.source_price_type,
                    "source_price_amount": str(row.get("price_amount")),
                    "derived_price_type": policy_rule.target_price_type,
                    "source_policy_interpretation_id": policy.id,
                    "formula_id": policy_rule.formula_id,
                }
                rule = DerivationRule(
                    id=rule_id,
                    rule_type=RuleType.price_lane_derivation,
                    description=(
                        f"{cc} policy-derived {policy_rule.target_category.value} "
                        f"from {policy_rule.source_price_type}."
                    ),
                    formula=policy_rule.formula,
                    input_fields=["price_amount", "price_type"],
                    output_field="price_amount",
                    effective_from=snapshot_date,
                    source_reference="; ".join(policy_rule.legal_basis),
                    created_at=datetime.now(timezone.utc),
                    created_by="policy-lane-graph",
                    country_code=cc,
                    parameters=params,
                    caveats=[*policy_rule.caveats, *notes],
                )
                derived = row.copy()
                derived["id"] = _stable_uuid(f"derived-record:{rule_id}")
                derived["price_amount"] = _q(amount)
                derived["price_type"] = policy_rule.target_price_type
                derived["price_includes_vat"] = (
                    policy.semantics.vat_position.value == "vat_inclusive"
                )
                derived["price_lane_source_record_id"] = source_id
                derived["price_lane_derivation_rule"] = rule
                rows.append(derived)
    if not rows:
        return pd.DataFrame(columns=list(df.columns))
    return pd.DataFrame(rows)


def _ie_ex_factory(row: pd.Series) -> tuple[Decimal | None, str, dict, list[str]]:
    amount = _as_decimal(row.get("price_amount"))
    if amount is None or amount <= 0:
        return None, "", {}, []
    form = str(row.get("dosage_form") or "").lower()
    route = str(row.get("route_of_administration") or "").lower()
    markup = Decimal("0.12") if (
        form in {"injectable", "infusible"} or route == "parenteral"
    ) else Decimal("0.08")
    return (
        amount / (Decimal("1") + markup),
        "ex_factory = reimbursement_price / (1 + wholesale_markup)",
        {"wholesale_markup": str(markup)},
        [
            "IE fridge/non-fridge classification is derived from normalised form/route; "
            "injectable or parenteral rows use 12%, other rows use 8%."
        ],
    )


def _it_ex_factory(row: pd.Series) -> tuple[Decimal | None, str, dict, list[str]]:
    amount = _as_decimal(row.get("price_amount"))
    if amount is None or amount <= 0:
        return None, "", {}, []
    factor = Decimal("0.6665")
    return (
        amount * factor,
        "ex_factory = prezzo_al_pubblico * 0.6665",
        {"ex_factory_share_of_public_price": str(factor)},
        [
            "Italy formula uses the standard Class A ex-factory share of public price; "
            "special distribution-share exceptions are not modelled in this first pass."
        ],
    )


def _pt_ex_factory(row: pd.Series) -> tuple[Decimal | None, str, dict, list[str]]:
    amount = _as_decimal(row.get("price_amount"))
    if amount is None or amount <= 0:
        return None, "", {}, []
    tiers = [
        (Decimal("0"), Decimal("5.00"), Decimal("1.1475"), Decimal("0.94"), "1"),
        (Decimal("5.01"), Decimal("7.00"), Decimal("1.1460"), Decimal("1.95"), "2"),
        (Decimal("7.01"), Decimal("10.00"), Decimal("1.1439"), Decimal("2.66"), "3"),
        (Decimal("10.01"), Decimal("20.00"), Decimal("1.1393"), Decimal("4.17"), "4"),
        (Decimal("20.01"), Decimal("50.00"), Decimal("1.1316"), Decimal("8.00"), "5"),
        (Decimal("50.01"), None, Decimal("1.1051"), Decimal("12.73"), "6"),
    ]
    for lower, upper, coefficient, fixed_fee, tier_id in tiers:
        pva = (amount - fixed_fee) / coefficient
        if pva < lower:
            continue
        if upper is not None and pva > upper:
            continue
        return (
            pva,
            "pva = (pvp_including_vat - fixed_fee) / tier_coefficient",
            {
                "tier": tier_id,
                "tier_lower_pva": str(lower),
                "tier_upper_pva": str(upper) if upper is not None else None,
                "coefficient": str(coefficient),
                "fixed_fee": str(fixed_fee),
                "vat_rate": "0.06",
            },
            [
                "Portugal PVA is derived from Infarmed commercial margin tiers; "
                "confidential discounts/rebates are not represented."
            ],
        )
    return None, "", {}, []


def _es_ex_factory(row: pd.Series) -> tuple[Decimal | None, str, dict, list[str]]:
    amount = _as_decimal(row.get("price_amount"))
    if amount is None or amount <= 0:
        return None, "", {}, []
    if amount <= Decimal("143.04"):
        pva = amount / Decimal("1.561083")
        parameters = {"tier": "1", "divisor": "1.561083"}
        formula = "pva = pvp_including_vat / 1.561083"
    elif amount <= Decimal("260.9464"):
        pva = (amount / Decimal("1.04")) - Decimal("45.91")
        parameters = {"tier": "2", "vat_rate": "0.04", "fixed_margin": "45.91"}
        formula = "pva = (pvp_including_vat / 1.04) - 45.91"
    elif amount <= Decimal("578.1464"):
        pva = (amount / Decimal("1.04")) - Decimal("50.91")
        parameters = {"tier": "3", "vat_rate": "0.04", "fixed_margin": "50.91"}
        formula = "pva = (pvp_including_vat / 1.04) - 50.91"
    else:
        pva = (amount / Decimal("1.04")) - Decimal("55.91")
        parameters = {"tier": "4", "vat_rate": "0.04", "fixed_margin": "55.91"}
        formula = "pva = (pvp_including_vat / 1.04) - 55.91"
    if pva <= 0:
        return None, "", {}, []
    return (
        pva,
        formula,
        parameters,
        [
            "Spain PVA is derived from PVP conversion tiers used for reference-price "
            "calculations; confidential rebates are not represented."
        ],
    )


_RULES: dict[str, tuple[str, Callable[[pd.Series], tuple[Decimal | None, str, dict, list[str]]], str]] = {
    "IE": ("Reimbursement Price", _ie_ex_factory, "S.I. 639/2019 and NCPE drug-cost guidance"),
    "IT": ("Prezzo al pubblico", _it_ex_factory, "AIFA Class A public-price/ex-factory framework"),
    "PT": ("PVP", _pt_ex_factory, "Infarmed Margens de Comercialização e Fatores de Conversão"),
    "ES": (
        "Precio de venta al público con IVA",
        _es_ex_factory,
        "Infarmed reference-country PVP-to-PVA conversion table for Spain",
    ),
}


def derive_price_lanes(
    df: pd.DataFrame,
    country_code: str,
    snapshot_date: date,
    policies: list[PolicyInterpretation] | None = None,
) -> pd.DataFrame:
    """Return virtual derived price-lane rows for a canonical snapshot."""
    if policies is not None:
        return _derive_price_lanes_from_policies(
            df, country_code, snapshot_date, policies
        )
    cc = country_code.upper()
    if cc not in _RULES or df.empty:
        return pd.DataFrame(columns=list(df.columns))
    if DERIVED_EX_FACTORY_PRICE_TYPE in set(df["price_type"].astype(str)):
        return pd.DataFrame(columns=list(df.columns))
    source_price_type, formula_fn, source_reference = _RULES[cc]
    rows: list[pd.Series] = []
    for _, row in df[df["price_type"] == source_price_type].iterrows():
        amount, formula, parameters, caveats = formula_fn(row)
        if amount is None:
            continue
        source_id = str(row["id"])
        rule_id = _stable_uuid(
            f"price_lane:{cc}:{source_id}:{DERIVED_EX_FACTORY_PRICE_TYPE}"
        )
        params = {
            **parameters,
            "source_record_id": source_id,
            "source_price_type": source_price_type,
            "source_price_amount": str(row.get("price_amount")),
            "derived_price_type": DERIVED_EX_FACTORY_PRICE_TYPE,
        }
        rule = DerivationRule(
            id=rule_id,
            rule_type=RuleType.price_lane_derivation,
            description=(
                f"{cc} policy-derived ex-factory/manufacturer price from "
                f"{source_price_type}."
            ),
            formula=formula,
            input_fields=["price_amount", "price_type"],
            output_field="price_amount",
            effective_from=snapshot_date,
            source_reference=source_reference,
            created_at=datetime.now(timezone.utc),
            created_by="price-lane-derivation",
            country_code=cc,
            parameters=params,
            caveats=caveats,
        )
        derived = row.copy()
        derived["id"] = _stable_uuid(f"derived-record:{rule_id}")
        derived["price_amount"] = _q(amount)
        derived["price_type"] = DERIVED_EX_FACTORY_PRICE_TYPE
        derived["price_includes_vat"] = False
        derived["price_lane_source_record_id"] = source_id
        derived["price_lane_derivation_rule"] = rule
        rows.append(derived)
    if not rows:
        return pd.DataFrame(columns=list(df.columns))
    return pd.DataFrame(rows)
