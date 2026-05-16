"""Source register and snapshot manifest models."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    excel = "excel"
    csv = "csv"
    pdf = "pdf"
    html = "html"
    api = "api"
    other = "other"


class UpdateFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    irregular = "irregular"
    unknown = "unknown"


class FetchMethod(str, Enum):
    automated = "automated"
    manual = "manual"


class SourceStatus(str, Enum):
    registered = "registered"
    captured = "captured"
    hash_verified = "hash_verified"
    hash_mismatch = "hash_mismatch"
    pending_manual_refresh = "pending_manual_refresh"
    blocked = "blocked"


class SourceRegistryEntry(BaseModel):
    source_id: str = Field(description="UUID")
    country_code: str = Field(min_length=2, max_length=2)
    source_name: str
    source_url: str
    source_type: SourceType
    update_frequency: UpdateFrequency
    fetch_method: FetchMethod
    robots_txt_compliant: bool
    tos_reviewed: bool
    tos_permits_research: bool | None = None
    manual_refresh_reason: str | None = None
    registered_at: datetime
    registered_by: str
    status: SourceStatus = SourceStatus.registered
    notes: str | None = None

    @field_validator("registered_at")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("registered_at must be timezone-aware UTC")
        return v


class FileEntry(BaseModel):
    filename: str
    file_hash: str = Field(description="sha256:<hex_digest>")
    file_size_bytes: int = Field(ge=0)
    media_type: str

    @field_validator("file_hash")
    @classmethod
    def must_be_sha256(cls, v: str) -> str:
        if not v.startswith("sha256:"):
            raise ValueError("file_hash must start with 'sha256:'")
        hex_part = v.removeprefix("sha256:")
        if len(hex_part) != 64:
            raise ValueError("sha256 hex digest must be 64 characters")
        return v


class SnapshotManifest(BaseModel):
    snapshot_id: str = Field(description="UUID")
    source_id: str
    country_code: str = Field(min_length=2, max_length=2)
    snapshot_date: date
    fetched_at: datetime
    fetch_method: FetchMethod
    files: list[FileEntry] = Field(min_length=1)
    source_url: str
    robots_txt_compliant: bool
    tos_reviewed: bool
    notes: str | None = None

    @field_validator("fetched_at")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware UTC")
        return v
