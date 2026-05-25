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

from eu_pharma_price.comparison.generator import generate_candidates
from eu_pharma_price.comparison.price_lane_derivation import derive_price_lanes
from eu_pharma_price.schemas.policy import PolicyInterpretation


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


class PriceLaneDerivationTests(unittest.TestCase):
    def _policy(self, payload: dict) -> PolicyInterpretation:
        return PolicyInterpretation.model_validate({
            "id": payload.get("id", "test-policy"),
            "country_code": payload.get("country_code", "IE"),
            "price_type": payload.get("price_type", "ex-factory (derived)"),
            "comparison_category": payload.get(
                "comparison_category", "manufacturer_price"
            ),
            "effective_from": payload.get("effective_from", "2020-01-01"),
            "source_references": payload.get("source_references", ["test"]),
            "interpretation_text": payload.get(
                "interpretation_text", "test policy interpretation"
            ),
            "confidence": payload.get("confidence", "high"),
            "authored_at": payload.get(
                "authored_at", datetime.now(timezone.utc).isoformat()
            ),
            "authored_by": payload.get("authored_by", "test"),
            "semantics": payload.get("semantics", {
                "comparison_category": "manufacturer_price",
                "vat_position": "vat_exclusive",
                "margin_position": "no_standard_margins",
                "derivation_kind": "derived",
                "derivation_basis": "test",
            }),
            "derivation_rules": payload.get("derivation_rules", []),
        })

    def test_policy_declared_lane_graph_drives_ie_manufacturer_derivation(self) -> None:
        df = pd.DataFrame([{
            "id": "ie-row",
            "raw_record_id": "raw-ie",
            "source_document_id": "src-ie",
            "country_code": "IE",
            "snapshot_date": date(2026, 5, 23),
            "price_type": "Reimbursement Price",
            "price_amount": "112.00",
            "price_currency": "EUR",
            "dosage_form": "injectable",
            "route_of_administration": "parenteral",
        }])
        policy = self._policy({
            "id": "ie-derived-policy",
            "country_code": "IE",
            "derivation_rules": [{
                "source_price_type": "Reimbursement Price",
                "target_price_type": "ex-factory (derived)",
                "source_category": "pharmacy_purchase_price",
                "target_category": "manufacturer_price",
                "formula_id": "divide_by_one_plus_markup",
                "formula": "target = source / (1 + markup)",
                "parameters": {"default_markup": "0.08"},
                "conditional_parameters": [{
                    "when": {
                        "any": [
                            {"field": "dosage_form", "equals": "injectable"},
                            {"field": "route_of_administration", "equals": "parenteral"},
                        ]
                    },
                    "parameters": {"markup": "0.12"},
                    "notes": ["statutory fridge/parenteral markup"],
                }],
                "legal_basis": ["S.I. 639/2019"],
                "confidence": "high",
                "caveats": ["test caveat"],
            }],
        })

        derived = derive_price_lanes(
            df,
            "IE",
            date(2026, 5, 23),
            policies=[policy],
        )

        self.assertEqual(len(derived), 1)
        row = derived.iloc[0]
        self.assertEqual(row["price_amount"], Decimal("100"))
        self.assertEqual(row["price_type"], "ex-factory (derived)")
        self.assertEqual(row["price_lane_source_record_id"], "ie-row")
        rule = row["price_lane_derivation_rule"]
        self.assertEqual(rule.parameters["source_policy_interpretation_id"], policy.id)
        self.assertEqual(rule.parameters["markup"], "0.12")

    def test_derived_lane_is_not_generated_without_policy_derivation_rule(self) -> None:
        df = pd.DataFrame([{
            "id": "ie-row",
            "country_code": "IE",
            "snapshot_date": date(2026, 5, 23),
            "price_type": "Reimbursement Price",
            "price_amount": "112.00",
            "price_currency": "EUR",
            "dosage_form": "injectable",
            "route_of_administration": "parenteral",
        }])

        derived = derive_price_lanes(
            df,
            "IE",
            date(2026, 5, 23),
            policies=[],
        )

        self.assertEqual(len(derived), 0)

    def test_country_formulas_emit_manufacturer_price_lanes(self) -> None:
        df = pd.DataFrame([
            {
                "id": "ie-row",
                "country_code": "IE",
                "snapshot_date": date(2026, 5, 23),
                "price_type": "Reimbursement Price",
                "price_amount": "112.00",
                "price_currency": "EUR",
                "dosage_form": "injectable",
                "route_of_administration": "parenteral",
            },
            {
                "id": "it-row",
                "country_code": "IT",
                "snapshot_date": date(2026, 5, 23),
                "price_type": "Prezzo al pubblico",
                "price_amount": "100.00",
                "price_currency": "EUR",
            },
            {
                "id": "pt-row",
                "country_code": "PT",
                "snapshot_date": date(2026, 5, 23),
                "price_type": "PVP",
                "price_amount": "776.28",
                "price_currency": "EUR",
            },
            {
                "id": "es-row",
                "country_code": "ES",
                "snapshot_date": date(2026, 5, 23),
                "price_type": "Precio de venta al público con IVA",
                "price_amount": "104.00",
                "price_currency": "EUR",
            },
        ])

        by_country = {
            country: derive_price_lanes(
                df[df["country_code"] == country].copy(),
                country,
                date(2026, 5, 23),
            )
            for country in ("IE", "IT", "PT", "ES")
        }

        self.assertEqual(by_country["IE"].iloc[0]["price_amount"], Decimal("100"))
        self.assertEqual(by_country["IT"].iloc[0]["price_amount"], Decimal("66.65"))
        self.assertEqual(by_country["PT"].iloc[0]["price_amount"], Decimal("690.932947"))
        self.assertEqual(by_country["ES"].iloc[0]["price_amount"], Decimal("66.620417"))
        for derived in by_country.values():
            self.assertEqual(derived.iloc[0]["price_type"], "ex-factory (derived)")
            self.assertFalse(derived.iloc[0]["price_includes_vat"])
            self.assertEqual(
                derived.iloc[0]["price_lane_source_record_id"],
                derived.iloc[0]["price_lane_derivation_rule"].parameters[
                    "source_record_id"
                ],
            )

    def test_generator_uses_ie_derived_exfactory_against_pl_manufacturer_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            ie_dir = repo / "data" / "canonical" / "ie" / "2026-05-23"
            pl_dir = repo / "data" / "canonical" / "pl" / "2026-05-23"
            ie_dir.mkdir(parents=True)
            pl_dir.mkdir(parents=True)
            ref_dir = repo / "data" / "reference"
            ref_dir.mkdir(parents=True)
            (ref_dir / "who_atc_ddd.csv").write_text(
                "atc_code,atc_name\nL04AB01,etanercept\n",
                encoding="utf-8",
            )
            pd.DataFrame([{
                "id": "ie-observed",
                "raw_record_id": "raw-ie",
                "source_document_id": "src-ie",
                "country_code": "IE",
                "snapshot_date": date(2026, 5, 23),
                "product_name": "Test injectable",
                "inn": "etanercept",
                "strength": "50 mg",
                "dosage_form": "injectable",
                "pack_size": "1",
                "price_amount": "112.00",
                "price_currency": "EUR",
                "price_type": "Reimbursement Price",
                "price_includes_vat": False,
                "route_of_administration": "parenteral",
            }]).to_parquet(ie_dir / "prices.parquet", index=False)
            pd.DataFrame([{
                "id": "pl-manufacturer",
                "raw_record_id": "raw-pl",
                "source_document_id": "src-pl",
                "country_code": "PL",
                "snapshot_date": date(2026, 5, 23),
                "product_name": "Test injectable",
                "inn": "etanercept",
                "strength": "50 mg",
                "dosage_form": "injectable",
                "pack_size": "1",
                "price_amount": "100.00",
                "price_currency": "EUR",
                "price_type": "Cena zbytu netto",
                "price_includes_vat": False,
                "route_of_administration": "parenteral",
            }]).to_parquet(pl_dir / "prices.parquet", index=False)
            _write_profile(repo, "IE", "2026-05-23")
            _write_profile(repo, "PL", "2026-05-23")
            authored = datetime.now(timezone.utc).isoformat()
            _write_policy(repo, "IE", [{
                "id": "ie-derived-policy",
                "country_code": "IE",
                "price_type": "ex-factory (derived)",
                "comparison_category": "manufacturer_price",
                "effective_from": "2020-01-01",
                "source_references": ["test"],
                "interpretation_text": "Derived from reimbursement price.",
                "confidence": "high",
                "authored_at": authored,
                "authored_by": "test",
                "includes_vat": False,
                "includes_margin": "no margins",
                "semantics": {
                    "comparison_category": "manufacturer_price",
                    "vat_position": "vat_exclusive",
                    "margin_position": "no_standard_margins",
                    "derivation_kind": "derived",
                    "derivation_basis": "policy-agent-structured-decision",
                    "notes": [],
                },
                "derivation_rules": [{
                    "source_price_type": "Reimbursement Price",
                    "target_price_type": "ex-factory (derived)",
                    "source_category": "pharmacy_purchase_price",
                    "target_category": "manufacturer_price",
                    "formula_id": "divide_by_one_plus_markup",
                    "formula": "ex_factory = reimbursement_price / (1 + wholesale_markup)",
                    "parameters": {"default_markup": "0.08"},
                    "conditional_parameters": [{
                        "when": {
                            "any": [
                                {"field": "dosage_form", "equals": "injectable"},
                                {
                                    "field": "route_of_administration",
                                    "equals": "parenteral",
                                },
                            ]
                        },
                        "parameters": {"markup": "0.12"},
                        "notes": ["test statutory injection markup"],
                    }],
                    "legal_basis": ["test"],
                    "confidence": "high",
                    "caveats": [],
                }],
            }])
            _write_policy(repo, "PL", [{
                "id": "pl-manufacturer-policy",
                "country_code": "PL",
                "price_type": "Cena zbytu netto",
                "comparison_category": "manufacturer_price",
                "effective_from": "2012-01-01",
                "source_references": ["test"],
                "interpretation_text": "Manufacturer net price.",
                "confidence": "high",
                "authored_at": authored,
                "authored_by": "test",
                "includes_vat": False,
                "includes_margin": "no margins",
                "semantics": {
                    "comparison_category": "manufacturer_price",
                    "vat_position": "vat_exclusive",
                    "margin_position": "no_standard_margins",
                    "derivation_kind": "observed",
                    "derivation_basis": "policy-agent-structured-decision",
                    "notes": [],
                },
            }])

            result = generate_candidates(
                repo,
                "IE",
                date(2026, 5, 23),
                "PL",
                date(2026, 5, 23),
            )

        self.assertEqual(len(result.candidates), 1)
        package = result.candidates[0]
        self.assertEqual(package.candidate.comparison_category, "manufacturer_price")
        self.assertEqual(str(package.candidate.price_ratio), "1")
        self.assertEqual(
            package.evidence_bundle["country_a"]["price_lane_source_record_id"],
            "ie-observed",
        )
        self.assertEqual(
            package.evidence_bundle["country_a"]["price_lane_derivation_rule_id"],
            package.evidence_bundle["country_a"]["price_lane_derivation_rule"]["id"],
        )

    def test_derive_price_lanes_does_not_duplicate_materialized_derived_lane(self) -> None:
        df = pd.DataFrame([
            {
                "id": "ie-observed",
                "country_code": "IE",
                "snapshot_date": date(2026, 5, 23),
                "price_type": "Reimbursement Price",
                "price_amount": "108.00",
                "price_currency": "EUR",
                "dosage_form": "oral_solid",
                "route_of_administration": "oral",
            },
            {
                "id": "ie-existing-derived",
                "country_code": "IE",
                "snapshot_date": date(2026, 5, 23),
                "price_type": "ex-factory (derived)",
                "price_amount": "100.00",
                "price_currency": "EUR",
                "dosage_form": "oral_solid",
                "route_of_administration": "oral",
            },
        ])

        derived = derive_price_lanes(df, "IE", date(2026, 5, 23))

        self.assertEqual(len(derived), 0)


if __name__ == "__main__":
    unittest.main()
