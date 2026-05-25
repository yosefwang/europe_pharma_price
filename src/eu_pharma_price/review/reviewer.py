"""Automated reviewer for comparison candidates.

Maps candidate evidence to a usability label using deterministic rules.
Caveats from upstream artifacts (policy interpretation, identity match,
normalisation) are concatenated into the assessment so they travel
with every downstream consumer.

This module never modifies upstream artifacts; it only emits new
ReviewAssessment records.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from ..policy.gating import load_interpretations
from ..schemas.comparison import IdentityConfidence
from ..schemas.review import (
    ReviewAssessment,
    Strength,
    Usability,
)

REVIEW_REPORT_ITEM_LIMIT = 100


def _stable_id(seed: str) -> str:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return str(uuid.UUID(h[:32]))


def _policy_strength(conf_a: str, conf_b: str) -> Strength:
    if conf_a == "high" and conf_b == "high":
        return Strength.strong
    if "low" in (conf_a, conf_b):
        return Strength.weak
    return Strength.adequate


def _data_strength(plaus_a: str, plaus_b: str) -> Strength:
    if plaus_a == "plausible" and plaus_b == "plausible":
        return Strength.strong
    if "implausible" in (plaus_a, plaus_b):
        return Strength.weak
    return Strength.adequate


def _identity_strength(conf: str | None) -> Strength:
    if conf == "exact":
        return Strength.strong
    if conf == "high":
        return Strength.adequate
    return Strength.weak


def _normalisation_strength(
    has_rule_a: bool, has_rule_b: bool, price_ratio: object | None,
) -> Strength:
    if not has_rule_a or not has_rule_b:
        return Strength.weak
    if price_ratio is None:
        return Strength.adequate
    return Strength.strong


def _final_usability(
    pol: Strength, dat: Strength, idn: Strength, norm: Strength,
    price_ratio: object | None, identity_conf: str | None,
) -> tuple[Usability, list[str]]:
    blocking: list[str] = []

    if dat == Strength.weak:
        blocking.append("data_strength=weak: at least one side has implausible profile")
    if idn == Strength.weak:
        blocking.append(
            f"identity_strength=weak: identity_confidence={identity_conf}"
        )
    if norm == Strength.weak:
        blocking.append("normalisation_strength=weak: per-unit derivation incomplete")

    if blocking:
        return Usability.not_comparable, blocking

    if price_ratio is None:
        return (
            Usability.exploratory,
            [],
        )

    strengths = (pol, dat, idn, norm)
    has_adequate = Strength.adequate in strengths
    if has_adequate:
        return Usability.usable_with_caveat, []
    return Usability.usable, []


def assess_candidate(
    candidate_row: pd.Series,
    policy_a_confidence: str,
    policy_b_confidence: str,
    profile_a_plausibility: str,
    profile_b_plausibility: str,
    policy_caveats_a: list[str],
    policy_caveats_b: list[str],
    repo_root: Path,
) -> ReviewAssessment:
    pol = _policy_strength(policy_a_confidence, policy_b_confidence)
    dat = _data_strength(profile_a_plausibility, profile_b_plausibility)
    idn = _identity_strength(
        candidate_row.get("identity_confidence")
    )
    has_rule_a = bool(candidate_row.get("derivation_rule_a_id"))
    has_rule_b = bool(candidate_row.get("derivation_rule_b_id"))
    price_ratio = candidate_row.get("price_ratio")
    if price_ratio is not None and pd.isna(price_ratio):
        price_ratio = None
    norm = _normalisation_strength(has_rule_a, has_rule_b, price_ratio)

    usability, blocking = _final_usability(
        pol, dat, idn, norm, price_ratio,
        candidate_row.get("identity_confidence"),
    )

    caveats: list[str] = []
    caveats.extend(c for c in policy_caveats_a if c)
    caveats.extend(c for c in policy_caveats_b if c)
    candidate_caveats = candidate_row.get("caveats")
    if isinstance(candidate_caveats, list):
        caveats.extend(c for c in candidate_caveats if c)
    if usability == Usability.exploratory and price_ratio is None:
        caveats.append("price_ratio not computed: currencies differ across countries")
    if usability == Usability.usable_with_caveat and not caveats:
        caveats.append("at least one strength dimension was adequate rather than strong")

    rationale = (
        f"policy_strength={pol.value}, data_strength={dat.value}, "
        f"identity_strength={idn.value}, normalisation_strength={norm.value}; "
        f"price_ratio={'null' if price_ratio is None else price_ratio}"
    )

    seed = f"review:{candidate_row['id']}:phase-7-auto"
    return ReviewAssessment(
        id=_stable_id(seed),
        comparison_candidate_id=candidate_row["id"],
        usability=usability,
        policy_strength=pol,
        data_strength=dat,
        identity_strength=idn,
        normalisation_strength=norm,
        rationale=rationale,
        reviewed_at=datetime.now(timezone.utc),
        reviewed_by="phase-7-auto-reviewer",
        caveats=caveats,
        blocking_issues=blocking,
        recommendations=[],
        human_override=False,
    )


def _resolve_policy_confidence_and_caveats(
    repo_root: Path, country_code: str, policy_id: str,
) -> tuple[str, list[str]]:
    interps = load_interpretations(repo_root, country_code)
    for i in interps:
        if i.id == policy_id:
            return i.confidence.value, list(i.caveats)
    return "low", []


def _resolve_profile_plausibility(
    repo_root: Path, country_code: str, snapshot_date: str, profile_id: str,
) -> str:
    requested_profile_path = (
        repo_root / "data" / "profiles" / country_code.lower()
        / snapshot_date / "data_profile.json"
    )
    candidate_paths = []
    if requested_profile_path.exists():
        candidate_paths.append(requested_profile_path)

    country_profile_dir = repo_root / "data" / "profiles" / country_code.lower()
    if country_profile_dir.exists():
        for path in sorted(country_profile_dir.glob("*/data_profile.json"), reverse=True):
            if path not in candidate_paths:
                candidate_paths.append(path)

    for path in candidate_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for entry in payload["profiles"]:
            if entry["id"] == profile_id:
                return entry["plausibility_assessment"]
    return "implausible"


def review_candidates(
    repo_root: Path, snapshot_window_id: str,
) -> list[ReviewAssessment]:
    candidates_path = (
        repo_root / "data" / "comparisons" / snapshot_window_id
        / "candidates.parquet"
    )
    if not candidates_path.exists():
        return []
    df = pd.read_parquet(candidates_path)

    out: list[ReviewAssessment] = []
    for _, row in df.iterrows():
        snap = str(row["snapshot_date"])
        conf_a, caveats_a = _resolve_policy_confidence_and_caveats(
            repo_root, row["country_a_code"], row["country_a_policy_id"],
        )
        conf_b, caveats_b = _resolve_policy_confidence_and_caveats(
            repo_root, row["country_b_code"], row["country_b_policy_id"],
        )
        plaus_a = _resolve_profile_plausibility(
            repo_root, row["country_a_code"], snap, row["country_a_profile_id"],
        )
        plaus_b = _resolve_profile_plausibility(
            repo_root, row["country_b_code"], snap, row["country_b_profile_id"],
        )
        out.append(assess_candidate(
            row, conf_a, conf_b, plaus_a, plaus_b,
            caveats_a, caveats_b, repo_root,
        ))
    return out


def write_review_artifacts(
    repo_root: Path, snapshot_window_id: str,
    assessments: Iterable[ReviewAssessment],
) -> dict[str, Path]:
    out_dir = repo_root / "data" / "review" / snapshot_window_id
    out_dir.mkdir(parents=True, exist_ok=True)
    rep_dir = repo_root / "reports" / "review"
    rep_dir.mkdir(parents=True, exist_ok=True)

    assessments = list(assessments)
    assess_path = out_dir / "review_assessments.jsonl"
    with assess_path.open("w", encoding="utf-8") as fh:
        for a in assessments:
            fh.write(a.model_dump_json() + "\n")

    queue_path = out_dir / "queue.jsonl"
    with queue_path.open("w", encoding="utf-8") as fh:
        for a in assessments:
            if a.usability == Usability.usable:
                continue
            fh.write(json.dumps({
                "candidate_id": a.comparison_candidate_id,
                "assessment_id": a.id,
                "usability": a.usability.value,
                "blocking_issues": a.blocking_issues,
                "caveats": a.caveats,
                "policy_strength": a.policy_strength.value,
                "data_strength": a.data_strength.value,
                "identity_strength": a.identity_strength.value,
                "normalisation_strength": a.normalisation_strength.value,
                "queue_status": (
                    "ready_for_human"
                    if a.usability != Usability.usable_with_caveat
                    else "ready_with_caveats"
                ),
            }) + "\n")

    rep_path = rep_dir / f"{snapshot_window_id}.md"
    rep_path.write_text(
        "\n".join(_render_review_report_lines(snapshot_window_id, assessments)),
        encoding="utf-8",
    )

    return {
        "assessments": assess_path,
        "queue": queue_path,
        "report": rep_path,
    }


def _render_review_report_lines(
    snapshot_window_id: str,
    assessments: list[ReviewAssessment],
    item_limit: int = REVIEW_REPORT_ITEM_LIMIT,
) -> list[str]:
    counts = {u.value: 0 for u in Usability}
    for a in assessments:
        counts[a.usability.value] += 1
    lines = [
        f"# Review summary — `{snapshot_window_id}`", "",
        f"**Total candidates reviewed:** {len(assessments)}", "",
        "## Usability counts", "",
    ]
    for label, count in counts.items():
        lines.append(f"- `{label}`: {count}")
    if assessments:
        shown = assessments[:item_limit]
        lines.extend([
            "",
            "## Items",
            "",
            f"**Items shown:** {len(shown)} of {len(assessments)}",
            "",
        ])
        for a in shown:
            lines.append(
                f"- `{a.id[:8]}…` candidate `{a.comparison_candidate_id[:8]}…` "
                f"→ **{a.usability.value}** "
                f"(pol={a.policy_strength.value}, "
                f"dat={a.data_strength.value}, "
                f"idn={a.identity_strength.value}, "
                f"norm={a.normalisation_strength.value})"
            )
            if a.blocking_issues:
                for b in a.blocking_issues:
                    lines.append(f"    - blocker: {b}")
            for c in a.caveats:
                lines.append(f"    - caveat: {c}")
        omitted = len(assessments) - len(shown)
        if omitted > 0:
            lines.append(
                f"- ... {omitted} additional assessments omitted from this summary."
            )
    return lines
