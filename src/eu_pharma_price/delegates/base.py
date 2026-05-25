"""Country delegate base class and shared utilities."""

import csv
import json
import uuid
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..normalization.dosage_forms import normalize_dosage_form
from ..schemas.records import CanonicalPriceRecord
from ..schemas.review import AnomalyReport, AnomalyStatus, AnomalyType, Severity
from ..schemas.source import RawRecord


class DelegateState(str, Enum):
    not_started = "not_started"
    source_captured = "source_captured"
    parsed = "parsed"
    canonicalized = "canonicalized"
    anomaly_reported = "anomaly_reported"
    needs_review = "needs_review"


class DelegateResult(BaseModel):
    country_code: str
    snapshot_date: date
    state: DelegateState
    raw_records: list[RawRecord]
    canonical_records: list[CanonicalPriceRecord]
    raw_to_canonical: list[dict[str, str]]
    anomalies: list[AnomalyReport]
    local_field_descriptions: dict[str, str]


class BaseDelegate(ABC):
    """Base class for country delegates.

    Subclasses must declare country_code, default_currency, field_mapping,
    decimal_separator, and price_field. Subclasses may override
    parse_csv() to handle custom encodings or separators.
    """

    country_code: str = ""
    default_currency: str = ""
    field_mapping: dict[str, str] = {}
    price_field: str = ""
    decimal_separator: str = "."
    delimiter: str = ","
    encoding: str = "utf-8"
    local_field_descriptions: dict[str, str] = {}
    price_includes_vat: bool | None = None
    price_includes_vat_by_lane: bool = False

    def __init__(self, repo_root: Path):
        if not self.country_code:
            raise ValueError(f"{type(self).__name__} must define country_code")
        if not self.default_currency:
            raise ValueError(f"{type(self).__name__} must define default_currency")
        if not self.price_field:
            raise ValueError(f"{type(self).__name__} must define price_field")
        if self.price_includes_vat is None and not self.price_includes_vat_by_lane:
            raise ValueError(
                f"{type(self).__name__} must define price_includes_vat "
                "or set price_includes_vat_by_lane=True"
            )
        self.repo_root = repo_root

    def parse_csv(self, file_path: Path) -> list[dict[str, str]]:
        with open(file_path, encoding=self.encoding, newline="") as f:
            reader = csv.DictReader(f, delimiter=self.delimiter)
            return [dict(row) for row in reader]

    def _derive_fields(self, raw_record: RawRecord) -> dict[str, Any]:
        """Hook for subclasses to derive canonical fields from raw fields.

        Default: no derivation. Subclasses override to extract values that
        are encoded inside other columns (e.g., dosage form embedded in
        a product-name string). Returns a dict keyed by canonical field
        name; only keys with non-None values are applied (and only when
        the canonical field is not already populated by the field_mapping).
        """
        return {}

    def _coerce_price(self, raw_value: str) -> Decimal | None:
        if raw_value is None or raw_value.strip() == "":
            return None
        normalised = raw_value.strip().replace(self.decimal_separator, ".")
        if self.decimal_separator == ",":
            normalised = normalised.replace(" ", "")
        try:
            return Decimal(normalised)
        except (InvalidOperation, ValueError):
            return None

    def _make_canonical(
        self,
        raw_record: RawRecord,
        snapshot_date: date,
        source_document_id: str,
    ) -> tuple[CanonicalPriceRecord | None, AnomalyReport | None]:
        raw_fields = raw_record.raw_fields
        mapped: dict[str, Any] = {}
        for source_field, canonical_field in self.field_mapping.items():
            if source_field in raw_fields:
                mapped[canonical_field] = raw_fields[source_field]

        # Country-specific derivations from raw fields (e.g., extract
        # dosage_form from a free-text product name when there is no
        # dedicated column). Subclasses override _derive_fields to
        # populate fields not directly mappable.
        derived = self._derive_fields(raw_record)
        for k, v in derived.items():
            if v is not None and not mapped.get(k):
                mapped[k] = v

        form_raw = mapped.get("dosage_form")
        form_norm = normalize_dosage_form(
            str(form_raw) if form_raw else None,
            country_code=self.country_code,
            source_field="dosage_form",
            product_name=str(mapped.get("product_name", "")),
        )
        if form_norm.comparable_form_class:
            mapped["dosage_form"] = form_norm.comparable_form_class

        required = ["product_name", "strength", "dosage_form", "pack_size"]
        missing = [f for f in required if not mapped.get(f)]
        if missing:
            return None, AnomalyReport(
                id=str(uuid.uuid4()),
                country_code=self.country_code,
                anomaly_type=AnomalyType.schema_mismatch,
                severity=Severity.medium,
                title=f"Missing required canonical fields: {', '.join(missing)}",
                description=(
                    f"Raw row {raw_record.row_index} could not be canonicalised: "
                    f"missing {missing}. Raw fields: {list(raw_fields.keys())}"
                ),
                evidence=[raw_record.id],
                reported_at=datetime.now(timezone.utc),
                reported_by=f"delegate.{self.country_code.lower()}",
                status=AnomalyStatus.open,
                affected_records=[raw_record.id],
            )

        price_raw = raw_fields.get(self.price_field)
        price_amount = self._coerce_price(price_raw) if price_raw else None
        if price_amount is None:
            return None, AnomalyReport(
                id=str(uuid.uuid4()),
                country_code=self.country_code,
                anomaly_type=AnomalyType.schema_mismatch,
                severity=Severity.medium,
                title=f"Unparseable price value: {price_raw!r}",
                description=(
                    f"Raw row {raw_record.row_index}: column '{self.price_field}' "
                    f"value {price_raw!r} could not be coerced to Decimal."
                ),
                evidence=[raw_record.id],
                reported_at=datetime.now(timezone.utc),
                reported_by=f"delegate.{self.country_code.lower()}",
                status=AnomalyStatus.open,
                affected_records=[raw_record.id],
            )

        canonical = CanonicalPriceRecord(
            id=str(uuid.uuid4()),
            raw_record_id=raw_record.id,
            source_document_id=source_document_id,
            country_code=self.country_code,
            snapshot_date=snapshot_date,
            product_name=str(mapped["product_name"]),
            strength=str(mapped["strength"]),
            dosage_form=str(mapped["dosage_form"]),
            pack_size=str(mapped["pack_size"]),
            price_amount=price_amount,
            price_currency=self.default_currency,
            price_type=self.price_field,
            price_includes_vat=self.price_includes_vat,
            dosage_form_raw=form_norm.raw_value,
            dosage_form_attributes=list(form_norm.presentation_attributes),
            dosage_form_normalization_method=form_norm.method,
            dosage_form_normalization_confidence=form_norm.confidence,
            dosage_form_rule_id=form_norm.rule_id,
            dosage_form_caveat=form_norm.caveat,
            manufacturer=mapped.get("manufacturer"),
            national_product_code=mapped.get("national_product_code"),
            inn=mapped.get("inn"),
            atc_code=mapped.get("atc_code"),
            route_of_administration=form_norm.route_family,
        )
        return canonical, None

    def run(self, snapshot_dir: Path) -> DelegateResult:
        manifest_path = snapshot_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        if manifest["country_code"] != self.country_code:
            raise ValueError(
                f"Country mismatch: delegate is {self.country_code}, "
                f"snapshot is {manifest['country_code']}. "
                "Delegates must not read other countries' data."
            )

        snapshot_date = date.fromisoformat(manifest["snapshot_date"])
        source_document_id = manifest["snapshot_id"]

        raw_records: list[RawRecord] = []
        canonical_records: list[CanonicalPriceRecord] = []
        raw_to_canonical: list[dict[str, str]] = []
        anomalies: list[AnomalyReport] = []

        for file_entry in manifest["files"]:
            file_path = snapshot_dir / file_entry["filename"]
            rows = self.parse_csv(file_path)
            for idx, row in enumerate(rows):
                raw = RawRecord(
                    id=str(uuid.uuid4()),
                    source_document_id=source_document_id,
                    country_code=self.country_code,
                    extracted_at=datetime.now(timezone.utc),
                    row_index=idx,
                    raw_fields=row,
                    extraction_method="csv_dictreader",
                )
                raw_records.append(raw)

                canonical, anomaly = self._make_canonical(
                    raw, snapshot_date, source_document_id
                )
                if canonical is not None:
                    canonical_records.append(canonical)
                    raw_to_canonical.append({
                        "canonical_id": canonical.id,
                        "raw_record_id": raw.id,
                        "source_document_id": source_document_id,
                        "snapshot_date": snapshot_date.isoformat(),
                    })
                if anomaly is not None:
                    anomalies.append(anomaly)

        if anomalies and not canonical_records:
            state = DelegateState.anomaly_reported
        elif anomalies:
            state = DelegateState.needs_review
        elif canonical_records:
            state = DelegateState.canonicalized
        else:
            state = DelegateState.parsed

        return DelegateResult(
            country_code=self.country_code,
            snapshot_date=snapshot_date,
            state=state,
            raw_records=raw_records,
            canonical_records=canonical_records,
            raw_to_canonical=raw_to_canonical,
            anomalies=anomalies,
            local_field_descriptions=self.local_field_descriptions,
        )
