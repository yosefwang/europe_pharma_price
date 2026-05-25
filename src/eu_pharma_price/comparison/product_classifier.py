"""Product type classifier: brand (originator) vs generic.

Classifies canonical price records within an ATC L5 group by comparing
the product_name against the canonical INN. Generic products typically
start with the INN; brand products use proprietary trade names.

Scalable to new countries: classification depends only on product_name
and canonical_inn (already language-normalized by InnNormalizer), not
on country-specific logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ProductType(str, Enum):
    generic = "generic"
    brand = "brand"


@dataclass(frozen=True)
class ProductClassification:
    product_type: ProductType
    confidence: float  # 0.0–1.0
    reason: str


def classify_product(
    product_name: str,
    canonical_inn: str | None,
    atc_name: str | None = None,
) -> ProductClassification:
    """Classify a product as brand or generic.

    Uses a cascading set of signals:
    1. product_name starts with canonical_inn → generic (high confidence)
    2. product_name contains INN stem (≥5 chars) → generic (medium)
    3. Otherwise → brand

    The atc_name (WHO ATC level-5 description) serves as a fallback
    reference when canonical_inn is unavailable.
    """
    if not product_name or not product_name.strip():
        return ProductClassification(
            ProductType.brand, 0.3, "empty product name",
        )

    name_lower = product_name.strip().lower()
    name_lower = re.sub(r"\s+", " ", name_lower)

    # Determine reference INN to compare against
    ref_inn = (canonical_inn or atc_name or "").strip().lower()
    if not ref_inn:
        return ProductClassification(
            ProductType.brand, 0.3, "no INN reference available",
        )

    # Signal 0: known generic manufacturer suffix in product name
    _GENERIC_MANUFACTURERS = (
        "teva", "mylan", "sandoz", "zentiva", "krka", "accord",
        "stada", "actavis", "ratiopharm", "aurobindo", "glenmark",
        "egis", "richter", "biotika", "léčiva", "leciva", "medochemie",
        "pharmavision", "rowex", "clonmel", "rowa",
    )
    name_parts = name_lower.split()
    if len(name_parts) >= 2 and any(
        m in name_lower for m in _GENERIC_MANUFACTURERS
    ):
        return ProductClassification(
            ProductType.generic, 0.85,
            f"known generic manufacturer in product name",
        )

    # Signal 1: product_name starts with INN
    if name_lower.startswith(ref_inn):
        return ProductClassification(
            ProductType.generic, 0.95,
            f"product name starts with INN '{ref_inn}'",
        )

    # Signal 2: INN stem (first N chars, min 5) appears at start
    # Handles cases like "Atorvastatin Teva" where INN is "atorvastatin calcium"
    inn_words = ref_inn.split()
    first_inn_word = inn_words[0] if inn_words else ref_inn
    if len(first_inn_word) >= 5 and name_lower.startswith(first_inn_word):
        return ProductClassification(
            ProductType.generic, 0.90,
            f"product name starts with INN stem '{first_inn_word}'",
        )

    # Signal 3: INN stem appears anywhere in the product name
    # (weaker signal — could be coincidence for short stems)
    if len(first_inn_word) >= 6 and first_inn_word in name_lower:
        return ProductClassification(
            ProductType.generic, 0.70,
            f"INN stem '{first_inn_word}' found in product name",
        )

    # Signal 4: near-match for Czech/Latin INN variants
    # e.g., prednison vs prednisone, morphin vs morphine, triamcinolon vs triamcinolone
    name_first_word = name_lower.split()[0].rstrip("-")
    if len(first_inn_word) >= 6 and len(name_first_word) >= 5:
        shorter = min(len(name_first_word), len(first_inn_word))
        if shorter >= 6 and name_first_word[:shorter-1] == first_inn_word[:shorter-1]:
            return ProductClassification(
                ProductType.generic, 0.80,
                f"product name near-matches INN ('{name_first_word}' ≈ '{first_inn_word}')",
            )

    # Default: brand
    return ProductClassification(
        ProductType.brand, 0.80,
        f"product name does not match INN '{ref_inn}'",
    )
