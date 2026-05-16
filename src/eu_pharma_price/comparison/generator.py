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
from .identity import IdentityMatch, assess_identity
from .parsers import parse_pack_size, parse_strength


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


def _filter_country_records(
    repo_root: Path, country_code: str, snapshot_date: date,
) -> tuple[pd.DataFrame, PolicyInterpretation | None, DataProfile | None, str | None]:
    """Return (records, policy, profile, block_reason)."""
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


def generate_candidates(
    repo_root: Path,
    country_a: str, snapshot_a: date,
    country_b: str, snapshot_b: date,
) -> GenerationResult:
    result = GenerationResult()

    df_a, pol_a, prof_a, block_a = _filter_country_records(
        repo_root, country_a, snapshot_a
    )
    df_b, pol_b, prof_b, block_b = _filter_country_records(
        repo_root, country_b, snapshot_b
    )

    if block_a:
        result.skipped.append({
            "country": country_a, "snapshot": snapshot_a.isoformat(),
            "reason": block_a,
        })
        return result
    if block_b:
        result.skipped.append({
            "country": country_b, "snapshot": snapshot_b.isoformat(),
            "reason": block_b,
        })
        return result

    if pol_a.comparison_category != pol_b.comparison_category:
        result.skipped.append({
            "pair": f"{country_a}/{country_b}",
            "reason": (
                f"comparison_category mismatch: "
                f"{pol_a.comparison_category.value} vs {pol_b.comparison_category.value}"
            ),
        })
        return result

    for _, row_a in df_a.iterrows():
        s_a = parse_strength(str(row_a.get("strength", "")))
        p_a = parse_pack_size(str(row_a.get("pack_size", "")))
        if s_a is None or p_a is None:
            result.anomalies.append(AnomalyReport(
                id=str(uuid.uuid4()),
                country_code=country_a,
                anomaly_type=AnomalyType.schema_mismatch,
                severity=Severity.medium,
                title=f"Unparseable strength/pack: {row_a.get('strength')!r}/{row_a.get('pack_size')!r}",
                description=(
                    f"Cannot normalise canonical record {row_a['id']} for "
                    f"{country_a}: strength={row_a.get('strength')!r}, "
                    f"pack_size={row_a.get('pack_size')!r}"
                ),
                evidence=[row_a["id"]],
                reported_at=datetime.now(timezone.utc),
                reported_by="phase-6-generator",
                status=AnomalyStatus.open,
                affected_records=[row_a["id"]],
            ))
            continue

        for _, row_b in df_b.iterrows():
            s_b = parse_strength(str(row_b.get("strength", "")))
            p_b = parse_pack_size(str(row_b.get("pack_size", "")))
            if s_b is None or p_b is None:
                continue

            inn_a = row_a.get("inn") or row_a.get("product_name", "").split()[0]
            inn_b = row_b.get("inn") or row_b.get("product_name", "").split()[0]

            match = assess_identity(
                inn_a, inn_b,
                row_a.get("dosage_form", ""), row_b.get("dosage_form", ""),
                row_a.get("route_of_administration"),
                row_b.get("route_of_administration"),
                s_a, s_b, p_a, p_b,
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

            same_currency = row_a["price_currency"] == row_b["price_currency"]
            price_ratio = (
                derived_a.price_per_strength_unit / derived_b.price_per_strength_unit
                if same_currency and derived_b.price_per_strength_unit != 0
                else None
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

            cid_seed = (
                f"{ra['id']}|{rb['id']}|{pa.id}|{pb.id}|{prfa.id}|{prfb.id}"
            )
            candidate = ComparisonCandidate(
                id=_stable_id(cid_seed),
                molecule_inn=str(inn_a).strip().lower(),
                atc_code=str(ra.get("atc_code") or rb.get("atc_code") or ""),
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
                price_ratio=price_ratio,
                normalisation_notes=(
                    f"per_unit + per_strength_unit on both sides; "
                    f"price_ratio currency-matched={same_currency}"
                ),
                caveats=([match.reason] if match.reason else []),
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
                },
                "comparison_category": pa.comparison_category.value,
                "identity_confidence": (
                    match.confidence.value if match.confidence else None
                ),
                "price_ratio": str(price_ratio) if price_ratio is not None else None,
            }

            result.candidates.append(CandidatePackage(
                candidate=candidate,
                derivation_rules=[
                    derA.rule_per_unit, derA.rule_per_strength_unit,
                    derB.rule_per_unit, derB.rule_per_strength_unit,
                ],
                identity_match=match,
                evidence_bundle=evidence_bundle,
            ))

    return result


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
