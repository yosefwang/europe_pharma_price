from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd

from eu_pharma_price.comparison.generator import _price_ratio_against_country_b
from eu_pharma_price.delegates.base import BaseDelegate
from eu_pharma_price.delegates.czechia import _normalize_form
from eu_pharma_price.delegates.ireland import IrelandDelegate
from eu_pharma_price.delegates.registry import get_delegate
from eu_pharma_price.profile.profiler import profile_snapshot
from eu_pharma_price.review.reviewer import (
    _render_review_report_lines,
    _resolve_profile_plausibility,
)
from eu_pharma_price.schemas.review import (
    ReviewAssessment,
    Strength,
    Usability,
)


class StabilisationCheckpointTests(unittest.TestCase):
    def test_same_currency_price_ratio_uses_country_b_denominator(self) -> None:
        ratio, converted, fx_rule = _price_ratio_against_country_b(
            repo_root=ROOT,
            country_a_price_per_strength_unit=Decimal("4"),
            country_a_currency="EUR",
            country_b_record_id="b",
            country_b_price_per_strength_unit=Decimal("2"),
            country_b_currency="EUR",
            rate_date=date(2026, 5, 16),
        )

        self.assertEqual(ratio, Decimal("2"))
        self.assertEqual(converted, Decimal("2"))
        self.assertIsNone(fx_rule)

    def test_review_resolves_profile_by_id_across_snapshot_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            profile_dir = repo_root / "data" / "profiles" / "pl" / "2026-04-01"
            profile_dir.mkdir(parents=True)
            profile_path = profile_dir / "data_profile.json"
            profile_path.write_text(
                json.dumps({
                    "profiles": [{
                        "id": "pl-profile",
                        "country_code": "PL",
                        "snapshot_date": "2026-04-01",
                        "price_type": "price_amount",
                        "field_exists": True,
                        "population_rate": 1.0,
                        "plausibility_assessment": "suspect",
                        "record_count": 12,
                        "assessed_at": datetime.now(timezone.utc).isoformat(),
                        "assessed_by": "test",
                        "issues": [],
                    }],
                }),
                encoding="utf-8",
            )

            plausibility = _resolve_profile_plausibility(
                repo_root, "PL", "2026-05-16", "pl-profile"
            )

        self.assertEqual(plausibility, "suspect")

    def test_policy_interpretation_lookup_is_order_independent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            policy_dir = repo_root / "data" / "policy" / "es"
            policy_dir.mkdir(parents=True)
            path = policy_dir / "policy_interpretations.jsonl"
            older = {
                "id": "es-old",
                "country_code": "ES",
                "price_type": "Precio de venta al público con IVA",
                "comparison_category": "public_retail_price",
                "effective_from": "2026-01-01",
                "source_references": ["source-a"],
                "interpretation_text": "older",
                "confidence": "high",
                "authored_at": "2026-01-02T00:00:00+00:00",
                "authored_by": "test",
                "includes_vat": True,
                "includes_margin": "public retail price including VAT",
                "semantics": {
                    "comparison_category": "public_retail_price",
                    "vat_position": "vat_inclusive",
                    "margin_position": "public_retail_components",
                    "derivation_kind": "observed",
                    "derivation_basis": "policy-agent-structured-decision",
                    "notes": [],
                },
            }
            newer = {
                "id": "es-new",
                "country_code": "ES",
                "price_type": "Precio de venta al público con IVA",
                "comparison_category": "public_retail_price",
                "effective_from": "2026-05-22",
                "source_references": ["source-b"],
                "interpretation_text": "newer",
                "confidence": "high",
                "authored_at": "2026-05-23T00:00:00+00:00",
                "authored_by": "test",
                "includes_vat": True,
                "includes_margin": "public retail price including VAT",
                "semantics": {
                    "comparison_category": "public_retail_price",
                    "vat_position": "vat_inclusive",
                    "margin_position": "public_retail_components",
                    "derivation_kind": "observed",
                    "derivation_basis": "policy-agent-structured-decision",
                    "notes": [],
                },
            }
            path.write_text(
                "\n".join([json.dumps(older), json.dumps(newer)]) + "\n",
                encoding="utf-8",
            )

            from eu_pharma_price.policy.gating import (
                interpretation_for_field,
                load_interpretations,
            )

            interpretations = load_interpretations(repo_root, "ES")
            selected = interpretation_for_field(
                interpretations,
                "Precio de venta al público con IVA",
                date(2026, 5, 23),
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "es-new")

    def test_czechia_delegate_is_registered(self) -> None:
        self.assertEqual(get_delegate("CZ").country_code, "CZ")

    def test_base_delegate_requires_explicit_vat_position(self) -> None:
        class MissingVatDelegate(BaseDelegate):
            country_code = "XX"
            default_currency = "EUR"
            price_field = "PRICE"

        with self.assertRaisesRegex(ValueError, "price_includes_vat"):
            MissingVatDelegate(ROOT)

    def test_ireland_delegate_declares_vat_excluded_price_lane(self) -> None:
        self.assertIs(IrelandDelegate(ROOT).price_includes_vat, False)

    def test_czechia_prefilled_injection_forms_normalize_to_injectable(self) -> None:
        self.assertEqual(_normalize_form("INJ SOL ISP"), "injectable")
        self.assertEqual(_normalize_form("INJ SOL PEP"), "injectable")

    def test_czechia_profile_counts_all_canonical_rows(self) -> None:
        prices_path = ROOT / "data" / "canonical" / "cz" / "2026-05-20" / "prices.parquet"
        canonical_rows = len(pd.read_parquet(prices_path))

        profiles, status = profile_snapshot("CZ", date(2026, 5, 20), ROOT)
        price_profile = next(p for p in profiles if p.price_type == "price_amount")

        self.assertEqual(price_profile.record_count, canonical_rows)
        self.assertEqual(status.value, "yellow")

    def test_review_markdown_summary_is_capped(self) -> None:
        assessments = [
            ReviewAssessment(
                id=f"assessment-{i}",
                comparison_candidate_id=f"candidate-{i}",
                usability=Usability.usable_with_caveat,
                policy_strength=Strength.strong,
                data_strength=Strength.adequate,
                identity_strength=Strength.strong,
                normalisation_strength=Strength.strong,
                rationale="data profile is suspect",
                reviewed_at=datetime.now(timezone.utc),
                reviewed_by="test",
                caveats=["profile has caveat"],
            )
            for i in range(3)
        ]

        lines = _render_review_report_lines(
            "2026-05-16", assessments, item_limit=2
        )

        self.assertIn("**Items shown:** 2 of 3", lines)
        self.assertIn("- ... 1 additional assessments omitted from this summary.", lines)
        self.assertNotIn("candidate `candidate-2", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
