"""Delegate runner: execute country delegates against captured snapshots
and write canonical artifacts and reports.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .base import DelegateResult, DelegateState
from .registry import get_delegate

CANONICAL_ROOT_NAME = "data/canonical"
REPORTS_DELEGATE_NAME = "reports/delegate"
REPORTS_ANOMALIES_NAME = "reports/anomalies"


def _decimal_to_str(value):
    return str(value) if isinstance(value, Decimal) else value


def write_canonical_parquet(
    result: DelegateResult, repo_root: Path
) -> dict[str, Path]:
    cc = result.country_code.lower()
    snap = result.snapshot_date.isoformat()
    out_dir = repo_root / CANONICAL_ROOT_NAME / cc / snap
    out_dir.mkdir(parents=True, exist_ok=True)

    prices_rows = []
    for rec in result.canonical_records:
        d = rec.model_dump(mode="json")
        d["price_amount"] = str(rec.price_amount)
        prices_rows.append(d)

    if prices_rows:
        df = pd.DataFrame(prices_rows)
        prices_path = out_dir / "prices.parquet"
        df.to_parquet(prices_path, index=False)
    else:
        prices_path = None

    if result.raw_to_canonical:
        link_df = pd.DataFrame(result.raw_to_canonical)
        link_path = out_dir / "raw_to_canonical.parquet"
        link_df.to_parquet(link_path, index=False)
    else:
        link_path = None

    raw_rows = []
    for rec in result.raw_records:
        raw_rows.append({
            "id": rec.id,
            "source_document_id": rec.source_document_id,
            "country_code": rec.country_code,
            "extracted_at": rec.extracted_at.isoformat(),
            "row_index": rec.row_index,
            "raw_fields_json": json.dumps(rec.raw_fields, ensure_ascii=False),
            "extraction_method": rec.extraction_method,
        })
    if raw_rows:
        raw_path = out_dir / "raw.parquet"
        pd.DataFrame(raw_rows).to_parquet(raw_path, index=False)
    else:
        raw_path = None

    return {"prices": prices_path, "raw_to_canonical": link_path, "raw": raw_path}


def write_delegate_report(result: DelegateResult, repo_root: Path) -> Path:
    cc = result.country_code.lower()
    snap = result.snapshot_date.isoformat()
    out_dir = repo_root / REPORTS_DELEGATE_NAME / cc
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{snap}.md"

    lines = [
        f"# Delegate Report — {result.country_code} — {snap}",
        "",
        f"**State:** `{result.state.value}`",
        f"**Raw records:** {len(result.raw_records)}",
        f"**Canonical records:** {len(result.canonical_records)}",
        f"**Anomalies:** {len(result.anomalies)}",
        "",
        "## Local field descriptions",
        "",
    ]
    if result.local_field_descriptions:
        for field, desc in result.local_field_descriptions.items():
            lines.append(f"### `{field}`")
            lines.append("")
            lines.append(desc)
            lines.append("")
    else:
        lines.append("_No local field descriptions provided._")
        lines.append("")

    lines.extend([
        "## Sample canonical records",
        "",
    ])
    for rec in result.canonical_records[:5]:
        lines.append(
            f"- `{rec.id[:8]}…` "
            f"{rec.product_name} ({rec.strength}, {rec.dosage_form}, "
            f"pack {rec.pack_size}) — "
            f"{rec.price_amount} {rec.price_currency} "
            f"[`{rec.price_type}`]"
        )
    if len(result.canonical_records) > 5:
        lines.append(f"- … and {len(result.canonical_records) - 5} more")
    lines.append("")

    if result.anomalies:
        lines.extend(["## Anomalies", ""])
        for a in result.anomalies:
            lines.append(f"- **{a.severity.value}**: {a.title}")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_anomaly_report(result: DelegateResult, repo_root: Path) -> Path | None:
    if not result.anomalies:
        return None
    cc = result.country_code.lower()
    snap = result.snapshot_date.isoformat()
    out_dir = repo_root / REPORTS_ANOMALIES_NAME / cc
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{snap}.md"
    lines = [f"# Anomalies — {result.country_code} — {snap}", ""]
    for a in result.anomalies:
        lines.extend([
            f"## {a.title}",
            "",
            f"- **Type:** `{a.anomaly_type.value}`",
            f"- **Severity:** `{a.severity.value}`",
            f"- **Status:** `{a.status.value}`",
            f"- **Reported by:** `{a.reported_by}`",
            f"- **Reported at:** `{a.reported_at.isoformat()}`",
            "",
            a.description,
            "",
        ])
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def run_delegate_for_snapshot(
    country_code: str, snapshot_dir: Path, repo_root: Path
) -> DelegateResult:
    delegate_cls = get_delegate(country_code)
    delegate = delegate_cls(repo_root=repo_root)
    return delegate.run(snapshot_dir)
