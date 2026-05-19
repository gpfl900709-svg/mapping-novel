from __future__ import annotations

import argparse
import csv
import json
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
WORK_DIR = PROJECT_ROOT / "담당컨텐츠_분류"

sys.path.insert(0, str(SCRIPTS_ROOT))

from ips.core.auth import resolve_env_path  # noqa: E402
from ips.core.browser import BrowserSettings  # noqa: E402
from ips.core.harness import IPSHarness  # noqa: E402
from ips.sites import get_site  # noqa: E402
from rename_ips_content_titles import RenameCandidate  # noqa: E402
from rename_ips_content_titles_api import (  # noqa: E402
    DEFAULT_STUFFING,
    DETAIL_PATH,
    SAVE_PATH,
    axios_call,
    coerce_csv_arrays,
    extract_detail_vo,
    normalize_list_fields,
    scrub_date_fields,
    split_csv,
    stuff_empty_required_fields,
)


DEFAULT_PLAN_CSV = WORK_DIR / "latest__북홀릭_update_ips_rename_apply.csv"
DEFAULT_OUTPUT_CSV = WORK_DIR / "latest__북홀릭_ips_live_rename_report.csv"
DEFAULT_OUTPUT_JSON = WORK_DIR / "latest__북홀릭_ips_live_rename_report.json"
DEFAULT_MANAGER = "조원재"


@dataclass
class LiveRenameResult:
    work_cid: str
    target_title: str
    plan_before_title: str = ""
    current_title: str = ""
    final_title: str = ""
    manager_name: str = ""
    status: str = ""
    reason: str = ""
    missing_required_fields: str = ""
    stuffed_fields: str = ""
    get_status: int | None = None
    put_status: int | None = None
    server_message: str = ""
    server_body: str = ""

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def text(value: Any) -> str:
    return str(value or "").strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply the 북홀릭 local rename plan to live IPS via in-page axios.",
    )
    parser.add_argument("--plan-csv", default=str(DEFAULT_PLAN_CSV))
    parser.add_argument("--csv-output", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--json-output", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--manager", default=DEFAULT_MANAGER)
    parser.add_argument("--env-file", default="")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--timeout-ms", type=int, default=20_000)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--content-id", action="append", default=[])
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually PUT the live IPS rename. Default is dry-run GET only.",
    )
    parser.add_argument(
        "--stuff-defaults",
        action="store_true",
        help="Fill empty required fields before PUT, matching the existing API rename harness behavior.",
    )
    parser.add_argument(
        "--skip-manager-check",
        action="store_true",
        help="Do not require live 담당자/chgerNm to match --manager.",
    )
    return parser.parse_args()


def load_candidates(path: Path, content_ids: list[str], limit: int) -> list[RenameCandidate]:
    requested = {text(value) for value in content_ids if text(value)}
    candidates: list[RenameCandidate] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            cid = text(row.get("콘텐츠ID"))
            target = text(row.get("변경후콘텐츠명"))
            if not cid or not target:
                continue
            if requested and cid not in requested:
                continue
            candidates.append(
                RenameCandidate(
                    work_cid=cid,
                    folder_path="",
                    source_title=text(row.get("변경전콘텐츠명")),
                    author_name="북홀릭",
                    remark="",
                    target_title=target,
                    note=text(row.get("처리사유")),
                )
            )
    if limit > 0:
        candidates = candidates[:limit]
    return candidates


def missing_required_fields(detail_vo: dict[str, Any]) -> list[str]:
    return [key for key in DEFAULT_STUFFING if detail_vo.get(key) in ("", None)]


def read_server_message(data: Any, error: Any) -> tuple[str, str]:
    message = ""
    if isinstance(data, dict):
        message = text(data.get("message") or data.get("error") or "")
    elif isinstance(data, str):
        message = data
    try:
        body = json.dumps(data, ensure_ascii=False)[:800] if data is not None else ""
    except Exception:  # noqa: BLE001
        body = text(data)[:800]
    return (message or text(error))[:500], body


def process_candidate(
    page: Any,
    candidate: RenameCandidate,
    *,
    write: bool,
    manager: str,
    stuff_defaults: bool,
    skip_manager_check: bool,
) -> LiveRenameResult:
    result = LiveRenameResult(
        work_cid=candidate.work_cid,
        target_title=candidate.target_title,
        plan_before_title=candidate.source_title,
    )

    get_resp = axios_call(page, "get", DETAIL_PATH.format(cid=candidate.work_cid))
    result.get_status = get_resp.get("status")
    if not get_resp.get("ok"):
        result.status = "get_failed"
        result.reason = text(get_resp.get("error") or get_resp.get("data"))[:300]
        return result

    full_response = get_resp.get("data") if isinstance(get_resp.get("data"), dict) else {}
    detail_vo = extract_detail_vo(full_response)
    if not detail_vo:
        result.status = "no_detail_vo"
        result.reason = f"response keys: {list(full_response.keys())}"
        return result

    result.current_title = text(detail_vo.get("ctnsNm"))
    result.final_title = result.current_title
    result.manager_name = text(detail_vo.get("chgerNm") or detail_vo.get("ctnsChgerNm"))
    result.missing_required_fields = ",".join(missing_required_fields(detail_vo))

    if not skip_manager_check and manager and result.manager_name != manager:
        result.status = "skipped_unexpected_manager"
        result.reason = f"manager={result.manager_name}"
        return result

    if result.current_title == candidate.target_title:
        result.status = "already_named"
        result.reason = "current_title_matches_target"
        return result

    if not write:
        result.status = "ready_api"
        result.reason = "dry_run"
        return result

    put_payload: dict[str, Any] = dict(detail_vo)
    put_payload["ctnsNm"] = candidate.target_title
    put_payload["rgtList"] = full_response.get("rgtList") or []
    if stuff_defaults:
        result.stuffed_fields = ",".join(stuff_empty_required_fields(put_payload))
    scrub_date_fields(put_payload)
    coerce_csv_arrays(put_payload)
    normalize_list_fields(put_payload)

    debug_dir = SIAAN_PROJECT_ROOT / "output" / "ips_api_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / f"bukholic_put_payload_{candidate.work_cid}.json").write_text(
        json.dumps(put_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    put_resp = axios_call(page, "put", SAVE_PATH, put_payload)
    result.put_status = put_resp.get("status")
    if not put_resp.get("ok"):
        result.server_message, result.server_body = read_server_message(
            put_resp.get("data"),
            put_resp.get("error"),
        )
        result.status = "put_failed"
        result.reason = f"status={put_resp.get('status')}"
        return result

    verify_resp = axios_call(page, "get", DETAIL_PATH.format(cid=candidate.work_cid))
    verify_vo = extract_detail_vo(verify_resp.get("data")) if verify_resp.get("ok") else None
    result.final_title = text((verify_vo or {}).get("ctnsNm"))
    if result.final_title == candidate.target_title:
        result.status = "updated"
        result.reason = "verified_after_reload"
    else:
        result.status = "verify_failed"
        result.reason = f"server_returned={result.final_title}"
    return result


def write_reports(rows: list[LiveRenameResult], csv_path: Path, json_path: Path, *, write: bool) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload_rows = [row.to_row() for row in rows]
    fieldnames = list(payload_rows[0].keys()) if payload_rows else list(LiveRenameResult("", "").to_row().keys())
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(payload_rows)
    summary = Counter(row.status for row in rows)
    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "write": write,
                "summary": dict(summary),
                "rows": payload_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    candidates = load_candidates(Path(args.plan_csv), args.content_id, args.limit)
    settings = BrowserSettings(
        headless=args.headless,
        slow_mo_ms=args.slow_mo_ms,
        timeout_ms=args.timeout_ms,
        artifacts_root=SIAAN_PROJECT_ROOT / "output" / "ips_harness",
    )
    env_path = resolve_env_path(args.env_file)
    site = get_site("kipm")

    rows: list[LiveRenameResult] = []
    with IPSHarness(site, settings=settings, env_path=env_path) as harness:
        harness.ensure_logged_in(path="/ip/cntsd/cntschg/ctns-chg-list?pageNum=1&pageSize=10")
        harness.page.wait_for_timeout(1_500)
        for index, candidate in enumerate(candidates, start=1):
            print(f"[{index}/{len(candidates)}] {candidate.work_cid} -> {candidate.target_title}")
            rows.append(
                process_candidate(
                    harness.page,
                    candidate,
                    write=args.write,
                    manager=args.manager,
                    stuff_defaults=args.stuff_defaults,
                    skip_manager_check=args.skip_manager_check,
                )
            )

    csv_output = Path(args.csv_output)
    json_output = Path(args.json_output)
    write_reports(rows, csv_output, json_output, write=args.write)
    summary = Counter(row.status for row in rows)
    print(
        json.dumps(
            {
                "write": args.write,
                "processed_count": len(rows),
                "summary": dict(summary),
                "csv_output": str(csv_output),
                "json_output": str(json_output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    for row in rows:
        if row.status in {"put_failed", "get_failed", "verify_failed", "skipped_unexpected_manager"}:
            print(f"  [{row.status}] {row.work_cid} {row.reason} {row.server_message}")


if __name__ == "__main__":
    main()
