"""Audit trail walker.

Resolves the full evidence chain for a comparison candidate, in order:
candidate -> review -> derivation rule -> profile -> policy ->
canonical -> raw -> source document. For each link, returns either
the resolved artifact or a broken-link indicator.

Read-only — never modifies any artifact.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class Link:
    label: str
    artifact_id: str | None
    found: bool
    payload: dict[str, Any] | None = None
    note: str | None = None


@dataclass
class AuditTrail:
    candidate_id: str
    snapshot_window: str
    links: list[Link] = field(default_factory=list)

    @property
    def all_resolved(self) -> bool:
        return all(l.found for l in self.links)

    @property
    def broken_links(self) -> list[Link]:
        return [l for l in self.links if not l.found]


def _read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [
        json.loads(line)
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_candidates(repo_root: Path, window: str) -> pd.DataFrame:
    p = repo_root / "data" / "comparisons" / window / "candidates.parquet"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def _load_canonical_for_country(repo_root: Path, cc: str, snap: str) -> pd.DataFrame:
    p = (
        repo_root / "data" / "canonical" / cc.lower() / snap / "prices.parquet"
    )
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def _load_raw_for_country(repo_root: Path, cc: str, snap: str) -> pd.DataFrame:
    p = repo_root / "data" / "canonical" / cc.lower() / snap / "raw.parquet"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def _load_register_entry(repo_root: Path, source_id: str) -> dict | None:
    register_path = repo_root / "data" / "sources" / "register.json"
    if not register_path.exists():
        return None
    entries = json.loads(register_path.read_text(encoding="utf-8"))
    for e in entries:
        if e["source_id"] == source_id:
            return e
    return None


def _find_manifest(
    repo_root: Path, source_id: str, snap: str,
) -> tuple[Path | None, dict | None]:
    """Search test fixtures for a snapshot whose manifest references source_id."""
    fixtures = repo_root / "tests" / "fixtures" / "sources"
    if not fixtures.exists():
        return None, None
    for cdir in fixtures.iterdir():
        if not cdir.is_dir():
            continue
        candidate = cdir / snap / "manifest.json"
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if data.get("source_id") == source_id:
                return candidate.parent, data
    return None, None


def build_audit_trail(
    repo_root: Path, snapshot_window: str, candidate_id: str,
) -> AuditTrail:
    trail = AuditTrail(candidate_id=candidate_id, snapshot_window=snapshot_window)
    cands = _load_candidates(repo_root, snapshot_window)
    match = cands[cands["id"] == candidate_id] if not cands.empty else cands
    if match.empty:
        trail.links.append(Link("comparisonCandidate", candidate_id, False,
                                note="candidate not found"))
        return trail
    cand = match.iloc[0].to_dict()
    trail.links.append(Link("comparisonCandidate", candidate_id, True, cand))

    # Review assessment
    assessments = _read_jsonl(
        repo_root / "data" / "review" / snapshot_window / "review_assessments.jsonl"
    )
    review = next(
        (a for a in assessments if a["comparison_candidate_id"] == candidate_id), None
    )
    trail.links.append(Link(
        "reviewAssessment",
        review["id"] if review else None,
        review is not None,
        review,
        note=None if review else "no review assessment for candidate",
    ))

    # Per-side chain
    for side, prefix in [("a", "country_a"), ("b", "country_b")]:
        cc = cand[f"country_{side}_code"]
        snap = str(cand["snapshot_date"])
        canonical_id = cand[f"country_{side}_record_id"]
        policy_id = cand[f"country_{side}_policy_id"]
        profile_id = cand[f"country_{side}_profile_id"]
        rule_id = cand.get(f"derivation_rule_{side}_id")

        # Derivation rule
        rules = _read_jsonl(
            repo_root / "data" / "comparisons" / snapshot_window
            / "derivation_rules.jsonl"
        )
        rule = next((r for r in rules if r["id"] == rule_id), None) if rule_id else None
        trail.links.append(Link(
            f"derivationRule.{side}",
            rule_id,
            rule is not None,
            rule,
            note=None if rule else "rule absent",
        ))

        # Data profile
        profile_payload = None
        profile_path = (
            repo_root / "data" / "profiles" / cc.lower() / snap / "data_profile.json"
        )
        if profile_path.exists():
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            profile_payload = next(
                (p for p in payload["profiles"] if p["id"] == profile_id), None
            )
        trail.links.append(Link(
            f"dataProfile.{side}",
            profile_id,
            profile_payload is not None,
            profile_payload,
            note=None if profile_payload else "profile absent",
        ))

        # Policy interpretation
        policy_path = (
            repo_root / "data" / "policy" / cc.lower()
            / "policy_interpretations.jsonl"
        )
        policies = _read_jsonl(policy_path)
        policy = next((p for p in policies if p["id"] == policy_id), None)
        trail.links.append(Link(
            f"policyInterpretation.{side}",
            policy_id,
            policy is not None,
            policy,
            note=None if policy else "policy absent",
        ))

        # Canonical record
        canonical_df = _load_canonical_for_country(repo_root, cc, snap)
        canonical = None
        if not canonical_df.empty:
            mc = canonical_df[canonical_df["id"] == canonical_id]
            if not mc.empty:
                canonical = {k: str(v) for k, v in mc.iloc[0].to_dict().items()}
        trail.links.append(Link(
            f"canonicalRecord.{side}",
            canonical_id,
            canonical is not None,
            canonical,
            note=None if canonical else "canonical absent",
        ))

        # Raw record
        raw_df = _load_raw_for_country(repo_root, cc, snap)
        raw_record = None
        raw_id = canonical.get("raw_record_id") if canonical else None
        if not raw_df.empty and raw_id:
            mr = raw_df[raw_df["id"] == raw_id]
            if not mr.empty:
                raw_record = {k: str(v) for k, v in mr.iloc[0].to_dict().items()}
        trail.links.append(Link(
            f"rawRecord.{side}",
            raw_id,
            raw_record is not None,
            raw_record,
            note=None if raw_record else "raw absent",
        ))

        # Source document (manifest + register entry)
        source_doc_id = canonical.get("source_document_id") if canonical else None
        snap_dir, manifest = (None, None)
        register_entry = None
        manifest_resolved = False
        if source_doc_id:
            register_entry = _load_register_entry(repo_root, source_doc_id)
            # snapshot_id is the manifest snapshot_id, which our delegate emits
            # as source_document_id; locate by walking fixtures
            fixtures = repo_root / "tests" / "fixtures" / "sources" / cc.lower() / snap
            mp = fixtures / "manifest.json"
            if mp.exists():
                m = json.loads(mp.read_text(encoding="utf-8"))
                if m.get("snapshot_id") == source_doc_id:
                    manifest = m
                    snap_dir = fixtures
                    manifest_resolved = True
        trail.links.append(Link(
            f"sourceDocument.{side}",
            source_doc_id,
            manifest_resolved,
            {"manifest": manifest, "register_entry": register_entry},
            note=None if manifest_resolved else "manifest not located",
        ))

        # Verify file hash if manifest resolved
        if snap_dir and manifest:
            for fentry in manifest["files"]:
                fp = snap_dir / fentry["filename"]
                ok = False
                if fp.exists():
                    actual = "sha256:" + hashlib.sha256(fp.read_bytes()).hexdigest()
                    ok = actual == fentry["file_hash"]
                trail.links.append(Link(
                    f"fileHashVerification.{side}.{fentry['filename']}",
                    fentry["file_hash"],
                    ok,
                    {"filename": fentry["filename"], "expected": fentry["file_hash"]},
                    note=None if ok else "hash mismatch",
                ))

    return trail
