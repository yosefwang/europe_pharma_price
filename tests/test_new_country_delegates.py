import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eu_pharma_price.delegates.registry import get_delegate
from eu_pharma_price.delegates.runner import run_delegate_for_snapshot


def _write_manifest(snapshot_dir: Path, country_code: str, filename: str) -> None:
    manifest = {
        "snapshot_id": f"test-{country_code.lower()}",
        "source_id": f"src-{country_code.lower()}-test",
        "country_code": country_code,
        "snapshot_date": "2026-05-22",
        "fetched_at": "2026-05-22T00:00:00+00:00",
        "fetch_method": "manual",
        "files": [{
            "filename": filename,
            "file_hash": "sha256:test",
            "file_size_bytes": 1,
            "media_type": "text/csv",
        }],
        "source_url": "https://example.test",
        "robots_txt_compliant": True,
        "tos_reviewed": True,
    }
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8",
    )


def _write_semicolon_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _write_excel(path: Path, sheet_name: str, rows: list[dict[str, str]]) -> None:
    import pandas as pd

    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False)


class NewCountryDelegateTests(unittest.TestCase):
    def test_belgium_source_is_registered(self) -> None:
        register = json.loads(
            (ROOT / "data" / "sources" / "register.json").read_text(
                encoding="utf-8",
            ),
        )
        be = next(item for item in register if item["country_code"] == "BE")
        self.assertEqual(
            be["source_name"],
            "INAMI reimbursable specialties reference files",
        )
        self.assertEqual(be["fetch_method"], "manual")
        self.assertEqual(be["status"], "captured")

    def test_belgium_delegate_canonicalizes_inami_spb_price(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            snapshot = repo / "raw" / "be" / "2026-05-24"
            _write_manifest(snapshot, "BE", "inami.xlsx")
            _write_excel(snapshot / "inami.xlsx", "SSP PRICE_COMPARISON", [{
                "SPB_PRICE": "10.80",
                "S_COD": "1234567",
                "S_NAM": "BELGIAN TEST",
                "S_NAM_SPECIF": "500 mg 30 tablets",
                "F_ORGA": "Test Pharma NV",
                "ATC_COD": "N02BE01",
                "SI_CONC_NOM": "500 mg",
                "S_PREP": "tablets",
                "RETARD": "",
                "VOLUME_TOTAL": "30",
                "SPB_BASE": "10.80",
                "SPB_PUBLIC": "13.25",
                "INN": "paracetamol",
                "RPT_PCK_LBL_FR": "30 comprimés pelliculés",
                "RPT_PCK_LBL_NL": "30 filmomhulde tabletten",
            }])

            result = run_delegate_for_snapshot("BE", snapshot, repo)

        self.assertEqual(len(result.canonical_records), 1)
        record = result.canonical_records[0]
        self.assertEqual(record.country_code, "BE")
        self.assertEqual(record.price_type, "SPB_PRICE")
        self.assertFalse(record.price_includes_vat)
        self.assertEqual(str(record.price_amount), "10.80")
        self.assertEqual(record.product_name, "BELGIAN TEST 500 mg 30 tablets")
        self.assertEqual(record.inn, "paracetamol")
        self.assertEqual(record.atc_code, "N02BE01")
        self.assertEqual(record.strength, "500 mg")
        self.assertEqual(record.pack_size, "30")
        self.assertEqual(record.dosage_form, "oral_solid")
        self.assertEqual(record.route_of_administration, "oral")
        self.assertEqual(record.manufacturer, "Test Pharma NV")
        self.assertEqual(record.national_product_code, "1234567")

    def test_belgium_delegate_canonicalizes_real_metformin_row(self) -> None:
        source = ROOT / "data" / "raw" / "be" / "2026-05-01" / "liste_specialites_20260501.xlsx"
        with pd.ExcelFile(source) as xls:
            df = xls.parse("SSP PRICE_COMPARISON", dtype=str).fillna("")
            row = df[
                df["S_NAM"].str.contains("METFORMIN", case=False, na=False)
                & df["SI_CONC_NOM"].eq("500 mg")
                & df["VOLUME_TOTAL"].eq("60")
            ].iloc[0].to_dict()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            reference = repo / "data" / "reference"
            reference.mkdir(parents=True)
            (reference / "who_atc_ddd.csv").write_text(
                "atc_code,atc_name,ddd,unit,route,note\n"
                "A10BA02,metformin,2,g,O,\n",
                encoding="utf-8",
            )
            snapshot = repo / "raw" / "be" / "2026-05-01"
            _write_manifest(snapshot, "BE", "liste_specialites_20260501.xlsx")
            _write_excel(snapshot / "liste_specialites_20260501.xlsx", "SSP PRICE_COMPARISON", [row])

            result = run_delegate_for_snapshot("BE", snapshot, repo)

        self.assertEqual(len(result.canonical_records), 1)
        record = result.canonical_records[0]
        self.assertEqual(record.country_code, "BE")
        self.assertEqual(record.price_type, "SPB_PRICE")
        self.assertEqual(record.price_includes_vat, False)
        self.assertEqual(record.dosage_form, "oral_solid")
        self.assertEqual(record.route_of_administration, "oral")
        self.assertEqual(record.strength, "500 mg")
        self.assertEqual(record.pack_size, "60")
        self.assertEqual(record.product_name, "METFORMINE VIATRIS 500 mg")
        self.assertEqual(record.inn, "metformin")

    def test_belgium_delegate_uses_active_ingredient_label_for_brand_row(self) -> None:
        source = ROOT / "data" / "raw" / "be" / "2026-05-01" / "liste_specialites_20260501.xlsx"
        with pd.ExcelFile(source) as xls:
            df = xls.parse("SSP PRICE_COMPARISON", dtype=str).fillna("")
            row = df[
                df["S_NAM"].eq("FORXIGA")
                & df["SI_CONC_NOM"].eq("10 mg")
                & df["VOLUME_TOTAL"].eq("28")
            ].iloc[0].to_dict()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            reference = repo / "data" / "reference"
            reference.mkdir(parents=True)
            (reference / "who_atc_ddd.csv").write_text(
                "atc_code,atc_name,ddd,unit,route,note\n"
                "A10BK01,dapagliflozin,10,mg,O,\n",
                encoding="utf-8",
            )
            snapshot = repo / "raw" / "be" / "2026-05-01"
            _write_manifest(snapshot, "BE", "liste_specialites_20260501.xlsx")
            _write_excel(snapshot / "liste_specialites_20260501.xlsx", "SSP PRICE_COMPARISON", [row])

            result = run_delegate_for_snapshot("BE", snapshot, repo)

        self.assertEqual(len(result.canonical_records), 1)
        record = result.canonical_records[0]
        self.assertEqual(record.product_name, "FORXIGA 10 mg")
        self.assertEqual(record.inn, "dapagliflozin")

    def test_spain_delegate_canonicalizes_public_retail_price(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            snapshot = repo / "raw" / "es" / "2026-05-22"
            _write_manifest(snapshot, "ES", "nomenclator.csv")
            _write_semicolon_csv(snapshot / "nomenclator.csv", [{
                "Código Nacional": "650004",
                "Nombre del producto farmacéutico": (
                    "DEPAKINE 500 mg comprimidos gastrorresistentes, "
                    "20 comprimidos"
                ),
                "Tipo de fármaco": "Medicamento Etica",
                "Nombre del laboratorio ofertante": "SANOFI AVENTIS, S.A",
                "Principio activo o asociación de principios activos": (
                    "VALPROATO SODIO"
                ),
                "Precio de venta al público con IVA": "2,50",
                "Precio de referencia": "2,50",
            }])

            result = run_delegate_for_snapshot("ES", snapshot, repo)

        self.assertEqual(len(result.canonical_records), 1)
        record = result.canonical_records[0]
        self.assertEqual(record.country_code, "ES")
        self.assertEqual(record.price_type, "Precio de venta al público con IVA")
        self.assertIs(record.price_includes_vat, True)
        self.assertEqual(str(record.price_amount), "2.50")
        self.assertEqual(record.strength, "500 mg")
        self.assertEqual(record.pack_size, "20")
        self.assertEqual(record.dosage_form, "oral_solid")
        self.assertEqual(record.route_of_administration, "oral")

    def test_italy_delegate_canonicalizes_public_retail_price(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            snapshot = repo / "raw" / "it" / "2026-05-22"
            _write_manifest(snapshot, "IT", "classe_a.csv")
            _write_semicolon_csv(snapshot / "classe_a.csv", [{
                "Principio Attivo": "Acarbosio",
                "Descrizione Gruppo": (
                    "ACARBOSIO 100MG 40 UNITA' USO ORALE"
                ),
                "Denominazione e Confezione": "ACARBOSIO*40 cpr 100 mg",
                "Prezzo al pubblico €": "5,63",
                "Titolare AIC": "DOC GENERICI Srl",
                "AIC": "044155024",
                "Codice Gruppo Equivalenza": "H1A",
            }])

            result = run_delegate_for_snapshot("IT", snapshot, repo)

        self.assertEqual(len(result.canonical_records), 1)
        record = result.canonical_records[0]
        self.assertEqual(record.country_code, "IT")
        self.assertEqual(record.price_type, "Prezzo al pubblico")
        self.assertIs(record.price_includes_vat, True)
        self.assertEqual(str(record.price_amount), "5.63")
        self.assertEqual(record.strength, "100MG")
        self.assertEqual(record.pack_size, "40")
        self.assertEqual(record.dosage_form, "oral_solid")

    def test_portugal_delegate_canonicalizes_infomed_public_retail_price(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            snapshot = repo / "raw" / "pt" / "2026-05-22"
            _write_manifest(snapshot, "PT", "infomed.csv")
            _write_semicolon_csv(snapshot / "infomed.csv", [{
                "Nome do Medicamento": "ACARBOSIO",
                "Substância Ativa/DCI": "Acarbose",
                "Forma Farmacêutica": "Comprimido",
                "Dosagem": "100 mg",
                "Apresentação": "40 comprimidos",
                "Titular de AIM": "Example Holder",
                "ATC": "A10BF01 - acarbose",
                "PVP": "5,63",
                "Código": "PT-TEST-1",
            }])

            result = run_delegate_for_snapshot("PT", snapshot, repo)

        self.assertEqual(len(result.canonical_records), 1)
        record = result.canonical_records[0]
        self.assertEqual(record.country_code, "PT")
        self.assertEqual(record.price_type, "PVP")
        self.assertIs(record.price_includes_vat, True)
        self.assertEqual(str(record.price_amount), "5.63")
        self.assertEqual(record.strength, "100 mg")
        self.assertEqual(record.pack_size, "40")
        self.assertEqual(record.dosage_form, "oral_solid")
        self.assertEqual(record.atc_code, "A10BF01")

    def test_new_country_delegates_are_registered(self) -> None:
        self.assertEqual(get_delegate("BE").country_code, "BE")
        self.assertEqual(get_delegate("ES").country_code, "ES")
        self.assertEqual(get_delegate("IT").country_code, "IT")
        self.assertEqual(get_delegate("PT").country_code, "PT")


if __name__ == "__main__":
    unittest.main()
