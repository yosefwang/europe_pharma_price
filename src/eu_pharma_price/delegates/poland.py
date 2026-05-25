"""Poland country delegate (real Ministry of Health reimbursement list).

Reads the multi-sheet XLSX published by the Polish Ministry of Health
(obwieszczenie Ministra Zdrowia). Sheet A1 (Leki refundowane dostępne w
aptece) is the primary source for community-pharmacy pricing.

Each source row publishes four price columns; each is a different
comparison concept. The delegate emits ONE canonical record per
(raw_row × price_type) pair so each price can flow through the
two-gear rule independently with its own PolicyInterpretation.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ..normalization.dosage_forms import normalize_dosage_form
from ..schemas.records import CanonicalPriceRecord
from ..schemas.review import (
    AnomalyReport,
    AnomalyStatus,
    AnomalyType,
    Severity,
)
from ..schemas.source import RawRecord
from .base import BaseDelegate, DelegateResult, DelegateState

A1_HEADER_ROW_INDEX = 1  # 0-indexed; row 0 is the section title
PRIMARY_SHEET = "A1"

PRICE_COLUMNS = [
    "Cena zbytu netto",
    "Urzędowa cena zbytu",
    "Cena hurtowa brutto",
    "Cena detaliczna",
]

_FORM_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\btabl\.\s*powl\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\btabl\.\s*draż\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\btabl\.\s*musuj\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\btabl\b\.?", re.IGNORECASE), "tablet"),
    (re.compile(r"\bkaps\.\s*twarde\b\.?", re.IGNORECASE), "capsule"),
    (re.compile(r"\bkaps\.\s*miękkie\b\.?", re.IGNORECASE), "capsule"),
    (re.compile(r"\bkaps\b\.?", re.IGNORECASE), "capsule"),
    (re.compile(r"\binj\b\.?", re.IGNORECASE), "injection"),
    (re.compile(r"\broztwór do wstrzykiwań\b\.?", re.IGNORECASE), "injection"),
    (re.compile(r"\bzaw\.\s*do\s*wstrz\b\.?", re.IGNORECASE), "injection"),
    (re.compile(r"\bgranulat\b.*\bzawiesiny\s+doustnej\b", re.IGNORECASE),
     "granules_for_oral_suspension"),
    (re.compile(r"\bgranulat\b", re.IGNORECASE), "granules"),
    (re.compile(r"\bkoncentrat\b", re.IGNORECASE), "concentrate_for_solution_for_infusion"),
    (re.compile(r"\bkoncetrat\b", re.IGNORECASE), "concentrate_for_solution_for_infusion"),
    (re.compile(r"\bzawiesina\b", re.IGNORECASE), "suspension"),
    (re.compile(r"\btabletk[ai]\b.*\bpowlekane?\b", re.IGNORECASE), "tablet"),
    (re.compile(r"\btabletk[ai]\b", re.IGNORECASE), "tablet"),
    (re.compile(r"\bkapsułk[ai]\b", re.IGNORECASE), "capsule"),
    (re.compile(r"\bproszek\b.*\brozp\w* do\s+wstrz\b", re.IGNORECASE),
     "powder_for_solution_for_injection"),
    (re.compile(r"\bproszek\b.*\bi\s+rozpuszczalnik\b", re.IGNORECASE),
     "powder_and_solvent_for_injection"),
    (re.compile(r"\bsyrop\b\.?", re.IGNORECASE), "syrup"),
    (re.compile(r"\bzaw\.\s*do\s*nebul\b\.?", re.IGNORECASE), "nebuliser_suspension"),
    (re.compile(r"\bzaw\.\s*doustna\b\.?", re.IGNORECASE), "oral_suspension"),
    (re.compile(r"\bzaw\b\.?", re.IGNORECASE), "suspension"),
    (re.compile(r"\bkrem\b\.?", re.IGNORECASE), "cream"),
    (re.compile(r"\bmaść\b\.?", re.IGNORECASE), "ointment"),
    (re.compile(r"\bżel\b\.?", re.IGNORECASE), "gel"),
    (re.compile(r"\bplastry?\b\.?", re.IGNORECASE), "transdermal_patch"),
    (re.compile(r"\bczopki?\b\.?", re.IGNORECASE), "suppository"),
    (re.compile(r"\bglobulki?\b\.?", re.IGNORECASE), "pessary"),
    (re.compile(r"\baerozol\b\.?", re.IGNORECASE), "spray"),
    (re.compile(r"\bproszek\b\.?", re.IGNORECASE), "powder"),
    (re.compile(r"\bsaszetk", re.IGNORECASE), "sachet"),
    (re.compile(r"\bkrople\b\.?", re.IGNORECASE), "drops"),
    (re.compile(r"\broztwór\b\.?", re.IGNORECASE), "solution"),
    (re.compile(r"\bpłyn\b\.?", re.IGNORECASE), "solution"),
]


_STRENGTH_RE = re.compile(
    r"[0-9]+(?:[.,][0-9]+)?"
    r"(?:\s*\+\s*[0-9]+(?:[.,][0-9]+)?)?"
    r"\s*(?:mg|g|mcg|µg|ml|iu|j\.?\s*m\.?|%|mln|tys)",
    re.IGNORECASE,
)


def _looks_numeric_fragment(s: str) -> bool:
    """True when s looks like a fragment of a numeric value split by a
    comma-as-decimal (e.g. '03+66' after '29,03+66,66 mg' was split)."""
    s = s.strip()
    if not s:
        return False
    # Starts with digit and contains only numeric/decimal/operator chars
    # (no letters, no Polish form keywords).
    if not re.match(r"^[0-9]", s):
        return False
    # Must have no letter characters (excludes units like mg)
    if re.search(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", s):
        return False
    return True


def _parse_nazwa(nazwa: str) -> tuple[str, str | None, str | None]:
    """Parse 'Adeksa, tabl., 100 mg' -> (name, form, strength).

    Handles European comma-as-decimal ambiguity: the nazwa uses commas
    both as field separators and decimal markers inside numbers (e.g.,
    '29,03+66,66 mg' splits into fragments that must be re-joined).
    """
    if not nazwa:
        return ("", None, None)
    raw_parts = [p.strip() for p in nazwa.split(",")]
    # Re-join numeric-only fragments broken by comma-as-decimal.
    # Only start a merge when raw_parts[i] itself is a numeric fragment
    # (no letters); then keep absorbing while subsequent parts start
    # with a digit (covers the terminal '66 mg'-style fragment).
    parts: list[str] = []
    i = 0
    while i < len(raw_parts):
        merged = [raw_parts[i]]
        if _looks_numeric_fragment(raw_parts[i]):
            j = i + 1
            while j < len(raw_parts) and (
                _looks_numeric_fragment(raw_parts[j])
                or re.match(r"^[0-9]", raw_parts[j].strip())
            ):
                merged.append(raw_parts[j])
                j += 1
            parts.append(",".join(merged))
            i = j
        else:
            parts.append(raw_parts[i])
            i += 1

    name = parts[0] if parts else nazwa
    form: str | None = None
    strength: str | None = None
    for part in parts[1:]:
        if form is None:
            for pat, canonical in _FORM_PATTERNS:
                if pat.search(part):
                    form = canonical
                    break
        if strength is None and _STRENGTH_RE.search(part):
            strength = part
    if strength is not None:
        strength = strength.replace(",", ".")
        # Normalise European thousands-space (e.g. "25 000" → "25000")
        strength = re.sub(r"(\d)\s+(\d)", r"\1\2", strength)
    return name, form, strength


def _coerce_pl_decimal(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace(" ", "").replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


class PolandDelegate(BaseDelegate):
    country_code = "PL"
    default_currency = "PLN"
    delimiter = ";"  # legacy CSV path; XLSX path overrides parse via run()
    decimal_separator = ","
    encoding = "utf-8"
    price_field = "Cena hurtowa brutto"
    price_includes_vat_by_lane = True
    field_mapping: dict[str, str] = {
        "Substancja czynna": "inn",
        "Numer GTIN lub inny kod jednoznacznie identyfikujący produkt": "national_product_code",
        "Zawartość opakowania": "pack_size",
    }
    local_field_descriptions = {
        "Cena zbytu netto": (
            "Manufacturer net selling price (cena zbytu netto) in PLN, "
            "excluding VAT. Set in the Reimbursement Act 2011 framework "
            "as the regulated manufacturer-side reference. Maps to "
            "comparison_category=manufacturer_price."
        ),
        "Urzędowa cena zbytu": (
            "Official sale price (urzędowa cena zbytu) in PLN, including "
            "VAT. Equals Cena zbytu netto × (1 + VAT) where VAT is 8% "
            "for medicines. Maps to manufacturer_price with VAT."
        ),
        "Cena hurtowa brutto": (
            "Wholesale price gross (cena hurtowa brutto) in PLN, "
            "including VAT. The price at which wholesalers supply "
            "pharmacies, including the regulated wholesale margin "
            "(currently 5% on cena zbytu netto, capped) plus VAT. "
            "Maps to comparison_category=pharmacy_purchase_price."
        ),
        "Cena detaliczna": (
            "Retail price (cena detaliczna) in PLN, including pharmacy "
            "margin and VAT. Maps to comparison_category=public_retail_price."
        ),
    }

    def _read_xlsx_sheet_a1(
        self, file_path: Path,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        import openpyxl

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb[PRIMARY_SHEET]
        rows = list(ws.iter_rows(values_only=True))
        headers = [str(h).strip() if h is not None else f"col_{i}"
                   for i, h in enumerate(rows[A1_HEADER_ROW_INDEX])]
        data: list[dict[str, Any]] = []
        for row in rows[A1_HEADER_ROW_INDEX + 1:]:
            if all(v is None for v in row):
                continue
            data.append({headers[i]: row[i] if i < len(row) else None
                         for i in range(len(headers))})
        wb.close()
        return data, headers

    def _make_canonical_for_price(
        self,
        raw_record: RawRecord,
        snapshot_date: date,
        source_document_id: str,
        price_column: str,
    ) -> tuple[CanonicalPriceRecord | None, AnomalyReport | None]:
        rf = raw_record.raw_fields
        nazwa = rf.get("Nazwa  postać i dawka") or rf.get("Nazwa  postać i dawka leku") or ""
        product_name, form, strength = _parse_nazwa(str(nazwa))
        form_norm = normalize_dosage_form(
            form,
            country_code=self.country_code,
            source_field="Nazwa  postać i dawka",
            product_name=str(nazwa),
        )
        if not (product_name and form_norm.comparable_form_class and strength):
            return None, AnomalyReport(
                id=str(uuid.uuid4()),
                country_code=self.country_code,
                anomaly_type=AnomalyType.schema_mismatch,
                severity=Severity.medium,
                title=f"Could not parse Nazwa: {nazwa!r}",
                description=(
                    f"Row {raw_record.row_index}: 'Nazwa, postać i dawka' "
                    f"expected to follow 'name, postać, dawka' pattern; "
                    f"got {nazwa!r}; parse: name={product_name!r}, "
                    f"form={form!r}, normalised_form={form_norm.comparable_form_class!r}, "
                    f"strength={strength!r}"
                ),
                evidence=[raw_record.id],
                reported_at=datetime.now(timezone.utc),
                reported_by=f"delegate.{self.country_code.lower()}",
                status=AnomalyStatus.open,
                affected_records=[raw_record.id],
            )

        price_amount = _coerce_pl_decimal(rf.get(price_column))
        if price_amount is None:
            return None, AnomalyReport(
                id=str(uuid.uuid4()),
                country_code=self.country_code,
                anomaly_type=AnomalyType.schema_mismatch,
                severity=Severity.low,
                title=f"Unparseable {price_column}",
                description=(
                    f"Row {raw_record.row_index}: column '{price_column}' "
                    f"value {rf.get(price_column)!r} could not be coerced."
                ),
                evidence=[raw_record.id],
                reported_at=datetime.now(timezone.utc),
                reported_by=f"delegate.{self.country_code.lower()}",
                status=AnomalyStatus.open,
                affected_records=[raw_record.id],
            )

        pack_raw = rf.get("Zawartość opakowania")
        pack = str(pack_raw).strip() if pack_raw else ""
        national_code = rf.get(
            "Numer GTIN lub inny kod jednoznacznie identyfikujący produkt"
        ) or rf.get("Numer GTIN")
        # VAT-included flag: brutto columns include VAT, netto excludes
        includes_vat = "brutto" in price_column.lower() or "detaliczna" in price_column.lower() or "urzędowa" in price_column.lower()

        canonical = CanonicalPriceRecord(
            id=str(uuid.uuid4()),
            raw_record_id=raw_record.id,
            source_document_id=source_document_id,
            country_code=self.country_code,
            snapshot_date=snapshot_date,
            product_name=product_name,
            inn=str(rf.get("Substancja czynna") or "").strip().lower() or None,
            strength=strength,
            dosage_form=form_norm.comparable_form_class,
            pack_size=pack,
            price_amount=price_amount,
            price_currency=self.default_currency,
            price_type=price_column,
            price_includes_vat=includes_vat,
            dosage_form_raw=form,
            dosage_form_attributes=list(form_norm.presentation_attributes),
            dosage_form_normalization_method=form_norm.method,
            dosage_form_normalization_confidence=form_norm.confidence,
            dosage_form_rule_id=form_norm.rule_id,
            dosage_form_caveat=form_norm.caveat,
            route_of_administration=form_norm.route_family,
            national_product_code=str(national_code) if national_code else None,
        )
        return canonical, None

    def run(self, snapshot_dir: Path) -> DelegateResult:
        import json as _json
        manifest_path = snapshot_dir / "manifest.json"
        manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["country_code"] != self.country_code:
            raise ValueError(
                f"Country mismatch: delegate is {self.country_code}, "
                f"snapshot is {manifest['country_code']}."
            )
        snapshot_date = date.fromisoformat(manifest["snapshot_date"])
        source_document_id = manifest["snapshot_id"]

        raw_records: list[RawRecord] = []
        canonical_records: list[CanonicalPriceRecord] = []
        raw_to_canonical: list[dict[str, str]] = []
        anomalies: list[AnomalyReport] = []

        for file_entry in manifest["files"]:
            file_path = snapshot_dir / file_entry["filename"]
            rows, _headers = self._read_xlsx_sheet_a1(file_path)
            for idx, row in enumerate(rows):
                raw = RawRecord(
                    id=str(uuid.uuid4()),
                    source_document_id=source_document_id,
                    country_code=self.country_code,
                    extracted_at=datetime.now(timezone.utc),
                    row_index=idx,
                    raw_fields={k: (str(v) if v is not None else "")
                                for k, v in row.items()},
                    extraction_method="openpyxl_sheet_a1",
                    sheet_name=PRIMARY_SHEET,
                )
                raw_records.append(raw)
                # Emit one canonical per price column
                for price_col in PRICE_COLUMNS:
                    canonical, anomaly = self._make_canonical_for_price(
                        raw, snapshot_date, source_document_id, price_col,
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

        # Dedup anomalies (parse failure repeats once per price column)
        seen_titles: set[tuple[str, int]] = set()
        unique_anomalies: list[AnomalyReport] = []
        for a in anomalies:
            row_idx = a.affected_records[0] if a.affected_records else ""
            key = (a.title, hash(row_idx))
            if key in seen_titles:
                continue
            seen_titles.add(key)
            unique_anomalies.append(a)

        if unique_anomalies and not canonical_records:
            state = DelegateState.anomaly_reported
        elif unique_anomalies:
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
            anomalies=unique_anomalies,
            local_field_descriptions=self.local_field_descriptions,
        )
