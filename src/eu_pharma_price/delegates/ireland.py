"""Ireland country delegate (real PCRS druglist).

Reads the columns published in the PCRS druglist CSV (sspcrs.ie/druglist/pub).
Note: the column called `Reimbursement Price` is the *ingredient cost* per
S.I. 639/2019 — i.e., ex-factory + 8% wholesale mark-up (12% for fridge
items), excluding VAT. The PolicyInterpretation maps this to the
`pharmacy_purchase_price` comparison category.

Decision: see decisions/003-pcrs-reimbursement-price-is-pharmacy-purchase-price.md
"""

from __future__ import annotations

import re
from typing import Any

from ..schemas.source import RawRecord
from .base import BaseDelegate

_DRUG_NAME_FORM_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bFilm Coated Tabs?\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bChewable Tabs?\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bDispersible Tabs?\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bSublingual Tabs?\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bOrodispersible Tabs?\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bModified Release Tabs?\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bProlonged Release Tabs?\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bEffervescent Tabs?\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bGastro-Resistant Tabs?\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bTabs?\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bHard Caps?\b\.?", re.IGNORECASE), "capsule"),
    (re.compile(r"\bSoft Caps?\b\.?", re.IGNORECASE), "capsule"),
    (re.compile(r"\bModified Release Caps?\b\.?", re.IGNORECASE), "capsule"),
    (re.compile(r"\bGastro-Resistant Caps?\b\.?", re.IGNORECASE), "capsule"),
    (re.compile(r"\bCaps?\b\.?", re.IGNORECASE), "capsule"),
    (re.compile(r"\bOral Susp\b\.?", re.IGNORECASE), "oral_suspension"),
    (re.compile(r"\bSusp\b\.?", re.IGNORECASE), "suspension"),
    (re.compile(r"\bOral Soln\b\.?", re.IGNORECASE), "oral_solution"),
    (re.compile(r"\bSoln for Inj\b\.?", re.IGNORECASE), "injection"),
    (re.compile(r"\bSoln\b\.?", re.IGNORECASE), "solution"),
    (re.compile(r"\bInj\b\.?", re.IGNORECASE), "injection"),
    (re.compile(r"\bAmpoules?\b", re.IGNORECASE), "injection"),
    (re.compile(r"\bVial\b", re.IGNORECASE), "injection"),
    (re.compile(r"\b(Pre-Filled|Prefilled)\s+(Pen|Syringe)\b", re.IGNORECASE),
     "injection"),
    (re.compile(r"\bPen\b", re.IGNORECASE), "injection"),
    (re.compile(r"\bSyrup\b\.?", re.IGNORECASE), "syrup"),
    (re.compile(r"\bMixture\b\.?", re.IGNORECASE), "oral_liquid"),
    (re.compile(r"\bDrops\b\.?", re.IGNORECASE), "drops"),
    (re.compile(r"\bSpray\b\.?", re.IGNORECASE), "spray"),
    (re.compile(r"\bGel\b\.?", re.IGNORECASE), "gel"),
    (re.compile(r"\bCream\b\.?", re.IGNORECASE), "cream"),
    (re.compile(r"\bOint\b\.?", re.IGNORECASE), "ointment"),
    (re.compile(r"\bPatch\b\.?", re.IGNORECASE), "transdermal_patch"),
    (re.compile(r"\bSachets?\b", re.IGNORECASE), "sachet"),
    (re.compile(r"\bPowder\b\.?", re.IGNORECASE), "powder"),
    (re.compile(r"\bSuppositor(y|ies)\b", re.IGNORECASE), "suppository"),
    (re.compile(r"\bPessar(y|ies)\b", re.IGNORECASE), "pessary"),
]


def _extract_dosage_form(drug_name: str) -> str | None:
    if not drug_name:
        return None
    for pattern, form in _DRUG_NAME_FORM_PATTERNS:
        if pattern.search(drug_name):
            return form
    return None


class IrelandDelegate(BaseDelegate):
    country_code = "IE"
    default_currency = "EUR"
    delimiter = ","
    decimal_separator = "."
    encoding = "utf-8"
    price_field = "Reimbursement Price"
    field_mapping = {
        "Drug Name": "product_name",
        "INN": "inn",
        "Strength Measure": "strength",
        "Pack Size": "pack_size",
        "Code": "national_product_code",
        "Non Proprietary Name": "manufacturer",
    }
    local_field_descriptions = {
        "Reimbursement Price": (
            "Published in the PCRS druglist as 'Reimbursement Price'. Per "
            "S.I. No. 639/2019 Article 2, this column is the 'ingredient "
            "cost', defined as the ex-factory price plus a wholesale "
            "mark-up of 8% (or 12% for fridge items). It excludes VAT and "
            "excludes pharmacy mark-up and dispensing fees (paid "
            "separately under GMS/DPS/LTI). Maps to comparison category "
            "pharmacy_purchase_price."
        ),
        "Code": (
            "PCRS-assigned national product code. Stable per pack but "
            "country-specific — does not interoperate with EAN/CIP codes."
        ),
        "INN": (
            "International Nonproprietary Name as published by PCRS. "
            "Approximately 88% of rows in the May 2026 download carry "
            "an INN; missing INNs typically indicate combination "
            "products, dental items, or ostomy items not in scope."
        ),
    }

    def _derive_fields(self, raw_record: RawRecord) -> dict[str, Any]:
        drug_name = raw_record.raw_fields.get("Drug Name", "")
        return {"dosage_form": _extract_dosage_form(drug_name)}
