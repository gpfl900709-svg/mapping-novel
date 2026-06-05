from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "SIAAN Project"

from ips.core.auth import resolve_env_path
from ips.core.browser import BrowserSettings
from ips.core.harness import IPSHarness
from ips.sites import get_site
from secret_redaction import write_json_redacted
from rename_ips_content_titles import (
    DEFAULT_MANUAL_OVERRIDES_PATH,
    DEFAULT_REVIEW_QUEUE_PATH,
    SPECIAL_CASE_TOKENS,
    RenameCandidate,
    build_abandon_candidates,
    build_explicit_candidates,
    build_safe_candidates,
    filter_candidates,
    load_json,
)

DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "exports" / "ips" / "ips_title_change_api_report.csv"
DEFAULT_JSON_PATH = PROJECT_ROOT / "data" / "catalog" / "ips_title_change_api_report.json"

DETAIL_PATH = "/cntsd/cntschg/ctns-chg-list/detail/{cid}"
SAVE_PATH = "/cntsd/cntschg/ctns-chg-list/ctns-info"

DEFAULT_STUFFING: dict[str, Any] = {
    "svcTyCd": "002",         # 연재
    "mnplyCd": "003",         # 비독점
    "serlPargCyclCd": "002",  # 주1회
    "ctnsExptQntCd": "003",   # 장편
    "exptSerlMt": "202601",
    "exptSerlTme": 100,
    "gradCd": "002",          # 비성인
    "genrCd": "002",          # 남성향
}

CSV_ARRAY_STRING_FIELDS = ("ctnsDtlGenrCd", "innExtChnlCd", "uperSchnCd")
CSV_ARRAY_INT_FIELDS = ("lwerSchnCd",)

AXIOS_CALL_SCRIPT = """
async ({ method, path, payload }) => {
    const app = document.querySelector('#app');
    const axios = app && app.__vue_app__._context.provides['$axios'];
    if (!axios) { return { ok: false, error: 'axios-not-found' }; }
    try {
        const config = { method, url: path };
        if (payload !== undefined) { config.data = payload; }
        const response = await axios.request(config);
        return { ok: true, status: response.status, data: response.data };
    } catch (error) {
        return {
            ok: false,
            error: String((error && error.message) || error),
            status: error && error.response && error.response.status,
            data: error && error.response && error.response.data,
        };
    }
}
"""


@dataclass
class ApiRenameResult:
    work_cid: str
    target_title: str
    current_title: str = ""
    final_title: str = ""
    status: str = ""
    reason: str = ""
    get_status: int | None = None
    put_status: int | None = None
    server_message: str = ""
    stuffed_fields: str = ""
    server_body: str = ""

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rename IPS 콘텐츠명 via API (bypasses Vuetify client-side validation).",
    )
    parser.add_argument("--manual-overrides", default=str(DEFAULT_MANUAL_OVERRIDES_PATH))
    parser.add_argument("--review-queue", default=str(DEFAULT_REVIEW_QUEUE_PATH))
    parser.add_argument("--env-file", default="")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--timeout-ms", type=int, default=20_000)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--content-id", action="append", default=[])
    parser.add_argument("--csv-output", default=str(DEFAULT_CSV_PATH))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_PATH))
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually PUT the rename. Default is dry-run (GET only).",
    )
    parser.add_argument(
        "--stuff-defaults",
        action="store_true",
        help="Fill empty required fields with sensible defaults before PUT.",
    )
    return parser.parse_args()


def axios_call(page: Any, method: str, path: str, payload: Any = None) -> dict[str, Any]:
    return page.evaluate(AXIOS_CALL_SCRIPT, {"method": method, "path": path, "payload": payload})


def extract_detail_vo(response_data: Any) -> dict[str, Any] | None:
    if not isinstance(response_data, dict):
        return None
    vo = response_data.get("ctnsDetailVO")
    if isinstance(vo, dict):
        return vo
    if "ctnsNm" in response_data:
        return response_data
    return None


def scrub_date_fields(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("exptSerlMt", "cntrStrtYmd", "cntrExpiYmd"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            payload[key] = value.replace("-", "")
    return payload


def normalize_list_fields(payload: dict[str, Any]) -> None:
    for key, value in list(payload.items()):
        if key.endswith("List") and value is None:
            payload[key] = []
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    normalize_list_fields(entry)
        elif isinstance(value, dict):
            normalize_list_fields(value)


def split_csv(raw: Any) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def coerce_csv_arrays(payload: dict[str, Any]) -> None:
    for key in CSV_ARRAY_STRING_FIELDS:
        if key in payload:
            payload[key] = split_csv(payload[key])
    for key in CSV_ARRAY_INT_FIELDS:
        if key in payload:
            parts = split_csv(payload[key])
            payload[key] = [int(part) for part in parts if part.lstrip("-").isdigit()]


def detect_special_case(detail_vo: dict[str, Any], full_response: dict[str, Any]) -> str:
    haystacks: list[str] = []
    for key in ("ctnsNm", "lwerSchnNm", "uperSchnNm", "innExtChnlSeNm", "pblcoNm", "pltfomExpsrNm"):
        value = detail_vo.get(key) or full_response.get(key)
        if value:
            haystacks.append(str(value))
    for item in (full_response.get("schnCtnsInfoList") or []):
        if not isinstance(item, dict):
            continue
        for key in ("lwerSchnNm", "pltfomExpsrNm", "schnCtnsNm", "innExtChnlSeNm"):
            value = item.get(key)
            if value:
                haystacks.append(str(value))
    blob = " | ".join(haystacks)
    for token in SPECIAL_CASE_TOKENS:
        if token and token in blob:
            return token
    return ""


def stuff_empty_required_fields(payload: dict[str, Any]) -> list[str]:
    stuffed: list[str] = []
    for key, default in DEFAULT_STUFFING.items():
        current = payload.get(key)
        if current in ("", None):
            payload[key] = default
            stuffed.append(key)
    return stuffed


def process_candidate(
    page: Any,
    candidate: RenameCandidate,
    *,
    write: bool,
    stuff_defaults: bool = False,
    bypass_special_case: bool = False,
) -> ApiRenameResult:
    result = ApiRenameResult(work_cid=candidate.work_cid, target_title=candidate.target_title)

    get_resp = axios_call(page, "get", DETAIL_PATH.format(cid=candidate.work_cid))
    result.get_status = get_resp.get("status")
    if not get_resp.get("ok"):
        result.status = "get_failed"
        result.reason = str(get_resp.get("error") or get_resp.get("data") or "")[:300]
        return result

    detail_vo = extract_detail_vo(get_resp.get("data"))
    if not detail_vo:
        result.status = "no_detail_vo"
        result.reason = f"response keys: {list((get_resp.get('data') or {}).keys())}"
        return result

    current_title = str(detail_vo.get("ctnsNm") or "").strip()
    result.current_title = current_title

    if current_title == candidate.target_title:
        result.status = "already_named"
        result.reason = "current_title_matches_target"
        result.final_title = current_title
        return result

    full_response = get_resp.get("data") if isinstance(get_resp.get("data"), dict) else {}
    if not bypass_special_case:
        special_token = detect_special_case(detail_vo, full_response)
        if special_token:
            result.status = "skipped_special_case"
            result.reason = f"special_token:{special_token}"
            result.final_title = current_title
            return result

    if not write:
        result.status = "ready_api"
        result.reason = "dry_run"
        result.final_title = current_title
        return result

    put_payload: dict[str, Any] = dict(detail_vo)
    put_payload["ctnsNm"] = candidate.target_title
    put_payload["rgtList"] = full_response.get("rgtList") or []
    if stuff_defaults:
        result.stuffed_fields = ",".join(stuff_empty_required_fields(put_payload))
    scrub_date_fields(put_payload)
    coerce_csv_arrays(put_payload)
    normalize_list_fields(put_payload)

    debug_dir = PROJECT_ROOT / "output" / "ips_api_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    write_json_redacted(debug_dir / f"put_payload_{candidate.work_cid}.json", put_payload)

    put_resp = axios_call(page, "put", SAVE_PATH, put_payload)
    result.put_status = put_resp.get("status")
    if not put_resp.get("ok"):
        data = put_resp.get("data")
        message = ""
        if isinstance(data, dict):
            message = str(data.get("message") or data.get("error") or "")
        elif isinstance(data, str):
            message = data
        result.server_message = (message or str(put_resp.get("error") or ""))[:500]
        try:
            result.server_body = json.dumps(data, ensure_ascii=False)[:800] if data is not None else ""
        except Exception:  # noqa: BLE001
            result.server_body = str(data)[:800]
        result.status = "put_failed"
        result.reason = f"status={put_resp.get('status')}"
        result.final_title = current_title
        return result

    verify_resp = axios_call(page, "get", DETAIL_PATH.format(cid=candidate.work_cid))
    verify_vo = extract_detail_vo(verify_resp.get("data")) if verify_resp.get("ok") else None
    verified_title = str((verify_vo or {}).get("ctnsNm") or "").strip()
    result.final_title = verified_title

    if verified_title == candidate.target_title:
        result.status = "updated"
        result.reason = "verified_after_reload"
    else:
        result.status = "verify_failed"
        result.reason = f"server_returned='{verified_title}'"
    return result


def write_reports(rows: list[ApiRenameResult], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload_rows = [row.to_row() for row in rows]
    fieldnames = list(payload_rows[0].keys()) if payload_rows else list(
        ApiRenameResult("", "").to_row().keys()
    )

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(payload_rows)

    summary = Counter(row.status for row in rows)
    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(),
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
    manual_overrides_payload = load_json(Path(args.manual_overrides))
    review_payload = load_json(Path(args.review_queue))

    candidates = build_safe_candidates(manual_overrides_payload, review_payload)
    abandon_candidates = build_abandon_candidates(manual_overrides_payload)
    explicit_candidates = build_explicit_candidates(manual_overrides_payload)
    candidates.extend(abandon_candidates)
    candidates.extend(explicit_candidates)
    selected = filter_candidates(candidates, args.content_id, args.limit)

    bypass_cids: set[str] = {
        str(cid).strip()
        for cid in manual_overrides_payload.get("ips_bundle_whitelist", []) or []
        if str(cid).strip()
    }
    bypass_cids.update(str(c.work_cid).strip() for c in abandon_candidates)
    bypass_cids.update(str(c.work_cid).strip() for c in explicit_candidates)

    settings = BrowserSettings(
        headless=args.headless,
        slow_mo_ms=args.slow_mo_ms,
        timeout_ms=args.timeout_ms,
        artifacts_root=PROJECT_ROOT / "output" / "ips_harness",
    )
    env_path = resolve_env_path(args.env_file)
    site = get_site("kipm")

    rows: list[ApiRenameResult] = []
    with IPSHarness(site, settings=settings, env_path=env_path) as harness:
        harness.ensure_logged_in(path="/ip/cntsd/cntschg/ctns-chg-list?pageNum=1&pageSize=10")
        harness.page.wait_for_timeout(1_500)
        for index, candidate in enumerate(selected, start=1):
            print(f"[{index}/{len(selected)}] {candidate.work_cid} {candidate.target_title}")
            rows.append(
                process_candidate(
                    harness.page,
                    candidate,
                    write=args.write,
                    stuff_defaults=args.stuff_defaults,
                    bypass_special_case=candidate.work_cid in bypass_cids,
                )
            )

    csv_path = Path(args.csv_output)
    json_path = Path(args.json_output)
    write_reports(rows, csv_path, json_path)

    summary = Counter(row.status for row in rows)
    print(
        json.dumps(
            {
                "write": args.write,
                "candidate_count": len(candidates),
                "processed_count": len(rows),
                "summary": dict(summary),
                "csv_output": str(csv_path),
                "json_output": str(json_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    failed_samples = [r for r in rows if r.status in {"put_failed", "get_failed"}][:3]
    for r in failed_samples:
        print(f"  [{r.status}] {r.work_cid}  status={r.put_status or r.get_status}  msg={r.server_message or r.reason}")
        if r.server_body:
            print(f"    body: {r.server_body[:300]}")


if __name__ == "__main__":
    main()
