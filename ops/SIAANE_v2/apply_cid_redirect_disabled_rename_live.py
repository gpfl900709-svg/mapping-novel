from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts"
SIAAN_PROJECT_ROOT = REPO_ROOT / "SIAAN Project"
WORK_DIR = PROJECT_ROOT / "담당자없는작품_재정리"

sys.path.insert(0, str(SCRIPTS_ROOT))

from ips.core.auth import resolve_env_path  # noqa: E402
from ips.core.browser import BrowserSettings  # noqa: E402
from ips.core.harness import IPSHarness  # noqa: E402
from ips.sites import get_site  # noqa: E402
from rename_ips_content_titles_api import (  # noqa: E402
    DEFAULT_STUFFING,
    DETAIL_PATH,
    SAVE_PATH,
    axios_call,
    coerce_csv_arrays,
    extract_detail_vo,
    normalize_list_fields,
    scrub_date_fields,
    stuff_empty_required_fields,
)


DEFAULT_PLAN_CSV = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__CID우회_사용안함_rename_plan.csv"
DEFAULT_OUTPUT_CSV = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__CID우회_사용안함_rename_result.csv"


@dataclass
class RenameResult:
    콘텐츠ID: str
    변경전콘텐츠명_plan: str
    변경후콘텐츠명: str
    현재콘텐츠명_live: str = ""
    최종콘텐츠명_live: str = ""
    담당자명_live: str = ""
    상태: str = ""
    사유: str = ""
    누락필수필드: str = ""
    기본값보강필드: str = ""
    get_status: int | None = None
    put_status: int | None = None
    server_message: str = ""
    처리사유: str = ""


def text(value: Any) -> str:
    return str(value or "").strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply approved [사용안함] IPS renames and write CSV-only report.")
    parser.add_argument("--plan-csv", default=str(DEFAULT_PLAN_CSV))
    parser.add_argument("--csv-output", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--env-file", default="")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--timeout-ms", type=int, default=20_000)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--content-id", action="append", default=[])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--stuff-defaults", action="store_true")
    return parser.parse_args()


def load_plan(path: Path, content_ids: list[str], limit: int) -> list[dict[str, str]]:
    requested = {text(value) for value in content_ids if text(value)}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            cid = text(row.get("콘텐츠ID"))
            target = text(row.get("변경후콘텐츠명"))
            if not cid or not target:
                continue
            if requested and cid not in requested:
                continue
            rows.append(
                {
                    "콘텐츠ID": cid,
                    "변경전콘텐츠명": text(row.get("변경전콘텐츠명")),
                    "변경후콘텐츠명": target,
                    "처리사유": text(row.get("처리사유")),
                }
            )
    if limit > 0:
        rows = rows[:limit]
    return rows


def missing_required_fields(detail_vo: dict[str, Any]) -> list[str]:
    return [key for key in DEFAULT_STUFFING if detail_vo.get(key) in ("", None)]


def server_message(data: Any, error: Any) -> str:
    if isinstance(data, dict):
        return text(data.get("message") or data.get("error") or error)[:500]
    if isinstance(data, str):
        return data[:500]
    return text(error)[:500]


def process_one(page: Any, row: dict[str, str], *, write: bool, stuff_defaults: bool) -> RenameResult:
    cid = row["콘텐츠ID"]
    target = row["변경후콘텐츠명"]
    result = RenameResult(
        콘텐츠ID=cid,
        변경전콘텐츠명_plan=row["변경전콘텐츠명"],
        변경후콘텐츠명=target,
        처리사유=row["처리사유"],
    )

    get_resp = axios_call(page, "get", DETAIL_PATH.format(cid=cid))
    result.get_status = get_resp.get("status")
    if not get_resp.get("ok"):
        result.상태 = "get_failed"
        result.사유 = text(get_resp.get("error") or get_resp.get("data"))[:300]
        return result

    full_response = get_resp.get("data") if isinstance(get_resp.get("data"), dict) else {}
    detail_vo = extract_detail_vo(full_response)
    if not detail_vo:
        result.상태 = "no_detail_vo"
        result.사유 = f"response keys: {list(full_response.keys())}"
        return result

    result.현재콘텐츠명_live = text(detail_vo.get("ctnsNm"))
    result.최종콘텐츠명_live = result.현재콘텐츠명_live
    result.담당자명_live = text(detail_vo.get("chgerNm") or detail_vo.get("ctnsChgerNm"))
    result.누락필수필드 = ",".join(missing_required_fields(detail_vo))

    if result.현재콘텐츠명_live == target:
        result.상태 = "already_named"
        result.사유 = "current_title_matches_target"
        return result
    if not write:
        result.상태 = "ready_api"
        result.사유 = "dry_run"
        return result

    payload: dict[str, Any] = dict(detail_vo)
    payload["ctnsNm"] = target
    payload["rgtList"] = full_response.get("rgtList") or []
    if stuff_defaults:
        result.기본값보강필드 = ",".join(stuff_empty_required_fields(payload))
    scrub_date_fields(payload)
    coerce_csv_arrays(payload)
    normalize_list_fields(payload)

    put_resp = axios_call(page, "put", SAVE_PATH, payload)
    result.put_status = put_resp.get("status")
    if not put_resp.get("ok"):
        result.상태 = "put_failed"
        result.사유 = f"status={put_resp.get('status')}"
        result.server_message = server_message(put_resp.get("data"), put_resp.get("error"))
        return result

    verify_resp = axios_call(page, "get", DETAIL_PATH.format(cid=cid))
    verify_vo = extract_detail_vo(verify_resp.get("data")) if verify_resp.get("ok") else None
    result.최종콘텐츠명_live = text((verify_vo or {}).get("ctnsNm"))
    if result.최종콘텐츠명_live == target:
        result.상태 = "updated"
        result.사유 = "verified_after_reload"
    else:
        result.상태 = "verify_failed"
        result.사유 = f"server_returned={result.최종콘텐츠명_live}"
    return result


def write_csv(rows: list[RenameResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(row) for row in rows]
    fieldnames = list(asdict(RenameResult("", "", "")).keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(payload)


def main() -> None:
    args = parse_args()
    plan_rows = load_plan(Path(args.plan_csv), args.content_id, args.limit)
    settings = BrowserSettings(
        headless=args.headless,
        slow_mo_ms=args.slow_mo_ms,
        timeout_ms=args.timeout_ms,
        artifacts_root=SIAAN_PROJECT_ROOT / "output" / "ips_harness",
    )
    env_path = resolve_env_path(args.env_file)
    site = get_site("kipm")

    results: list[RenameResult] = []
    with IPSHarness(site, settings=settings, env_path=env_path) as harness:
        harness.ensure_logged_in(path="/ip/cntsd/cntschg/ctns-chg-list?pageNum=1&pageSize=10")
        harness.page.wait_for_timeout(1_500)
        for index, row in enumerate(plan_rows, start=1):
            print(f"[{index}/{len(plan_rows)}] {row['콘텐츠ID']} -> {row['변경후콘텐츠명']}", flush=True)
            results.append(process_one(harness.page, row, write=args.write, stuff_defaults=args.stuff_defaults))

    output = Path(args.csv_output)
    write_csv(results, output)
    summary = Counter(row.상태 for row in results)
    summary_path = output.with_name(output.stem + "_summary.csv")
    with summary_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["항목", "값"])
        writer.writeheader()
        writer.writerow({"항목": "generated_at", "값": datetime.now().isoformat(timespec="seconds")})
        writer.writerow({"항목": "write", "값": str(bool(args.write))})
        writer.writerow({"항목": "processed_count", "값": str(len(results))})
        writer.writerow({"항목": "csv_output", "값": str(output)})
        for key, value in summary.items():
            writer.writerow({"항목": f"status.{key}", "값": str(value)})

    print(f"processed={len(results)} summary={dict(summary)}")
    print(f"csv_output={output}")
    print(f"summary_csv={summary_path}")


if __name__ == "__main__":
    main()
