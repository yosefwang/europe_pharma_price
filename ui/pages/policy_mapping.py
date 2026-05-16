"""Policy Mapping page for the Research Audit Workbench.

Displays per-country policy interpretations: which national price field
maps to which entry in the shared comparison vocabulary, with citations,
effective date window, confidence, caveats, and adjudication state.

Source citations and IDs render in their original form regardless of UI
language. Only the explanatory chrome around them is localised.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from i18n import t

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from eu_pharma_price.policy.gating import (  # noqa: E402
    blocks_comparison,
    load_interpretations,
)

INCLUDED_COUNTRIES = [("ie", "IE"), ("pl", "PL"), ("fr", "FR")]


def _confidence_badge(level: str) -> str:
    return {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(level, "⚪")


def _comparability_label(interp) -> tuple[str, str]:
    blocked, _ = blocks_comparison(interp)
    if blocked:
        return ("🔴", t("policy.notComparable"))
    if interp.confidence.value == "low":
        return ("🟡", t("policy.needsReview"))
    return ("🟢", t("policy.comparable"))


def _render_country_picker():
    st.subheader(t("country.selectCountry"))
    if "policy_country" not in st.session_state:
        st.session_state.policy_country = INCLUDED_COUNTRIES[0][0]
    if "policy_selected_id" not in st.session_state:
        st.session_state.policy_selected_id = None

    name_map = {"ie": "ireland", "pl": "poland", "fr": "france"}
    for cdir, label in INCLUDED_COUNTRIES:
        country_label = t(f"country.{name_map[cdir]}")
        if st.button(
            f"{label} — {country_label}",
            key=f"policy_country_{cdir}",
            use_container_width=True,
            type="primary" if st.session_state.policy_country == cdir else "secondary",
        ):
            st.session_state.policy_country = cdir
            st.session_state.policy_selected_id = None
            st.rerun()
    return st.session_state.policy_country


def _render_interpretation_list(interpretations):
    if not interpretations:
        st.info(t("policy.noInterpretations"))
        return None

    if st.session_state.policy_selected_id is None:
        st.session_state.policy_selected_id = interpretations[0].id

    for interp in interpretations:
        badge, _ = _comparability_label(interp)
        cat_label = t(f"policy.category.{interp.comparison_category.value}")
        is_selected = st.session_state.policy_selected_id == interp.id
        if st.button(
            f"{badge} `{interp.price_type}` → {cat_label}",
            key=f"policy_interp_{interp.id}",
            use_container_width=True,
            type="primary" if is_selected else "secondary",
        ):
            st.session_state.policy_selected_id = interp.id
            st.rerun()

    return st.session_state.policy_selected_id


def _render_interpretation_detail(interp):
    cat_label = t(f"policy.category.{interp.comparison_category.value}")
    badge, status_label = _comparability_label(interp)

    st.subheader(f"`{interp.price_type}` → **{cat_label}**")
    st.markdown(f"{badge} **{status_label}**")

    blocked, reason = blocks_comparison(interp)
    if blocked:
        st.error(reason)

    eff_to = (
        interp.effective_to.isoformat() if interp.effective_to
        else t("policy.fields.present")
    )
    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"**{t('policy.fields.effectiveFrom')}**: "
                    f"`{interp.effective_from.isoformat()}`")
        st.markdown(f"**{t('policy.fields.effectiveTo')}**: `{eff_to}`")
        conf_label = t(f"policy.confidence.{interp.confidence.value}")
        conf_badge = _confidence_badge(interp.confidence.value)
        st.markdown(f"**{t('policy.fields.confidence')}**: {conf_badge} {conf_label}")
    with cols[1]:
        vat_value = (
            t("source.yes") if interp.includes_vat is True
            else t("source.no") if interp.includes_vat is False
            else "—"
        )
        st.markdown(f"**{t('policy.fields.vatIncluded')}**: {vat_value}")
        st.markdown(f"**{t('policy.fields.margin')}**: "
                    f"{interp.includes_margin or '—'}")

    st.markdown(f"**{t('policy.fields.interpretationText')}**")
    st.markdown(interp.interpretation_text)

    st.markdown(f"**{t('policy.fields.sourceReferences')}**")
    for ref in interp.source_references:
        if ref.startswith("http"):
            st.markdown(f"- [{ref}]({ref})")
        else:
            st.markdown(f"- {ref}")

    if interp.caveats:
        st.markdown(f"**{t('policy.fields.caveats')}**")
        for cav in interp.caveats:
            st.warning(cav)

    if interp.adjudication_notes:
        st.markdown(f"**{t('policy.fields.adjudicationNotes')}**")
        st.markdown(interp.adjudication_notes)


def _render_provenance_panel(interp):
    st.subheader(t("ui.provenance"))
    if interp is None:
        st.info(t("policy.selectInterpretation"))
        return
    st.markdown(f"**{t('policy.fields.interpretationId')}**")
    st.code(interp.id)
    st.markdown(f"**{t('policy.fields.authoredAt')}**")
    st.code(interp.authored_at.isoformat())
    st.markdown(f"**{t('policy.fields.authoredBy')}**")
    st.code(interp.authored_by)


def render_policy_mapping():
    st.header(t("policy.title"))
    st.caption(t("policy.subtitle"))

    main_col, prov_col = st.columns([3, 1])

    with main_col:
        picker_col, content_col = st.columns([1, 3])
        with picker_col:
            country_dir_name = _render_country_picker()
        with content_col:
            interpretations = load_interpretations(REPO_ROOT, country_dir_name.upper())
            selected_id = _render_interpretation_list(interpretations)
            selected = next(
                (i for i in interpretations if i.id == selected_id), None
            )
            if selected is not None:
                st.markdown("---")
                _render_interpretation_detail(selected)

    with prov_col:
        selected = None
        if st.session_state.get("policy_selected_id") and country_dir_name:
            interps = load_interpretations(REPO_ROOT, country_dir_name.upper())
            selected = next(
                (i for i in interps if i.id == st.session_state.policy_selected_id),
                None,
            )
        _render_provenance_panel(selected)
