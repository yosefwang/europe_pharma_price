"""Belgium INAMI workbook helpers."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .capture import compute_file_hash
from .models import FetchMethod, FileEntry, SnapshotManifest


SHEET_NAME = "SSP PRICE_COMPARISON"


def read_inami_workbook(path: Path) -> list[dict[str, str]]:
    df = pd.read_excel(path, sheet_name=SHEET_NAME, dtype=str).fillna("")
    return [
        {str(k): str(v).strip() for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def write_inami_extract(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("rows must not be empty")
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def build_inami_manifest(
    *,
    snapshot_id: str,
    source_id: str,
    snapshot_date: str,
    source_url: str,
    file_path: Path,
    fetch_method: FetchMethod = FetchMethod.manual,
) -> SnapshotManifest:
    return SnapshotManifest(
        snapshot_id=snapshot_id,
        source_id=source_id,
        country_code="BE",
        snapshot_date=snapshot_date,
        fetched_at=datetime.now(timezone.utc),
        fetch_method=fetch_method,
        files=[FileEntry(
            filename=file_path.name,
            file_hash=compute_file_hash(file_path),
            file_size_bytes=file_path.stat().st_size,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )],
        source_url=source_url,
        robots_txt_compliant=True,
        tos_reviewed=True,
        notes="Belgium INAMI reimbursable specialties workbook",
    )
