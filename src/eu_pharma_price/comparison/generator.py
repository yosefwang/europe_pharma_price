"""Comparison candidate generator.

Combines policy gating, data gating, identity matching, and derivation
rules to produce ComparisonCandidate artifacts. Enforces the two-gear
rule on both sides; never modifies canonical records on disk.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd

from ..policy.gating import (
    blocks_comparison as policy_blocks,
    interpretation_for_field,
    load_interpretations,
)
from ..profile.gating import is_field_blocked
from ..schemas.comparison import ComparisonCandidate, DerivationRule
from ..schemas.policy import PolicyInterpretation
from ..schemas.profile import DataProfile
from ..schemas.review import (
    AnomalyReport,
    AnomalyStatus,
    AnomalyType,
    Severity,
)
from .derivation import derive_per_unit_price
from .fx import convert_currency
from .identity import IdentityMatch, assess_identity
from .inn_normalizer import InnNormalizer
from .parsers import parse_pack_size, parse_strength
from .price_lane_derivation import derive_price_lanes
from .product_classifier import classify_product


@dataclass
class CandidatePackage:
    candidate: ComparisonCandidate
    derivation_rules: list[DerivationRule]
    identity_match: IdentityMatch
    evidence_bundle: dict


@dataclass
class GenerationResult:
    candidates: list[CandidatePackage] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    anomalies: list[AnomalyReport] = field(default_factory=list)


def _stable_id(seed: str) -> str:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return str(uuid.UUID(h[:32]))


def _price_ratio_against_country_b(
    repo_root: Path,
    country_a_price_per_strength_unit: Decimal,
    country_a_currency: str,
    country_b_record_id: str,
    country_b_price_per_strength_unit: Decimal,
    country_b_currency: str,
    rate_date: date,
) -> tuple[Decimal | None, Decimal | None, DerivationRule | None]:
    """Return country A / country B ratio, converting B into A currency if needed."""
    country_b_comparable_price = country_b_price_per_strength_unit
    fx_rule: DerivationRule | None = None

    if country_a_currency != country_b_currency:
        fx = convert_currency(
            repo_root,
            country_b_price_per_strength_unit,
            from_ccy=country_b_currency,
            to_ccy=country_a_currency,
            rate_date=rate_date,
            canonical_id=country_b_record_id,
        )
        if fx is None:
            return None, None, None
        country_b_comparable_price = fx.converted_amount
        fx_rule = fx.rule

    if country_b_comparable_price == 0:
        return None, country_b_comparable_price, fx_rule
    return (
        country_a_price_per_strength_unit / country_b_comparable_price,
        country_b_comparable_price,
        fx_rule,
    )


def _load_canonical(repo_root: Path, country_code: str, snapshot_date: date) -> pd.DataFrame:
    p = (
        repo_root / "data" / "canonical" / country_code.lower()
        / snapshot_date.isoformat() / "prices.parquet"
    )
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    df["price_amount"] = df["price_amount"].astype(str).map(Decimal)
    return df


def _load_profile_for_field(
    repo_root: Path, country_code: str, snapshot_date: date,
    profile_field: str = "price_amount",
) -> DataProfile | None:
    p = (
        repo_root / "data" / "profiles" / country_code.lower()
        / snapshot_date.isoformat() / "data_profile.json"
    )
    if not p.exists():
        return None
    payload = json.loads(p.read_text(encoding="utf-8"))
    for entry in payload["profiles"]:
        if entry["price_type"] == profile_field:
            return DataProfile.model_validate(entry)
    return None


def _coerce_form_attributes(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            if hasattr(item, "tolist"):
                item = item.tolist()
            if isinstance(item, (list, tuple, set)):
                out.extend(str(v) for v in item if str(v))
            elif item is not None and str(item):
                out.append(str(item))
        return tuple(out)
    return (str(value),) if str(value) else ()


def _nullable_evidence_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _form_evidence(row) -> dict:
    dosage_form = _nullable_evidence_value(row.get("dosage_form", ""))
    return {
        "dosage_form": str(dosage_form) if dosage_form is not None else "",
        "route_of_administration": _nullable_evidence_value(
            row.get("route_of_administration")
        ),
        "dosage_form_raw": _nullable_evidence_value(row.get("dosage_form_raw")),
        "dosage_form_attributes": list(
            _coerce_form_attributes(row.get("dosage_form_attributes"))
        ),
        "dosage_form_normalization_method": _nullable_evidence_value(
            row.get("dosage_form_normalization_method")
        ),
        "dosage_form_normalization_confidence": _nullable_evidence_value(
            row.get("dosage_form_normalization_confidence")
        ),
        "dosage_form_rule_id": _nullable_evidence_value(
            row.get("dosage_form_rule_id")
        ),
        "dosage_form_caveat": _nullable_evidence_value(row.get("dosage_form_caveat")),
    }


def _lane_derivation_rule(row) -> DerivationRule | None:
    rule = row.get("price_lane_derivation_rule")
    return rule if isinstance(rule, DerivationRule) else None


def _lane_derivation_evidence(row) -> dict:
    rule = _lane_derivation_rule(row)
    if rule is None:
        return {
            "price_lane_source_record_id": None,
            "price_lane_derivation_rule_id": None,
            "price_lane_derivation_rule": None,
        }
    return {
        "price_lane_source_record_id": _nullable_evidence_value(
            row.get("price_lane_source_record_id")
        ),
        "price_lane_derivation_rule_id": rule.id,
        "price_lane_derivation_rule": json.loads(rule.model_dump_json()),
    }


def _filter_country_records(
    repo_root: Path, country_code: str, snapshot_date: date,
) -> tuple[pd.DataFrame, PolicyInterpretation | None, DataProfile | None, str | None]:
    """Return (records, policy, profile, block_reason) for the FIRST price_type
    in the canonical data. Kept for backwards compatibility with single-price-
    type ingestions; multi-price ingestions should call _enumerate_price_lanes
    instead."""
    df = _load_canonical(repo_root, country_code, snapshot_date)
    if df.empty:
        return df, None, None, "no canonical data"

    interps = load_interpretations(repo_root, country_code)
    pt = df["price_type"].iloc[0]
    policy = interpretation_for_field(interps, pt, snapshot_date)
    p_blocked, p_reason = policy_blocks(policy)
    if p_blocked:
        return df, policy, None, f"policy: {p_reason}"

    profile = _load_profile_for_field(repo_root, country_code, snapshot_date)
    d_blocked, d_reason = is_field_blocked(profile)
    if d_blocked:
        return df, policy, profile, f"data: {d_reason}"

    return df, policy, profile, None


def _enumerate_price_lanes(
    repo_root: Path, country_code: str, snapshot_date: date,
) -> tuple[
    list[tuple[str, pd.DataFrame, PolicyInterpretation, DataProfile]],
    list[dict],
]:
    """Return one (price_type, df_subset, policy, profile) tuple per price
    type that survives both gates. Also returns skip reasons for blocked lanes.
    Multi-price ingestions (e.g., PL with cena netto / hurtowa / detaliczna)
    produce multiple lanes from a single snapshot.
    """
    df = _load_canonical(repo_root, country_code, snapshot_date)
    skips: list[dict] = []
    lanes: list[tuple[str, pd.DataFrame, PolicyInterpretation, DataProfile]] = []
    if df.empty:
        skips.append({
            "country": country_code, "snapshot": snapshot_date.isoformat(),
            "reason": "no canonical data",
        })
        return lanes, skips

    interps = load_interpretations(repo_root, country_code)
    derived = derive_price_lanes(
        df,
        country_code,
        snapshot_date,
        policies=interps,
    )
    if not derived.empty:
        df = pd.concat([df, derived], ignore_index=True, sort=False)

    profile = _load_profile_for_field(repo_root, country_code, snapshot_date)
    d_blocked, d_reason = is_field_blocked(profile)
    if d_blocked:
        skips.append({
            "country": country_code, "snapshot": snapshot_date.isoformat(),
            "reason": f"data: {d_reason}",
        })
        return lanes, skips

    for pt in df["price_type"].unique():
        policy = interpretation_for_field(interps, pt, snapshot_date)
        p_blocked, p_reason = policy_blocks(policy)
        if p_blocked:
            skips.append({
                "country": country_code, "snapshot": snapshot_date.isoformat(),
                "price_type": pt,
                "reason": f"policy: {p_reason}",
            })
            continue
        df_subset = df[df["price_type"] == pt].copy()
        lanes.append((pt, df_subset, policy, profile))

    return lanes, skips


def generate_candidates(
    repo_root: Path,
    country_a: str, snapshot_a: date,
    country_b: str, snapshot_b: date,
) -> GenerationResult:
    result = GenerationResult()

    lanes_a, skips_a = _enumerate_price_lanes(repo_root, country_a, snapshot_a)
    lanes_b, skips_b = _enumerate_price_lanes(repo_root, country_b, snapshot_b)
    result.skipped.extend(skips_a)
    result.skipped.extend(skips_b)

    if not lanes_a or not lanes_b:
        return result

    # Match lanes by comparison_category. A pair of lanes generates candidates
    # only when both sides agree on the category.
    matched_pairs = []
    for pt_a, df_a_lane, pol_a, prof_a in lanes_a:
        for pt_b, df_b_lane, pol_b, prof_b in lanes_b:
            if pol_a.semantics.comparison_category != pol_b.semantics.comparison_category:
                continue
            matched_pairs.append((pt_a, df_a_lane, pol_a, prof_a, pt_b, df_b_lane, pol_b, prof_b))

    if not matched_pairs:
        result.skipped.append({
            "pair": f"{country_a}/{country_b}",
            "reason": (
                "no overlapping comparison_category across lanes: "
                f"{country_a} has {[a[0] for a in lanes_a]}, "
                f"{country_b} has {[b[0] for b in lanes_b]}"
            ),
        })
        return result

    for (pt_a, df_a, pol_a, prof_a, pt_b, df_b, pol_b, prof_b) in matched_pairs:
        _generate_for_lane_pair(
            result, repo_root,
            country_a, snapshot_a, df_a, pol_a, prof_a,
            country_b, snapshot_b, df_b, pol_b, prof_b,
        )
    return result


def _prepare_lane_rows(
    df: pd.DataFrame, normalizer: InnNormalizer | None, country_code: str,
) -> list[dict]:
    """Pre-parse strength/pack/INN/form per row exactly once, drop rows that
    can't be matched. Normalizes INN through the two-layer pipeline so the
    INN-blocked join operates on canonical forms. Returns a list of dicts
    keyed for fast inner-loop use.
    """
    prepared: list[dict] = []
    for _, row in df.iterrows():
        raw_inn = (row.get("inn") or "")
        if isinstance(raw_inn, str):
            raw_inn = raw_inn.strip()
        if not raw_inn:
            continue

        # Two-layer INN normalization
        if normalizer is not None:
            nr = normalizer.normalize(raw_inn, country_code)
            if nr.canonical_inn is None:
                continue
            canonical_inn = nr.canonical_inn
            inn_atc = nr.atc_code
            inn_method = nr.method.value
        else:
            canonical_inn = raw_inn.strip().lower()
            inn_atc = None
            inn_method = "structured"

        s = parse_strength(str(row.get("strength", "")))
        if s is None:
            continue
        p = parse_pack_size(str(row.get("pack_size", "")))
        if p is None:
            continue
        prepared.append({
            "row": row,
            "inn": canonical_inn,
            "atc": inn_atc,
            "inn_method": inn_method,
            "product_name": str(row.get("product_name", "")),
            "strength": s,
            "pack": p,
            "form": row.get("dosage_form", ""),
            "route": row.get("route_of_administration"),
            "form_attrs": _coerce_form_attributes(row.get("dosage_form_attributes")),
            "form_confidence": row.get("dosage_form_normalization_confidence") or "strong",
        })
    return prepared


def _generate_for_lane_pair(
    result: GenerationResult,
    repo_root: Path,
    country_a: str, snapshot_a: date,
    df_a: pd.DataFrame, pol_a: PolicyInterpretation, prof_a: DataProfile,
    country_b: str, snapshot_b: date,
    df_b: pd.DataFrame, pol_b: PolicyInterpretation, prof_b: DataProfile,
) -> None:
    """Inner loop: generate candidates for one matched (price_type_a, price_type_b)
    pair. Mutates result in place."""
    normalizer = InnNormalizer(repo_root)
    prepped_a = _prepare_lane_rows(df_a, normalizer, country_a)
    prepped_b = _prepare_lane_rows(df_b, normalizer, country_b)

    # INN-blocked inner loop. Both sides are already INN-normalised.
    by_inn_b: dict[str, list[dict]] = {}
    for entry in prepped_b:
        by_inn_b.setdefault(entry["inn"], []).append(entry)

    # ATC-blocked index: for records with ATC codes, also index by ATC
    # so that salt-form vs base-molecule pairs (e.g. "metformin" vs
    # "metformin hydrochloride") can still be matched when ATC L5 agrees.
    by_atc_b: dict[str, list[dict]] = {}
    for entry in prepped_b:
        atc = entry.get("atc")
        if atc and len(atc) == 7:
            by_atc_b.setdefault(atc, []).append(entry)

    # Lane-level VAT caveat. Both policies map to the same comparison_category
    # (matched upstream), but they may differ on whether the price includes VAT.
    # That's a real numerical caveat for ratios, not a blocker.
    lane_caveats: list[str] = []
    semantics_a = pol_a.semantics
    semantics_b = pol_b.semantics

    if semantics_a.vat_position != semantics_b.vat_position:
        lane_caveats.append(
            f"VAT inclusion differs: {country_a} {pol_a.price_type} "
            f"vat_position={semantics_a.vat_position}, {country_b} {pol_b.price_type} "
            f"vat_position={semantics_b.vat_position}. Price ratio is uncorrected; "
            f"a VAT-stripping derivation rule should be applied before headline use."
        )

    # Build pairs to evaluate: INN-matched first, then ATC-matched (no dups)
    seen_pair_ids: set[tuple[str, str]] = set()
    pairs_to_evaluate: list[tuple[dict, dict]] = []

    # Pass 1: INN-blocked pairs (canonical INN must match exactly)
    for entry_a in prepped_a:
        inn_a = entry_a["inn"]
        candidates_b = by_inn_b.get(inn_a)
        if not candidates_b:
            continue
        for entry_b in candidates_b:
            pair_key = (entry_a["row"]["id"], entry_b["row"]["id"])
            if pair_key not in seen_pair_ids:
                seen_pair_ids.add(pair_key)
                pairs_to_evaluate.append((entry_a, entry_b))

    # Pass 2: ATC-blocked pairs (same ATC L5 code, different canonical INN)
    for entry_a in prepped_a:
        atc_a = entry_a.get("atc")
        if not atc_a or len(atc_a) != 7:
            continue
        candidates_b = by_atc_b.get(atc_a)
        if not candidates_b:
            continue
        for entry_b in candidates_b:
            pair_key = (entry_a["row"]["id"], entry_b["row"]["id"])
            if pair_key not in seen_pair_ids:
                seen_pair_ids.add(pair_key)
                pairs_to_evaluate.append((entry_a, entry_b))

    for entry_a, entry_b in pairs_to_evaluate:
        inn_a = entry_a["inn"]
        inn_b = entry_b["inn"]
        row_a = entry_a["row"]
        row_b = entry_b["row"]
        s_a, p_a = entry_a["strength"], entry_a["pack"]
        s_b, p_b = entry_b["strength"], entry_b["pack"]

        match = assess_identity(
            inn_a, inn_b,
            entry_a["form"], entry_b["form"],
            entry_a["route"], entry_b["route"],
            s_a, s_b, p_a, p_b,
            inn_atc_a=entry_a.get("atc"),
            inn_atc_b=entry_b.get("atc"),
            inn_method_a=entry_a.get("inn_method", "structured"),
            inn_method_b=entry_b.get("inn_method", "structured"),
            form_attrs_a=entry_a.get("form_attrs", ()),
            form_attrs_b=entry_b.get("form_attrs", ()),
            form_confidence_a=entry_a.get("form_confidence", "strong"),
            form_confidence_b=entry_b.get("form_confidence", "strong"),
        )
        if not match.matches:
            continue

        derived_a = derive_per_unit_price(
            row_a["id"], row_a["price_amount"], p_a, s_a,
            snapshot_a, country_a,
        )
        derived_b = derive_per_unit_price(
            row_b["id"], row_b["price_amount"], p_b, s_b,
            snapshot_b, country_b,
        )

        if country_a < country_b:
            ca, cb = country_a, country_b
            ra, rb = row_a, row_b
            pa, pb = pol_a, pol_b
            prfa, prfb = prof_a, prof_b
            snap_a, snap_b = snapshot_a, snapshot_b
            derA, derB = derived_a, derived_b
        else:
            ca, cb = country_b, country_a
            ra, rb = row_b, row_a
            pa, pb = pol_b, pol_a
            prfa, prfb = prof_b, prof_a
            snap_a, snap_b = snapshot_b, snapshot_a
            derA, derB = derived_b, derived_a

        price_ratio, price_b_converted, fx_rule = _price_ratio_against_country_b(
            repo_root=repo_root,
            country_a_price_per_strength_unit=derA.price_per_strength_unit,
            country_a_currency=ra["price_currency"],
            country_b_record_id=rb["id"],
            country_b_price_per_strength_unit=derB.price_per_strength_unit,
            country_b_currency=rb["price_currency"],
            rate_date=max(snap_a, snap_b),
        )

        cid_seed = (
            f"{ra['id']}|{rb['id']}|{pa.id}|{pb.id}|{prfa.id}|{prfb.id}"
        )
        fx_note = ""
        candidate_caveats = (
            ([match.reason] if match.reason else []) + lane_caveats
        )
        lane_rule_a = _lane_derivation_rule(ra)
        lane_rule_b = _lane_derivation_rule(rb)
        for lane_rule in (lane_rule_a, lane_rule_b):
            if lane_rule is not None:
                candidate_caveats.extend(lane_rule.caveats)
        if fx_rule is not None:
            fx_note = (
                f"; FX: {rb['price_currency']}→{ra['price_currency']} "
                f"at {fx_rule.parameters.get('rate', '?')} "
                f"(ECB {fx_rule.fx_date})"
            )
            candidate_caveats.append(
                f"FX conversion applied: {fx_rule.description}"
            )
        candidate = ComparisonCandidate(
            id=_stable_id(cid_seed),
            molecule_inn=str(inn_a).strip().lower(),
            atc_code=str(
                entry_a.get("atc") or entry_b.get("atc")
                or ra.get("atc_code") or rb.get("atc_code") or ""
            ),
            strength=str(ra["strength"]),
            dosage_form=str(ra["dosage_form"]),
            country_a_code=ca,
            country_b_code=cb,
            country_a_record_id=ra["id"],
            country_b_record_id=rb["id"],
            country_a_policy_id=pa.id,
            country_b_policy_id=pb.id,
            country_a_profile_id=prfa.id,
            country_b_profile_id=prfb.id,
            comparison_category=pa.comparison_category.value,
            snapshot_date=max(snap_a, snap_b),
            created_at=datetime.now(timezone.utc),
            created_by="phase-6-generator",
            derivation_rule_a_id=derA.rule_per_strength_unit.id,
            derivation_rule_b_id=derB.rule_per_strength_unit.id,
            identity_match_method=match.method,
            identity_confidence=match.confidence,
            product_type_a=classify_product(
                entry_a["product_name"], entry_a["inn"],
            ).product_type.value,
            product_type_b=classify_product(
                entry_b["product_name"], entry_b["inn"],
            ).product_type.value,
            price_ratio=price_ratio,
            normalisation_notes=(
                f"per_unit + per_strength_unit on both sides"
                f"{fx_note}"
            ),
            caveats=candidate_caveats,
        )

        evidence_bundle = {
            "candidate_id": candidate.id,
            "country_a": {
                "country_code": ca,
                "canonical_record_id": ra["id"],
                "raw_record_id": ra["raw_record_id"],
                "source_document_id": ra["source_document_id"],
                "policy_interpretation_id": pa.id,
                "data_profile_id": prfa.id,
                "derivation_rule_id": derA.rule_per_strength_unit.id,
                "price_amount": str(ra["price_amount"]),
                "price_currency": ra["price_currency"],
                "price_type": ra["price_type"],
                "price_per_strength_unit": str(derA.price_per_strength_unit),
                **_lane_derivation_evidence(ra),
                **_form_evidence(ra),
            },
            "country_b": {
                "country_code": cb,
                "canonical_record_id": rb["id"],
                "raw_record_id": rb["raw_record_id"],
                "source_document_id": rb["source_document_id"],
                "policy_interpretation_id": pb.id,
                "data_profile_id": prfb.id,
                "derivation_rule_id": derB.rule_per_strength_unit.id,
                "price_amount": str(rb["price_amount"]),
                "price_currency": rb["price_currency"],
                "price_type": rb["price_type"],
                "price_per_strength_unit": str(derB.price_per_strength_unit),
                **_lane_derivation_evidence(rb),
                **_form_evidence(rb),
            },
            "comparison_category": pa.comparison_category.value,
            "identity_confidence": (
                match.confidence.value if match.confidence else None
            ),
            "price_ratio": str(price_ratio) if price_ratio is not None else None,
            "fx": (
                {
                    "applied": True,
                    "derivation_rule_id": fx_rule.id,
                    "from_ccy": rb["price_currency"],
                    "to_ccy": ra["price_currency"],
                    "rate": fx_rule.parameters.get("rate"),
                    "rate_date": fx_rule.fx_date.isoformat(),
                    "source": fx_rule.fx_source,
                    "converted_country_code": cb,
                    "original_price_per_strength_unit": str(
                        derB.price_per_strength_unit
                    ),
                    "converted_price_per_strength_unit": str(price_b_converted),
                }
                if fx_rule is not None
                else {"applied": False}
            ),
        }

        rules = [
            derA.rule_per_unit, derA.rule_per_strength_unit,
            derB.rule_per_unit, derB.rule_per_strength_unit,
        ]
        if lane_rule_a is not None:
            rules.append(lane_rule_a)
        if lane_rule_b is not None:
            rules.append(lane_rule_b)
        if fx_rule is not None:
            rules.append(fx_rule)

        result.candidates.append(CandidatePackage(
            candidate=candidate,
            derivation_rules=rules,
            identity_match=match,
            evidence_bundle=evidence_bundle,
        ))

def write_candidate_artifacts(
    repo_root: Path, snapshot_window_id: str, result: GenerationResult,
) -> dict[str, Path]:
    out_dir = repo_root / "data" / "comparisons" / snapshot_window_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for pkg in result.candidates:
        d = json.loads(pkg.candidate.model_dump_json())
        rows.append(d)
    if rows:
        df = pd.DataFrame(rows)
        candidates_path = out_dir / "candidates.parquet"
        df.to_parquet(candidates_path, index=False)
    else:
        candidates_path = None

    bundle_path = out_dir / "evidence_bundle.jsonl"
    with bundle_path.open("w", encoding="utf-8") as fh:
        for pkg in result.candidates:
            fh.write(json.dumps(pkg.evidence_bundle, ensure_ascii=False) + "\n")

    rules_path = out_dir / "derivation_rules.jsonl"
    with rules_path.open("w", encoding="utf-8") as fh:
        seen = set()
        for pkg in result.candidates:
            for rule in pkg.derivation_rules:
                if rule.id in seen:
                    continue
                seen.add(rule.id)
                fh.write(rule.model_dump_json() + "\n")

    rep_dir = repo_root / "reports" / "comparisons" / snapshot_window_id
    rep_dir.mkdir(parents=True, exist_ok=True)
    rep_path = rep_dir / "candidate-summary.md"
    lines = [
        f"# Comparison candidates — window `{snapshot_window_id}`",
        "",
        f"**Candidates:** {len(result.candidates)}",
        f"**Skipped:** {len(result.skipped)}",
        f"**Anomalies:** {len(result.anomalies)}",
        "",
    ]
    if result.candidates:
        lines.extend(["## Candidates", ""])
        for pkg in result.candidates[:20]:
            c = pkg.candidate
            ev = pkg.evidence_bundle
            ratio = (
                f"price_ratio={c.price_ratio:.4f}" if c.price_ratio is not None
                else "price_ratio=null (currencies differ)"
            )
            lines.append(
                f"- `{c.id[:8]}…` {c.molecule_inn} {c.strength} {c.dosage_form} "
                f"— {c.country_a_code} {ev['country_a']['price_per_strength_unit']} "
                f"{ev['country_a']['price_currency']}/{pkg.derivation_rules[1].parameters['strength_unit']} "
                f"vs {c.country_b_code} {ev['country_b']['price_per_strength_unit']} "
                f"{ev['country_b']['price_currency']}/{pkg.derivation_rules[3].parameters['strength_unit']} "
                f"— {ratio} — identity={c.identity_confidence.value if c.identity_confidence else 'n/a'}"
            )
    if result.skipped:
        lines.extend(["", "## Skipped", ""])
        for s in result.skipped:
            lines.append(f"- {s}")
    if result.anomalies:
        lines.extend(["", "## Anomalies", ""])
        for a in result.anomalies:
            lines.append(f"- [{a.severity.value}] {a.title}")
    rep_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "candidates_parquet": candidates_path,
        "evidence_bundle": bundle_path,
        "derivation_rules": rules_path,
        "report": rep_path,
    }
