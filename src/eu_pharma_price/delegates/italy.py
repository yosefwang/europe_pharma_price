"""Italy country delegate (AIFA Class A/H public lists)."""

from __future__ import annotations

from typing import Any

from ..schemas.source import RawRecord
from ._simple_public_retail import PublicRetailDelegate, first_match


class ItalyDelegate(PublicRetailDelegate):
    country_code = "IT"
    default_currency = "EUR"
    delimiter = ";"
    decimal_separator = ","
    encoding = "latin1"
    price_field = "Prezzo al pubblico"
    field_mapping = {
        "Principio Attivo": "inn",
        "Denominazione e Confezione": "product_name",
        "Titolare AIC": "manufacturer",
        "AIC": "national_product_code",
    }
    local_field_descriptions = {
        "Prezzo al pubblico": (
            "AIFA published public retail price. Maps to "
            "comparison_category=public_retail_price."
        ),
    }

    def parse_csv(self, file_path):
        rows = super().parse_csv(file_path)
        normalized = []
        for row in rows:
            out = dict(row)
            for key in list(out):
                if key.startswith("Prezzo al pubblico"):
                    out[self.price_field] = out[key]
            normalized.append(out)
        return normalized

    def _derive_fields(self, raw_record: RawRecord) -> dict[str, Any]:
        group = raw_record.raw_fields.get("Descrizione Gruppo", "")
        name = raw_record.raw_fields.get("Denominazione e Confezione", "")
        strength = first_match(group, [
            r"\b(\d+(?:[,.]\d+)?\s*(?:MG/ML|MG|MCG|G|%))\b",
        ])
        pack_size = first_match(group, [r"\b(\d+)\s+UNITA'"])
        form = first_match(" ".join([name, group]), [
            r"\b(cpr)\b",
            r"\b(cps)\b",
            r"\b(uso parenterale)\b",
            r"\b(orale sosp|orale soluz)\b",
        ])
        return {
            "strength": strength.replace(",", ".") if strength else None,
            "pack_size": pack_size,
            "dosage_form": form,
        }
