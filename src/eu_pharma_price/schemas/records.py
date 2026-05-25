"""Canonical price record schema."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class CanonicalPriceRecord(BaseModel):
    id: str = Field(description="UUID")
    raw_record_id: str
    source_document_id: str
    country_code: str = Field(min_length=2, max_length=2)
    snapshot_date: date
    product_name: str
    inn: str | None = None
    atc_code: str | None = None
    strength: str
    dosage_form: str
    pack_size: str
    price_amount: Decimal
    price_currency: str = Field(min_length=3, max_length=3)
    price_type: str
    price_includes_vat: bool | None = None
    dosage_form_raw: str | None = None
    dosage_form_attributes: list[str] = Field(default_factory=list)
    dosage_form_normalization_method: str | None = None
    dosage_form_normalization_confidence: str | None = None
    dosage_form_rule_id: str | None = None
    dosage_form_caveat: str | None = None

    manufacturer: str | None = None
    national_product_code: str | None = None
    route_of_administration: str | None = None
    unit_of_measure: str | None = None
    notes: str | None = None

    @field_validator("price_currency")
    @classmethod
    def must_be_iso4217(cls, v: str) -> str:
        if not v.isalpha() or not v.isupper():
            raise ValueError("price_currency must be a 3-letter uppercase ISO 4217 code")
        return v
