import unittest
import json
from datetime import date
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eu_pharma_price.normalization.dosage_forms import (
    assess_form_compatibility,
    normalize_dosage_form,
)
from eu_pharma_price.delegates.czechia import CzechiaDelegate, _normalize_form
from eu_pharma_price.comparison.identity import assess_identity
from eu_pharma_price.comparison.parsers import parse_pack_size, parse_strength
from eu_pharma_price.comparison.generator import _prepare_lane_rows
from eu_pharma_price.profile.profiler import profile_snapshot
import numpy as np
import pandas as pd


class DosageFormNormalizationTests(unittest.TestCase):
    def test_cz_inj_pso_lqf_maps_to_injectable_powder_and_solvent(self) -> None:
        result = normalize_dosage_form(
            "INJ PSO LQF", country_code="CZ", source_field="lekovaFormaKod",
        )

        self.assertEqual(result.comparable_form_class, "injectable")
        self.assertEqual(result.route_family, "parenteral")
        self.assertIn("powder_and_solvent", result.presentation_attributes)
        self.assertEqual(result.confidence, "strong")
        self.assertEqual(result.rule_id, "cz.sukl.inj_pso_lqf")

    def test_ie_prefilled_pen_maps_to_injectable_with_device_attribute(self) -> None:
        result = normalize_dosage_form(
            None,
            country_code="IE",
            source_field="Drug Name",
            product_name="Enbrel Soln. for Inj. in Pre-filled Pen 50 mg. 4",
        )

        self.assertEqual(result.comparable_form_class, "injectable")
        self.assertEqual(result.route_family, "parenteral")
        self.assertIn("prefilled_pen", result.presentation_attributes)
        self.assertEqual(result.confidence, "adequate")

    def test_injectable_presentations_are_compatible_with_caveat(self) -> None:
        a = normalize_dosage_form("INJ PSO LQF", country_code="CZ")
        b = normalize_dosage_form(
            None,
            country_code="IE",
            product_name="Enbrel Soln. for Inj. in Pre-filled Pen 50 mg. 4",
        )

        compatibility = assess_form_compatibility(a, b)

        self.assertTrue(compatibility.compatible)
        self.assertEqual(compatibility.confidence_cap, "high")
        self.assertIn("presentation differs", compatibility.caveat or "")

    def test_oral_and_parenteral_are_not_compatible(self) -> None:
        a = normalize_dosage_form("TBL FLM", country_code="CZ")
        b = normalize_dosage_form("INJ SOL", country_code="CZ")

        compatibility = assess_form_compatibility(a, b)

        self.assertFalse(compatibility.compatible)
        self.assertIn("route_family mismatch", compatibility.reason or "")

    def test_czechia_delegate_uses_comparable_form_class(self) -> None:
        self.assertEqual(_normalize_form("INJ PSO LQF"), "injectable")

    def test_czechia_canonical_record_carries_form_metadata(self) -> None:
        delegate = CzechiaDelegate(ROOT)
        raw_records = []
        canonical_records = []
        raw_to_canonical = []
        anomalies = []

        delegate._process_record(
            {
                "kodSUKL": "0154909",
                "nazev": "ENBREL PRO PEDIATRICKÉ POUŽITÍ",
                "sila": "10MG",
                "lekovaFormaKod": "INJ PSO LQF",
                "baleni": "4",
                "ATCkod": "L04AB01",
                "cenaPuvodce": "3311.99",
            },
            date(2026, 5, 20),
            "sukl-scau-2026-05-20",
            raw_records,
            canonical_records,
            raw_to_canonical,
            anomalies,
        )

        self.assertEqual(len(canonical_records), 1)
        record = canonical_records[0]
        self.assertEqual(record.dosage_form, "injectable")
        self.assertEqual(record.route_of_administration, "parenteral")
        self.assertEqual(record.dosage_form_raw, "INJ PSO LQF")
        self.assertEqual(record.dosage_form_rule_id, "cz.sukl.inj_pso_lqf")
        self.assertIn("powder_and_solvent", record.dosage_form_attributes)

    def test_identity_allows_compatible_injectable_presentations_with_high_confidence(self) -> None:
        match = assess_identity(
            "etanercept",
            "etanercept",
            "injectable",
            "injectable",
            "parenteral",
            "parenteral",
            parse_strength("50MG"),
            parse_strength("50MG"),
            parse_pack_size("4"),
            parse_pack_size("4"),
            form_attrs_a=("powder_and_solvent",),
            form_attrs_b=("prefilled_pen",),
            form_confidence_a="strong",
            form_confidence_b="adequate",
            inn_atc_a="L04AB01",
            inn_atc_b="L04AB01",
        )

        self.assertTrue(match.matches)
        self.assertEqual(match.confidence.value, "high")
        self.assertIn("presentation differs", match.reason or "")

    def test_identity_blocks_oral_vs_parenteral_route_family(self) -> None:
        match = assess_identity(
            "etanercept",
            "etanercept",
            "oral_solid",
            "injectable",
            "oral",
            "parenteral",
            parse_strength("50MG"),
            parse_strength("50MG"),
            parse_pack_size("4"),
            parse_pack_size("4"),
        )

        self.assertFalse(match.matches)
        self.assertIn("route_family mismatch", match.reason or "")

    def test_profile_reports_dosage_form_normalization_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            prices_dir = repo / "data" / "canonical" / "xx" / "2026-05-20"
            prices_dir.mkdir(parents=True)
            pd.DataFrame([
                {
                    "price_amount": "10.0",
                    "price_currency": "EUR",
                    "snapshot_date": date(2026, 5, 20),
                    "dosage_form": "injectable",
                    "dosage_form_raw": "INJ PSO LQF",
                    "dosage_form_normalization_confidence": "strong",
                    "dosage_form_rule_id": "cz.sukl.inj_pso_lqf",
                },
                {
                    "price_amount": "20.0",
                    "price_currency": "EUR",
                    "snapshot_date": date(2026, 5, 20),
                    "dosage_form": "",
                    "dosage_form_raw": "UNKNOWN LOCAL FORM",
                    "dosage_form_normalization_confidence": "weak",
                    "dosage_form_rule_id": None,
                },
            ]).to_parquet(prices_dir / "prices.parquet", index=False)

            profiles, _status = profile_snapshot("XX", date(2026, 5, 20), repo)

        form_profile = next(
            p for p in profiles if p.price_type == "dosage_form_normalization"
        )
        self.assertIn("confidence={'strong': 1, 'weak': 1}", form_profile.distribution_notes)
        self.assertIn("rule_id_population=0.5000", form_profile.distribution_notes)
        self.assertIn("unmapped=['UNKNOWN LOCAL FORM']", form_profile.distribution_notes)

    def test_prepare_lane_rows_accepts_parquet_array_form_attributes(self) -> None:
        df = pd.DataFrame([{
            "id": "row-1",
            "inn": "etanercept",
            "product_name": "Enbrel",
            "strength": "50MG",
            "pack_size": "4",
            "dosage_form": "injectable",
            "route_of_administration": "parenteral",
            "dosage_form_attributes": None,
            "dosage_form_normalization_confidence": "adequate",
        }])
        df.at[0, "dosage_form_attributes"] = np.array(["prefilled_pen"], dtype=object)

        rows = _prepare_lane_rows(df, normalizer=None, country_code="IE")

        self.assertEqual(rows[0]["form_attrs"], ("prefilled_pen",))

    def test_evidence_bundle_carries_dosage_form_metadata(self) -> None:
        first_bundle = {
            "country_a": {
                "dosage_form": "injectable",
                "route_of_administration": "parenteral",
                "dosage_form_raw": "INJ PSO LQF",
                "dosage_form_attributes": ["powder_and_solvent"],
                "dosage_form_normalization_method": "rule_based",
                "dosage_form_normalization_confidence": "strong",
                "dosage_form_rule_id": "cz.sukl.inj_pso_lqf",
                "dosage_form_caveat": None,
            },
            "country_b": {
                "dosage_form": "injectable",
                "route_of_administration": "parenteral",
                "dosage_form_raw": "Soln. for Inj. in Pre-filled Pen",
                "dosage_form_attributes": ["prefilled_pen"],
                "dosage_form_normalization_method": "rule_based",
                "dosage_form_normalization_confidence": "adequate",
                "dosage_form_rule_id": "text.prefilled_pen",
                "dosage_form_caveat": None,
            },
        }

        for side in ("country_a", "country_b"):
            with self.subTest(side=side):
                evidence = first_bundle[side]
                self.assertIn("dosage_form", evidence)
                self.assertIn("route_of_administration", evidence)
                self.assertIn("dosage_form_raw", evidence)
                self.assertIn("dosage_form_attributes", evidence)
                self.assertIn("dosage_form_normalization_method", evidence)
                self.assertIn("dosage_form_normalization_confidence", evidence)
                self.assertIn("dosage_form_rule_id", evidence)
                self.assertIn("dosage_form_caveat", evidence)
                self.assertIsNone(evidence["dosage_form_caveat"])


if __name__ == "__main__":
    unittest.main()
