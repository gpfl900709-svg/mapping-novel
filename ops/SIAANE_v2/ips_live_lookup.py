from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.parse
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
AUTOMATION_ROOT = PROJECT_ROOT.parent
SIAAN_PROJECT_ROOT = AUTOMATION_ROOT / "SIAAN Project"
SCRIPTS_ROOT = AUTOMATION_ROOT / "scripts"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from ips.core.auth import resolve_env_path  # noqa: E402
from ips.core.browser import BrowserSettings  # noqa: E402
from ips.core.harness import IPSHarness  # noqa: E402
from ips.sites import get_site  # noqa: E402
from rename_ips_content_titles_api import DETAIL_PATH, axios_call, extract_detail_vo  # noqa: E402


DEFAULT_EXPORT_DIR = PROJECT_ROOT / "0513_temp" / "exports"
LIST_PATH = "/cntsd/cntschg/ctns-chg-list"
LIST_FILTERS = {
    "srcCtnsNm": "",
    "srcPencNm": "",
    "srcmnply": "",
    "srcCtnsStle": "",
    "srcGrad": "",
    "srcGenr": "",
    "srchCmpyCd": "",
    "srchChgerId": "",
    "srchCmnGrpCd": "",
    "srchOnslfMnftYn": "",
    "srcExptSerlMtSt": "",
    "srcExptSerlMtEd": "",
    "srcChgerDept": "",
    "srcRversCprCd": "1000",
    "srcCtnsId": "",
}


def text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_disabled_title(value: Any) -> bool:
    return any(marker in text(value) for marker in ("사용안함", "사용금지", "사용x", "사용X"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live IPS title/CID lookup through the KIPM list/detail API.")
    parser.add_argument("--query", action="append", default=[], help="콘텐츠명 검색어. Repeatable.")
    parser.add_argument("--content-id", action="append", default=[], help="콘텐츠ID detail 조회. Repeatable.")
    parser.add_argument("--manager", default="", help="If set, keep only rows whose chgerNm matches this value.")
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--fetch-all", action="store_true", help="Fetch every result page for title queries.")
    parser.add_argument("--env-file", default=str(SIAAN_PROJECT_ROOT / ".env"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument(
        "--csv-output",
        default=str(DEFAULT_EXPORT_DIR / "ips_live_lookup.csv"),
    )
    parser.add_argument(
        "--json-output",
        default=str(DEFAULT_EXPORT_DIR / "ips_live_lookup.json"),
    )
    return parser.parse_args()


def list_query_path(*, query: str, content_id: str, page_num: int, page_size: int) -> str:
    params = dict(LIST_FILTERS)
    params["srcCtnsNm"] = query
    params["srcCtnsId"] = content_id
    params["pageNum"] = str(page_num)
    params["pageSize"] = str(page_size)
    return f"{LIST_PATH}?{urllib.parse.urlencode(params)}"


def flatten_list_row(row: dict[str, Any], *, lookup_type: str, lookup_value: str, total: int) -> dict[str, Any]:
    title = text(row.get("ctnsNm"))
    disabled = is_disabled_title(title)
    return {
        "lookup_type": lookup_type,
        "lookup_value": lookup_value,
        "total": total,
        "ctnsId": text(row.get("ctnsId")),
        "ctnsNm": title,
        "pencNm": text(row.get("pencNm")),
        "chgerNm": text(row.get("chgerNm")),
        "chgerTeam": text(row.get("chgerTeam")),
        "ctnsStleNm": text(row.get("ctnsStleNm")),
        "svcTyNm": text(row.get("svcTyNm")),
        "gradNm": text(row.get("gradNm")),
        "genrNm": text(row.get("genrNm")),
        "ctnsDtlGenrNm": text(row.get("ctnsDtlGenrNm")),
        "disabled_marker": "Y" if disabled else "N",
        "active_candidate": "N" if disabled else "Y",
        "source": "list",
    }


def flatten_detail_vo(vo: dict[str, Any], *, content_id: str) -> dict[str, Any]:
    title = text(vo.get("ctnsNm"))
    disabled = is_disabled_title(title)
    return {
        "lookup_type": "content_id",
        "lookup_value": content_id,
        "total": 1,
        "ctnsId": text(vo.get("ctnsId") or content_id),
        "ctnsNm": title,
        "pencNm": text(vo.get("pencNm")),
        "chgerNm": text(vo.get("chgerNm") or vo.get("ctnsChgerNm")),
        "chgerTeam": text(vo.get("chgerTeam") or vo.get("ctnsChgerTeam")),
        "ctnsStleNm": text(vo.get("ctnsStleNm")),
        "svcTyNm": text(vo.get("svcTyNm")),
        "gradNm": text(vo.get("gradNm")),
        "genrNm": text(vo.get("genrNm")),
        "ctnsDtlGenrNm": text(vo.get("ctnsDtlGenrNm")),
        "disabled_marker": "Y" if disabled else "N",
        "active_candidate": "N" if disabled else "Y",
        "source": "detail",
    }


def fetch_list_rows(page: Any, *, query: str, page_size: int, fetch_all: bool) -> list[dict[str, Any]]:
    first = axios_call(page, "get", list_query_path(query=query, content_id="", page_num=1, page_size=page_size))
    data = first.get("data") if isinstance(first.get("data"), dict) else {}
    total = int(data.get("total") or 0)
    rows = [flatten_list_row(row, lookup_type="query", lookup_value=query, total=total) for row in (data.get("list") or [])]
    if not fetch_all or total <= page_size:
        return rows
    pages = (total + page_size - 1) // page_size
    for page_num in range(2, pages + 1):
        response = axios_call(page, "get", list_query_path(query=query, content_id="", page_num=page_num, page_size=page_size))
        page_data = response.get("data") if isinstance(response.get("data"), dict) else {}
        rows.extend(
            flatten_list_row(row, lookup_type="query", lookup_value=query, total=total)
            for row in (page_data.get("list") or [])
        )
    return rows


def fetch_detail_row(page: Any, *, content_id: str) -> dict[str, Any]:
    response = axios_call(page, "get", DETAIL_PATH.format(cid=content_id))
    vo = extract_detail_vo(response.get("data")) or {}
    if not vo:
        return {
            "lookup_type": "content_id",
            "lookup_value": content_id,
            "total": 0,
            "ctnsId": content_id,
            "ctnsNm": "",
            "pencNm": "",
            "chgerNm": "",
            "chgerTeam": "",
            "ctnsStleNm": "",
            "svcTyNm": "",
            "gradNm": "",
            "genrNm": "",
            "ctnsDtlGenrNm": "",
            "disabled_marker": "",
            "active_candidate": "",
            "source": "detail_failed",
        }
    return flatten_detail_vo(vo, content_id=content_id)


def write_reports(rows: list[dict[str, Any]], csv_path: Path, json_path: Path, summary: dict[str, Any]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "lookup_type",
        "lookup_value",
        "total",
        "ctnsId",
        "ctnsNm",
        "pencNm",
        "chgerNm",
        "chgerTeam",
        "ctnsStleNm",
        "svcTyNm",
        "gradNm",
        "genrNm",
        "ctnsDtlGenrNm",
        "disabled_marker",
        "active_candidate",
        "source",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    settings = BrowserSettings(
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        artifacts_root=SIAAN_PROJECT_ROOT / "output" / "ips_harness",
    )
    env_path = resolve_env_path(args.env_file)
    site = get_site("kipm")
    rows: list[dict[str, Any]] = []
    with IPSHarness(site, settings=settings, env_path=env_path) as harness:
        harness.ensure_logged_in(path="/ip/cntsd/cntschg/ctns-chg-list?pageNum=1&pageSize=10")
        harness.page.wait_for_timeout(1_000)
        for query in args.query:
            rows.extend(fetch_list_rows(harness.page, query=query, page_size=args.page_size, fetch_all=args.fetch_all))
        for content_id in args.content_id:
            rows.append(fetch_detail_row(harness.page, content_id=content_id))

    if args.manager:
        rows = [row for row in rows if row.get("chgerNm") == args.manager]

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "query_count": len(args.query),
        "content_id_count": len(args.content_id),
        "row_count": len(rows),
        "manager_filter": args.manager,
        "source_counts": dict(Counter(row.get("source") for row in rows)),
    }
    write_reports(rows, Path(args.csv_output), Path(args.json_output), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
