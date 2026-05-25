import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eu_pharma_price.comparison.lane_index import (  # noqa: E402
    build_multinational_lane_index,
)
from eu_pharma_price.comparison.price_lane_derivation import (  # noqa: E402
    build_policy_derivation_graph,
)
from eu_pharma_price.comparison.product_identity import (  # noqa: E402
    resolve_product_identity,
)


def _write_profile(repo: Path, country: str, snapshot: str) -> None:
    path = repo / "data" / "profiles" / country.lower() / snapshot / "data_profile.json"
    path.parent.mkdir(parents=True)
    payload = {
        "profiles": [{
            "id": f"{country}-profile",
            "country_code": country,
            "snapshot_date": snapshot,
            "price_type": "price_amount",
            "field_exists": True,
            "population_rate": 1.0,
            "plausibility_assessment": "plausible",
            "record_count": 1,
            "assessed_at": datetime.now(timezone.utc).isoformat(),
            "assessed_by": "test",
            "issues": [],
        }],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_policy(repo: Path, country: str, lines: list[dict]) -> None:
    path = repo / "data" / "policy" / country.lower() / "policy_interpretations.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")


class GlobalSubstrateHardeningTests(unittest.TestCase):
    def test_policy_derivation_graph_reports_derived_lanes_and_legal_basis(self) -> None:
        graph = build_policy_derivation_graph(ROOT, ["IE", "ES", "IT", "PT", "BE"])

        keys = {(edge.country_code, edge.target_price_type) for edge in graph.edges}
        self.assertIn(("IE", "ex-factory (derived)"), keys)
        self.assertIn(("ES", "ex-factory (derived)"), keys)
        self.assertIn(("IT", "ex-factory (derived)"), keys)
        self.assertIn(("PT", "ex-factory (derived)"), keys)
        self.assertNotIn(("BE", "ex-factory (derived)"), keys)
        for edge in graph.edges:
            self.assertTrue(edge.legal_basis, edge)
            self.assertTrue(edge.formula_id, edge)
            self.assertEqual(edge.target_category, "manufacturer_price")

    def test_product_identity_resolves_from_atc_active_ingredient_and_brand_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ref = repo / "data" / "reference"
            ref.mkdir(parents=True)
            (ref / "who_atc_ddd.csv").write_text(
                "atc_code,atc_name\n"
                "N02BE01,paracetamol\n"
                "A10BK01,dapagliflozin\n"
                "A10BA02,metformin\n",
                encoding="utf-8",
            )

            atc = resolve_product_identity(
                repo,
                country_code="BE",
                inn=None,
                atc_code="N02BE01",
                active_ingredient_labels=[],
                product_name="BELGIAN TEST",
            )
            self.assertEqual(atc.canonical_inn, "paracetamol")
            self.assertEqual(atc.method, "atc_exact")

            ingredient = resolve_product_identity(
                repo,
                country_code="BE",
                inn=None,
                atc_code=None,
                active_ingredient_labels=["Dapagliflozine"],
                product_name="FORXIGA 10 mg",
            )
            self.assertEqual(ingredient.canonical_inn, "dapagliflozin")
            self.assertEqual(ingredient.method, "active_ingredient_label")

            brand = resolve_product_identity(
                repo,
                country_code="BE",
                inn=None,
                atc_code=None,
                active_ingredient_labels=[],
                product_name="FORXIGA 10 mg",
            )
            self.assertIsNone(brand.canonical_inn)
            self.assertEqual(brand.method, "none")

            generic = resolve_product_identity(
                repo,
                country_code="BE",
                inn=None,
                atc_code=None,
                active_ingredient_labels=[],
                product_name="METFORMINE VIATRIS 500 mg",
            )
            self.assertEqual(generic.canonical_inn, "metformin")
            self.assertEqual(generic.method, "product_name_prefix")

    def test_multinational_lane_index_materializes_and_reuses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ref = repo / "data" / "reference"
            ref.mkdir(parents=True)
            (ref / "who_atc_ddd.csv").write_text(
                "atc_code,atc_name\nN02BE01,paracetamol\n",
                encoding="utf-8",
            )
            snapshot = "2026-05-24"
            cdir = repo / "data" / "canonical" / "aa" / snapshot
            cdir.mkdir(parents=True)
            pd.DataFrame([{
                "id": "aa-row",
                "raw_record_id": "raw-aa",
                "source_document_id": "src-aa",
                "country_code": "AA",
                "snapshot_date": date(2026, 5, 24),
                "product_name": "Paracetamol Test",
                "inn": None,
                "atc_code": "N02BE01",
                "strength": "500 mg",
                "dosage_form": "oral_solid",
                "pack_size": "30",
                "price_amount": "3.00",
                "price_currency": "EUR",
                "price_type": "manufacturer",
                "price_includes_vat": False,
                "route_of_administration": "oral",
            }]).to_parquet(cdir / "prices.parquet", index=False)
            _write_profile(repo, "AA", snapshot)
            authored = datetime.now(timezone.utc).isoformat()
            _write_policy(repo, "AA", [{
                "id": "aa-policy",
                "country_code": "AA",
                "price_type": "manufacturer",
                "comparison_category": "manufacturer_price",
                "effective_from": "2026-01-01",
                "source_references": ["test"],
                "interpretation_text": "test",
                "confidence": "high",
                "authored_at": authored,
                "authored_by": "test",
                "semantics": {
                    "comparison_category": "manufacturer_price",
                    "vat_position": "vat_exclusive",
                    "margin_position": "no_standard_margins",
                    "derivation_kind": "observed",
                },
            }])

            first = build_multinational_lane_index(
                repo,
                {"AA": date(2026, 5, 24)},
                cache_window_id="test-window",
                use_cache=True,
            )
            cache_path = repo / "data" / "lane_index" / "test-window" / "lane_index.parquet"
            manifest_path = repo / "data" / "lane_index" / "test-window" / "manifest.json"
            self.assertTrue(cache_path.exists())
            self.assertTrue(manifest_path.exists())

            (cdir / "prices.parquet").unlink()
            second = build_multinational_lane_index(
                repo,
                {"AA": date(2026, 5, 24)},
                cache_window_id="test-window",
                use_cache=True,
            )
            self.assertEqual(len(first), len(second))
            self.assertEqual(second.iloc[0]["canonical_inn"], "paracetamol")


if __name__ == "__main__":
    unittest.main()
