"""Belgium country delegate (INAMI/RIZIV reimbursable specialties)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from ..comparison.product_identity import resolve_product_identity
from ..schemas.source import RawRecord
from ..sources.belgium_inami import read_inami_workbook
from ._simple_public_retail import first_match
from .base import BaseDelegate


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _normalise_form(raw: str | None) -> str | None:
    return _clean_cell(raw) or None


def _join_product_name(name: str, specific: str | None) -> str:
    base = _clean_cell(name)
    spec = _clean_cell(specific)
    if not base:
        return spec
    if not spec:
        return base
    if spec.casefold() in base.casefold():
        return base
    return f"{base} {spec}".strip()


class BelgiumDelegate(BaseDelegate):
    country_code = "BE"
    default_currency = "EUR"
    price_field = "SPB_PRICE"
    price_includes_vat = False
    decimal_separator = "."
    field_mapping = {
        "F_ORGA": "manufacturer",
        "S_COD": "national_product_code",
        "ATC_COD": "atc_code",
        "SI_CONC_NOM": "strength",
    }
    local_field_descriptions = {
        "SPB_PRICE": (
            "INAMI/RIZIV ex-factory price for reimbursable specialties; maps "
            "to comparison_category=manufacturer_price."
        ),
        "SPB_BASE": "Reimbursement base field retained as raw policy evidence.",
        "SPB_PUBLIC": "Public-price field retained as raw policy evidence.",
        "S_COD": "INAMI/RIZIV specialty pack code.",
        "S_NAM": (
            "Specialty name. For generic entries where no explicit INN field "
            "exists in the workbook, the delegate derives a candidate INN from "
            "the leading name token and validates it through the shared "
            "WHO/INN normaliser."
        ),
        "B_LBL_FR": (
            "French active-ingredient label used as the primary INN inference "
            "signal when the workbook has no explicit INN column."
        ),
        "B_LBL_NL": (
            "Dutch active-ingredient label used as secondary INN inference "
            "evidence."
        ),
        "S_NAM_SPECIF": "Specific presentation text.",
        "F_ORGA": "Responsible firm.",
        "ATC_COD": "ATC code.",
        "SI_CONC_NOM": "Active-ingredient strength text.",
        "S_PREP": "Preparation / pharmaceutical form text.",
        "RETARD": "Modified-release flag.",
        "VOLUME_TOTAL": "Total units or volume in the presentation.",
    }

    def parse_csv(self, file_path: Path) -> list[dict[str, str]]:
        return read_inami_workbook(file_path)

    def _coerce_price(self, raw_value: str) -> Decimal | None:
        text = _clean_cell(raw_value).replace("\xa0", "").replace("€", "")
        if not text:
            return None
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None

    def _derive_inn_from_fields(self, fields: dict[str, Any], product_name: str) -> str | None:
        identity = resolve_product_identity(
            self.repo_root,
            country_code=self.country_code,
            inn=(
                fields.get("INN")
                or fields.get("INN_NAM")
                or fields.get("DCI")
                or fields.get("SUBSTANCE")
            ),
            atc_code=fields.get("ATC_COD"),
            active_ingredient_labels=[
                fields.get("B_LBL_FR"),
                fields.get("B_LBL_NL"),
            ],
            product_name=product_name,
        )
        return identity.canonical_inn

    def _derive_fields(self, raw_record: RawRecord) -> dict[str, Any]:
        fields = raw_record.raw_fields
        name = _clean_cell(fields.get("S_NAM"))
        presentation = " ".join(
            part for part in [
                fields.get("RPT_PCK_LBL_FR", ""),
                fields.get("RPT_PCK_LBL_NL", ""),
            ]
            if part
        )
        inn = self._derive_inn_from_fields(fields, name)
        strength = fields.get("SI_CONC_NOM") or first_match(name, [
            r"(\d+(?:[,.]\d+)?\s*(?:mg/ml|mg|microgram|mcg|g|%))",
        ])
        pack_size = fields.get("VOLUME_TOTAL") or first_match(name, [
            r"\b(\d+)\s*(?:tablets?|comprim[eé]s?|capsules?|g[ée]lules?|vials?|flacons?)\b",
            r"\b(?:x|pack of)\s*(\d+)\b",
        ]) or first_match(presentation, [
            r"\b(\d+)\s+(?:comprim[eé]s?|tabletten?|capsules?|g[ée]lules?|flacons?|injectieflacons?|ampoules?)\b",
        ])
        form = first_match(" ".join([presentation, name]), [
            r"\b(tablets?|comprim[eé]s?|tabletten?)\b",
            r"\b(capsules?|g[ée]lules?)\b",
            r"\b(solution|suspension|po(e|è)dre)\s+(?:pour|voor)\s+(?:injection|injectie|perfusion|infusie)\b",
            r"\b(injectieflacon|ampoules?|injectable)\b",
            r"\b(perfusion|infusie)\b",
            r"\b(oral(?:e)?\s+solution|solution\s+buvable|orale?\s+suspension)\b",
        ])
        return {
            "product_name": _join_product_name(name, fields.get("S_NAM_SPECIF")),
            "inn": inn.lower() if inn else None,
            "strength": strength.replace(",", ".") if strength else None,
            "pack_size": pack_size,
            "dosage_form": _normalise_form(form),
        }

    def _make_canonical(self, raw_record, snapshot_date, source_document_id):
        if not _clean_cell(raw_record.raw_fields.get(self.price_field)):
            return None, None
        return super()._make_canonical(
            raw_record, snapshot_date, source_document_id,
        )
