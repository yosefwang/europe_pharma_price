"""Read-only researcher-facing API over the substrate."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel

from ..audit import AuditTrail, build_audit_trail


def _repo_root_default() -> Path:
    return Path(__file__).resolve().parents[3]


class ComparisonRow(BaseModel):
    candidate_id: str
    country_a_code: str
    country_b_code: str
    comparison_category: str
    snapshot_date: str
    molecule_inn: str
    dosage_form: str
    strength: str
    price_a: Decimal
    currency_a: str
    price_b: Decimal
    currency_b: str
    price_per_strength_unit_a: Decimal | None
    price_per_strength_unit_b: Decimal | None
    price_ratio: Decimal | None
    identity_confidence: str | None
    usability: str
    caveats: list[str]


class CandidateBundle(BaseModel):
    candidate_id: str
    snapshot_window: str
    all_links_resolved: bool
    broken_link_count: int
    chain: list[dict[str, Any]]


class QueueEntry(BaseModel):
    candidate_id: str
    assessment_id: str
    usability: str
    blocking_issues: list[str]
    caveats: list[str]
    policy_strength: str
    data_strength: str
    identity_strength: str
    normalisation_strength: str


def available_windows(repo_root: Path | None = None) -> list[str]:
    repo_root = repo_root or _repo_root_default()
    base = repo_root / "data" / "comparisons"
    if not base.exists():
        return []
    return sorted(
        d.name for d in base.iterdir()
        if d.is_dir() and (d / "candidates.parquet").exists()
    )


def available_molecules(
    window: str, repo_root: Path | None = None,
) -> list[str]:
    repo_root = repo_root or _repo_root_default()
    df = _load_candidates(repo_root, window)
    if df.empty:
        return []
    return sorted(df["molecule_inn"].unique().tolist())


def _load_candidates(repo_root: Path, window: str) -> pd.DataFrame:
    p = repo_root / "data" / "comparisons" / window / "candidates.parquet"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def _load_evidence_bundles(repo_root: Path, window: str) -> dict[str, dict]:
    p = repo_root / "data" / "comparisons" / window / "evidence_bundle.jsonl"
    out: dict[str, dict] = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            b = json.loads(line)
            out[b["candidate_id"]] = b
    return out


def _load_assessments(repo_root: Path, window: str) -> dict[str, dict]:
    p = repo_root / "data" / "review" / window / "review_assessments.jsonl"
    out: dict[str, dict] = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            a = json.loads(line)
            out[a["comparison_candidate_id"]] = a
    return out


def candidates_for_molecule(
    window: str, molecule_inn: str, repo_root: Path | None = None,
) -> list[ComparisonRow]:
    repo_root = repo_root or _repo_root_default()
    df = _load_candidates(repo_root, window)
    if df.empty:
        return []
    needle = molecule_inn.strip().lower()
    matches = df[df["molecule_inn"].str.strip().str.lower() == needle]
    bundles = _load_evidence_bundles(repo_root, window)
    assessments = _load_assessments(repo_root, window)

    out: list[ComparisonRow] = []
    for _, row in matches.iterrows():
        cid = row["id"]
        bundle = bundles.get(cid, {})
        a_side = bundle.get("country_a", {})
        b_side = bundle.get("country_b", {})
        review = assessments.get(cid, {})
        ratio = row.get("price_ratio")
        if ratio is not None and pd.isna(ratio):
            ratio = None
        out.append(ComparisonRow(
            candidate_id=cid,
            country_a_code=row["country_a_code"],
            country_b_code=row["country_b_code"],
            comparison_category=row["comparison_category"],
            snapshot_date=str(row["snapshot_date"]),
            molecule_inn=row["molecule_inn"],
            dosage_form=row["dosage_form"],
            strength=row["strength"],
            price_a=Decimal(a_side.get("price_amount", "0") or "0"),
            currency_a=a_side.get("price_currency", ""),
            price_b=Decimal(b_side.get("price_amount", "0") or "0"),
            currency_b=b_side.get("price_currency", ""),
            price_per_strength_unit_a=(
                Decimal(a_side["price_per_strength_unit"])
                if a_side.get("price_per_strength_unit") else None
            ),
            price_per_strength_unit_b=(
                Decimal(b_side["price_per_strength_unit"])
                if b_side.get("price_per_strength_unit") else None
            ),
            price_ratio=Decimal(str(ratio)) if ratio is not None else None,
            identity_confidence=row.get("identity_confidence"),
            usability=review.get("usability", "unreviewed"),
            caveats=review.get("caveats", []),
        ))
    return out


def candidate_with_evidence(
    window: str, candidate_id: str, repo_root: Path | None = None,
) -> CandidateBundle:
    repo_root = repo_root or _repo_root_default()
    trail: AuditTrail = build_audit_trail(repo_root, window, candidate_id)
    chain = []
    for link in trail.links:
        chain.append({
            "label": link.label,
            "artifact_id": link.artifact_id,
            "found": link.found,
            "note": link.note,
        })
    return CandidateBundle(
        candidate_id=candidate_id,
        snapshot_window=window,
        all_links_resolved=trail.all_resolved,
        broken_link_count=len(trail.broken_links),
        chain=chain,
    )


def queue_for_window(
    window: str, repo_root: Path | None = None,
) -> list[QueueEntry]:
    repo_root = repo_root or _repo_root_default()
    p = repo_root / "data" / "review" / window / "queue.jsonl"
    if not p.exists():
        return []
    out: list[QueueEntry] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out.append(QueueEntry(**{
                k: d[k] for k in QueueEntry.model_fields if k in d
            }))
    return out
