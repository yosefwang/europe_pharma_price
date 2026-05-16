"""Source and raw record schemas."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FetchMethod(str, Enum):
    automated = "automated"
    manual = "manual"


class SourceDocument(BaseModel):
    id: str = Field(description="UUID")
    country_code: str = Field(min_length=2, max_length=2)
    source_url: str
    fetched_at: datetime
    file_hash: str = Field(description="SHA-256 hex digest")
    file_path: str
    media_type: str
    file_size_bytes: int = Field(ge=0)
    fetch_method: FetchMethod

    description: str | None = None
    robots_txt_compliant: bool | None = None
    tos_reviewed: bool | None = None
    superseded_by: str | None = None

    @field_validator("fetched_at")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware UTC")
        return v


class RawRecord(BaseModel):
    id: str = Field(description="UUID")
    source_document_id: str
    country_code: str = Field(min_length=2, max_length=2)
    extracted_at: datetime
    row_index: int = Field(ge=0)
    raw_fields: dict[str, Any]

    sheet_name: str | None = None
    extraction_method: str | None = None
    extraction_notes: str | None = None

    @field_validator("extracted_at")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("extracted_at must be timezone-aware UTC")
        return v
