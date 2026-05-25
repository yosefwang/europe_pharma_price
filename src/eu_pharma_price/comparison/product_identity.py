"""Product identity resolution before comparison indexing.

Country delegates often have different identity evidence: explicit INN fields,
ATC codes, active-ingredient labels, or only product names. This module keeps
the fallback policy in one comparison-layer place so country delegates do not
each invent their own brand/INN heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .inn_normalizer import InnNormalizer


@dataclass(frozen=True)
class ProductIdentity:
    canonical_inn: str | None
    atc_code: str | None
    method: str
    evidence: str | None = None


def _clean(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _leading_token(value: str | None) -> str | None:
    text = _clean(value)
    if not text:
        return None
    token = text.split()[0].strip(" ,;:()[]{}*")
    if len(token) < 4 or not any(ch.isalpha() for ch in token):
        return None
    return token


def _inn_from_atc(normalizer: InnNormalizer, atc_code: str | None) -> str | None:
    code = _clean(atc_code).upper()
    if len(code) != 7:
        return None
    index = normalizer._get_index()
    if not index._loaded:
        return None
    matches = [inn for inn, codes in index.inn_to_atc.items() if code in codes]
    if len(matches) != 1:
        return None
    return matches[0]


def _normalise_candidate(
    normalizer: InnNormalizer,
    value: str | None,
    country_code: str,
    *,
    allow_unverified: bool,
    require_atc: bool = False,
) -> ProductIdentity | None:
    text = _clean(value)
    if not text:
        return None
    result = normalizer.normalize(text, country_code)
    if result.canonical_inn is not None:
        if require_atc and not result.atc_code:
            return None
        return ProductIdentity(
            canonical_inn=result.canonical_inn,
            atc_code=result.atc_code,
            method="normalizer",
            evidence=text,
        )
    if allow_unverified and not require_atc:
        return ProductIdentity(
            canonical_inn=text.lower(),
            atc_code=None,
            method="unverified_label",
            evidence=text,
        )
    return None


def resolve_product_identity(
    repo_root: Path,
    *,
    country_code: str,
    inn: str | None,
    atc_code: str | None,
    active_ingredient_labels: Iterable[str | None] = (),
    product_name: str | None = None,
    normalizer: InnNormalizer | None = None,
) -> ProductIdentity:
    """Resolve a row to canonical INN evidence for comparison.

    Evidence priority:
    1. ATC L5 exact reverse lookup, when unique.
    2. Explicit INN field.
    3. Active-ingredient labels from source columns.
    4. Product-name leading token, but only when WHO/ATC normalisation verifies it.

    The final product-name step intentionally refuses unverified brand names.
    """
    normalizer = normalizer or InnNormalizer(repo_root)

    atc_inn = _inn_from_atc(normalizer, atc_code)
    if atc_inn:
        return ProductIdentity(
            canonical_inn=atc_inn,
            atc_code=_clean(atc_code).upper(),
            method="atc_exact",
            evidence=_clean(atc_code).upper(),
        )

    explicit = _normalise_candidate(
        normalizer,
        inn,
        country_code,
        allow_unverified=True,
    )
    if explicit is not None:
        return ProductIdentity(
            explicit.canonical_inn,
            explicit.atc_code,
            "explicit_inn",
            explicit.evidence,
        )

    for label in active_ingredient_labels:
        ingredient = _normalise_candidate(
            normalizer,
            label,
            country_code,
            allow_unverified=True,
        )
        if ingredient is not None:
            return ProductIdentity(
                ingredient.canonical_inn,
                ingredient.atc_code,
                "active_ingredient_label",
                ingredient.evidence,
            )

    token = _leading_token(product_name)
    prefix = _normalise_candidate(
        normalizer,
        token,
        country_code,
        allow_unverified=False,
        require_atc=True,
    )
    if prefix is not None:
        return ProductIdentity(
            prefix.canonical_inn,
            prefix.atc_code,
            "product_name_prefix",
            prefix.evidence,
        )

    return ProductIdentity(None, _clean(atc_code).upper() or None, "none", None)
