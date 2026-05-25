"""Czech Republic country delegate (SÚKL SCAU reimbursement list).

Reads the JSONL file produced by fetching the SÚKL API
(prehledy.sukl.gov.cz/dlp/v1/cau-scau/{kodSUKL}) for all products
in the "Seznam cen a úhrad" (SCAU) list.

Key pricing field: cenaPuvodce (manufacturer price, ex-VAT, in CZK).
Czech pharma VAT is 12% (reduced rate since 2024-01-01).
cenaPuvodce is the regulated maximum manufacturer price excluding VAT.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ..normalization.dosage_forms import (
    DosageFormNormalization,
    normalize_dosage_form,
)
from ..schemas.records import CanonicalPriceRecord
from ..schemas.review import (
    AnomalyReport,
    AnomalyStatus,
    AnomalyType,
    Severity,
)
from ..schemas.source import RawRecord
from .base import BaseDelegate, DelegateResult, DelegateState

_ATC_TO_INN: dict[str, str] | None = None


def _get_atc_to_inn(repo_root: Path) -> dict[str, str]:
    global _ATC_TO_INN
    if _ATC_TO_INN is not None:
        return _ATC_TO_INN
    from ..comparison.inn_normalizer import InnNormalizer
    n = InnNormalizer(repo_root)
    idx = n._get_index()
    mapping: dict[str, str] = {}
    for inn, atcs in idx.inn_to_atc.items():
        for atc in atcs:
            if atc not in mapping:
                mapping[atc] = inn
    _ATC_TO_INN = mapping
    return mapping

_FORM_MAP: dict[str, str] = {
    "TBL NOB": "tablet",
    "TBL FLM": "tablet",
    "TBL ENT": "tablet",
    "TBL PRO": "tablet",
    "TBL EFF": "tablet",
    "TBL ORD": "tablet",
    "TBL MND": "tablet",
    "TBL SLG": "tablet",
    "TBL DIS": "tablet",
    "CPS DUR": "capsule",
    "CPS MOL": "capsule",
    "CPS END": "capsule",
    "INJ SOL": "injection",
    "INJ SOL ISP": "injection",
    "INJ SOL PEP": "injection",
    "INF SOL": "infusion",
    "INF CNC": "infusion",
    "DRM GEL": "gel",
    "OPH GTT": "eye_drops",
    "NAS SPR": "nasal_spray",
}


def _normalize_form(form_code: str) -> str:
    result = _normalize_form_result(form_code)
    return result.comparable_form_class or ""


def _normalize_form_result(form_code: str) -> DosageFormNormalization:
    if not form_code:
        return normalize_dosage_form(None, country_code="CZ", source_field="lekovaFormaKod")
    return normalize_dosage_form(
        form_code.strip(),
        country_code="CZ",
        source_field="lekovaFormaKod",
    )


def _parse_pack_size(baleni: str) -> str:
    if not baleni:
        return ""
    m = re.match(r"(\d+)", baleni.strip())
    return m.group(1) if m else baleni.strip()


class CzechiaDelegate(BaseDelegate):
    country_code = "CZ"
    default_currency = "CZK"
    field_mapping: dict[str, str] = {}
    price_field = "cenaPuvodce"
    price_includes_vat_by_lane = True
    decimal_separator = "."

    local_field_descriptions = {
        "cenaPuvodce": "Manufacturer price ex-VAT (CZK)",
        "maxCenaLekarna": "Maximum pharmacy retail price inc-VAT (CZK)",
        "uhrada": "Reimbursement amount from health insurance (CZK)",
        "kodSUKL": "SÚKL product code (7-digit)",
        "ATCkod": "ATC code from SÚKL",
        "lekovaFormaKod": "Dosage form code (SÚKL codelist)",
        "sila": "Strength as registered",
        "baleni": "Pack size as registered",
    }

    def run(self, snapshot_date: date | Path) -> DelegateResult:
        if isinstance(snapshot_date, Path):
            snapshot_date = date.fromisoformat(snapshot_date.name)
        raw_dir = self.repo_root / "data" / "raw" / "cz" / str(snapshot_date)
        jsonl_path = raw_dir / "sukl_scau_all.jsonl"

        if not jsonl_path.exists():
            return DelegateResult(
                country_code=self.country_code,
                snapshot_date=snapshot_date,
                state=DelegateState.not_started,
                raw_records=[],
                canonical_records=[],
                raw_to_canonical=[],
                anomalies=[],
                local_field_descriptions=self.local_field_descriptions,
            )

        source_doc_id = f"sukl-scau-{snapshot_date.isoformat()}"
        raw_records: list[RawRecord] = []
        canonical_records: list[CanonicalPriceRecord] = []
        raw_to_canonical: list[dict[str, str]] = []
        anomalies: list[AnomalyReport] = []

        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if "_error" in record:
                    continue
                if not record.get("cenaPuvodce"):
                    continue
                self._process_record(
                    record, snapshot_date, source_doc_id,
                    raw_records, canonical_records,
                    raw_to_canonical, anomalies,
                    price_field="cenaPuvodce",
                    price_type="cenaPuvodce",
                    includes_vat=False,
                )
                if record.get("maxCenaLekarna"):
                    self._process_record(
                        record, snapshot_date, source_doc_id,
                        raw_records, canonical_records,
                        raw_to_canonical, anomalies,
                        price_field="maxCenaLekarna",
                        price_type="maxCenaLekarna",
                        includes_vat=True,
                    )

        return DelegateResult(
            country_code=self.country_code,
            snapshot_date=snapshot_date,
            state=DelegateState.canonicalized,
            raw_records=raw_records,
            canonical_records=canonical_records,
            raw_to_canonical=raw_to_canonical,
            anomalies=anomalies,
            local_field_descriptions=self.local_field_descriptions,
        )

    def _process_record(
        self,
        record: dict[str, Any],
        snapshot_date: date,
        source_doc_id: str,
        raw_records: list[RawRecord],
        canonical_records: list[CanonicalPriceRecord],
        raw_to_canonical: list[dict[str, str]],
        anomalies: list[AnomalyReport],
        price_field: str = "cenaPuvodce",
        price_type: str = "cenaPuvodce",
        includes_vat: bool = False,
    ) -> None:
        raw_id = str(uuid.uuid4())
        raw_rec = RawRecord(
            id=raw_id,
            source_document_id=source_doc_id,
            country_code=self.country_code,
            extracted_at=datetime.now(timezone.utc),
            row_index=len(raw_records),
            raw_fields={k: str(v) if v is not None else ""
                        for k, v in record.items()
                        if k != "uhrady"},
        )
        raw_records.append(raw_rec)

        kod = record.get("kodSUKL", "")
        nazev = record.get("nazev", "")
        sila = record.get("sila", "")
        forma = record.get("lekovaFormaKod", "")
        baleni = record.get("baleni", "")
        atc = record.get("ATCkod", "")
        cena = record.get(price_field)

        dosage_form_result = _normalize_form_result(forma)
        dosage_form = dosage_form_result.comparable_form_class or ""
        pack_size = _parse_pack_size(baleni)

        if not sila or not dosage_form or not pack_size:
            anomalies.append(AnomalyReport(
                id=str(uuid.uuid4()),
                country_code=self.country_code,
                record_id=raw_id,
                anomaly_type=AnomalyType.schema_mismatch,
                severity=Severity.medium,
                status=AnomalyStatus.open,
                title=f"Missing field: {nazev}",
                description=(
                    f"Missing required field for {nazev}: "
                    f"sila={sila!r} forma={forma!r} baleni={baleni!r}"
                ),
                evidence=[f"kodSUKL={kod}, nazev={nazev}"],
                reported_at=datetime.now(timezone.utc),
                reported_by="cz-delegate",
                snapshot_date=snapshot_date,
            ))
            return

        canonical_id = str(uuid.uuid4())
        try:
            price_decimal = Decimal(str(cena))
        except (InvalidOperation, ValueError, TypeError):
            return

        canonical = CanonicalPriceRecord(
            id=canonical_id,
            raw_record_id=raw_id,
            source_document_id=source_doc_id,
            country_code=self.country_code,
            snapshot_date=snapshot_date,
            product_name=nazev,
            inn=_get_atc_to_inn(self.repo_root).get(atc, nazev.split(" ")[0].lower()) if atc else nazev.split(" ")[0].lower(),
            atc_code=atc if atc else None,
            strength=sila.upper(),
            dosage_form=dosage_form,
            pack_size=pack_size,
            price_amount=str(price_decimal),
            price_currency="CZK",
            price_type=price_type,
            price_includes_vat=includes_vat,
            dosage_form_raw=forma,
            dosage_form_attributes=list(dosage_form_result.presentation_attributes),
            dosage_form_normalization_method=dosage_form_result.method,
            dosage_form_normalization_confidence=dosage_form_result.confidence,
            dosage_form_rule_id=dosage_form_result.rule_id,
            dosage_form_caveat=dosage_form_result.caveat,
            manufacturer=None,
            national_product_code=kod,
            route_of_administration=dosage_form_result.route_family,
            unit_of_measure=None,
            notes=None,
        )
        canonical_records.append(canonical)
        raw_to_canonical.append({
            "raw_record_id": raw_id,
            "canonical_record_id": canonical_id,
        })
