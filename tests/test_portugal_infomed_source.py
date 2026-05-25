import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eu_pharma_price.sources.portugal_infomed import (
    combine_infomed_index_rows,
    extract_atc_options,
    extract_form_action,
    extract_result_count,
    extract_result_detail_link_ids,
    extract_view_state,
    parse_infomed_detail,
    read_infomed_export,
    write_infomed_extract,
)


DETAIL_HTML = """
<label>Substância Ativa/DCI:</label><label class="labelTexto">Adalimumab</label>
<label>Forma Farmacêutica:</label>
<label class="labelTexto">Solução injetável em caneta pré-cheia</label>
<label>Nome do Medicamento:</label><label id="detalheMedNomeMed" class="labelTexto">Humira</label>
<label>Dosagem:</label><label class="labelTexto">40 mg/0.4 ml</label>
<label>Titular de AIM:</label><label class="labelTexto">AbbVie Deutschland GmbH &amp; Co. KG</label>
<label>Via(s) de Administração:</label><label class="labelTexto">Via subcutânea</label>
<label>Classificação ATC:</label><label class="labelTexto">L04AB04 - adalimumab</label>
<div class="embalagem-main-panel">
  <span class="btn btn-link">Caneta pré-cheia</span>
  <span class="btn btn-link">2 unidade(s) - 0.4 ml</span>
  <label>Número de Registo:</label><span>5671003</span>
  <label>CNPEM:</label><span>50157000</span>
  <label>PVP:</label><label class="labelTexto">776,28 €</label>
</div>
"""

ADVANCED_HTML = """
<form id="mainForm" name="mainForm" method="post"
  action="/INFOMED-fo/pesquisa-avancada.xhtml;jsessionid=test"
  enctype="application/x-www-form-urlencoded">
<input type="hidden" name="javax.faces.ViewState"
  id="j_id1:javax.faces.ViewState:1" value="12345:-67890" autocomplete="off" />
<select id="mainForm:classif-atc_input" name="mainForm:classif-atc_input">
  <option value=""></option>
  <option value="REF_CLASS_ATC:N02BE">N02BE - Anilides</option>
  <option value="REF_CLASS_ATC:N02BE01">N02BE01 - paracetamol</option>
  <option value="REF_CLASS_ATC:L04AB04">L04AB04 - adalimumab</option>
</select>
<tbody id="mainForm:dt-medicamentos_data">
  <tr data-ri="0"><td><a id="mainForm:dt-medicamentos:0:linkNome">Humira</a></td></tr>
  <tr data-ri="1"><td><a id="mainForm:dt-medicamentos:1:linkNome">Humira</a></td></tr>
</tbody>
<span class="ui-paginator-current">A mostrar 1 - 2 de um total de 2 registos.</span>
</form>
"""


class PortugalInfomedSourceTests(unittest.TestCase):
    def test_extract_jsf_form_metadata(self) -> None:
        self.assertEqual(extract_view_state(ADVANCED_HTML), "12345:-67890")
        self.assertEqual(
            extract_form_action(ADVANCED_HTML),
            "/INFOMED-fo/pesquisa-avancada.xhtml;jsessionid=test",
        )

    def test_extract_atc_options_returns_only_level_5_codes(self) -> None:
        options = extract_atc_options(ADVANCED_HTML)

        self.assertEqual([o.code for o in options], ["N02BE01", "L04AB04"])
        self.assertEqual(options[0].value, "REF_CLASS_ATC:N02BE01")
        self.assertEqual(options[0].label, "N02BE01 - paracetamol")

    def test_extract_result_detail_link_ids_returns_desktop_detail_links(self) -> None:
        self.assertEqual(
            extract_result_detail_link_ids(ADVANCED_HTML),
            [
                "mainForm:dt-medicamentos:0:linkNome",
                "mainForm:dt-medicamentos:1:linkNome",
            ],
        )

    def test_extract_result_count_reads_paginator_total(self) -> None:
        self.assertEqual(extract_result_count(ADVANCED_HTML), 2)

    def test_read_infomed_export_and_dedupe_index_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.xlsx"
            rows = [
                {
                    "Substância Ativa/DCI": "Paracetamol",
                    "Nome do Medicamento": "Doloramol",
                    "Forma Farmacêutica": "Comprimido",
                    "Dosagem": "500 mg",
                    "Titular de AIM": "Teva B.V.",
                    "Comercialização": "Comercializado",
                },
                {
                    "Substância Ativa/DCI": "Paracetamol",
                    "Nome do Medicamento": "Doloramol",
                    "Forma Farmacêutica": "Comprimido",
                    "Dosagem": "500 mg",
                    "Titular de AIM": "Teva B.V.",
                    "Comercialização": "Comercializado",
                },
            ]
            import pandas as pd

            pd.DataFrame(rows).to_excel(path, index=False)

            exported = read_infomed_export(path)
            deduped = combine_infomed_index_rows(exported)

        self.assertEqual(len(exported), 2)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["Nome do Medicamento"], "Doloramol")

    def test_parse_detail_extracts_presentation_price_rows(self) -> None:
        rows = parse_infomed_detail(DETAIL_HTML)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Nome do Medicamento"], "Humira")
        self.assertEqual(rows[0]["Substância Ativa/DCI"], "Adalimumab")
        self.assertEqual(
            rows[0]["Forma Farmacêutica"],
            "Solução injetável em caneta pré-cheia",
        )
        self.assertEqual(rows[0]["Dosagem"], "40 mg/0.4 ml")
        self.assertEqual(rows[0]["Apresentação"], "Caneta pré-cheia; 2 unidade(s) - 0.4 ml")
        self.assertEqual(rows[0]["Titular de AIM"], "AbbVie Deutschland GmbH & Co. KG")
        self.assertEqual(rows[0]["Via"], "Via subcutânea")
        self.assertEqual(rows[0]["ATC"], "L04AB04 - adalimumab")
        self.assertEqual(rows[0]["PVP"], "776,28")
        self.assertEqual(rows[0]["Código"], "5671003")
        self.assertEqual(rows[0]["CNPEM"], "50157000")

    def test_parse_detail_skips_presentations_without_pvp(self) -> None:
        html = DETAIL_HTML.replace(
            '<label>PVP:</label><label class="labelTexto">776,28 €</label>',
            '<label>PVP:</label><label class="labelTexto"></label>',
        )

        self.assertEqual(parse_infomed_detail(html), [])

    def test_parse_detail_skips_non_numeric_pvp(self) -> None:
        html = DETAIL_HTML.replace("776,28 €", "N/A")

        self.assertEqual(parse_infomed_detail(html), [])

    def test_parse_detail_prefers_explicit_medicine_name_id_and_dedupes(self) -> None:
        html = DETAIL_HTML.replace(
            '<label>Nome do Medicamento:</label>',
            '<label>Nome do Medicamento:</label><label>Número de Registo:</label>',
        ) + DETAIL_HTML.split('<div class="embalagem-main-panel">', 1)[1]

        rows = parse_infomed_detail(html)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Nome do Medicamento"], "Humira")

    def test_write_infomed_extract_writes_stable_semicolon_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "infomed.csv"

            write_infomed_extract(path, parse_infomed_detail(DETAIL_HTML))

            with path.open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f, delimiter=";"))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Nome do Medicamento"], "Humira")
        self.assertEqual(rows[0]["PVP"], "776,28")


if __name__ == "__main__":
    unittest.main()
