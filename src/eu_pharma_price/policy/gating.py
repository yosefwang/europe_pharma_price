"""Policy interpretation gating: blocks comparison without a usable interpretation.

Loads policy_interpretations.jsonl files and provides lookup helpers for the
comparison layer. The boundary is one-directional: this module reads
interpretations and answers "is this field comparable?" — it never modifies
prices, dates, or any numeric value.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ..schemas.policy import PolicyInterpretation


def _interpretations_path(repo_root: Path, country_code: str) -> Path:
    return (
        repo_root / "data" / "policy" / country_code.lower()
        / "policy_interpretations.jsonl"
    )


def load_interpretations(
    repo_root: Path, country_code: str
) -> list[PolicyInterpretation]:
    path = _interpretations_path(repo_root, country_code)
    if not path.exists():
        return []
    out: list[PolicyInterpretation] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(PolicyInterpretation.model_validate_json(line))
    return out


def interpretation_for_field(
    interpretations: list[PolicyInterpretation],
    price_type: str,
    on_date: date,
) -> PolicyInterpretation | None:
    """Return the current interpretation for (price_type, on_date), or None.

    A current interpretation has effective_from <= on_date and either
    effective_to is None or effective_to >= on_date.
    """
    candidates = [
        interp
        for interp in interpretations
        if interp.price_type == price_type
        and interp.effective_from <= on_date
        and (interp.effective_to is None or interp.effective_to >= on_date)
        and interp.superseded_by is None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda interp: (interp.effective_from, interp.authored_at))


def blocks_comparison(
    interpretation: PolicyInterpretation | None,
) -> tuple[bool, str | None]:
    """Return (blocked, reason). The comparison layer must call this.

    A field is blocked from comparison candidate construction when:
    - no interpretation exists for the field on the snapshot date
    - the interpretation maps the field to `unmapped_price_concept`
    - the interpretation maps the field to `not_comparable`
    """
    if interpretation is None:
        return True, "no policy interpretation for field"
    cat = interpretation.comparison_category.value
    if cat == "unmapped_price_concept":
        return True, "field is an unmapped price concept"
    if cat == "not_comparable":
        return True, "field has been adjudicated as not comparable"
    return False, None


def write_interpretations(
    repo_root: Path,
    country_code: str,
    interpretations: list[PolicyInterpretation],
) -> Path:
    path = _interpretations_path(repo_root, country_code)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [interp.model_dump_json() for interp in interpretations]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path
