"""Comparison report generator.

Produces markdown reports per the [report-generation.md](docs/specs/report-generation.md)
spec. Pulls every figure from the underlying artifacts so the report is a
view, not a snapshot — re-running with the same inputs produces identical
output (modulo the generation timestamp).

Translatable chrome is rendered in the requested locale; source citations,
IDs, and original-language text are passed through verbatim.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..audit import build_audit_trail
from ..policy.gating import load_interpretations


def _repo_root_default() -> Path:
    return Path(__file__).resolve().parents[3]


_CHROME = {
    "en": {
        "title_prefix": "Comparison report",
        "snapshot_window": "Snapshot window",
        "generated": "Generated",
        "candidate_id": "Candidate ID",
        "usability": "Usability",
        "summary": "Summary",
        "headline_figures": "Headline figures",
        "why_compatible": "Why these fields are compatible",
        "caveats": "Caveats",
        "evidence_chain": "Evidence chain",
        "review_assessment": "Review assessment",
        "country_a_side": "Country A side",
        "country_b_side": "Country B side",
        "per_pack": "per pack of",
        "per_strength_unit": "per strength unit",
        "price_ratio": "Price ratio (A / B)",
        "ratio_null": "Ratio not computed (currencies differ)",
        "blocking_issues": "Blocking issues",
        "rationale": "Rationale",
        "blocked_banner": (
            "**This candidate is not suitable for headline use.** Review "
            "marked it as not comparable. The evidence chain is preserved "
            "below for audit; do not cite the figures as a comparison."
        ),
        "exploratory_banner": (
            "**Exploratory only.** This candidate has the full evidence "
            "chain but currencies differ between countries — the price "
            "ratio is not computed and any cross-country claim requires "
            "an explicit currency-conversion derivation rule."
        ),
    },
    "zh-CN": {
        "title_prefix": "比较报告",
        "snapshot_window": "快照窗口",
        "generated": "生成时间",
        "candidate_id": "候选 ID",
        "usability": "可用性",
        "summary": "概要",
        "headline_figures": "头条数字",
        "why_compatible": "为何这些字段可比",
        "caveats": "注意事项",
        "evidence_chain": "证据链",
        "review_assessment": "审查评估",
        "country_a_side": "国家 A 侧",
        "country_b_side": "国家 B 侧",
        "per_pack": "每包",
        "per_strength_unit": "每规格单位",
        "price_ratio": "价格比 (A / B)",
        "ratio_null": "未计算比值（货币不同）",
        "blocking_issues": "阻断问题",
        "rationale": "理由",
        "blocked_banner": (
            "**该候选不适合作为头条结论使用。** 审查将其标记为 not comparable。"
            "下方证据链保留供审计；请勿将这些数字作为比较结论引用。"
        ),
        "exploratory_banner": (
            "**仅供探索。** 该候选具备完整证据链，但两国货币不同——"
            "未计算价格比；任何跨国主张需要明确的货币换算派生规则。"
        ),
    },
}


def _load_assessment(repo_root: Path, window: str, candidate_id: str) -> dict | None:
    p = repo_root / "data" / "review" / window / "review_assessments.jsonl"
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            a = json.loads(line)
            if a["comparison_candidate_id"] == candidate_id:
                return a
    return None


def _format_money(amount, currency: str) -> str:
    if amount is None:
        return "—"
    return f"{amount} {currency}"


def generate_report(
    window: str, candidate_id: str, locale: str = "en",
    repo_root: Path | None = None,
) -> str:
    repo_root = repo_root or _repo_root_default()
    chrome = _CHROME.get(locale, _CHROME["en"])

    cands = pd.read_parquet(
        repo_root / "data" / "comparisons" / window / "candidates.parquet"
    )
    match = cands[cands["id"] == candidate_id]
    if match.empty:
        return f"# Candidate {candidate_id} not found in window {window}\n"
    cand = match.iloc[0].to_dict()

    bundles_path = (
        repo_root / "data" / "comparisons" / window / "evidence_bundle.jsonl"
    )
    bundle = {}
    for line in bundles_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            b = json.loads(line)
            if b["candidate_id"] == candidate_id:
                bundle = b
                break
    a_side = bundle.get("country_a", {})
    b_side = bundle.get("country_b", {})

    review = _load_assessment(repo_root, window, candidate_id) or {}
    interps_a = load_interpretations(repo_root, cand["country_a_code"])
    interps_b = load_interpretations(repo_root, cand["country_b_code"])
    pol_a = next(
        (i for i in interps_a if i.id == cand["country_a_policy_id"]), None
    )
    pol_b = next(
        (i for i in interps_b if i.id == cand["country_b_policy_id"]), None
    )

    title = (
        f"# {chrome['title_prefix']} — {cand['molecule_inn']} — "
        f"{cand['country_a_code']} ↔ {cand['country_b_code']}"
    )
    lines = [
        title,
        "",
        f"**{chrome['snapshot_window']}:** `{window}`",
        f"**{chrome['generated']}:** `{datetime.now(timezone.utc).isoformat()}`",
        f"**{chrome['candidate_id']}:** `{candidate_id}`",
        f"**{chrome['usability']}:** `{review.get('usability', 'unreviewed')}`",
        "",
    ]

    usability = review.get("usability")
    if usability == "not_comparable":
        lines.extend([chrome["blocked_banner"], ""])
    elif usability == "exploratory":
        lines.extend([chrome["exploratory_banner"], ""])

    ratio = cand.get("price_ratio")
    if ratio is not None and pd.isna(ratio):
        ratio = None
    if ratio is not None:
        try:
            ratio_str = f"{float(ratio):.4f}"
        except (TypeError, ValueError):
            ratio_str = str(ratio)
    else:
        ratio_str = None
    summary_ratio = (
        f"price ratio {ratio_str}" if ratio_str is not None
        else chrome["ratio_null"]
    )
    summary_caveat = ""
    if review.get("caveats"):
        first = review["caveats"][0]
        summary_caveat = f" Strongest caveat: {first}"
    lines.extend([
        f"## {chrome['summary']}",
        "",
        f"Comparison of `{cand['molecule_inn']}` "
        f"`{cand['strength']}` `{cand['dosage_form']}` between "
        f"`{cand['country_a_code']}` and `{cand['country_b_code']}` under "
        f"category `{cand['comparison_category']}`: {summary_ratio}.{summary_caveat}",
        "",
    ])

    a_unit = a_side.get("price_per_strength_unit", "—")
    b_unit = b_side.get("price_per_strength_unit", "—")
    lines.extend([
        f"## {chrome['headline_figures']}",
        "",
        f"- **{chrome['country_a_side']} (`{cand['country_a_code']}`)**: "
        f"{_format_money(a_side.get('price_amount'), a_side.get('price_currency', ''))} "
        f"{chrome['per_pack']} {cand['strength']}; "
        f"{chrome['per_strength_unit']}: `{a_unit}` "
        f"{a_side.get('price_currency', '')}/strength_unit",
        f"- **{chrome['country_b_side']} (`{cand['country_b_code']}`)**: "
        f"{_format_money(b_side.get('price_amount'), b_side.get('price_currency', ''))} "
        f"{chrome['per_pack']} {cand['strength']}; "
        f"{chrome['per_strength_unit']}: `{b_unit}` "
        f"{b_side.get('price_currency', '')}/strength_unit",
        f"- **{chrome['price_ratio']}**: "
        f"{f'`{ratio_str}`' if ratio_str is not None else chrome['ratio_null']}",
        "",
    ])

    lines.extend([
        f"## {chrome['why_compatible']}",
        "",
        f"Both sides' policy interpretations map their national price field "
        f"to comparison category `{cand['comparison_category']}`.",
        "",
    ])
    if pol_a:
        lines.extend([
            f"**{cand['country_a_code']} ({pol_a.price_type})**: "
            f"{pol_a.interpretation_text}", "",
            "Sources:", "",
        ])
        for ref in pol_a.source_references:
            lines.append(f"- {ref}")
        lines.append("")
    if pol_b:
        lines.extend([
            f"**{cand['country_b_code']} ({pol_b.price_type})**: "
            f"{pol_b.interpretation_text}", "",
            "Sources:", "",
        ])
        for ref in pol_b.source_references:
            lines.append(f"- {ref}")
        lines.append("")

    if review.get("caveats"):
        lines.extend([f"## {chrome['caveats']}", ""])
        for c in review["caveats"]:
            lines.append(f"- {c}")
        lines.append("")

    if review.get("blocking_issues"):
        lines.extend([f"## {chrome['blocking_issues']}", ""])
        for b in review["blocking_issues"]:
            lines.append(f"- {b}")
        lines.append("")

    lines.extend([f"## {chrome['evidence_chain']}", ""])
    for label, side, prefix in [
        (chrome["country_a_side"], a_side, "a"),
        (chrome["country_b_side"], b_side, "b"),
    ]:
        lines.extend([f"### {label}", ""])
        chain = [
            ("source_document_id", side.get("source_document_id")),
            ("raw_record_id", side.get("raw_record_id")),
            ("canonical_record_id", side.get("canonical_record_id")),
            ("policy_interpretation_id", side.get("policy_interpretation_id")),
            ("data_profile_id", side.get("data_profile_id")),
            ("derivation_rule_id", side.get("derivation_rule_id")),
        ]
        for k, v in chain:
            lines.append(f"- `{k}`: `{v}`")
        lines.append("")

    if review:
        lines.extend([
            f"## {chrome['review_assessment']}", "",
            f"- policy_strength: `{review.get('policy_strength')}`",
            f"- data_strength: `{review.get('data_strength')}`",
            f"- identity_strength: `{review.get('identity_strength')}`",
            f"- normalisation_strength: `{review.get('normalisation_strength')}`",
            "",
            f"**{chrome['rationale']}**", "",
            review.get("rationale", "—"), "",
        ])

    return "\n".join(lines)


def write_report(
    window: str, candidate_id: str, locale: str = "en",
    repo_root: Path | None = None,
) -> Path:
    repo_root = repo_root or _repo_root_default()
    body = generate_report(window, candidate_id, locale, repo_root)
    out_dir = repo_root / "reports" / "comparisons" / window
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{candidate_id}-{locale}.md"
    out_path.write_text(body, encoding="utf-8")
    return out_path
