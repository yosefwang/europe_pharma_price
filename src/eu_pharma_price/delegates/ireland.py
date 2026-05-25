"""Ireland country delegate (real PCRS druglist).

Reads the columns published in the PCRS druglist CSV (sspcrs.ie/druglist/pub).
Note: the column called `Reimbursement Price` is the *ingredient cost* per
S.I. 639/2019 — i.e., ex-factory + 8% wholesale mark-up (12% for fridge
items), excluding VAT. The PolicyInterpretation maps this to the
`pharmacy_purchase_price` comparison category.

Per decisions/005, rows with Reimbursement Price = 0 are filtered out and
emit a `policy_gap` anomaly instead. These are administrative markers
(High Tech medicines, reference-priced items, special-claim items) — not
pricing data — and including them as canonical records pollutes the
data profile.

Decisions: see decisions/003 and decisions/005.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from typing import Any

from ..schemas.records import CanonicalPriceRecord
from ..schemas.review import (
    AnomalyReport,
    AnomalyStatus,
    AnomalyType,
    Severity,
)
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
    price_includes_vat = False
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

    def _make_canonical(
        self,
        raw_record: RawRecord,
        snapshot_date: date,
        source_document_id: str,
    ) -> tuple[CanonicalPriceRecord | None, AnomalyReport | None]:
        """Override base to filter zero-priced rows per decisions/005.

        These rows are administrative markers (High Tech, reference-priced,
        special-claim items), not pricing data. They are not silent drops:
        each one emits a low-severity policy_gap anomaly with full
        provenance back to the raw record.
        """
        raw_value = raw_record.raw_fields.get(self.price_field, "")
        coerced = self._coerce_price(str(raw_value)) if raw_value else None
        if coerced is not None and coerced == 0:
            code = raw_record.raw_fields.get("Code", "")
            return None, AnomalyReport(
                id=str(uuid.uuid4()),
                country_code=self.country_code,
                anomaly_type=AnomalyType.policy_gap,
                severity=Severity.low,
                title="Zero-priced row excluded from canonical (decisions/005)",
                description=(
                    f"PCRS row {raw_record.row_index} (Code={code}) has "
                    f"Reimbursement Price=0.0; this is an administrative "
                    f"marker for High Tech / reference-priced / special-"
                    f"claim items, not pricing data. Per decisions/005 it "
                    f"is filtered from canonical and recorded here."
                ),
                evidence=[raw_record.id],
                reported_at=datetime.now(timezone.utc),
                reported_by=f"delegate.{self.country_code.lower()}",
                status=AnomalyStatus.open,
                affected_records=[raw_record.id],
            )
        return super()._make_canonical(
            raw_record, snapshot_date, source_document_id,
        )
