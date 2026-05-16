"""Country Workspace page for the Research Audit Workbench.

Displays per-country canonical records, raw-to-canonical lineage,
delegate report summary, and anomalies. Selecting a canonical record
shows the raw record it came from in the right provenance panel.

Cross-country joins are forbidden: only one country's data is loaded
at a time.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from i18n import t

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

CANONICAL_ROOT = REPO_ROOT / "data" / "canonical"
DELEGATE_REPORTS = REPO_ROOT / "reports" / "delegate"
ANOMALY_REPORTS = REPO_ROOT / "reports" / "anomalies"

INCLUDED_COUNTRIES = [("ie", "IE"), ("pl", "PL"), ("fr", "FR")]


def _list_country_snapshots(country_dir_name: str) -> list[str]:
    cdir = CANONICAL_ROOT / country_dir_name
    if not cdir.exists():
        return []
    return sorted(
        d.name for d in cdir.iterdir()
        if d.is_dir() and (d / "prices.parquet").exists()
    )


@st.cache_data
def _load_prices(country_dir_name: str, snapshot_date: str) -> pd.DataFrame:
    p = CANONICAL_ROOT / country_dir_name / snapshot_date / "prices.parquet"
    return pd.read_parquet(p)


@st.cache_data
def _load_raw(country_dir_name: str, snapshot_date: str) -> pd.DataFrame:
    p = CANONICAL_ROOT / country_dir_name / snapshot_date / "raw.parquet"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


@st.cache_data
def _load_lineage(country_dir_name: str, snapshot_date: str) -> pd.DataFrame:
    p = CANONICAL_ROOT / country_dir_name / snapshot_date / "raw_to_canonical.parquet"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def _load_delegate_report(country_dir_name: str, snapshot_date: str) -> str | None:
    p = DELEGATE_REPORTS / country_dir_name / f"{snapshot_date}.md"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def _load_anomaly_report(country_dir_name: str, snapshot_date: str) -> str | None:
    p = ANOMALY_REPORTS / country_dir_name / f"{snapshot_date}.md"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def _state_badge(state: str) -> str:
    return {
        "not_started": "⚪",
        "source_captured": "🔵",
        "parsed": "🟡",
        "canonicalized": "🟢",
        "anomaly_reported": "🟠",
        "needs_review": "🔴",
    }.get(state, "⚪")


def _detect_state(country_dir_name: str, snapshot_date: str) -> str:
    if _load_anomaly_report(country_dir_name, snapshot_date):
        prices = _load_prices(country_dir_name, snapshot_date)
        if len(prices) > 0:
            return "needs_review"
        return "anomaly_reported"
    return "canonicalized"


def _render_country_picker():
    st.subheader(t("country.selectCountry"))
    if "ws_country" not in st.session_state:
        st.session_state.ws_country = INCLUDED_COUNTRIES[0][0]
    if "ws_snapshot" not in st.session_state:
        st.session_state.ws_snapshot = None
    if "ws_selected_canonical" not in st.session_state:
        st.session_state.ws_selected_canonical = None

    country_dir_name = None
    for cdir, label in INCLUDED_COUNTRIES:
        country_label = t(f"country.{ {'ie': 'ireland', 'pl': 'poland', 'fr': 'france'}[cdir] }")
        if st.button(
            f"{label} — {country_label}",
            key=f"ws_country_{cdir}",
            use_container_width=True,
            type="primary" if st.session_state.ws_country == cdir else "secondary",
        ):
            st.session_state.ws_country = cdir
            st.session_state.ws_snapshot = None
            st.session_state.ws_selected_canonical = None
            st.rerun()

    return st.session_state.ws_country


def _render_snapshot_picker(country_dir_name: str):
    snapshots = _list_country_snapshots(country_dir_name)
    if not snapshots:
        st.info(t("country.noSnapshots"))
        return None

    if st.session_state.ws_snapshot not in snapshots:
        st.session_state.ws_snapshot = snapshots[-1]

    cols = st.columns(min(len(snapshots), 4))
    for i, snap in enumerate(snapshots):
        state = _detect_state(country_dir_name, snap)
        badge = _state_badge(state)
        with cols[i % len(cols)]:
            if st.button(
                f"{badge} {snap}",
                key=f"ws_snap_{country_dir_name}_{snap}",
                use_container_width=True,
                type="primary" if st.session_state.ws_snapshot == snap else "secondary",
            ):
                st.session_state.ws_snapshot = snap
                st.session_state.ws_selected_canonical = None
                st.rerun()
    return st.session_state.ws_snapshot


def _render_canonical_table(country_dir_name: str, snapshot_date: str):
    df = _load_prices(country_dir_name, snapshot_date)
    if df.empty:
        st.info(t("country.noCanonicalRecords"))
        return None

    st.markdown(f"**{t('country.canonicalRecords')}** — {len(df)}")

    show_cols = ["product_name", "strength", "dosage_form",
                 "pack_size", "price_amount", "price_currency", "price_type"]
    display = df[show_cols].copy()
    display.columns = [
        t("country.fields.productName"),
        t("country.fields.strength"),
        t("country.fields.dosageForm"),
        t("country.fields.packSize"),
        t("country.fields.price"),
        "Cur",
        t("country.fields.priceType"),
    ]
    st.dataframe(display, use_container_width=True, hide_index=True)

    options = [
        f"{r['product_name']} ({r['strength']}, pack {r['pack_size']})"
        for _, r in df.iterrows()
    ]
    pick = st.selectbox(
        t("country.selectRecord"),
        options=range(len(options)),
        format_func=lambda i: options[i],
        key=f"ws_pick_{country_dir_name}_{snapshot_date}",
    )
    if pick is not None:
        st.session_state.ws_selected_canonical = df.iloc[pick]["id"]
    return df


def _render_provenance(country_dir_name: str, snapshot_date: str, df_prices: pd.DataFrame):
    cid = st.session_state.get("ws_selected_canonical")
    if cid is None or df_prices is None or df_prices.empty:
        st.info(t("country.selectRecord"))
        return

    rec = df_prices[df_prices["id"] == cid]
    if rec.empty:
        st.info(t("country.selectRecord"))
        return
    rec = rec.iloc[0]

    st.markdown(f"**{t('country.fields.canonicalId')}**")
    st.code(rec["id"])
    st.markdown(f"**{t('country.fields.rawRecordId')}**")
    st.code(rec["raw_record_id"])
    st.markdown(f"**{t('country.fields.sourceDocumentId')}**")
    st.code(rec["source_document_id"])

    st.markdown(f"**{t('source.fields.fileHash')}**")
    cc_upper = country_dir_name.upper()
    fixture_dir = REPO_ROOT / "tests" / "fixtures" / "sources" / country_dir_name / snapshot_date
    manifest_path = fixture_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for fentry in manifest["files"]:
            st.code(fentry["file_hash"])

    raw_df = _load_raw(country_dir_name, snapshot_date)
    if not raw_df.empty:
        match = raw_df[raw_df["id"] == rec["raw_record_id"]]
        if not match.empty:
            raw_row = match.iloc[0]
            st.markdown(f"**{t('country.fields.rowIndex')}**: `{raw_row['row_index']}`")
            st.markdown(f"**{t('country.rawFields')}**")
            raw_fields = json.loads(raw_row["raw_fields_json"])
            for k, v in raw_fields.items():
                st.markdown(f"- `{k}`: `{v}`")


def _render_reports(country_dir_name: str, snapshot_date: str):
    delegate = _load_delegate_report(country_dir_name, snapshot_date)
    anomaly = _load_anomaly_report(country_dir_name, snapshot_date)

    tab_labels = [t("country.delegateReport")]
    if anomaly:
        tab_labels.append(t("country.anomalyReport"))
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        if delegate:
            st.markdown(delegate)
        else:
            st.info(t("status.notStarted"))

    if anomaly:
        with tabs[1]:
            st.markdown(anomaly)


def render_country_workspace():
    st.header(t("country.title"))
    st.caption(t("country.subtitle"))

    main_col, prov_col = st.columns([3, 1])

    with main_col:
        picker_col, content_col = st.columns([1, 3])
        with picker_col:
            country_dir_name = _render_country_picker()
        with content_col:
            snapshot_date = _render_snapshot_picker(country_dir_name)
            df_prices = None
            if snapshot_date:
                state = _detect_state(country_dir_name, snapshot_date)
                badge = _state_badge(state)
                state_label_key = {
                    "canonicalized": "canonicalized",
                    "needs_review": "needsReview",
                    "anomaly_reported": "anomalyReported",
                    "parsed": "parsed",
                    "source_captured": "sourceCaptured",
                    "not_started": "notStarted",
                }[state]
                st.markdown(
                    f"**State:** {badge} "
                    f"`{t(f'country.delegateState.{state_label_key}')}`"
                )
                df_prices = _render_canonical_table(country_dir_name, snapshot_date)
                st.markdown("---")
                _render_reports(country_dir_name, snapshot_date)

    with prov_col:
        st.subheader(t("ui.provenance"))
        if snapshot_date:
            _render_provenance(country_dir_name, snapshot_date, df_prices)
        else:
            st.info(t("country.noSnapshots"))
