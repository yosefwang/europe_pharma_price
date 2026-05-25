#!/usr/bin/env python3
"""Capture a full Portugal Infomed presentation-level PVP extract.

Infomed exposes PVP only on medicine detail pages. The capture therefore
enumerates the advanced-search ATC level-5 list, pages through each result set,
opens each medicine detail page, and writes the existing PT delegate CSV shape.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eu_pharma_price.sources.portugal_infomed import (  # noqa: E402
    FIELDNAMES,
    extract_atc_options,
    extract_form_action,
    extract_result_count,
    extract_result_detail_link_ids,
    extract_view_state,
    parse_infomed_detail,
    write_infomed_extract,
)

BASE_URL = "https://extranet.infarmed.pt/INFOMED-fo/"
ADVANCED_PATH = "pesquisa-avancada.xhtml"
DETAIL_PATH = "detalhes-medicamento.xhtml"
AJAX_HEADERS = {"Faces-Request": "partial/ajax"}


def _search_fields(atc_value: str) -> dict[str, str]:
    return {
        "mainForm:dci_input": "",
        "mainForm:dci_hinput": "",
        "mainForm:ff_input": "",
        "mainForm:vias-admin_input": "",
        "mainForm:generico_input": "",
        "mainForm:estado-aim_input": "REF_EST_AIM:001",
        "mainForm:estado-comercializacao_input": "REF_EST_COMERC:001",
        "mainForm:classif-dispensa_input": "",
        "mainForm:classif-farmacoterapeutica_input": "",
        "mainForm:classif-atc_input": atc_value,
        "mainForm:medicamento_input": "",
        "mainForm:medicamento_hinput": "",
        "mainForm:taim_input": "",
        "mainForm:taim_hinput": "",
        "mainForm:dosagem_input": "",
        "mainForm:dosagem_hinput": "",
        "mainForm:num-processo": "",
        "mainForm:numero-registro": "",
        "mainForm:cnpem": "",
        "mainForm:chnm": "",
    }


class InfomedClient:
    def __init__(
        self,
        *,
        timeout: int,
        sleep_seconds: float,
        max_attempts: int,
        retry_backoff: float,
    ) -> None:
        self.session = requests.Session()
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds
        self.max_attempts = max_attempts
        self.retry_backoff = retry_backoff

    def _sleep(self) -> None:
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)

    def request(self, method: str, url: str, **kwargs: Any) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            self._sleep()
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    **kwargs,
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    response.raise_for_status()
                response.raise_for_status()
                return response.text
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 == self.max_attempts:
                    break
                self.session = requests.Session()
                time.sleep(self.retry_backoff * (2 ** attempt))
        if last_error is None:
            raise RuntimeError("Infomed request failed without an exception")
        raise last_error

    def get(self, path: str) -> str:
        return self.request("GET", urljoin(BASE_URL, path))

    def post(self, url: str, data: dict[str, str], *, ajax: bool = False) -> str:
        return self.request(
            "POST",
            url,
            data=data,
            headers=AJAX_HEADERS if ajax else None,
        )

    def search_atc(self, atc_value: str) -> tuple[str, str, int]:
        page = self.get(ADVANCED_PATH)
        view_state = extract_view_state(page)
        action_url = urljoin(BASE_URL, extract_form_action(page))
        payload = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "mainForm:btnDoSearch",
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": (
                "messages minLenghtMessage mainForm:dt-medicamentos "
                "mainForm:dg-medicamentos mainForm:dciMessage mainForm:nomeMessage "
                "mainForm:taimMessage mainForm:numProcessoMessage "
                "mainForm:nrRegistoMessage mainForm:cnpemMessage "
                "mainForm:chnmMessage mainForm:data-invertida-message"
            ),
            "mainForm:btnDoSearch": "mainForm:btnDoSearch",
            "mainForm": "mainForm",
            "javax.faces.ViewState": view_state,
            **_search_fields(atc_value),
        }
        self.post(action_url, payload, ajax=True)
        result_page = self.get(ADVANCED_PATH)
        return (
            result_page,
            urljoin(BASE_URL, extract_form_action(result_page)),
            extract_result_count(result_page),
        )

    def result_links_for_page(
        self,
        action_url: str,
        view_state: str,
        *,
        first: int,
        rows: int,
    ) -> list[str]:
        payload = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "mainForm:dt-medicamentos",
            "javax.faces.partial.execute": "mainForm:dt-medicamentos",
            "javax.faces.partial.render": "mainForm:dt-medicamentos",
            "mainForm:dt-medicamentos": "mainForm:dt-medicamentos",
            "mainForm:dt-medicamentos_pagination": "true",
            "mainForm:dt-medicamentos_first": str(first),
            "mainForm:dt-medicamentos_rows": str(rows),
            "mainForm:dt-medicamentos_skipChildren": "true",
            "mainForm:dt-medicamentos_encodeFeature": "true",
            "mainForm": "mainForm",
            "javax.faces.ViewState": view_state,
        }
        markup = self.post(action_url, payload, ajax=True)
        return extract_result_detail_link_ids(markup)

    def detail_rows(
        self,
        action_url: str,
        view_state: str,
        link_id: str,
    ) -> list[dict[str, str]]:
        payload = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": link_id,
            "javax.faces.partial.execute": link_id,
            link_id: link_id,
            "mainForm": "mainForm",
            "javax.faces.ViewState": view_state,
        }
        self.post(action_url, payload, ajax=True)
        detail_page = self.get(DETAIL_PATH)
        return parse_infomed_detail(detail_page)


def _append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def _read_done_atcs(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def _read_checkpoint_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            rows.append({field: item.get(field, "") for field in FIELDNAMES})
    return rows


def _write_manifest(snapshot_dir: Path, snapshot_date: str, notes: str) -> None:
    csv_path = snapshot_dir / "infomed.csv"
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    manifest = {
        "snapshot_id": f"pt-infomed-full-{snapshot_date}",
        "source_id": "src-pt-infomed",
        "country_code": "PT",
        "snapshot_date": snapshot_date,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "fetch_method": "scripted_jsf_capture",
        "files": [{
            "filename": "infomed.csv",
            "file_hash": f"sha256:{digest}",
            "file_size_bytes": csv_path.stat().st_size,
            "media_type": "text/csv",
        }],
        "source_url": BASE_URL,
        "robots_txt_compliant": True,
        "tos_reviewed": True,
        "notes": notes,
    }
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (row.get("Código", ""), row.get("Apresentação", ""), row.get("PVP", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append({field: row.get(field, "") for field in FIELDNAMES})
    return deduped


def capture(args: argparse.Namespace) -> None:
    checkpoint_dir = args.checkpoint_dir
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    rows_path = checkpoint_dir / "rows.jsonl"
    failures_path = checkpoint_dir / "failures.jsonl"
    done_path = checkpoint_dir / "done_atc.txt"

    client = InfomedClient(
        timeout=args.timeout,
        sleep_seconds=args.sleep,
        max_attempts=args.max_attempts,
        retry_backoff=args.retry_backoff,
    )
    advanced_page = client.get(ADVANCED_PATH)
    options = extract_atc_options(advanced_page)
    if args.atc_code:
        wanted = {code.upper() for code in args.atc_code}
        options = [option for option in options if option.code in wanted]
    if args.limit_atc:
        options = options[: args.limit_atc]

    snapshot_dir = args.snapshot_dir
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    with (snapshot_dir / "atc_options.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["value", "code", "label"])
        writer.writeheader()
        writer.writerows([option.__dict__ for option in options])

    done_atcs = _read_done_atcs(done_path)
    for idx, option in enumerate(options, start=1):
        if option.code in done_atcs:
            continue
        try:
            page, action_url, count = client.search_atc(option.value)
            view_state = extract_view_state(page)
            for first in range(0, count, args.page_size):
                links = client.result_links_for_page(
                    action_url,
                    view_state,
                    first=first,
                    rows=args.page_size,
                )
                for link_id in links:
                    for row in client.detail_rows(action_url, view_state, link_id):
                        _append_jsonl(rows_path, {
                            **row,
                            "_source_atc_code": option.code,
                            "_source_atc_label": option.label,
                            "_source_link_id": link_id,
                        })
            with done_path.open("a", encoding="utf-8") as f:
                f.write(option.code + "\n")
            print(f"[{idx}/{len(options)}] {option.code}: {count} index rows", flush=True)
        except Exception as exc:  # pragma: no cover - capture resilience
            _append_jsonl(failures_path, {
                "atc_code": option.code,
                "atc_value": option.value,
                "error": repr(exc),
            })
            print(f"[{idx}/{len(options)}] {option.code}: failed: {exc!r}", flush=True)

    rows = _dedupe_rows(_read_checkpoint_rows(rows_path))
    write_infomed_extract(snapshot_dir / "infomed.csv", rows)
    notes = (
        "Full internal research extract from Infomed advanced-search ATC "
        "level-5 enumeration. The source list export does not include PVP, "
        "so the capture opened each medicine detail page and retained numeric "
        "presentation-level PVP rows in infomed.csv. atc_options.csv is retained "
        "as capture metadata and is not a delegate input file."
    )
    _write_manifest(snapshot_dir, args.snapshot_date, notes)
    print(f"Wrote {len(rows)} deduplicated PVP rows to {snapshot_dir / 'infomed.csv'}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, default=Path("/tmp/pt-infomed-full"))
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--retry-backoff", type=float, default=2.0)
    parser.add_argument("--limit-atc", type=int)
    parser.add_argument("--atc-code", action="append")
    return parser.parse_args()


if __name__ == "__main__":
    capture(parse_args())
