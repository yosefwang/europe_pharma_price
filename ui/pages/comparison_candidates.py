"""Comparison Candidates page for the Research Audit Workbench.

Shows candidate proposals with the full evidence chain: source documents,
raw records, canonical records, policy interpretations, data profiles,
and derivation rules — all six links visible per side, plus the
candidate ID itself. Untranslatable IDs are shown as code.
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

COMPARISONS_ROOT = REPO_ROOT / "data" / "comparisons"
REPORTS_ROOT = REPO_ROOT / "reports" / "comparisons"


def _list_windows() -> list[str]:
    if not COMPARISONS_ROOT.exists():
        return []
    return sorted(
        d.name for d in COMPARISONS_ROOT.iterdir()
        if d.is_dir() and (d / "candidates.parquet").exists()
    )


@st.cache_data
def _load_candidates(window: str) -> pd.DataFrame:
    p = COMPARISONS_ROOT / window / "candidates.parquet"
    return pd.read_parquet(p)


@st.cache_data
def _load_evidence_bundle(window: str) -> dict[str, dict]:
    p = COMPARISONS_ROOT / window / "evidence_bundle.jsonl"
    out: dict[str, dict] = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        bundle = json.loads(line)
        out[bundle["candidate_id"]] = bundle
    return out


@st.cache_data
def _load_derivation_rules(window: str) -> dict[str, dict]:
    p = COMPARISONS_ROOT / window / "derivation_rules.jsonl"
    out: dict[str, dict] = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rule = json.loads(line)
        out[rule["id"]] = rule
    return out


def _confidence_badge(level: str) -> str:
    return {"exact": "🟢", "high": "🟢", "medium": "🟡", "low": "🟠"}.get(level, "⚪")


def _render_window_picker():
    if "cand_window" not in st.session_state:
        st.session_state.cand_window = None
    if "cand_selected" not in st.session_state:
        st.session_state.cand_selected = None

    windows = _list_windows()
    if not windows:
        st.info(t("candidates.noWindows"))
        return None
    if st.session_state.cand_window not in windows:
        st.session_state.cand_window = windows[-1]

    cols = st.columns(min(len(windows), 4))
    for i, w in enumerate(windows):
        with cols[i % len(cols)]:
            if st.button(
                w, key=f"cand_w_{w}",
                use_container_width=True,
                type="primary" if st.session_state.cand_window == w else "secondary",
            ):
                st.session_state.cand_window = w
                st.session_state.cand_selected = None
                st.rerun()
    return st.session_state.cand_window


def _render_candidate_table(df: pd.DataFrame):
    if df.empty:
        st.info(t("candidates.noCandidates"))
        return None

    show = df[[
        "molecule_inn", "strength", "dosage_form",
        "country_a_code", "country_b_code",
        "comparison_category", "price_ratio", "identity_confidence",
    ]].copy()
    show.columns = [
        t("candidates.molecule"), t("candidates.strength"), t("candidates.form"),
        "A", "B",
        t("candidates.category"),
        t("candidates.priceRatio"),
        t("candidates.identityConfidence"),
    ]
    st.dataframe(show, use_container_width=True, hide_index=True)

    options = [
        f"{r['molecule_inn']} {r['strength']} {r['dosage_form']} "
        f"({r['country_a_code']} vs {r['country_b_code']})"
        for _, r in df.iterrows()
    ]
    pick = st.selectbox(
        t("candidates.selectCandidate"),
        options=range(len(options)),
        format_func=lambda i: options[i],
        key=f"cand_pick_{st.session_state.cand_window}",
    )
    if pick is not None:
        st.session_state.cand_selected = df.iloc[pick]["id"]


def _render_side(label: str, side: dict, rules: dict[str, dict]):
    st.markdown(f"### {label}: `{side['country_code']}`")
    st.markdown(
        f"`{side['price_amount']}` {side['price_currency']} "
        f"(`{side['price_type']}`)"
    )
    st.markdown(
        f"**{t('candidates.pricePerStrength')}**: "
        f"`{side['price_per_strength_unit']}` "
        f"{side['price_currency']}/strength_unit"
    )
    st.markdown(f"**{t('candidates.evidenceChain')}**")
    chain = [
        ("sourceDocument", side["source_document_id"]),
        ("rawRecord", side["raw_record_id"]),
        ("canonicalRecord", side["canonical_record_id"]),
        ("policyInterpretation", side["policy_interpretation_id"]),
        ("dataProfile", side["data_profile_id"]),
        ("derivationRule", side["derivation_rule_id"]),
    ]
    for label_key, value in chain:
        st.markdown(f"- **{t(f'candidates.links.{label_key}')}**")
        st.code(value)

    rule = rules.get(side["derivation_rule_id"])
    if rule:
        rt_label = t(f"candidates.ruleType.{rule['rule_type']}")
        st.caption(f"{rt_label}: `{rule['formula']}`")


def _render_candidate_detail(
    cand_row: pd.Series, bundle: dict, rules: dict[str, dict]
):
    st.subheader(
        f"{cand_row['molecule_inn']} · {cand_row['strength']} · {cand_row['dosage_form']}"
    )
    st.warning(t("candidates.candidateNotFinal"))

    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"**{t('candidates.category')}**: "
                    f"`{cand_row['comparison_category']}`")
        ratio = cand_row.get("price_ratio")
        if ratio is None or pd.isna(ratio):
            st.markdown(f"**{t('candidates.priceRatio')}**: "
                        f"_{t('candidates.ratioNullCurrencyMismatch')}_")
        else:
            st.markdown(f"**{t('candidates.priceRatio')}**: `{float(ratio):.4f}`")
    with cols[1]:
        conf = cand_row.get("identity_confidence")
        if conf:
            badge = _confidence_badge(conf)
            label = t(f"candidates.confidence.{conf}")
            st.markdown(f"**{t('candidates.identityConfidence')}**: {badge} {label}")
        if cand_row.get("caveats") is not None:
            cv = cand_row["caveats"]
            if isinstance(cv, list) and cv:
                for c in cv:
                    if c:
                        st.warning(c)

    st.markdown("---")
    sides = st.columns(2)
    with sides[0]:
        _render_side(t("candidates.sideA"), bundle["country_a"], rules)
    with sides[1]:
        _render_side(t("candidates.sideB"), bundle["country_b"], rules)


def _render_provenance(cand_row: pd.Series | None):
    st.subheader(t("ui.provenance"))
    if cand_row is None:
        st.info(t("candidates.selectCandidate"))
        return
    st.markdown(f"**{t('candidates.links.comparisonCandidate')}**")
    st.code(cand_row["id"])
    st.markdown(f"**created_at**")
    st.code(str(cand_row.get("created_at")))
    st.markdown(f"**created_by**")
    st.code(str(cand_row.get("created_by")))


def render_comparison_candidates():
    st.header(t("candidates.title"))
    st.caption(t("candidates.subtitle"))

    main_col, prov_col = st.columns([3, 1])
    with main_col:
        window = _render_window_picker()
        if not window:
            return

        df = _load_candidates(window)
        bundles = _load_evidence_bundle(window)
        rules = _load_derivation_rules(window)

        st.markdown(f"**{t('candidates.candidatesIn')} `{window}`**: {len(df)}")
        _render_candidate_table(df)

        sel_id = st.session_state.cand_selected
        if sel_id and sel_id in bundles:
            cand_row = df[df["id"] == sel_id].iloc[0]
            st.markdown("---")
            _render_candidate_detail(cand_row, bundles[sel_id], rules)

        rep_path = REPORTS_ROOT / window / "candidate-summary.md"
        if rep_path.exists():
            with st.expander(t("candidates.skipped")):
                st.markdown(rep_path.read_text(encoding="utf-8"))

    with prov_col:
        sel_id = st.session_state.get("cand_selected")
        cand_row = None
        if sel_id and st.session_state.get("cand_window"):
            df = _load_candidates(st.session_state.cand_window)
            match = df[df["id"] == sel_id]
            if not match.empty:
                cand_row = match.iloc[0]
        _render_provenance(cand_row)
