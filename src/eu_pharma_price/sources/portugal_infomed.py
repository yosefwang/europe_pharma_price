"""Utilities for Portugal Infomed research extracts.

Infomed is a JSF search application, not a stable bulk data feed. These helpers
turn captured detail-page HTML into the small semicolon CSV consumed by the PT
delegate. Raw HTML capture remains the evidence source; the CSV is an internal
research extract.
"""

from __future__ import annotations

import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


FIELDNAMES = [
    "Nome do Medicamento",
    "Substância Ativa/DCI",
    "Forma Farmacêutica",
    "Dosagem",
    "Apresentação",
    "Titular de AIM",
    "Via",
    "ATC",
    "PVP",
    "Código",
    "CNPEM",
]

INDEX_KEY_FIELDS = [
    "Substância Ativa/DCI",
    "Nome do Medicamento",
    "Forma Farmacêutica",
    "Dosagem",
    "Titular de AIM",
]


@dataclass(frozen=True)
class InfomedAtcOption:
    value: str
    code: str
    label: str


def _clean_text(value: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _value_after_label(markup: str, label: str) -> str:
    pos = markup.find(label)
    if pos < 0:
        return ""
    tail = markup[pos + len(label): pos + len(label) + 12000]
    for match in re.finditer(
        r"<(?:label|span|div)\b[^>]*>(.*?)</(?:label|span|div)>",
        tail,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        text = _clean_text(match.group(1))
        if text and text != label.rstrip(":"):
            return text
    return ""


def _text_by_id(markup: str, element_id: str) -> str:
    match = re.search(
        rf"<(?:label|span|div)\b[^>]*\bid=[\"']{re.escape(element_id)}[\"'][^>]*>"
        r"(.*?)</(?:label|span|div)>",
        markup,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return _clean_text(match.group(1)) if match else ""


def _normalise_price(value: str) -> str:
    return _clean_text(value).replace("€", "").strip()


def _has_numeric_price(value: str) -> bool:
    return bool(re.search(r"\d", value))


def extract_view_state(markup: str) -> str:
    match = re.search(
        r"\bname=[\"']javax\.faces\.ViewState[\"'][^>]*\bvalue=[\"']([^\"']+)[\"']",
        markup,
        flags=re.IGNORECASE,
    )
    return html.unescape(match.group(1)) if match else ""


def extract_form_action(markup: str, *, form_id: str = "mainForm") -> str:
    match = re.search(
        rf"<form\b[^>]*\bid=[\"']{re.escape(form_id)}[\"'][^>]*\baction=[\"']([^\"']+)[\"']",
        markup,
        flags=re.IGNORECASE,
    )
    return html.unescape(match.group(1)) if match else ""


def extract_atc_options(markup: str, *, level: int = 5) -> list[InfomedAtcOption]:
    """Extract ATC options from the Infomed advanced-search form.

    Level 5 is the default because broad ATC searches may be capped or return
    sparse/odd JSF result sets. Iterating the leaf options gives fuller
    coverage while still avoiding medicine-name targeting.
    """
    if level != 5:
        raise ValueError("Only ATC level 5 is currently supported")

    options: list[InfomedAtcOption] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"<option\b[^>]*\bvalue=[\"'](REF_CLASS_ATC:([A-Z][0-9]{2}[A-Z]{2}[0-9]{2}))[\"'][^>]*>"
        r"(.*?)</option>",
        markup,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        value, code, label_markup = match.groups()
        if code in seen:
            continue
        seen.add(code)
        options.append(InfomedAtcOption(
            value=html.unescape(value),
            code=code,
            label=_clean_text(label_markup),
        ))
    return options


def extract_result_detail_link_ids(markup: str) -> list[str]:
    """Return desktop result-table link ids used to open detail pages."""
    links: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"\bid=[\"'](mainForm:dt-medicamentos:\d+:linkNome)[\"']",
        markup,
        flags=re.IGNORECASE,
    ):
        link_id = html.unescape(match.group(1))
        if link_id in seen:
            continue
        seen.add(link_id)
        links.append(link_id)
    return links


def extract_result_count(markup: str) -> int:
    match = re.search(r"\btotal de\s+(\d+)\s+registos\b", markup, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _clean_export_cell(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def read_infomed_export(path: Path) -> list[dict[str, str]]:
    """Read an Infomed advanced-search Excel export as text rows."""
    df = pd.read_excel(path)
    return [
        {str(k): _clean_export_cell(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def combine_infomed_index_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Dedupe medicine-index rows from multiple ATC exports."""
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(row.get(field, "").casefold() for field in INDEX_KEY_FIELDS)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _presentation_sections(markup: str) -> list[str]:
    matches = list(re.finditer(r"\bembalagem-main-panel\b", markup, re.IGNORECASE))
    sections: list[str] = []
    for idx, match in enumerate(matches):
        start = max(0, markup.rfind("<", 0, match.start()))
        end = matches[idx + 1].start() if idx + 1 < len(matches) else match.start() + 30000
        sections.append(markup[start:end])
    return sections


def _presentation_text(section: str) -> str:
    bits: list[str] = []
    for match in re.finditer(
        r"<span\b[^>]*\bbtn\s+btn-link\b[^>]*>(.*?)</span>",
        section,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        text = _clean_text(match.group(1))
        if text and text not in bits:
            bits.append(text)
    return "; ".join(bits)


def parse_infomed_detail(markup: str) -> list[dict[str, str]]:
    """Parse one Infomed detail HTML page into delegate-ready extract rows."""
    base = {
        "Nome do Medicamento": (
            _text_by_id(markup, "detalheMedNomeMed")
            or _value_after_label(markup, "Nome do Medicamento:")
        ),
        "Substância Ativa/DCI": _value_after_label(markup, "Substância Ativa/DCI:"),
        "Forma Farmacêutica": _value_after_label(markup, "Forma Farmacêutica:"),
        "Dosagem": _value_after_label(markup, "Dosagem:"),
        "Titular de AIM": _value_after_label(markup, "Titular de AIM:"),
        "Via": _value_after_label(markup, "Via(s) de Administração:"),
        "ATC": _value_after_label(markup, "Classificação ATC:"),
    }

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for section in _presentation_sections(markup):
        pvp = _normalise_price(_value_after_label(section, "PVP:"))
        if not pvp or not _has_numeric_price(pvp):
            continue
        presentation = _presentation_text(section)
        code = _value_after_label(section, "Número de Registo:")
        dedupe_key = (code, presentation, pvp)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        row = {
            **base,
            "Apresentação": presentation,
            "PVP": pvp,
            "Código": code,
            "CNPEM": _value_after_label(section, "CNPEM:"),
        }
        rows.append({field: row.get(field, "") for field in FIELDNAMES})
    return rows


def write_infomed_extract(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
