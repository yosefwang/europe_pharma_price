"""Multinational comparable price-lane index.

The index is the substrate between country-specific canonical records and
country-pair candidate generation. It applies the policy-data two-gear gate,
adds policy-supported virtual price lanes, and records the identity keys needed
for apple-to-apple comparisons without materialising every country pair.
"""

from __future__ import annotations

import json
import hashlib
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Mapping

import pandas as pd

from ..normalization.price_lanes import (
    comparable_lane_key,
    semantics_from_policy,
)
from ..policy.gating import (
    blocks_comparison,
    interpretation_for_field,
    load_interpretations,
)
from ..profile.gating import is_field_blocked
from ..schemas.profile import DataProfile
from .inn_normalizer import InnNormalizer
from .parsers import parse_pack_size, parse_strength
from .derivation import derive_per_unit_price
from .fx import convert_currency
from .price_lane_derivation import derive_price_lanes
from .product_classifier import classify_product
from .product_identity import resolve_product_identity


def _stable_uuid(seed: str) -> str:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return str(uuid.UUID(h[:32]))


def _decimal_key(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _canonical_path(repo_root: Path, country_code: str, snapshot_date: date) -> Path:
    return (
        repo_root / "data" / "canonical" / country_code.lower()
        / snapshot_date.isoformat() / "prices.parquet"
    )


def _cache_dir(repo_root: Path, cache_window_id: str) -> Path:
    return repo_root / "data" / "lane_index" / cache_window_id


def _snapshot_payload(snapshots: Mapping[str, date]) -> dict[str, str]:
    return {
        country.upper(): snapshot.isoformat()
        for country, snapshot in sorted(snapshots.items())
    }


def _cache_manifest_matches(path: Path, snapshots: Mapping[str, date]) -> bool:
    if not path.exists():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("snapshots") == _snapshot_payload(snapshots)


def _json_tuple(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return value
        return tuple(loaded) if isinstance(loaded, list) else loaded
    if isinstance(value, list):
        return tuple(value)
    return value


def _prepare_for_cache(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in (
        "comparable_lane_key",
        "identity_key",
        "presentation_key",
        "dosage_form_attributes",
        "policy_caveats",
    ):
        if column in out.columns:
            out[column] = out[column].map(lambda value: json.dumps(list(value)))
    return out


def _restore_from_cache(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in ("comparable_lane_key", "identity_key", "presentation_key"):
        if column in out.columns:
            out[column] = out[column].map(_json_tuple)
    for column in ("dosage_form_attributes", "policy_caveats"):
        if column in out.columns:
            out[column] = out[column].map(_json_tuple)
    if "price_amount" in out.columns:
        out["price_amount"] = out["price_amount"].astype(str).map(Decimal)
    for column in (
        "price_per_unit",
        "price_per_strength_unit",
        "price_per_strength_unit_eur",
        "strength_value",
    ):
        if column in out.columns:
            out[column] = out[column].astype(str).map(Decimal)
    return out


def _write_lane_index_cache(
    repo_root: Path,
    cache_window_id: str,
    snapshots: Mapping[str, date],
    lane_index: pd.DataFrame,
) -> None:
    out_dir = _cache_dir(repo_root, cache_window_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    _prepare_for_cache(lane_index).to_parquet(out_dir / "lane_index.parquet", index=False)
    manifest = {
        "cache_window_id": cache_window_id,
        "snapshots": _snapshot_payload(snapshots),
        "row_count": len(lane_index),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "multinational-lane-index-cache",
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _load_canonical(repo_root: Path, country_code: str, snapshot_date: date) -> pd.DataFrame:
    path = _canonical_path(repo_root, country_code, snapshot_date)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["price_amount"] = df["price_amount"].astype(str).map(Decimal)
    return df


def _load_price_profile(
    repo_root: Path, country_code: str, snapshot_date: date,
) -> DataProfile | None:
    path = (
        repo_root / "data" / "profiles" / country_code.lower()
        / snapshot_date.isoformat() / "data_profile.json"
    )
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    for entry in payload["profiles"]:
        if entry["price_type"] == "price_amount":
            return DataProfile.model_validate(entry)
    return None


def _nullable(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _bool_or_none(value) -> bool | None:
    value = _nullable(value)
    if value is None:
        return None
    return bool(value)


def _coerce_attrs(value) -> tuple[str, ...]:
    value = _nullable(value)
    if value is None:
        return ()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(v) for v in value if v is not None and str(v))
    return (str(value),) if str(value) else ()


def _derivation_rule_id(row) -> str | None:
    rule = row.get("price_lane_derivation_rule")
    return getattr(rule, "id", None)


def _source_record_id(row) -> str | None:
    return _nullable(row.get("price_lane_source_record_id"))


def build_country_lane_index(
    repo_root: Path, country_code: str, snapshot_date: date,
    *,
    fx_rate_date: date | None = None,
) -> pd.DataFrame:
    """Build comparable price-lane rows for one country snapshot."""
    df = _load_canonical(repo_root, country_code, snapshot_date)
    if df.empty:
        return pd.DataFrame()

    policies = load_interpretations(repo_root, country_code)
    derived = derive_price_lanes(
        df,
        country_code,
        snapshot_date,
        policies=policies,
    )
    if not derived.empty:
        df = pd.concat([df, derived], ignore_index=True, sort=False)

    profile = _load_price_profile(repo_root, country_code, snapshot_date)
    data_blocked, _reason = is_field_blocked(profile)
    if data_blocked or profile is None:
        return pd.DataFrame()

    normalizer = InnNormalizer(repo_root)
    rows: list[dict] = []
    observed_by_raw = {
        row["raw_record_id"]: row["id"]
        for _, row in df.iterrows()
        if "derived" not in str(row["price_type"]).lower()
    }

    for _, row in df.iterrows():
        policy = interpretation_for_field(
            policies, str(row["price_type"]), snapshot_date,
        )
        policy_blocked, _policy_reason = blocks_comparison(policy)
        if policy_blocked or policy is None:
            continue

        raw_inn_value = _nullable(row.get("inn"))
        raw_inn = str(raw_inn_value or "").strip()
        identity = resolve_product_identity(
            repo_root,
            country_code=country_code,
            inn=raw_inn,
            atc_code=_nullable(row.get("atc_code")),
            active_ingredient_labels=[
                _nullable(row.get("active_ingredient_label")),
                _nullable(row.get("active_ingredient_labels")),
            ],
            product_name=str(row.get("product_name") or ""),
            normalizer=normalizer,
        )
        if identity.canonical_inn is None:
            continue
        raw_inn = raw_inn or str(identity.evidence or "")

        strength = parse_strength(str(row.get("strength") or ""))
        pack = parse_pack_size(str(row.get("pack_size") or ""))
        if strength is None or pack is None:
            continue
        if strength.value <= 0 or pack.units <= 0:
            continue
        unit_price = derive_per_unit_price(
            row["id"], row["price_amount"], pack, strength,
            snapshot_date, country_code,
        )
        normalized_amount = unit_price.price_per_strength_unit
        normalized_currency = row["price_currency"]
        fx_rule_id = None
        if normalized_currency != "EUR":
            fx = convert_currency(
                repo_root,
                unit_price.price_per_strength_unit,
                from_ccy=normalized_currency,
                to_ccy="EUR",
                rate_date=fx_rate_date or snapshot_date,
                canonical_id=row["id"],
            )
            if fx is None:
                continue
            normalized_amount = fx.converted_amount
            normalized_currency = "EUR"
            fx_rule_id = fx.rule.id

        semantics = semantics_from_policy(policy)
        lane_key = comparable_lane_key(semantics)
        source_record_id = _source_record_id(row)
        derivation_rule_id = _derivation_rule_id(row)
        if semantics.derivation_kind == "derived":
            source_record_id = source_record_id or observed_by_raw.get(row["raw_record_id"])
            derivation_rule_id = derivation_rule_id or _stable_uuid(
                f"materialized-price-lane:{country_code}:{source_record_id}:{row['id']}"
            )
        product = classify_product(
            str(row.get("product_name") or ""),
            identity.canonical_inn,
        )
        route = _nullable(row.get("route_of_administration"))
        form = str(_nullable(row.get("dosage_form")) or "")
        form_attrs = _coerce_attrs(row.get("dosage_form_attributes"))
        identity_key = (
            identity.canonical_inn,
            _decimal_key(strength.value),
            strength.unit,
            form,
            str(route or ""),
        )
        presentation_key = identity_key + (str(pack.units),) + form_attrs

        rows.append({
            "country_code": country_code,
            "snapshot_date": snapshot_date.isoformat(),
            "canonical_record_id": row["id"],
            "raw_record_id": row["raw_record_id"],
            "source_document_id": row["source_document_id"],
            "price_type": row["price_type"],
            "price_amount": row["price_amount"],
            "price_currency": row["price_currency"],
            "price_includes_vat": _bool_or_none(row.get("price_includes_vat")),
            "price_per_unit": unit_price.price_per_unit,
            "price_per_strength_unit": unit_price.price_per_strength_unit,
            "price_per_strength_unit_eur": normalized_amount,
            "normalized_currency": normalized_currency,
            "fx_derivation_rule_id": fx_rule_id,
            "price_lane_source_record_id": source_record_id,
            "price_lane_derivation_rule_id": derivation_rule_id,
            "policy_interpretation_id": policy.id,
            "data_profile_id": profile.id,
            "comparison_category": semantics.comparison_category,
            "vat_position": semantics.vat_position,
            "margin_position": semantics.margin_position,
            "derivation_kind": semantics.derivation_kind,
            "policy_confidence": semantics.policy_confidence,
            "comparable_lane_key": lane_key,
            "raw_inn": raw_inn,
            "canonical_inn": identity.canonical_inn,
            "inn_normalization_method": identity.method,
            "atc_code": identity.atc_code or _nullable(row.get("atc_code")),
            "strength_value": strength.value,
            "strength_unit": strength.unit,
            "strength_pattern_id": strength.pattern_id,
            "pack_units": pack.units,
            "pack_pattern_id": pack.pattern_id,
            "dosage_form": form,
            "route_of_administration": route,
            "dosage_form_raw": _nullable(row.get("dosage_form_raw")),
            "dosage_form_attributes": form_attrs,
            "dosage_form_rule_id": _nullable(row.get("dosage_form_rule_id")),
            "dosage_form_confidence": _nullable(
                row.get("dosage_form_normalization_confidence")
            ),
            "product_name": str(row.get("product_name") or ""),
            "manufacturer": _nullable(row.get("manufacturer")),
            "national_product_code": _nullable(row.get("national_product_code")),
            "product_type": product.product_type.value,
            "identity_key": identity_key,
            "presentation_key": presentation_key,
            "policy_caveats": semantics.caveats,
        })

    return pd.DataFrame(rows)


def build_multinational_lane_index(
    repo_root: Path,
    snapshots: Mapping[str, date],
    *,
    cache_window_id: str | None = None,
    use_cache: bool = False,
) -> pd.DataFrame:
    if use_cache and cache_window_id is not None:
        out_dir = _cache_dir(repo_root, cache_window_id)
        manifest_path = out_dir / "manifest.json"
        cache_path = out_dir / "lane_index.parquet"
        if cache_path.exists() and _cache_manifest_matches(manifest_path, snapshots):
            return _restore_from_cache(pd.read_parquet(cache_path))

    fx_rate_date = max(snapshots.values()) if snapshots else None
    frames = [
        build_country_lane_index(
            repo_root, country, snapshot,
            fx_rate_date=fx_rate_date,
        )
        for country, snapshot in snapshots.items()
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    lane_index = pd.concat(frames, ignore_index=True, sort=False)
    if use_cache and cache_window_id is not None:
        _write_lane_index_cache(repo_root, cache_window_id, snapshots, lane_index)
    return lane_index


def find_comparable_rows(
    lane_index: pd.DataFrame,
    molecule: str,
    *,
    comparable_key: tuple[str, str, str] | None = None,
    min_countries: int = 2,
) -> pd.DataFrame:
    """Return indexed rows that can support an apple-to-apple comparison.

    Rows are retained only when they share molecule, comparable price-lane key,
    and identity key across at least `min_countries` countries. This is a
    cohort/query view over the substrate, not a pairwise materialisation.
    """
    if lane_index.empty:
        return lane_index.copy()
    target = molecule.strip().lower()
    df = lane_index[lane_index["canonical_inn"].str.lower() == target].copy()
    if comparable_key is not None:
        df = df[df["comparable_lane_key"] == comparable_key].copy()
    if df.empty:
        return df

    keep_keys: set[tuple[tuple[str, str, str], tuple]] = set()
    for (lane_key, identity_key), group in df.groupby(
        ["comparable_lane_key", "identity_key"],
        sort=False,
    ):
        if group["country_code"].nunique() >= min_countries:
            keep_keys.add((lane_key, identity_key))

    if not keep_keys:
        return df.iloc[0:0].copy()
    out = df[
        df.apply(
            lambda row: (
                row["comparable_lane_key"],
                row["identity_key"],
            ) in keep_keys,
            axis=1,
        )
    ].copy()
    out["comparison_group_id"] = out.apply(
        lambda row: _stable_uuid(
            f"group:{row['canonical_inn']}:{row['comparable_lane_key']}:"
            f"{row['identity_key']}"
        ),
        axis=1,
    )
    return out
