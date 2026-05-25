"""Portugal country delegate (Infarmed Infomed research extract)."""

from __future__ import annotations

import re
from typing import Any

from ..schemas.source import RawRecord
from ._simple_public_retail import PublicRetailDelegate, first_match


class PortugalDelegate(PublicRetailDelegate):
    country_code = "PT"
    default_currency = "EUR"
    delimiter = ";"
    decimal_separator = ","
    price_field = "PVP"
    field_mapping = {
        "Nome do Medicamento": "product_name",
        "Substância Ativa/DCI": "inn",
        "Forma Farmacêutica": "dosage_form",
        "Dosagem": "strength",
        "Titular de AIM": "manufacturer",
        "Código": "national_product_code",
    }
    local_field_descriptions = {
        "PVP": (
            "Infomed preço de venda ao público. Maps to "
            "comparison_category=public_retail_price."
        ),
    }

    def _derive_fields(self, raw_record: RawRecord) -> dict[str, Any]:
        presentation = raw_record.raw_fields.get("Apresentação", "")
        atc_match = re.search(
            r"\b([A-Z][0-9]{2}[A-Z]{2}[0-9]{2})\b",
            raw_record.raw_fields.get("ATC", ""),
        )
        return {
            "pack_size": first_match(presentation, [
                r"\b(\d+)\s+comprimidos?",
                r"\b(\d+)\s+c[aá]psulas?",
                r"\b(\d+)\s+frascos?",
                r"\b(\d+)\s+seringas?",
                r"\b(\d+)\s+unidade",
            ]),
            "atc_code": atc_match.group(1) if atc_match else None,
        }
