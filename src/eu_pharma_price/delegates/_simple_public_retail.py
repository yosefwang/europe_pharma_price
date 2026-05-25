"""Helpers for public-retail-price delegates."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from .base import BaseDelegate


def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def parse_decimal(value: Any) -> Decimal | None:
    text = clean_cell(value)
    if not text:
        return None
    text = text.replace("\xa0", "").replace("€", "").strip()
    text = text.replace(".", "").replace(",", ".") if "," in text else text
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def as_text_rows_from_excel(file_path: Path) -> list[dict[str, str]]:
    df = pd.read_excel(file_path)
    return [
        {str(k): clean_cell(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


class PublicRetailDelegate(BaseDelegate):
    price_includes_vat = True

    def _coerce_price(self, raw_value: str) -> Decimal | None:
        return parse_decimal(raw_value)
