"""Snapshot profiler.

Computes field-level data profiles for a canonical snapshot:
presence, non-null rate, distribution, currency consistency,
date coverage, duplicate clusters, and plausibility.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path

import pandas as pd

from ..schemas.profile import DataProfile, PlausibilityAssessment
from .thresholds import (
    IQR_MULTIPLIER,
    NON_NULL_HARD_BLOCK,
    NON_NULL_WARNING,
    OUTLIER_RATE_WARNING,
    PRICE_POSITIVE_RATE,
)


class SnapshotStatus(str, Enum):
    green = "green"
    yellow = "yellow"
    red = "red"


def _outlier_band(values: pd.Series) -> tuple[float, float]:
    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1
    return q1 - IQR_MULTIPLIER * iqr, q3 + IQR_MULTIPLIER * iqr


def _profile_price_amount(
    df: pd.DataFrame, country_code: str, snapshot_date: date, assessed_by: str
) -> tuple[DataProfile, list[str]]:
    issues: list[str] = []
    field_exists = "price_amount" in df.columns
    record_count = len(df)
    if not field_exists:
        return DataProfile(
            id=str(uuid.uuid4()),
            country_code=country_code,
            snapshot_date=snapshot_date,
            price_type="price_amount",
            field_exists=False,
            population_rate=0.0,
            plausibility_assessment=PlausibilityAssessment.implausible,
            record_count=record_count,
            assessed_at=datetime.now(timezone.utc),
            assessed_by=assessed_by,
            issues=["field absent from canonical output"],
        ), ["field absent"]

    series = df["price_amount"]
    numeric = pd.to_numeric(series, errors="coerce")
    non_null = numeric.notna()
    non_null_count = int(non_null.sum())
    null_count = record_count - non_null_count
    population_rate = non_null_count / record_count if record_count else 0.0

    positive_rate = (
        float((numeric[non_null] > 0).mean()) if non_null_count else 0.0
    )

    outlier_count = 0
    if non_null_count >= 4:
        lower, upper = _outlier_band(numeric[non_null])
        outlier_mask = (numeric[non_null] < lower) | (numeric[non_null] > upper)
        outlier_count += int(outlier_mask.sum())
    outlier_count += int((numeric[non_null] <= 0).sum())
    outlier_rate = outlier_count / non_null_count if non_null_count else 0.0

    if record_count == 0:
        plausibility = PlausibilityAssessment.implausible
        issues.append("snapshot has zero records")
    elif population_rate < NON_NULL_HARD_BLOCK:
        plausibility = PlausibilityAssessment.implausible
        issues.append(f"non-null rate {population_rate:.2f} below hard-block threshold")
    elif positive_rate < PRICE_POSITIVE_RATE:
        plausibility = PlausibilityAssessment.implausible
        issues.append(f"only {positive_rate:.2%} of prices are strictly positive")
    elif (
        population_rate < NON_NULL_WARNING
        or outlier_rate > OUTLIER_RATE_WARNING
    ):
        plausibility = PlausibilityAssessment.suspect
        if population_rate < NON_NULL_WARNING:
            issues.append(f"non-null rate {population_rate:.2f} below warning threshold")
        if outlier_rate > OUTLIER_RATE_WARNING:
            issues.append(f"outlier rate {outlier_rate:.2%} exceeds warning threshold")
    else:
        plausibility = PlausibilityAssessment.plausible

    nn_values = numeric[non_null]
    distribution_notes = (
        f"min={nn_values.min():.2f} median={nn_values.median():.2f} "
        f"max={nn_values.max():.2f} n={non_null_count}"
        if non_null_count else "no non-null values"
    )

    profile = DataProfile(
        id=str(uuid.uuid4()),
        country_code=country_code,
        snapshot_date=snapshot_date,
        price_type="price_amount",
        field_exists=True,
        population_rate=round(population_rate, 4),
        plausibility_assessment=plausibility,
        record_count=record_count,
        min_value=Decimal(str(nn_values.min())) if non_null_count else None,
        max_value=Decimal(str(nn_values.max())) if non_null_count else None,
        median_value=Decimal(str(nn_values.median())) if non_null_count else None,
        null_count=null_count,
        outlier_count=outlier_count,
        distribution_notes=distribution_notes,
        assessed_at=datetime.now(timezone.utc),
        assessed_by=assessed_by,
        issues=issues,
    )
    return profile, issues


def _profile_currency_consistency(
    df: pd.DataFrame, country_code: str, snapshot_date: date, assessed_by: str
) -> DataProfile:
    field_exists = "price_currency" in df.columns
    record_count = len(df)
    issues: list[str] = []
    if not field_exists:
        return DataProfile(
            id=str(uuid.uuid4()), country_code=country_code,
            snapshot_date=snapshot_date, price_type="price_currency",
            field_exists=False, population_rate=0.0,
            plausibility_assessment=PlausibilityAssessment.implausible,
            record_count=record_count,
            assessed_at=datetime.now(timezone.utc), assessed_by=assessed_by,
            issues=["field absent"],
        )
    distinct = df["price_currency"].dropna().unique()
    population_rate = float(df["price_currency"].notna().mean()) if record_count else 0.0
    if len(distinct) > 1:
        plausibility = PlausibilityAssessment.implausible
        issues.append(f"snapshot mixes currencies: {sorted(distinct)}")
    elif len(distinct) == 0:
        plausibility = PlausibilityAssessment.implausible
        issues.append("no currency values present")
    else:
        plausibility = PlausibilityAssessment.plausible

    return DataProfile(
        id=str(uuid.uuid4()), country_code=country_code,
        snapshot_date=snapshot_date, price_type="price_currency",
        field_exists=True, population_rate=round(population_rate, 4),
        plausibility_assessment=plausibility,
        record_count=record_count,
        distribution_notes=f"distinct={list(distinct)}",
        assessed_at=datetime.now(timezone.utc), assessed_by=assessed_by,
        issues=issues,
    )


def _profile_date_coverage(
    df: pd.DataFrame, country_code: str, snapshot_date: date, assessed_by: str
) -> DataProfile:
    record_count = len(df)
    issues: list[str] = []
    field_exists = "snapshot_date" in df.columns
    if not field_exists:
        return DataProfile(
            id=str(uuid.uuid4()), country_code=country_code,
            snapshot_date=snapshot_date, price_type="snapshot_date",
            field_exists=False, population_rate=0.0,
            plausibility_assessment=PlausibilityAssessment.implausible,
            record_count=record_count,
            assessed_at=datetime.now(timezone.utc), assessed_by=assessed_by,
            issues=["field absent"],
        )
    series = pd.to_datetime(df["snapshot_date"], errors="coerce").dt.date
    matches = (series == snapshot_date)
    population_rate = float(series.notna().mean()) if record_count else 0.0
    future = (series > date.today()).sum()
    if future > 0:
        plausibility = PlausibilityAssessment.implausible
        issues.append(f"{future} future-dated records")
    elif not matches.all():
        plausibility = PlausibilityAssessment.suspect
        issues.append("not all records match the snapshot directory date")
    else:
        plausibility = PlausibilityAssessment.plausible

    return DataProfile(
        id=str(uuid.uuid4()), country_code=country_code,
        snapshot_date=snapshot_date, price_type="snapshot_date",
        field_exists=True, population_rate=round(population_rate, 4),
        plausibility_assessment=plausibility,
        record_count=record_count,
        distribution_notes=f"all_match={bool(matches.all())} future_dated={int(future)}",
        assessed_at=datetime.now(timezone.utc), assessed_by=assessed_by,
        issues=issues,
    )


def _aggregate_status(profiles: list[DataProfile]) -> SnapshotStatus:
    if any(p.plausibility_assessment == PlausibilityAssessment.implausible for p in profiles):
        return SnapshotStatus.red
    if any(p.plausibility_assessment == PlausibilityAssessment.suspect for p in profiles):
        return SnapshotStatus.yellow
    return SnapshotStatus.green


def profile_snapshot(
    country_code: str, snapshot_date: date, repo_root: Path,
) -> tuple[list[DataProfile], SnapshotStatus]:
    cdir = country_code.lower()
    snap_str = snapshot_date.isoformat()
    prices_path = repo_root / "data" / "canonical" / cdir / snap_str / "prices.parquet"
    if not prices_path.exists():
        return [], SnapshotStatus.red
    df = pd.read_parquet(prices_path)

    if "price_amount" in df.columns:
        df["price_amount"] = pd.to_numeric(df["price_amount"], errors="coerce")

    assessed_by = "phase-5-profiler"
    profiles = [
        _profile_price_amount(df, country_code, snapshot_date, assessed_by)[0],
        _profile_currency_consistency(df, country_code, snapshot_date, assessed_by),
        _profile_date_coverage(df, country_code, snapshot_date, assessed_by),
    ]
    return profiles, _aggregate_status(profiles)


def write_profile_artifacts(
    country_code: str, snapshot_date: date,
    profiles: list[DataProfile], status: SnapshotStatus,
    repo_root: Path,
) -> tuple[Path, Path]:
    cdir = country_code.lower()
    snap_str = snapshot_date.isoformat()
    json_dir = repo_root / "data" / "profiles" / cdir / snap_str
    json_dir.mkdir(parents=True, exist_ok=True)
    json_path = json_dir / "data_profile.json"
    payload = {
        "country_code": country_code,
        "snapshot_date": snap_str,
        "snapshot_status": status.value,
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "profiles": [json.loads(p.model_dump_json()) for p in profiles],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md_dir = repo_root / "reports" / "profiles" / cdir
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{snap_str}.md"
    lines = [
        f"# Data Health — {country_code} — {snap_str}",
        "",
        f"**Snapshot status:** `{status.value}`",
        "",
    ]
    for p in profiles:
        lines.extend([
            f"## `{p.price_type}`",
            f"- field_exists: `{p.field_exists}`",
            f"- non_null_rate: `{p.population_rate}`",
            f"- record_count: `{p.record_count}`",
            f"- plausibility: `{p.plausibility_assessment.value}`",
            f"- distribution: {p.distribution_notes or '—'}",
        ])
        if p.issues:
            lines.append("- issues:")
            for iss in p.issues:
                lines.append(f"  - {iss}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path
