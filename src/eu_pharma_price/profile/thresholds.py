"""Data quality threshold constants used by the profiler.

These match docs/specs/data-quality-thresholds.md. They are working
hypotheses; revisions belong in decisions/ and should update both this
file and the spec in the same change.
"""

NON_NULL_HARD_BLOCK = 0.50
NON_NULL_WARNING = 0.90
OUTLIER_RATE_WARNING = 0.05
PRICE_POSITIVE_RATE = 0.95
IQR_MULTIPLIER = 1.5

PROFILED_NUMERIC_FIELDS = ("price_amount",)
PROFILED_CATEGORICAL_FIELDS = ("dosage_form",)
