"""EU Pharma Price — Research Audit Workbench.

Entry point for the Streamlit app. Provides sidebar navigation
and language switching across all workbench views.
"""

import streamlit as st

st.set_page_config(
    page_title="EU Pharma Price Workbench",
    layout="wide",
    initial_sidebar_state="expanded",
)

from i18n import get_locale, set_locale, t  # noqa: E402
from pages.country_workspace import render_country_workspace  # noqa: E402
from pages.data_health import render_data_health  # noqa: E402
from pages.policy_mapping import render_policy_mapping  # noqa: E402
from pages.project_map import render_project_map  # noqa: E402
from pages.schema_map import render_schema_map  # noqa: E402
from pages.source_register import render_source_register  # noqa: E402

NAV_KEYS = [
    "projectMap",
    "schemaMap",
    "sourceRegister",
    "countryWorkspace",
    "policyMapping",
    "dataHealth",
    "comparisonCandidates",
    "reviewQueue",
    "auditTrail",
    "comparisonWorkbench",
]

ACTIVE_VIEWS = {"projectMap", "schemaMap", "sourceRegister", "countryWorkspace", "policyMapping", "dataHealth"}


def _sidebar():
    with st.sidebar:
        st.markdown("### EU Pharma Price")
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("EN", use_container_width=True,
                         type="primary" if get_locale() == "en" else "secondary"):
                set_locale("en")
                st.rerun()
        with col2:
            if st.button("中文", use_container_width=True,
                         type="primary" if get_locale() == "zh-CN" else "secondary"):
                set_locale("zh-CN")
                st.rerun()

        st.markdown("---")

        if "active_view" not in st.session_state:
            st.session_state.active_view = "projectMap"

        for key in NAV_KEYS:
            label = t(f"nav.{key}")
            disabled = key not in ACTIVE_VIEWS
            if st.button(
                label,
                key=f"nav_{key}",
                use_container_width=True,
                disabled=disabled,
            ):
                st.session_state.active_view = key
                st.rerun()


def _main_content():
    view = st.session_state.get("active_view", "projectMap")
    if view == "projectMap":
        render_project_map()
    elif view == "schemaMap":
        render_schema_map()
    elif view == "sourceRegister":
        render_source_register()
    elif view == "countryWorkspace":
        render_country_workspace()
    elif view == "policyMapping":
        render_policy_mapping()
    elif view == "dataHealth":
        render_data_health()
    else:
        st.info(t("status.notStarted"))


_sidebar()
_main_content()
