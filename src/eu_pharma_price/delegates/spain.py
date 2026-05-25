"""Spain country delegate (Ministerio de Sanidad Nomenclator)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..schemas.source import RawRecord
from ._simple_public_retail import PublicRetailDelegate, as_text_rows_from_excel, first_match


class SpainDelegate(PublicRetailDelegate):
    country_code = "ES"
    default_currency = "EUR"
    delimiter = ";"
    decimal_separator = ","
    price_field = "Precio de venta al público con IVA"
    field_mapping = {
        "Nombre del producto farmacéutico": "product_name",
        "Principio activo o asociación de principios activos": "inn",
        "Nombre del laboratorio ofertante": "manufacturer",
        "Código Nacional": "national_product_code",
    }
    local_field_descriptions = {
        "Precio de venta al público con IVA": (
            "Spanish Nomenclator public retail price including VAT. Maps to "
            "comparison_category=public_retail_price."
        ),
    }

    def parse_csv(self, file_path: Path) -> list[dict[str, str]]:
        if file_path.suffix.lower() == ".xls":
            return as_text_rows_from_excel(file_path)
        return super().parse_csv(file_path)

    def _derive_fields(self, raw_record: RawRecord) -> dict[str, Any]:
        name = raw_record.raw_fields.get("Nombre del producto farmacéutico", "")
        strength = first_match(name, [
            r"(\d+(?:[,.]\d+)?\s*(?:mg/ml|mg|microgramos|mcg|g|%))",
        ])
        pack_size = first_match(name, [
            r",\s*(\d+)\s+comprimidos?",
            r"\b(\d+)\s+comprimidos?",
            r"\b(\d+)\s+c[aá]psulas?",
            r"\b(\d+)\s+frascos?",
            r"\b(\d+)\s+viales?",
        ])
        form = first_match(name, [
            r"\b(comprimidos?(?:\s+gastrorresistentes)?)\b",
            r"\b(c[aá]psulas?)\b",
            r"\b(soluci[oó]n\s+inyectable)\b",
            r"\b(jarabe|suspensi[oó]n oral|soluci[oó]n oral)\b",
        ])
        return {
            "strength": strength.replace(",", ".") if strength else None,
            "pack_size": pack_size,
            "dosage_form": form,
        }

    def _make_canonical(self, raw_record, snapshot_date, source_document_id):
        if not raw_record.raw_fields.get("Tipo de fármaco"):
            return None, None
        price = raw_record.raw_fields.get(self.price_field)
        if price in (None, ""):
            return None, None
        return super()._make_canonical(
            raw_record, snapshot_date, source_document_id,
        )
