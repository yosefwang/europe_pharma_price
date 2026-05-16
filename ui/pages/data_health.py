"""Data Health page for the Research Audit Workbench.

Displays per-snapshot field profiles, plausibility assessments, and a
combined comparison-readiness check that joins policy gating and data
gating to surface the explicit "policy permits, data does not" state
required by Phase 5.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import streamlit as st

from i18n import t

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from eu_pharma_price.policy.gating import (  # noqa: E402
    blocks_comparison as policy_blocks,
    interpretation_for_field,
    load_interpretations,
)
from eu_pharma_price.profile.gating import is_field_blocked  # noqa: E402
from eu_pharma_price.schemas.profile import DataProfile  # noqa: E402

PROFILES_ROOT = REPO_ROOT / "data" / "profiles"
INCLUDED_COUNTRIES = [("ie", "IE"), ("pl", "PL"), ("fr", "FR")]


def _list_snapshots(country_dir: str) -> list[str]:
    cdir = PROFILES_ROOT / country_dir
    if not cdir.exists():
        return []
    return sorted(
        d.name for d in cdir.iterdir()
        if d.is_dir() and (d / "data_profile.json").exists()
    )


@st.cache_data
def _load_profile_payload(country_dir: str, snap: str) -> dict:
    p = PROFILES_ROOT / country_dir / snap / "data_profile.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _snapshot_status_badge(status: str) -> str:
    return {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(status, "⚪")


def _plausibility_badge(p: str) -> str:
    return {"plausible": "🟢", "suspect": "🟡", "implausible": "🔴"}.get(p, "⚪")


def _readiness_label(policy_blocked, policy_reason, data_blocked, data_reason, conf):
    if policy_blocked:
        return ("🔴", t("dataHealth.policyNotPermitted"), policy_reason)
    if data_blocked:
        return ("🔴", t("dataHealth.blockedByData"), data_reason)
    if conf == "low":
        return ("🟡", t("dataHealth.needsReview"), None)
    return ("🟢", t("dataHealth.ready"), None)


def _render_country_picker():
    if "dh_country" not in st.session_state:
        st.session_state.dh_country = INCLUDED_COUNTRIES[0][0]
    if "dh_snapshot" not in st.session_state:
        st.session_state.dh_snapshot = None

    name_map = {"ie": "ireland", "pl": "poland", "fr": "france"}
    st.subheader(t("country.selectCountry"))
    for cdir, label in INCLUDED_COUNTRIES:
        country_label = t(f"country.{name_map[cdir]}")
        if st.button(
            f"{label} — {country_label}",
            key=f"dh_country_{cdir}",
            use_container_width=True,
            type="primary" if st.session_state.dh_country == cdir else "secondary",
        ):
            st.session_state.dh_country = cdir
            st.session_state.dh_snapshot = None
            st.rerun()
    return st.session_state.dh_country


def _render_snapshot_picker(country_dir: str):
    snapshots = _list_snapshots(country_dir)
    if not snapshots:
        st.info(t("dataHealth.noProfiles"))
        return None
    if st.session_state.dh_snapshot not in snapshots:
        st.session_state.dh_snapshot = snapshots[-1]

    cols = st.columns(min(len(snapshots), 4))
    for i, snap in enumerate(snapshots):
        payload = _load_profile_payload(country_dir, snap)
        badge = _snapshot_status_badge(payload["snapshot_status"])
        with cols[i % len(cols)]:
            if st.button(
                f"{badge} {snap}",
                key=f"dh_snap_{country_dir}_{snap}",
                use_container_width=True,
                type="primary" if st.session_state.dh_snapshot == snap else "secondary",
            ):
                st.session_state.dh_snapshot = snap
                st.rerun()
    return st.session_state.dh_snapshot


def _render_field_profile(profile_dict: dict, country_dir: str, snap: str):
    profile = DataProfile.model_validate(profile_dict)
    plaus = profile.plausibility_assessment.value
    badge = _plausibility_badge(plaus)
    plaus_label = t(f"dataHealth.plausibility.{plaus}")

    with st.expander(f"{badge} `{profile.price_type}` — {plaus_label}", expanded=True):
        cols = st.columns(3)
        with cols[0]:
            st.markdown(f"**{t('dataHealth.fields.fieldExists')}**: "
                        f"`{profile.field_exists}`")
            st.markdown(f"**{t('dataHealth.fields.nonNullRate')}**: "
                        f"`{profile.population_rate}`")
            st.markdown(f"**{t('dataHealth.fields.recordCount')}**: "
                        f"`{profile.record_count}`")
        with cols[1]:
            if profile.min_value is not None:
                st.markdown(f"**{t('dataHealth.fields.minValue')}**: "
                            f"`{profile.min_value}`")
                st.markdown(f"**{t('dataHealth.fields.medianValue')}**: "
                            f"`{profile.median_value}`")
                st.markdown(f"**{t('dataHealth.fields.maxValue')}**: "
                            f"`{profile.max_value}`")
            if profile.outlier_count is not None:
                st.markdown(f"**{t('dataHealth.fields.outlierCount')}**: "
                            f"`{profile.outlier_count}`")
        with cols[2]:
            st.markdown(f"**{t('dataHealth.fields.distribution')}**")
            st.code(profile.distribution_notes or "—", language=None)

        if profile.issues:
            st.markdown(f"**{t('dataHealth.fields.issues')}**")
            for iss in profile.issues:
                st.warning(iss)

        # Cross-gate readiness
        country_code = profile.country_code.upper()
        interps = load_interpretations(REPO_ROOT, country_code)
        snap_date = date.fromisoformat(snap)
        # Match interpretation by canonical price_type if applicable
        if profile.price_type == "price_amount":
            from eu_pharma_price.policy.gating import (
                interpretation_for_field as ifield,
            )
            from pathlib import Path as _Path
            import pandas as pd
            prices_path = (
                REPO_ROOT / "data" / "canonical" / country_dir / snap / "prices.parquet"
            )
            if prices_path.exists():
                df = pd.read_parquet(prices_path)
                pt_in_data = (
                    df["price_type"].iloc[0] if "price_type" in df.columns and len(df) > 0
                    else None
                )
                interp = ifield(interps, pt_in_data, snap_date) if pt_in_data else None
            else:
                interp = None
        else:
            interp = interpretation_for_field(interps, profile.price_type, snap_date)

        p_blocked, p_reason = policy_blocks(interp)
        d_blocked, d_reason = is_field_blocked(profile)
        conf = interp.confidence.value if interp else None
        ready_badge, ready_text, ready_detail = _readiness_label(
            p_blocked, p_reason, d_blocked, d_reason, conf
        )
        st.markdown("---")
        st.markdown(f"**{t('dataHealth.comparisonReadiness')}**: "
                    f"{ready_badge} {ready_text}")
        cols2 = st.columns(2)
        with cols2[0]:
            label = t("dataHealth.policyPermits")
            mark = "✅" if not p_blocked else "❌"
            st.markdown(f"{mark} {label}")
            if p_blocked and p_reason:
                st.caption(p_reason)
        with cols2[1]:
            label = t("dataHealth.dataPermits")
            mark = "✅" if not d_blocked else "❌"
            st.markdown(f"{mark} {label}")
            if d_blocked and d_reason:
                st.caption(d_reason)


def render_data_health():
    st.header(t("dataHealth.title"))
    st.caption(t("dataHealth.subtitle"))

    main_col, prov_col = st.columns([3, 1])
    with main_col:
        picker_col, content_col = st.columns([1, 3])
        with picker_col:
            country_dir = _render_country_picker()
        with content_col:
            snap = _render_snapshot_picker(country_dir)
            if snap:
                payload = _load_profile_payload(country_dir, snap)
                badge = _snapshot_status_badge(payload["snapshot_status"])
                status_label = t(
                    f"dataHealth.snapshotStatus.{payload['snapshot_status']}"
                )
                st.markdown(f"**Snapshot status:** {badge} `{status_label}`")
                st.markdown("---")
                if not payload["profiles"]:
                    st.info(t("dataHealth.noFieldProfiles"))
                else:
                    st.subheader(t("dataHealth.fieldProfiles"))
                    for prof in payload["profiles"]:
                        _render_field_profile(prof, country_dir, snap)

    with prov_col:
        st.subheader(t("ui.provenance"))
        if st.session_state.get("dh_snapshot"):
            payload = _load_profile_payload(
                st.session_state.dh_country, st.session_state.dh_snapshot
            )
            st.markdown(f"**country_code**")
            st.code(payload["country_code"])
            st.markdown(f"**snapshot_date**")
            st.code(payload["snapshot_date"])
            st.markdown(f"**assessed_at**")
            st.code(payload["assessed_at"])
