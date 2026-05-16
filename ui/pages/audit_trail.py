"""Audit Trail page.

Renders the full evidence chain for a comparison candidate with broken-
link indicators. Resolves all 16 links (8 shared/per-side) and shows
each artifact's payload on demand. Bilingual labels; IDs and source
URLs remain canonical.
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

from eu_pharma_price.audit import build_audit_trail  # noqa: E402

COMPARISONS_ROOT = REPO_ROOT / "data" / "comparisons"


def _list_windows() -> list[str]:
    if not COMPARISONS_ROOT.exists():
        return []
    return sorted(
        d.name for d in COMPARISONS_ROOT.iterdir()
        if d.is_dir() and (d / "candidates.parquet").exists()
    )


def _list_candidates(window: str) -> pd.DataFrame:
    p = COMPARISONS_ROOT / window / "candidates.parquet"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def _link_label(label: str) -> str:
    parts = label.split(".")
    base = parts[0]
    suffix_a_or_b = parts[1] if len(parts) > 1 else None
    base_label = t(f"audit.links.{base}")
    if suffix_a_or_b == "a":
        return f"{base_label} ({t('audit.sideA')})"
    if suffix_a_or_b == "b":
        return f"{base_label} ({t('audit.sideB')})"
    if suffix_a_or_b:
        return f"{base_label} ({suffix_a_or_b})"
    return f"{base_label} ({t('audit.shared')})"


def _render_window_picker():
    if "audit_window" not in st.session_state:
        st.session_state.audit_window = None
    if "audit_candidate" not in st.session_state:
        st.session_state.audit_candidate = None

    windows = _list_windows()
    if not windows:
        st.info(t("audit.noWindows"))
        return None
    if st.session_state.audit_window not in windows:
        st.session_state.audit_window = windows[-1]

    cols = st.columns(min(len(windows), 4))
    for i, w in enumerate(windows):
        with cols[i % len(cols)]:
            if st.button(
                w, key=f"audit_w_{w}",
                use_container_width=True,
                type="primary" if st.session_state.audit_window == w else "secondary",
            ):
                st.session_state.audit_window = w
                st.session_state.audit_candidate = None
                st.rerun()
    return st.session_state.audit_window


def _render_candidate_picker(window: str):
    df = _list_candidates(window)
    if df.empty:
        st.info(t("audit.noCandidates"))
        return None

    options = df["id"].tolist()
    labels = [
        f"{r['molecule_inn']} {r['strength']} {r['dosage_form']} "
        f"({r['country_a_code']}–{r['country_b_code']})"
        for _, r in df.iterrows()
    ]
    if st.session_state.audit_candidate not in options:
        st.session_state.audit_candidate = options[0]

    pick = st.selectbox(
        t("audit.selectCandidate"),
        options=range(len(options)),
        format_func=lambda i: labels[i],
        index=options.index(st.session_state.audit_candidate),
        key=f"audit_pick_{window}",
    )
    st.session_state.audit_candidate = options[pick]
    return st.session_state.audit_candidate


def _render_chain(trail):
    if trail.all_resolved:
        st.success(f"✅ {t('audit.allLinksResolved')} — {len(trail.links)} links")
    else:
        st.error(
            f"❌ {len(trail.broken_links)} {t('audit.brokenLinks')}"
        )

    for link in trail.links:
        badge = "✅" if link.found else "❌"
        label = _link_label(link.label)
        with st.expander(f"{badge} {label}"):
            if link.artifact_id:
                st.markdown("**ID**")
                st.code(link.artifact_id)
            if link.note:
                st.warning(link.note)
            if link.payload:
                st.markdown(f"**{t('audit.viewPayload')}**")
                if isinstance(link.payload, dict):
                    st.json(link.payload)
                else:
                    st.code(str(link.payload))


def render_audit_trail():
    st.header(t("audit.title"))
    st.caption(t("audit.subtitle"))

    main_col, prov_col = st.columns([3, 1])
    with main_col:
        window = _render_window_picker()
        if not window:
            return
        candidate_id = _render_candidate_picker(window)
        if not candidate_id:
            return
        trail = build_audit_trail(REPO_ROOT, window, candidate_id)
        st.markdown("---")
        st.subheader(t("audit.chainStatus"))
        _render_chain(trail)

    with prov_col:
        st.subheader(t("ui.provenance"))
        st.markdown("**candidate_id**")
        st.code(st.session_state.get("audit_candidate", ""))
        if st.session_state.get("audit_window"):
            st.markdown("**window**")
            st.code(st.session_state.audit_window)
