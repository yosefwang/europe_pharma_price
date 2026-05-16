"""Review Queue page.

Lists assessments per snapshot window with filters by country pair,
molecule, usability, and weakness. Selecting an item shows full
strength tuple, blocking issues, caveats, and rationale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from i18n import t

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

REVIEW_ROOT = REPO_ROOT / "data" / "review"
COMPARISONS_ROOT = REPO_ROOT / "data" / "comparisons"


def _list_windows() -> list[str]:
    if not REVIEW_ROOT.exists():
        return []
    return sorted(
        d.name for d in REVIEW_ROOT.iterdir()
        if d.is_dir() and (d / "review_assessments.jsonl").exists()
    )


@st.cache_data
def _load_assessments(window: str) -> list[dict]:
    p = REVIEW_ROOT / window / "review_assessments.jsonl"
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


@st.cache_data
def _load_candidates(window: str) -> pd.DataFrame:
    p = COMPARISONS_ROOT / window / "candidates.parquet"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def _usability_badge(level: str) -> str:
    return {
        "usable": "🟢",
        "usable_with_caveat": "🟡",
        "exploratory": "🟠",
        "not_comparable": "🔴",
    }.get(level, "⚪")


def _strength_badge(level: str) -> str:
    return {
        "strong": "🟢",
        "adequate": "🟡",
        "weak": "🔴",
        "not_applicable": "⚪",
    }.get(level, "⚪")


def _render_window_picker():
    if "rev_window" not in st.session_state:
        st.session_state.rev_window = None
    if "rev_selected" not in st.session_state:
        st.session_state.rev_selected = None
    windows = _list_windows()
    if not windows:
        st.info(t("review.noWindows"))
        return None
    if st.session_state.rev_window not in windows:
        st.session_state.rev_window = windows[-1]
    cols = st.columns(min(len(windows), 4))
    for i, w in enumerate(windows):
        with cols[i % len(cols)]:
            if st.button(
                w, key=f"rev_w_{w}",
                use_container_width=True,
                type="primary" if st.session_state.rev_window == w else "secondary",
            ):
                st.session_state.rev_window = w
                st.session_state.rev_selected = None
                st.rerun()
    return st.session_state.rev_window


def _has_weak(a: dict) -> bool:
    return any(
        a[k] == "weak"
        for k in ("policy_strength", "data_strength", "identity_strength", "normalisation_strength")
    )


def _apply_filters(
    rows: list[dict], cands: pd.DataFrame,
    pair_filter: str, molecule_filter: str,
    usability_filter: str, weakness_filter: str,
) -> list[dict]:
    out = []
    cand_lookup = {r["id"]: r for _, r in cands.iterrows()} if not cands.empty else {}
    for a in rows:
        cand = cand_lookup.get(a["comparison_candidate_id"])
        pair = (
            f"{cand['country_a_code']}-{cand['country_b_code']}"
            if cand is not None else "?"
        )
        molecule = cand["molecule_inn"] if cand is not None else "?"
        if pair_filter != "__all__" and pair_filter != pair:
            continue
        if molecule_filter != "__all__" and molecule_filter != molecule:
            continue
        if usability_filter != "__all__" and usability_filter != a["usability"]:
            continue
        if weakness_filter == "__yes__" and not _has_weak(a):
            continue
        if weakness_filter == "__no__" and _has_weak(a):
            continue
        out.append(a)
    return out


def _render_filters(rows: list[dict], cands: pd.DataFrame):
    st.subheader(t("review.filters"))
    cand_by_id = {r["id"]: r for _, r in cands.iterrows()} if not cands.empty else {}
    pairs = sorted({
        f"{cand_by_id[a['comparison_candidate_id']]['country_a_code']}-"
        f"{cand_by_id[a['comparison_candidate_id']]['country_b_code']}"
        for a in rows if a["comparison_candidate_id"] in cand_by_id
    })
    molecules = sorted({
        cand_by_id[a["comparison_candidate_id"]]["molecule_inn"]
        for a in rows if a["comparison_candidate_id"] in cand_by_id
    })
    usabilities = ["usable", "usable_with_caveat", "exploratory", "not_comparable"]

    pair_choice = st.selectbox(
        t("review.filterByCountryPair"),
        options=["__all__"] + pairs,
        format_func=lambda x: t("review.all") if x == "__all__" else x,
        key="rev_filter_pair",
    )
    mol_choice = st.selectbox(
        t("review.filterByMolecule"),
        options=["__all__"] + molecules,
        format_func=lambda x: t("review.all") if x == "__all__" else x,
        key="rev_filter_molecule",
    )
    use_choice = st.selectbox(
        t("review.filterByUsability"),
        options=["__all__"] + usabilities,
        format_func=lambda x: (
            t("review.all") if x == "__all__"
            else t(f"review.usability.{x}")
        ),
        key="rev_filter_use",
    )
    weak_choice = st.selectbox(
        t("review.filterByWeakness"),
        options=["__all__", "__yes__", "__no__"],
        format_func=lambda x: {
            "__all__": t("review.all"),
            "__yes__": t("source.yes"),
            "__no__": t("source.no"),
        }[x],
        key="rev_filter_weak",
    )
    return pair_choice, mol_choice, use_choice, weak_choice


def _render_assessment_list(rows: list[dict], cands: pd.DataFrame):
    if not rows:
        st.info(t("review.noAssessments"))
        return None

    cand_by_id = {r["id"]: r for _, r in cands.iterrows()} if not cands.empty else {}
    if (
        st.session_state.rev_selected is None
        or st.session_state.rev_selected not in {a["id"] for a in rows}
    ):
        st.session_state.rev_selected = rows[0]["id"]

    for a in rows:
        cand = cand_by_id.get(a["comparison_candidate_id"])
        badge = _usability_badge(a["usability"])
        usable_label = t(f"review.usability.{a['usability']}")
        weak_indicator = "⚠️" if _has_weak(a) else ""
        if cand is not None:
            label = (
                f"{badge} {weak_indicator} {cand['molecule_inn']} "
                f"({cand['country_a_code']}–{cand['country_b_code']}) "
                f"— {usable_label}"
            )
        else:
            label = f"{badge} {weak_indicator} {a['id'][:8]}… — {usable_label}"
        if st.button(
            label, key=f"rev_pick_{a['id']}",
            use_container_width=True,
            type="primary" if st.session_state.rev_selected == a["id"] else "secondary",
        ):
            st.session_state.rev_selected = a["id"]
            st.rerun()
    return st.session_state.rev_selected


def _render_assessment_detail(a: dict, cand: pd.Series | None):
    badge = _usability_badge(a["usability"])
    usable_label = t(f"review.usability.{a['usability']}")
    st.subheader(f"{badge} {usable_label}")

    if cand is not None:
        st.markdown(
            f"**{cand['molecule_inn']}** {cand['strength']} {cand['dosage_form']} "
            f"— `{cand['country_a_code']}` vs `{cand['country_b_code']}`"
        )

    st.markdown(f"**{t('review.strengths')}**")
    cols = st.columns(4)
    dims = [
        ("policyStrength", a["policy_strength"]),
        ("dataStrength", a["data_strength"]),
        ("identityStrength", a["identity_strength"]),
        ("normalisationStrength", a["normalisation_strength"]),
    ]
    for col, (key, level) in zip(cols, dims):
        with col:
            badge = _strength_badge(level)
            label = t(f"review.{key}")
            level_label = t(f"review.strength.{level}")
            st.markdown(f"{badge} **{label}**")
            st.caption(level_label)

    if a["blocking_issues"]:
        st.markdown(f"**{t('review.blockingIssues')}**")
        for b in a["blocking_issues"]:
            st.error(b)

    if a["caveats"]:
        st.markdown(f"**{t('review.caveats')}**")
        for c in a["caveats"]:
            st.warning(c)

    st.markdown(f"**{t('review.rationale')}**")
    st.code(a["rationale"], language=None)

    if a.get("human_override"):
        st.info(f"**{t('review.humanOverride')}**: "
                f"{a.get('override_rationale', '—')}")
    if a.get("superseded_by"):
        st.caption(f"{t('review.supersededBy')}: `{a['superseded_by']}`")


def render_review_queue():
    st.header(t("review.title"))
    st.caption(t("review.subtitle"))

    main_col, prov_col = st.columns([3, 1])
    with main_col:
        window = _render_window_picker()
        if not window:
            return
        rows = _load_assessments(window)
        cands = _load_candidates(window)

        filter_col, list_col, detail_col = st.columns([1, 2, 3])
        with filter_col:
            pair_f, mol_f, use_f, weak_f = _render_filters(rows, cands)
        filtered = _apply_filters(rows, cands, pair_f, mol_f, use_f, weak_f)
        with list_col:
            sel = _render_assessment_list(filtered, cands)
        with detail_col:
            if sel:
                a = next((x for x in rows if x["id"] == sel), None)
                if a:
                    cand = None
                    if not cands.empty:
                        match = cands[cands["id"] == a["comparison_candidate_id"]]
                        if not match.empty:
                            cand = match.iloc[0]
                    _render_assessment_detail(a, cand)

        rep = REPO_ROOT / "reports" / "review" / f"{window}.md"
        if rep.exists():
            with st.expander(t("review.summary")):
                st.markdown(rep.read_text(encoding="utf-8"))

    with prov_col:
        st.subheader(t("ui.provenance"))
        sel = st.session_state.get("rev_selected")
        if sel:
            rows = _load_assessments(st.session_state.rev_window)
            a = next((x for x in rows if x["id"] == sel), None)
            if a:
                st.markdown(f"**review_id**")
                st.code(a["id"])
                st.markdown(f"**candidate_id**")
                st.code(a["comparison_candidate_id"])
                st.markdown(f"**reviewed_at**")
                st.code(a["reviewed_at"])
                st.markdown(f"**reviewed_by**")
                st.code(a["reviewed_by"])
