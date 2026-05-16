"""Schema Map page for the Research Audit Workbench.

Displays the 9 evidence chain artifact types as an interactive dependency
graph. Selecting an artifact shows its dependencies and dependents, plus
the system invariants (two-gear rule, no bare prices, no silent transforms).
"""

import streamlit as st

from i18n import t

ARTIFACTS = [
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

DEPENDENCIES: dict[str, list[str]] = {
    "sourceDocument": [],
    "rawRecord": ["sourceDocument"],
    "canonicalPriceRecord": ["rawRecord", "sourceDocument"],
    "policyInterpretation": ["sourceDocument"],
    "dataProfile": ["canonicalPriceRecord", "policyInterpretation"],
    "derivationRule": ["canonicalPriceRecord", "sourceDocument"],
    "comparisonCandidate": [
        "canonicalPriceRecord",
        "policyInterpretation",
        "dataProfile",
        "sourceDocument",
        "derivationRule",
    ],
    "reviewAssessment": ["comparisonCandidate"],
    "anomalyReport": [],
}

DEPENDED_ON_BY: dict[str, list[str]] = {}
for artifact, deps in DEPENDENCIES.items():
    for dep in deps:
        DEPENDED_ON_BY.setdefault(dep, []).append(artifact)


def render_schema_map():
    st.header(t("schema.title"))
    st.caption(t("schema.subtitle"))

    st.markdown("---")

    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.subheader(t("evidence.sourceDocument").title() + "s")
        selected = None
        for key in ARTIFACTS:
            label = t(f"evidence.{key}")
            if st.button(label, key=f"schema_{key}", use_container_width=True):
                st.session_state.selected_artifact = key

        selected = st.session_state.get("selected_artifact")

    with col_right:
        if selected:
            st.subheader(t(f"evidence.{selected}"))
            st.markdown(t(f"schema.desc.{selected}"))

            st.markdown("---")

            deps = DEPENDENCIES.get(selected, [])
            st.markdown(f"**{t('schema.dependencies')}**")
            if deps:
                for dep in deps:
                    st.markdown(f"- {t(f'evidence.{dep}')}")
            else:
                st.markdown(f"*{t('schema.noDependencies')}*")

            dependents = DEPENDED_ON_BY.get(selected, [])
            st.markdown(f"**{t('schema.dependedOnBy')}**")
            if dependents:
                for dep in dependents:
                    st.markdown(f"- {t(f'evidence.{dep}')}")
            else:
                st.markdown("*—*")

            if selected == "comparisonCandidate":
                st.markdown("---")
                st.warning(t("schema.twoGearRule"))
        else:
            st.info(t("schema.selectArtifact"))

    st.markdown("---")
    st.subheader("Invariants")
    st.markdown(f"1. {t('schema.twoGearRule')}")
    st.markdown(f"2. {t('schema.noBarePrices')}")
    st.markdown(f"3. {t('schema.noSilentTransforms')}")
