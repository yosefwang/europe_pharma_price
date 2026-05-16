"""Comparison Workbench page.

The researcher-facing search and browse surface. Pulls from the same
query interface that Python users call. Renders evidence-aware cards
and an inline report preview in the active locale.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from i18n import get_locale, t

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from eu_pharma_price.query import (  # noqa: E402
    available_molecules,
    available_windows,
    candidates_for_molecule,
)
from eu_pharma_price.query.report import generate_report  # noqa: E402


def _usability_badge(level: str) -> str:
    return {
        "usable": "🟢",
        "usable_with_caveat": "🟡",
        "exploratory": "🟠",
        "not_comparable": "🔴",
    }.get(level, "⚪")


def _render_filters():
    if "ws_window" not in st.session_state:
        st.session_state.ws_window = None
    if "ws_molecule" not in st.session_state:
        st.session_state.ws_molecule = None
    if "ws_pair_filter" not in st.session_state:
        st.session_state.ws_pair_filter = "__all__"
    if "ws_usability_filter" not in st.session_state:
        st.session_state.ws_usability_filter = "__all__"

    windows = available_windows(REPO_ROOT)
    if not windows:
        st.info(t("audit.noWindows"))
        return None, None
    if st.session_state.ws_window not in windows:
        st.session_state.ws_window = windows[-1]

    st.markdown(f"**{t('audit.selectWindow')}**")
    cols = st.columns(min(len(windows), 4))
    for i, w in enumerate(windows):
        with cols[i % len(cols)]:
            if st.button(
                w, key=f"ws_w_{w}",
                use_container_width=True,
                type="primary" if st.session_state.ws_window == w else "secondary",
            ):
                st.session_state.ws_window = w
                st.session_state.ws_molecule = None
                st.rerun()

    molecules = available_molecules(st.session_state.ws_window, REPO_ROOT)
    if not molecules:
        st.info(t("workbench.noMolecules"))
        return st.session_state.ws_window, None

    st.markdown(f"**{t('workbench.selectMolecule')}**")
    if st.session_state.ws_molecule not in molecules:
        st.session_state.ws_molecule = molecules[0]
    cols = st.columns(min(len(molecules), 4))
    for i, m in enumerate(molecules):
        with cols[i % len(cols)]:
            if st.button(
                m, key=f"ws_m_{m}",
                use_container_width=True,
                type="primary" if st.session_state.ws_molecule == m else "secondary",
            ):
                st.session_state.ws_molecule = m
                st.rerun()

    return st.session_state.ws_window, st.session_state.ws_molecule


def _render_card(row, locale: str):
    badge = _usability_badge(row.usability)
    st.markdown(
        f"### {badge} {row.molecule_inn} · {row.strength} · {row.dosage_form}"
    )
    st.markdown(
        f"`{row.country_a_code}` ↔ `{row.country_b_code}` · "
        f"{t('workbench.comparisonCategoryLabel')}: `{row.comparison_category}` · "
        f"{t('workbench.caveatCount')}: {len(row.caveats)}"
    )

    if row.usability == "not_comparable":
        st.error(t("workbench.blockedBanner"))
    elif row.usability == "exploratory":
        st.warning(t("workbench.exploratoryBanner"))

    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"**{row.country_a_code}**")
        st.markdown(
            f"`{row.price_a}` {row.currency_a} {t('workbench.perPack')} {row.strength}"
        )
        if row.price_per_strength_unit_a is not None:
            st.markdown(
                f"per strength unit: `{row.price_per_strength_unit_a}` "
                f"{row.currency_a}/strength_unit"
            )
    with cols[1]:
        st.markdown(f"**{row.country_b_code}**")
        st.markdown(
            f"`{row.price_b}` {row.currency_b} {t('workbench.perPack')} {row.strength}"
        )
        if row.price_per_strength_unit_b is not None:
            st.markdown(
                f"per strength unit: `{row.price_per_strength_unit_b}` "
                f"{row.currency_b}/strength_unit"
            )

    if row.price_ratio is None:
        st.info(t("workbench.ratioNullCurrency"))
    else:
        try:
            ratio_str = f"{float(row.price_ratio):.4f}"
        except (TypeError, ValueError):
            ratio_str = str(row.price_ratio)
        st.markdown(f"**{t('workbench.ratio')}**: `{ratio_str}`")

    if row.caveats:
        st.markdown(f"**{t('workbench.caveatCount')}**")
        for c in row.caveats:
            st.warning(c)

    btn_cols = st.columns(2)
    with btn_cols[0]:
        if st.button(
            t("workbench.openReport"),
            key=f"report_{row.candidate_id}",
            use_container_width=True,
        ):
            st.session_state[f"showreport_{row.candidate_id}"] = True
    with btn_cols[1]:
        if st.button(
            t("workbench.openAuditTrail"),
            key=f"audit_{row.candidate_id}",
            use_container_width=True,
        ):
            st.session_state.audit_window = st.session_state.ws_window
            st.session_state.audit_candidate = row.candidate_id
            st.session_state.active_view = "auditTrail"
            st.rerun()

    if st.session_state.get(f"showreport_{row.candidate_id}"):
        st.markdown("---")
        body = generate_report(
            st.session_state.ws_window, row.candidate_id, locale, REPO_ROOT
        )
        st.markdown(body)


def render_comparison_workbench():
    st.header(t("workbench.title"))
    st.caption(t("workbench.subtitle"))

    main_col, prov_col = st.columns([3, 1])
    with main_col:
        window, molecule = _render_filters()
        if not window or not molecule:
            return

        rows = candidates_for_molecule(window, molecule, REPO_ROOT)
        if not rows:
            st.info(t("workbench.noCandidatesForMolecule"))
            return

        # Country pair and usability filters
        pairs = sorted({f"{r.country_a_code}-{r.country_b_code}" for r in rows})
        usabilities = sorted({r.usability for r in rows})

        f_cols = st.columns(2)
        with f_cols[0]:
            pair_choice = st.selectbox(
                t("workbench.filterCountryPair"),
                options=["__all__"] + pairs,
                format_func=lambda x: t("workbench.all") if x == "__all__" else x,
                key="ws_pair_filter",
            )
        with f_cols[1]:
            use_choice = st.selectbox(
                t("workbench.filterUsability"),
                options=["__all__"] + usabilities,
                format_func=lambda x: (
                    t("workbench.all") if x == "__all__"
                    else t(f"review.usability.{x}")
                ),
                key="ws_usability_filter",
            )

        filtered = [
            r for r in rows
            if (pair_choice == "__all__"
                or f"{r.country_a_code}-{r.country_b_code}" == pair_choice)
            and (use_choice == "__all__" or r.usability == use_choice)
        ]
        if not filtered:
            st.info(t("workbench.noResults"))
            return

        st.markdown("---")
        for r in filtered:
            _render_card(r, get_locale())
            st.markdown("---")

    with prov_col:
        st.subheader(t("ui.provenance"))
        if st.session_state.get("ws_window"):
            st.markdown("**snapshot_window**")
            st.code(st.session_state.ws_window)
        if st.session_state.get("ws_molecule"):
            st.markdown("**molecule_inn**")
            st.code(st.session_state.ws_molecule)
