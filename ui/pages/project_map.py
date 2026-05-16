"""Project Map page for the Research Audit Workbench.

Displays phase roadmap, country scope summary, artifact status,
and an empty provenance panel. Distinguishes stable commitments
from working hypotheses.
"""

import streamlit as st

from i18n import t

PHASES = [
    ("p0", "completed"),
    ("p1", "completed"),
    ("p2", "completed"),
    ("p3", "completed"),
    ("p4", "completed"),
    ("p5", "completed"),
    ("p6", "not_started"),
    ("p3", "not_started"),
    ("p4", "not_started"),
    ("p5", "not_started"),
    ("p6", "not_started"),
    ("p7", "not_started"),
    ("p8", "not_started"),
    ("p9", "not_started"),
]

INCLUDED_COUNTRIES = ["ireland", "poland", "france"]
EXCLUDED_COUNTRIES = ["germany"]
CANDIDATE_COUNTRIES = [
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czechRepublic",
    "denmark", "estonia", "finland", "greece", "hungary", "iceland", "italy",
    "latvia", "liechtenstein", "lithuania", "luxembourg", "malta",
    "netherlands", "norway", "portugal", "romania", "slovakia", "slovenia",
    "spain", "sweden", "switzerland", "unitedKingdom",
]

EVIDENCE_ARTIFACTS = [
    "sourceDocument",
    "rawRecord",
    "canonicalPriceRecord",
    "policyInterpretation",
    "dataProfile",
    "derivationRule",
    "comparisonCandidate",
    "reviewAssessment",
    "anomalyReport",
]


def _status_badge(status_key: str) -> str:
    colors = {
        "in_progress": "🟡",
        "not_started": "⚪",
        "completed": "🟢",
    }
    return colors.get(status_key, "⚪")


def _commitment_tag(is_stable: bool) -> str:
    if is_stable:
        return f"`{t('status.stableCommitment')}`"
    return f"*{t('status.workingHypothesis')}*"


STATUS_KEY_MAP = {
    "in_progress": "inProgress",
    "not_started": "notStarted",
    "completed": "completed",
}


def _render_phase_roadmap():
    st.subheader(t("nav.projectMap"))
    st.caption(_commitment_tag(is_stable=False))

    for phase_key, status in PHASES:
        badge = _status_badge(status)
        name = t(f"phase.{phase_key}.name")
        desc = t(f"phase.{phase_key}.description")
        status_label = t(f"status.{STATUS_KEY_MAP[status]}")
        st.markdown(f"{badge} **{name}** — {desc} ({status_label})")


def _render_country_scope():
    st.subheader(t("countryScope.aPrioriIncluded") + " " + _commitment_tag(is_stable=True))

    cols = st.columns(3)
    for i, key in enumerate(INCLUDED_COUNTRIES):
        with cols[i]:
            st.success(t(f"country.{key}"))

    st.subheader(t("countryScope.aPrioriExcluded") + " " + _commitment_tag(is_stable=True))
    st.error(t("country.germany"))

    with st.expander(t("countryScope.candidatePool") + f" ({len(CANDIDATE_COUNTRIES)})"):
        col_count = 4
        rows = [CANDIDATE_COUNTRIES[i:i + col_count]
                for i in range(0, len(CANDIDATE_COUNTRIES), col_count)]
        for row in rows:
            cols = st.columns(col_count)
            for j, key in enumerate(row):
                with cols[j]:
                    st.markdown(t(f"country.{key}"))


def _render_artifact_status():
    st.subheader(t("ui.status"))

    for artifact_key in EVIDENCE_ARTIFACTS:
        label = t(f"evidence.{artifact_key}")
        st.markdown(f"⚪ {label} — *{t('status.notStarted')}*")


def _render_provenance_panel():
    st.subheader(t("ui.provenance"))
    st.caption(t("status.notStarted"))


def render_project_map():
    main_col, prov_col = st.columns([3, 1])

    with main_col:
        _render_phase_roadmap()
        st.markdown("---")
        _render_country_scope()
        st.markdown("---")
        _render_artifact_status()

    with prov_col:
        _render_provenance_panel()
