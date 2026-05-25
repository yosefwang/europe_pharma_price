import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eu_pharma_price.schemas.expansion import (
    CountryReadinessAssessment,
    ExpansionPhase,
    ExpansionStatus,
)


class ExpansionReadinessTests(unittest.TestCase):
    def test_ready_country_requires_source_price_meaning_identity_and_basis(self) -> None:
        assessment = CountryReadinessAssessment.model_validate({
            "country_code": "BE",
            "country_name": "Belgium",
            "phase": "phase_1",
            "status": "ready_for_country_plan",
            "official_sources": [{
                "name": "INAMI reimbursable specialties reference files",
                "url": "https://www.inami.fgov.be/",
                "source_format": "excel",
                "access_mode": "public_download",
                "legal_status": "research_use_ok",
            }],
            "observed_price_lanes": [{
                "price_type": "SPB_PRICE",
                "comparison_category": "manufacturer_price",
                "vat_position": "vat_exclusive",
                "margin_position": "no_standard_margins",
                "confidence": "high",
                "notes": ["Prix ex usine field in reference file description."],
            }],
            "derived_price_lanes": [],
            "identity_fields": [
                "inn",
                "strength",
                "dosage_form",
                "pack_size",
                "national_product_code",
            ],
            "first_comparison_basis": ["manufacturer_price"],
            "blockers": [],
            "review_notes": ["Suitable first Phase 1 country."],
        })

        self.assertEqual(assessment.country_code, "BE")
        self.assertEqual(assessment.phase, ExpansionPhase.phase_1)
        self.assertEqual(
            assessment.status,
            ExpansionStatus.ready_for_country_plan,
        )

    def test_ready_country_cannot_have_blockers(self) -> None:
        with self.assertRaisesRegex(ValueError, "ready countries cannot have blockers"):
            CountryReadinessAssessment.model_validate({
                "country_code": "AE",
                "country_name": "United Arab Emirates",
                "phase": "phase_3",
                "status": "ready_for_country_plan",
                "official_sources": [{
                    "name": "MOHAP price list",
                    "url": "https://mohap.gov.ae/",
                    "source_format": "manual",
                    "access_mode": "restricted_request",
                    "legal_status": "needs_review",
                }],
                "observed_price_lanes": [],
                "derived_price_lanes": [],
                "identity_fields": ["product_name"],
                "first_comparison_basis": ["public_retail_price"],
                "blockers": ["Price list access and licensing unresolved."],
                "review_notes": [],
            })

    def test_ready_country_requires_at_least_one_observed_lane(self) -> None:
        with self.assertRaisesRegex(ValueError, "ready countries need observed lanes"):
            CountryReadinessAssessment.model_validate({
                "country_code": "SG",
                "country_name": "Singapore",
                "phase": "excluded",
                "status": "ready_for_country_plan",
                "official_sources": [{
                    "name": "MOH subsidised drugs",
                    "url": "https://www.moh.gov.sg/",
                    "source_format": "html",
                    "access_mode": "public_download",
                    "legal_status": "research_use_ok",
                }],
                "observed_price_lanes": [],
                "derived_price_lanes": [],
                "identity_fields": ["product_name"],
                "first_comparison_basis": ["payer_reimbursement_price"],
                "blockers": [],
                "review_notes": [],
            })

    def test_expansion_tracker_loads_and_keeps_us_ca_deferred(self) -> None:
        import json

        path = ROOT / "data" / "expansion" / "country_readiness.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assessments = [
            CountryReadinessAssessment.model_validate(item)
            for item in payload["countries"]
        ]
        by_code = {item.country_code: item for item in assessments}

        self.assertEqual(by_code["IE"].status.value, "baseline_complete")
        self.assertEqual(by_code["BE"].status.value, "complete")
        self.assertEqual(by_code["US"].status.value, "deferred_special_substrate")
        self.assertEqual(by_code["CA"].status.value, "deferred_special_substrate")
        self.assertEqual(
            by_code["HK"].status.value,
            "excluded_from_price_comparison",
        )

    def test_country_report_template_requires_policy_data_and_status_sections(self) -> None:
        template = (
            ROOT / "docs" / "templates" / "country-expansion-report.md"
        ).read_text(encoding="utf-8")
        required = [
            "## Status",
            "## Sources",
            "## Observed Price Lanes",
            "## Derived Price Lanes",
            "## Comparison Basis",
            "## Validation Cohort",
            "## Open Caveats",
            "## Next Step",
        ]
        for heading in required:
            self.assertIn(heading, template)

    def test_baseline_six_countries_are_tracked_before_expansion(self) -> None:
        import json

        path = ROOT / "data" / "expansion" / "country_readiness.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assessments = [
            CountryReadinessAssessment.model_validate(item)
            for item in payload["countries"]
        ]
        baseline = {
            item.country_code
            for item in assessments
            if item.phase.value == "baseline"
            and item.status.value == "baseline_complete"
        }

        self.assertEqual(baseline, {"IE", "PL", "CZ", "ES", "IT", "PT"})

    def test_roadmap_links_phase_0_artifacts(self) -> None:
        roadmap = (
            ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-05-24-global-price-expansion-roadmap.md"
        ).read_text(encoding="utf-8")
        self.assertIn("data/expansion/country_readiness.json", roadmap)
        self.assertIn("docs/templates/country-expansion-report.md", roadmap)
        self.assertIn("CountryReadinessAssessment", roadmap)


if __name__ == "__main__":
    unittest.main()
