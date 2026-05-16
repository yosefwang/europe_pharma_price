"""Profile gating: decide whether a profiled field admits comparison.

Together with policy.gating, this enforces the two-gear rule. The two
modules are independent: each can refuse on its own, both must agree to
permit. Neither modifies any numeric value.
"""

from __future__ import annotations

from ..schemas.profile import DataProfile, PlausibilityAssessment
from .thresholds import NON_NULL_HARD_BLOCK


def is_field_blocked(profile: DataProfile | None) -> tuple[bool, str | None]:
    """Return (blocked, reason). Comparison layer must call this.

    A field is blocked from comparison candidate construction when:
    - no profile exists for the field on the snapshot date
    - the field does not exist in the canonical output
    - the non-null rate is below the hard-block threshold
    - the plausibility assessment is `implausible`
    """
    if profile is None:
        return True, "no data profile for field"
    if not profile.field_exists:
        return True, "field is absent from canonical output"
    if profile.population_rate < NON_NULL_HARD_BLOCK:
        return (
            True,
            f"non-null rate {profile.population_rate:.2f} "
            f"below hard-block threshold {NON_NULL_HARD_BLOCK:.2f}",
        )
    if profile.plausibility_assessment == PlausibilityAssessment.implausible:
        return True, "plausibility assessment is implausible"
    return False, None
