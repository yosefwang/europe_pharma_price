"""Shared price-lane semantics for cross-country comparison.

This module turns a policy interpretation into an explicit comparable lane
identity. It does not calculate prices; deterministic derivation remains in
comparison.price_lane_derivation and produces DerivationRule evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas.policy import PolicyInterpretation


@dataclass(frozen=True)
class PriceLaneSemantics:
    country_code: str
    observed_price_type: str
    normalized_price_type: str
    comparison_category: str
    vat_position: str
    margin_position: str
    derivation_kind: str
    policy_interpretation_id: str
    policy_confidence: str
    caveats: tuple[str, ...]


def semantics_from_policy(policy: PolicyInterpretation) -> PriceLaneSemantics:
    semantics = policy.semantics
    return PriceLaneSemantics(
        country_code=policy.country_code,
        observed_price_type=policy.price_type,
        normalized_price_type=policy.price_type,
        comparison_category=semantics.comparison_category.value,
        vat_position=semantics.vat_position.value,
        margin_position=semantics.margin_position.value,
        derivation_kind=semantics.derivation_kind.value,
        policy_interpretation_id=policy.id,
        policy_confidence=policy.confidence.value,
        caveats=tuple(policy.caveats),
    )


def comparable_lane_key(semantics: PriceLaneSemantics) -> tuple[str, str, str]:
    """Key for apple-to-apple price-lane comparison.

    Country and observed/derived provenance are intentionally excluded: a
    derived ex-factory lane and an observed ex-factory lane can compare when
    their policy concept, VAT state, and margin state align.
    """
    return (
        semantics.comparison_category,
        semantics.vat_position,
        semantics.margin_position,
    )
