"""Source Register page for the Research Audit Workbench.

Displays the list of registered pricing data sources, their capture status,
and the snapshots associated with each. Hashes and timestamps render
identically across languages (untranslated technical strings).
"""

import json
import sys
from pathlib import Path

import streamlit as st

from i18n import t

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from eu_pharma_price.sources import load_register, verify_snapshot  # noqa: E402

REGISTER_PATH = REPO_ROOT / "data" / "sources" / "register.json"
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "sources"


def _bool_label(value):
    if value is True:
        return f"✅ {t('source.yes')}"
    if value is False:
        return f"❌ {t('source.no')}"
    return "—"


def _status_badge(status: str) -> str:
    badges = {
        "registered": "⚪",
        "captured": "🟡",
        "hash_verified": "🟢",
        "hash_mismatch": "🔴",
        "pending_manual_refresh": "🟠",
        "blocked": "⛔",
    }
    return badges.get(status, "⚪")


def _status_label(status: str) -> str:
    key_map = {
        "registered": "registered",
        "captured": "captured",
        "hash_verified": "hashVerified",
        "hash_mismatch": "hashMismatch",
        "pending_manual_refresh": "pendingManualRefresh",
        "blocked": "blocked",
    }
    return t(f"source.status.{key_map.get(status, 'registered')}")


def _list_snapshots(country_code: str) -> list[Path]:
    country_dir = FIXTURES_ROOT / country_code.lower()
    if not country_dir.exists():
        return []
    return sorted(d for d in country_dir.iterdir()
                  if d.is_dir() and (d / "manifest.json").exists())


def _render_source_list(register: list[dict]):
    st.subheader(t("source.sources"))

    if not register:
        st.info(t("source.noSources"))
        return None

    if "selected_source_id" not in st.session_state:
        st.session_state.selected_source_id = register[0]["source_id"]

    for entry in register:
        sid = entry["source_id"]
        badge = _status_badge(entry.get("status", "registered"))
        label = f"{badge} {entry['country_code']} — {entry['source_name']}"
        if st.button(label, key=f"src_{sid}", use_container_width=True):
            st.session_state.selected_source_id = sid

    return st.session_state.selected_source_id


def _render_source_detail(entry: dict):
    st.subheader(entry["source_name"])
    st.caption(f"{_status_badge(entry.get('status', 'registered'))} "
               f"{_status_label(entry.get('status', 'registered'))}")

    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"**{t('source.fields.sourceUrl')}**")
        st.code(entry["source_url"])
        type_label = t(f"source.type.{entry['source_type']}")
        freq_label = t(f"source.frequency.{entry['update_frequency']}")
        method_label = t(f"source.fetchMethodLabel.{entry['fetch_method']}")
        st.markdown(f"**{t('source.fields.sourceType')}**: {type_label}")
        st.markdown(f"**{t('source.fields.updateFrequency')}**: {freq_label}")
        st.markdown(f"**{t('source.fields.fetchMethod')}**: {method_label}")

    with cols[1]:
        st.markdown(f"**{t('source.fields.robotsTxt')}**: "
                    f"{_bool_label(entry.get('robots_txt_compliant'))}")
        st.markdown(f"**{t('source.fields.tosReviewed')}**: "
                    f"{_bool_label(entry.get('tos_reviewed'))}")
        st.markdown(f"**{t('source.fields.registeredAt')}**")
        st.code(entry["registered_at"])

    if entry.get("manual_refresh_reason"):
        st.warning(entry["manual_refresh_reason"])

    if entry.get("notes"):
        st.caption(entry["notes"])

    st.markdown("---")
    st.subheader(t("source.snapshots"))

    snapshots = _list_snapshots(entry["country_code"])
    if not snapshots:
        st.info(t("source.noSnapshots"))
        return

    for snap_dir in snapshots:
        manifest = json.loads((snap_dir / "manifest.json").read_text(encoding="utf-8"))
        ok, errors = verify_snapshot(snap_dir)
        verify_badge = "🟢" if ok else "🔴"

        with st.expander(f"{verify_badge} {manifest['snapshot_date']}", expanded=ok):
            mcols = st.columns(2)
            with mcols[0]:
                st.markdown(f"**{t('source.fields.snapshotDate')}**: `{manifest['snapshot_date']}`")
                st.markdown(f"**{t('source.fields.fetchedAt')}**: `{manifest['fetched_at']}`")
            with mcols[1]:
                snap_method = t(f"source.fetchMethodLabel.{manifest['fetch_method']}")
                st.markdown(f"**{t('source.fields.fetchMethod')}**: {snap_method}")

            for fentry in manifest["files"]:
                st.markdown(f"**{t('source.fields.filename')}**: `{fentry['filename']}`")
                st.markdown(f"**{t('source.fields.fileHash')}**")
                st.code(fentry["file_hash"], language=None)
                st.markdown(f"**{t('source.fields.fileSize')}**: "
                            f"`{fentry['file_size_bytes']:,} bytes`")

            if not ok:
                for err in errors:
                    st.error(err)


def render_source_register():
    st.header(t("source.title"))
    st.caption(t("source.subtitle"))

    register = load_register(REGISTER_PATH)

    main_col, prov_col = st.columns([3, 1])

    with main_col:
        list_col, detail_col = st.columns([1, 2])

        with list_col:
            selected_id = _render_source_list(register)

        with detail_col:
            if selected_id and register:
                entry = next((e for e in register if e["source_id"] == selected_id), None)
                if entry:
                    _render_source_detail(entry)
                else:
                    st.info(t("source.selectSource"))
            else:
                st.info(t("source.selectSource"))

    with prov_col:
        st.subheader(t("ui.provenance"))
        if selected_id and register:
            entry = next((e for e in register if e["source_id"] == selected_id), None)
            if entry:
                st.markdown(f"**Source ID**")
                st.code(entry["source_id"])
                st.markdown(f"**{t('source.fields.registeredAt')}**")
                st.code(entry["registered_at"])
