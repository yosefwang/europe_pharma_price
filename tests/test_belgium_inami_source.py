import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eu_pharma_price.sources.belgium_inami import (
    SHEET_NAME,
    build_inami_manifest,
    read_inami_workbook,
    write_inami_extract,
)
from eu_pharma_price.sources.capture import verify_snapshot


class BelgiumInamiSourceTests(unittest.TestCase):
    def test_real_snapshot_hash_verifies(self) -> None:
        ok, errors = verify_snapshot(ROOT / "data" / "raw" / "be" / "2026-05-01")

        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_reads_price_comparison_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inami.xlsx"
            pd.DataFrame([{
                "S_NAM": "METFORMINE VIATRIS",
                "S_NAM_SPECIF": "500 mg",
                "SPB_PRICE": "1.15",
            }]).to_excel(path, sheet_name=SHEET_NAME, index=False)

            rows = read_inami_workbook(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["S_NAM"], "METFORMINE VIATRIS")
        self.assertEqual(rows[0]["SPB_PRICE"], "1.15")

    def test_manifest_uses_workbook_hash_and_xlsx_media_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inami.xlsx"
            pd.DataFrame([{"S_NAM": "METFORMINE VIATRIS"}]).to_excel(
                path,
                sheet_name=SHEET_NAME,
                index=False,
            )

            manifest = build_inami_manifest(
                snapshot_id="be-test",
                source_id="src-be-inami",
                snapshot_date="2026-05-01",
                source_url="https://www.inami.fgov.be/",
                file_path=path,
            )

        self.assertEqual(manifest.country_code, "BE")
        self.assertEqual(manifest.files[0].filename, "inami.xlsx")
        self.assertTrue(manifest.files[0].file_hash.startswith("sha256:"))
        self.assertIn("spreadsheetml.sheet", manifest.files[0].media_type)

    def test_writes_semicolon_extract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "extract.csv"
            write_inami_extract(path, [{
                "S_NAM": "METFORMINE VIATRIS",
                "SPB_PRICE": "1.15",
            }])
            self.assertTrue(path.exists())
            self.assertIn(";", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
