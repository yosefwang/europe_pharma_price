"""Locale loader for the Research Audit Workbench.

Loads JSON locale dictionaries from ui/locales/ and provides a translation
function with fallback to English per the ui-localization spec (section 7).
"""

import json
from pathlib import Path
from typing import Any

import streamlit as st

LOCALES_DIR = Path(__file__).parent / "locales"
SUPPORTED_LOCALES = ("en", "zh-CN")
DEFAULT_LOCALE = "en"


@st.cache_data
def _load_locale(locale: str) -> dict[str, Any]:
    path = LOCALES_DIR / f"{locale}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _resolve_key(data: dict[str, Any], key: str) -> str | None:
    parts = key.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    if isinstance(current, str) and current:
        return current
    return None


def get_locale() -> str:
    if "locale" not in st.session_state:
        st.session_state.locale = DEFAULT_LOCALE
    return st.session_state.locale


def set_locale(locale: str) -> None:
    if locale in SUPPORTED_LOCALES:
        st.session_state.locale = locale


def t(key: str) -> str:
    locale = get_locale()
    data = _load_locale(locale)
    value = _resolve_key(data, key)
    if value is not None:
        return value
    if locale != DEFAULT_LOCALE:
        fallback = _load_locale(DEFAULT_LOCALE)
        value = _resolve_key(fallback, key)
        if value is not None:
            return value
    return f"[missing: {key}]"
