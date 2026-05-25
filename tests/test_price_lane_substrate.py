import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eu_pharma_price.normalization.price_lanes import (
    comparable_lane_key,
    semantics_from_policy,
)
from eu_pharma_price.schemas.policy import PolicyInterpretation


def _policy(
    *,
    country: str,
    price_type: str,
    category: str,
    includes_vat: bool,
    includes_margin: str,
    confidence: str = "high",
    semantics: dict | None = None,
) -> PolicyInterpretation:
    return PolicyInterpretation(
        id=f"{country.lower()}-{price_type.lower().replace(' ', '-')}",
        country_code=country,
        price_type=price_type,
        comparison_category=category,
        effective_from=date(2020, 1, 1),
        source_references=["test-policy-source"],
        interpretation_text="test policy",
        confidence=confidence,
        authored_at=datetime.now(timezone.utc),
        authored_by="test",
        includes_vat=includes_vat,
        includes_margin=includes_margin,
        semantics=semantics or {
            "comparison_category": category,
            "vat_position": (
                "vat_inclusive" if includes_vat else "vat_exclusive"
            ),
            "margin_position": (
                "public_retail_components"
                if "public retail" in includes_margin.lower()
                else (
                    "no_standard_margins"
                    if "no " in includes_margin.lower()
                    or "none" in includes_margin.lower()
                    else (
                        "wholesale_margin"
                        if "wholesale" in includes_margin.lower()
                        else "margin_unknown"
                    )
                )
            ),
            "derivation_kind": "derived"
            if "derived" in price_type.lower()
            else "observed",
        },
        caveats=["test caveat"],
    )


class PriceLaneSubstrateTests(unittest.TestCase):
    _index = None

    @classmethod
    def _multinational_index(cls):
        if cls._index is None:
            from eu_pharma_price.comparison.lane_index import build_multinational_lane_index

            cls._index = build_multinational_lane_index(
                ROOT,
                {
                    "IE": date(2026, 5, 16),
                    "PL": date(2026, 4, 1),
                    "CZ": date(2026, 5, 20),
                    "ES": date(2026, 5, 22),
                    "IT": date(2026, 5, 22),
                    "PT": date(2026, 5, 23),
                    "BE": date(2026, 5, 1),
                },
            )
        return cls._index

    def test_price_lane_semantics_distinguishes_observed_and_derived_lanes(self) -> None:
        observed = semantics_from_policy(
            _policy(
                country="ES",
                price_type="Precio de venta al público con IVA",
                category="public_retail_price",
                includes_vat=True,
                includes_margin="public retail price including VAT and applicable pharmacy-level components",
            )
        )
        derived = semantics_from_policy(
            _policy(
                country="ES",
                price_type="ex-factory (derived)",
                category="manufacturer_price",
                includes_vat=False,
                includes_margin="no standard wholesale/pharmacy margins after derivation",
                confidence="medium",
            )
        )

        self.assertEqual(observed.derivation_kind, "observed")
        self.assertEqual(derived.derivation_kind, "derived")
        self.assertEqual(observed.vat_position, "vat_inclusive")
        self.assertEqual(derived.vat_position, "vat_exclusive")
        self.assertNotEqual(
            comparable_lane_key(observed),
            comparable_lane_key(derived),
        )

    def test_vat_mismatch_blocks_apple_to_apple_key_even_with_same_category(self) -> None:
        ie = semantics_from_policy(
            _policy(
                country="IE",
                price_type="Reimbursement Price",
                category="pharmacy_purchase_price",
                includes_vat=False,
                includes_margin="wholesale margin only (8%, 12% for fridge items)",
            )
        )
        pl = semantics_from_policy(
            _policy(
                country="PL",
                price_type="Cena hurtowa brutto",
                category="pharmacy_purchase_price",
                includes_vat=True,
                includes_margin="wholesale margin (5%, capped) + VAT",
            )
        )

        self.assertEqual(ie.comparison_category, pl.comparison_category)
        self.assertNotEqual(comparable_lane_key(ie), comparable_lane_key(pl))

    def test_manufacturer_ex_vat_lanes_share_key_across_observed_and_derived_sources(self) -> None:
        cz = semantics_from_policy(
            _policy(
                country="CZ",
                price_type="cenaPuvodce",
                category="manufacturer_price",
                includes_vat=False,
                includes_margin="no margins (manufacturer ex-factory price)",
            )
        )
        pt = semantics_from_policy(
            _policy(
                country="PT",
                price_type="ex-factory (derived)",
                category="manufacturer_price",
                includes_vat=False,
                includes_margin="no standard wholesale/pharmacy margins after derivation",
                confidence="medium",
            )
        )

        self.assertEqual(comparable_lane_key(cz), comparable_lane_key(pt))

    def test_unrecognized_margin_text_stays_unknown(self) -> None:
        semantics = semantics_from_policy(
            _policy(
                country="ES",
                price_type="Precio de venta al público con IVA",
                category="public_retail_price",
                includes_vat=True,
                includes_margin="custom margin wording that is not mapped",
            )
        )

        self.assertEqual(semantics.margin_position, "margin_unknown")
        self.assertEqual(
            comparable_lane_key(semantics),
            ("public_retail_price", "vat_inclusive", "margin_unknown"),
        )

    def test_policy_semantics_are_consumed_directly(self) -> None:
        policy = _policy(
            country="ES",
            price_type="Custom public retail label",
            category="public_retail_price",
            includes_vat=False,
            includes_margin="completely misleading text",
            semantics={
                "comparison_category": "public_retail_price",
                "vat_position": "vat_inclusive",
                "margin_position": "public_retail_components",
                "derivation_kind": "observed",
                "derivation_basis": "policy agent decision",
            },
        )
        semantics = semantics_from_policy(policy)

        self.assertEqual(semantics.vat_position, "vat_inclusive")
        self.assertEqual(semantics.margin_position, "public_retail_components")
        self.assertEqual(semantics.derivation_kind, "observed")

    def test_multinational_lane_index_preserves_policy_data_and_comparable_keys(self) -> None:
        index = self._multinational_index()

        self.assertEqual(
            set(index["country_code"]),
            {"IE", "PL", "CZ", "ES", "IT", "PT", "BE"},
        )
        self.assertTrue(index["policy_interpretation_id"].notna().all())
        self.assertTrue(index["data_profile_id"].notna().all())

        derived = index[index["derivation_kind"] == "derived"]
        self.assertGreater(len(derived), 0)
        self.assertTrue(derived["price_lane_source_record_id"].notna().all())
        self.assertTrue(derived["price_lane_derivation_rule_id"].notna().all())

        ie_pharmacy = index[
            (index["country_code"] == "IE")
            & (index["price_type"] == "Reimbursement Price")
        ]["comparable_lane_key"].iloc[0]
        pl_pharmacy = index[
            (index["country_code"] == "PL")
            & (index["price_type"] == "Cena hurtowa brutto")
        ]["comparable_lane_key"].iloc[0]
        self.assertNotEqual(ie_pharmacy, pl_pharmacy)

        public_keys = {
            country: index[
                (index["country_code"] == country)
                & (index["comparison_category"] == "public_retail_price")
            ]["comparable_lane_key"].iloc[0]
            for country in ("ES", "IT", "PT")
        }
        self.assertEqual(len(set(public_keys.values())), 1)

        manufacturer = index[
            (index["comparison_category"] == "manufacturer_price")
            & (index["vat_position"] == "vat_exclusive")
            & (index["margin_position"] == "no_standard_margins")
        ]
        self.assertTrue({"IE", "PL", "CZ", "ES", "IT", "PT", "BE"}.issubset(
            set(manufacturer["country_code"])
        ))

    def test_five_common_drugs_compare_across_seven_countries_as_manufacturer_ex_vat(self) -> None:
        from eu_pharma_price.comparison.lane_index import find_comparable_rows

        index = self._multinational_index()
        manufacturer_key = (
            "manufacturer_price",
            "vat_exclusive",
            "no_standard_margins",
        )

        expected_identity = {
            "atorvastatin": ("atorvastatin", "20", "mg", "oral_solid", "oral"),
            "olanzapine": ("olanzapine", "10", "mg", "oral_solid", "oral"),
            "pantoprazole": ("pantoprazole", "40", "mg", "oral_solid", "oral"),
            "clopidogrel": ("clopidogrel", "75", "mg", "oral_solid", "oral"),
            "dapagliflozin": ("dapagliflozin", "10", "mg", "oral_solid", "oral"),
        }
        for molecule, identity_key in expected_identity.items():
            rows = find_comparable_rows(
                index,
                molecule,
                comparable_key=manufacturer_key,
                min_countries=7,
            )
            selected = rows[rows["identity_key"] == identity_key]

            self.assertFalse(selected.empty, molecule)
            self.assertEqual(
                set(selected["country_code"]),
                {"IE", "PL", "CZ", "ES", "IT", "PT", "BE"},
            )
            self.assertEqual(set(selected["comparable_lane_key"]), {manufacturer_key})
            self.assertEqual(set(selected["vat_position"]), {"vat_exclusive"})
            self.assertEqual(set(selected["margin_position"]), {"no_standard_margins"})
            self.assertTrue(selected["price_per_strength_unit_eur"].notna().all())
            self.assertTrue((selected["price_per_strength_unit_eur"] > 0).all())
            self.assertEqual(set(selected["normalized_currency"]), {"EUR"})


if __name__ == "__main__":
    unittest.main()
