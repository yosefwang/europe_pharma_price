"""Two-layer INN normalization for cross-language identity matching.

Layer 1 (linguistic rules): Language-specific transformation rules that
map non-English INN variants to English canonical forms. Deterministic,
zero false-positive risk. Each rule carries provenance text.

Layer 2 (constrained fuzzy matching): Safe fallback against the WHO
ATC-DDD dictionary. Only runs on INNs Layer 1 couldn't normalize.
Constrained by first-character + edit distance <= 2 + length ratio
80-120% + single-winner rule. Ambiguous matches route to Review.

Adding a new language = adding a LanguageRuleSet to _LANGUAGE_RULES.
No code changes needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import ClassVar


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class NormalizationMethod(str, Enum):
    exact = "exact"           # Already in canonical form
    rule_based = "rule_based"  # Matched by Layer 1 linguistic rule
    fuzzy = "fuzzy"           # Matched by Layer 2 fuzzy lookup
    none = "none"             # Could not be normalized


@dataclass(frozen=True)
class NormalizationResult:
    canonical_inn: str | None
    atc_code: str | None
    method: NormalizationMethod
    rule_label: str | None = None   # e.g. "strip_-um" or "acidum_X_to_X_acid"
    candidates: list[str] | None = None  # when ambiguous, the competing options


# ---------------------------------------------------------------------------
# Language rule sets (Layer 1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InnTransformRule:
    """One linguistic transformation rule for a language."""
    label: str            # short identifier, e.g. "strip_-um"
    description: str      # human-readable rationale
    pattern: str          # regex pattern to match
    replacement: str      # replacement string
    order: int = 0        # execution order (lower = first)
    terminal: bool = False  # True → stop further rule application after this fires


# Country code → language mapping
COUNTRY_LANGUAGE: dict[str, str] = {
    "IE": "en",
    "PL": "pl",
    "FR": "fr",
}

# Language code → ordered list of InnTransformRules
_LANGUAGE_RULES: dict[str, list[InnTransformRule]] = {
    "pl": [
        InnTransformRule(
            label="acidum_X_to_X_acid",
            description="Latin 'acidum X-icum/um' → English 'X-ic acid'",
            pattern=r"^acidum\s+(.+?)(?:ic)?um$",
            replacement=r"\1ic acid",
            order=0,
            terminal=True,
        ),
        InnTransformRule(
            label="compound_hydrochloridum",
            description="Latin 'X-ini/i/um hydrochloridum' → 'X hydrochloride'",
            pattern=r"^(.+)(?:ini|i|um)\s+hydrochloridum$",
            replacement=r"\1 hydrochloride",
            order=1,
            terminal=True,
        ),
        InnTransformRule(
            label="compound_sodium_salt",
            description="Latin 'natrii X-as' → English 'X-ate sodium' salt",
            pattern=r"^natrii\s+(.+?)(?:as)$",
            replacement=r"\1ate sodium",
            order=2,
            terminal=True,
        ),
        InnTransformRule(
            label="as_to_ate",
            description="Latin -as suffix (salt) → English -ate",
            pattern=r"^(.+)as$",
            replacement=r"\1ate",
            order=3,
        ),
        InnTransformRule(
            label="strip_um_i_suffix",
            description="Latin neuter -um / genitive -i suffix → English bare stem",
            pattern=r"^(.+?)(?:um|i)$",
            replacement=r"\1",
            order=4,
        ),
    ],
    "en": [],  # English is the canonical form, no rules needed
    "fr": [],  # French rules TBD when FR data is available
}


def _apply_layer1(inn: str, language: str) -> NormalizationResult | None:
    """Apply linguistic rules for the given language. Returns None if no
    rule matches; the caller should fall through to Layer 2.

    Rules are applied iteratively — the rule list is re-scanned after any
    match, so a compound rule (e.g. hydrochloridum → base + hydrochloride)
    can have its base part further normalized by suffix-stripping rules.
    """
    rules = _LANGUAGE_RULES.get(language, [])
    if not rules:
        return NormalizationResult(
            canonical_inn=inn,
            atc_code=None,
            method=NormalizationMethod.exact,
        )

    current = inn.strip().lower()
    applied: list[str] = []

    for _pass in range(5):
        changed = False
        for rule in sorted(rules, key=lambda r: r.order):
            m = re.match(rule.pattern, current)
            if m:
                current = m.expand(rule.replacement).strip().lower()
                applied.append(rule.label)
                changed = True
                if rule.terminal:
                    return NormalizationResult(
                        canonical_inn=current,
                        atc_code=None,
                        method=NormalizationMethod.rule_based,
                        rule_label=" + ".join(applied),
                    )
                break  # restart from lowest-order rule
        if not changed:
            break

    if applied:
        return NormalizationResult(
            canonical_inn=current,
            atc_code=None,
            method=NormalizationMethod.rule_based,
            rule_label=" + ".join(applied),
        )

    return None


# ---------------------------------------------------------------------------
# Layer 2: Constrained fuzzy matching against WHO ATC dictionary
# ---------------------------------------------------------------------------

def _levenshtein(s1: str, s2: str) -> int:
    """Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if len(s2) == 0:
        return len(s1)

    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1, 1):
        curr = [i]
        for j, c2 in enumerate(s2, 1):
            if c1 == c2:
                curr.append(prev[j - 1])
            else:
                curr.append(1 + min(prev[j], curr[-1], prev[j - 1]))
        prev = curr
    return prev[-1]


@dataclass
class WhoAtcIndex:
    """Index over the WHO ATC-DDD CSV for fast constrained fuzzy lookup."""

    # inn → set of atc codes (one INN can map to multiple ATC codes)
    inn_to_atc: dict[str, set[str]] = field(default_factory=dict)
    # All INN names (lowercased) for fuzzy scanning
    all_inns: list[str] = field(default_factory=list)

    _loaded: bool = False

    def load(self, csv_path: Path) -> None:
        """Load WHO ATC-DDD CSV, index level-5 entries only."""
        import csv as _csv

        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                code = row.get("atc_code", "").strip()
                name = row.get("atc_name", "").strip().lower()
                # Level-5 ATC codes are exactly 7 chars (e.g., N02BE01)
                if len(code) == 7 and name:
                    self.inn_to_atc.setdefault(name, set()).add(code)

        self.all_inns = sorted(self.inn_to_atc.keys())
        self._loaded = True

    def exact_lookup(self, inn: str) -> tuple[str | None, set[str]]:
        """Return (canonical_inn, atc_codes) for exact match, or (None, empty)."""
        inn_lower = inn.strip().lower()
        atcs = self.inn_to_atc.get(inn_lower, set())
        if atcs:
            return inn_lower, atcs
        return None, set()

    def fuzzy_lookup(
        self, inn: str, *, len_ratio_min: float = 0.80,
    ) -> NormalizationResult | None:
        """Constrained fuzzy match: first-char same, edit <= 2, length ratio
        within [len_ratio_min, 1/len_ratio_min]. For compound bases (shorter
        stems after Layer 1), caller may pass a lower len_ratio_min (0.65).
        Returns None when no match, or NormalizationResult with method=fuzzy."""
        inn = inn.strip().lower()
        if not inn or len(inn) < 4:
            return None

        best_dist = 999
        best_matches: list[str] = []

        for candidate in self.all_inns:
            # Constraint 1: first character must match
            if candidate[0] != inn[0]:
                continue
            # Constraint 2: length ratio
            if not (len_ratio_min <= len(candidate) / len(inn) <= 1 / len_ratio_min):
                continue
            # Compute distance
            dist = _levenshtein(inn, candidate)
            # Constraint 3: distance <= 2
            if dist > 2:
                continue

            if dist < best_dist:
                best_dist = dist
                best_matches = [candidate]
            elif dist == best_dist:
                best_matches.append(candidate)

        if not best_matches:
            return None

        # Constraint 4: single winner only
        if len(best_matches) > 1:
            return NormalizationResult(
                canonical_inn=None,
                atc_code=None,
                method=NormalizationMethod.none,
                candidates=best_matches,
            )

        winner = best_matches[0]
        atcs = self.inn_to_atc.get(winner, set())
        return NormalizationResult(
            canonical_inn=winner,
            atc_code=sorted(atcs)[0] if atcs else None,
            method=NormalizationMethod.fuzzy,
        )


# ---------------------------------------------------------------------------
# Main normalizer
# ---------------------------------------------------------------------------

@dataclass
class InnNormalizer:
    """Two-layer INN normalizer with lazy WHO ATC index loading."""

    repo_root: Path

    _index: WhoAtcIndex | None = None

    def _get_index(self) -> WhoAtcIndex:
        if self._index is None:
            self._index = WhoAtcIndex()
            csv_path = self.repo_root / "data" / "reference" / "who_atc_ddd.csv"
            if csv_path.exists():
                self._index.load(csv_path)
        return self._index

    def normalize(
        self, inn: str | None, country_code: str,
    ) -> NormalizationResult:
        """Normalize an INN from the given country to English canonical form.

        Returns NormalizationResult with method=none when the INN is None,
        empty, or could not be matched by either layer.
        """
        if not inn or not inn.strip():
            return NormalizationResult(
                canonical_inn=None, atc_code=None,
                method=NormalizationMethod.none,
            )

        language = COUNTRY_LANGUAGE.get(country_code.upper(), "en")

        # Layer 1: linguistic rules
        result = _apply_layer1(inn, language)
        if result is not None and result.canonical_inn:
            canonical_out = result.canonical_inn

            # Enrich with ATC from WHO index — exact match on full output
            canonical, atcs = self._get_index().exact_lookup(canonical_out)
            if canonical:
                return NormalizationResult(
                    canonical_inn=canonical,
                    atc_code=sorted(atcs)[0] if atcs else None,
                    method=result.method,
                    rule_label=result.rule_label,
                )

            # Compound handling: if output has a space (e.g. "amlodip
            # hydrochloride"), try exact then fuzzy lookup on the base
            # word, then reassemble with the salt suffix.
            if " " in canonical_out:
                parts = canonical_out.split(" ", 1)
                base, salt = parts[0], parts[1]

                # Try exact match on base
                base_canonical, atcs_base = self._get_index().exact_lookup(base)
                if base_canonical:
                    return NormalizationResult(
                        canonical_inn=f"{base_canonical} {salt}",
                        atc_code=sorted(atcs_base)[0] if atcs_base else None,
                        method=result.method,
                        rule_label=result.rule_label,
                    )

                # Try fuzzy match on base (relaxed ratio: compound bases
                # are often shorter stems, e.g. "amlodip" → "amlodipine")
                base_fuzzy = self._get_index().fuzzy_lookup(
                    base, len_ratio_min=0.65,
                )
                if base_fuzzy is not None and base_fuzzy.canonical_inn:
                    return NormalizationResult(
                        canonical_inn=f"{base_fuzzy.canonical_inn} {salt}",
                        atc_code=base_fuzzy.atc_code,
                        method=NormalizationMethod.fuzzy,
                    )

                return result

            # Layer 2: fuzzy match on the full non-compound output
            fuzzy_result = self._get_index().fuzzy_lookup(
                canonical_out, len_ratio_min=0.80,
            )
            if fuzzy_result is not None:
                return fuzzy_result

            return result

        # Try exact lookup in WHO index (for English or already-canonical INNs)
        canonical, atcs = self._get_index().exact_lookup(inn)
        if canonical:
            return NormalizationResult(
                canonical_inn=canonical,
                atc_code=sorted(atcs)[0] if atcs else None,
                method=NormalizationMethod.exact,
            )

        # Layer 2: constrained fuzzy matching (non-English only)
        if language != "en":
            fuzzy_result = self._get_index().fuzzy_lookup(
                inn, len_ratio_min=0.80,
            )
            if fuzzy_result is not None:
                return fuzzy_result

        return NormalizationResult(
            canonical_inn=None, atc_code=None,
            method=NormalizationMethod.none,
        )
