from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ips.core.auth import resolve_env_path
from ips.core.browser import BrowserSettings
from ips.core.harness import IPSHarness
from ips.sites import get_site
from ips_sales_channel_harness import axios_get_detail, match_platform_rows, platform_match_keys, platform_key


PROJECT_ROOT = Path(__file__).resolve().parents[1] / "SIAAN Project"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "ips_sales_channel_additions"
DETAIL_VIEW_PATH_TEMPLATE = "/ip/cntsd/cntslt/ctns-detail?parCtnsId={cid}"
ADD_PLATFORM_PATH = "cntsd/cntslt/ctns-list/add-ctns-schn-info"
SETTLEMENT_TEMPLATE_PATH = "cntsd/cntslt/ctns-list/ctns-cntr-setl-srcCntrId-list"
CONTENT_DETAIL_PATH = "cntsd/cntslt/ctns-list/detail/{cid}"
CHANNEL_LIST_PATH = "schn/cmm/select-schn-list"

ADD_PAYLOAD_FIELDS = (
    "pymtCrcy",
    "pymtExchrDtCd",
    "srcCrcy",
    "srcExchrDtCd",
    "setlCrcy",
    "setlExchrDtCd",
    "adpycTyCd",
    "adpycPymtTyCd",
    "mgCntrAmt",
    "adpycPymtAmt",
    "adpycStoffTyCd",
    "adpycStoffBlceTyCd",
    "adpycStoffAmt",
    "rsMgStoffTrgYn",
    "rsSetlMthCd",
    "rsSetlRt",
    "rsSetlBnusCoinYn",
    "webCoinSetlAmt",
    "appCoinSetlAmt",
    "webCoinSetlRt",
    "webCoinUnpcWithRt",
    "appCoinSetlRt",
    "appCoinUnpcWithRt",
)

ADD_PAYLOAD_DEFAULTS: dict[str, Any] = {
    "pymtCrcy": "KRW",
    "pymtExchrDtCd": "999",
    "srcCrcy": "KRW",
    "srcExchrDtCd": "999",
    "setlCrcy": "KRW",
    "setlExchrDtCd": "999",
    "adpycTyCd": "001",
    "adpycPymtTyCd": "999",
    "mgCntrAmt": 0,
    "adpycPymtAmt": 0,
    "adpycStoffTyCd": "001",
    "adpycStoffBlceTyCd": "001",
    "adpycStoffAmt": 0,
    "rsMgStoffTrgYn": "N",
    "rsSetlMthCd": "001",
    "rsSetlRt": 70,
    "rsSetlBnusCoinYn": "N",
    "webCoinSetlAmt": 0,
    "appCoinSetlAmt": 0,
    "webCoinSetlRt": 0,
    "webCoinUnpcWithRt": 0,
    "appCoinSetlRt": 0,
    "appCoinUnpcWithRt": 0,
}


@dataclass(frozen=True)
class AddRequest:
    index: int
    row: dict[str, Any]
    cid: str
    platform_name: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read ips_sales_channel_harness output rows with next_action=add_platform_in_ips, "
            "open [7021] 콘텐츠상세 > 정산정보 > 판매채널추가, and save the missing 판매채널."
        ),
    )
    parser.add_argument("--input", required=True, help="CSV/JSON output path from ips_sales_channel_harness.py")
    parser.add_argument("--output", default="", help="Optional CSV output path")
    parser.add_argument("--json-output", default="", help="Optional JSON output path")
    parser.add_argument("--cid-column", default="work_cid")
    parser.add_argument("--platform-column", default="input_platform")
    parser.add_argument("--action-column", default="next_action")
    parser.add_argument("--required-action", default="add_platform_in_ips")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--env-file", default="")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=25_000)
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--write", action="store_true", help="Actually add missing sales channels in live KIPM. Default is dry-run.")
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [dict(item) for item in payload]
        if isinstance(payload, dict):
            rows = payload.get("rows")
            if isinstance(rows, list):
                return [dict(item) for item in rows]
        raise ValueError(f"Unsupported JSON shape for {path}")
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    raise ValueError(f"Unsupported input format: {path.suffix}")


def build_requests(
    rows: list[dict[str, Any]],
    *,
    cid_column: str,
    platform_column: str,
    action_column: str,
    required_action: str,
    limit: int,
) -> list[AddRequest]:
    requests: list[AddRequest] = []
    for index, row in enumerate(rows):
        if str(row.get(action_column) or "").strip() != required_action:
            continue
        cid = str(row.get(cid_column) or "").strip()
        platform_name = str(row.get(platform_column) or "").strip()
        if not cid or not platform_name:
            continue
        requests.append(AddRequest(index=index, row=row, cid=cid, platform_name=platform_name))
        if limit and len(requests) >= limit:
            break
    return requests


def build_output_paths(args: argparse.Namespace) -> tuple[Path | None, Path | None]:
    main_output = Path(args.output) if args.output else None
    json_output = Path(args.json_output) if args.json_output else None
    if main_output is None and json_output is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        main_output = DEFAULT_OUTPUT_DIR / f"{stamp}__ips_sales_channel_additions.csv"
        json_output = DEFAULT_OUTPUT_DIR / f"{stamp}__ips_sales_channel_additions.json"
    elif main_output is not None and main_output.suffix.lower() == ".csv" and json_output is None:
        json_output = main_output.with_suffix(".json")
    return main_output, json_output


def build_detail_view_url(cid: str) -> str:
    site = get_site("kipm")
    return site.resolve_url(DETAIL_VIEW_PATH_TEMPLATE.format(cid=cid))


def click_tab(page: Any, title: str) -> None:
    page.locator("button.v-tab", has_text=title).first.click()
    page.wait_for_timeout(800)


def find_visible_dialog(page: Any) -> Any:
    dialogs = page.locator('[role="dialog"]')
    for index in range(dialogs.count()):
        dialog = dialogs.nth(index)
        if dialog.is_visible():
            return dialog
    raise LookupError("판매채널 추가 팝업을 찾지 못했습니다.")


def select_platform_option(page: Any, platform_name: str) -> None:
    requested_keys = platform_match_keys(platform_name)
    dropdowns = page.locator(".rg-dropdownlist[id^='rg-dropdown-list-']")
    fallback_option = None
    for index in range(dropdowns.count()):
        dropdown = dropdowns.nth(index)
        if not dropdown.is_visible():
            continue
        options = dropdown.locator("[role='option']")
        for option_index in range(options.count()):
            option = options.nth(option_index)
            if not option.is_visible():
                continue
            option_text = option.inner_text().strip()
            option_key = platform_key(option_text)
            if option_text == platform_name or option_key in requested_keys:
                option.click()
                return
            if option_key and any(requested in option_key or option_key in requested for requested in requested_keys):
                fallback_option = option
    if fallback_option is not None:
        fallback_option.click()
        return
    raise LookupError(f"판매채널 옵션을 찾지 못했습니다: {platform_name}")


def select_channel_row(channels: list[dict[str, Any]], platform_name: str) -> dict[str, Any] | None:
    requested_keys = platform_match_keys(platform_name)
    fallback: dict[str, Any] | None = None
    for channel in channels:
        option_key = platform_key(str(channel.get("schnNm") or ""))
        if not option_key:
            continue
        if option_key in requested_keys:
            return channel
        if any(requested in option_key or option_key in requested for requested in requested_keys):
            fallback = channel
    return fallback


def click_visible_button(scope: Any, label: str) -> bool:
    buttons = scope.locator("button")
    for index in range(buttons.count()):
        button = buttons.nth(index)
        if not button.is_visible():
            continue
        if button.inner_text().strip() == label:
            button.click()
            return True
    return False


def platform_snapshot(detail_data: dict[str, Any], platform_name: str) -> tuple[dict[str, Any] | None, str]:
    matched_platform, rows = match_platform_rows(detail_data, platform_name)
    snapshot = []
    for row in rows:
        row_name = str(row.get("lwerSchnNm") or "").strip()
        if not row_name:
            continue
        schn_ctns_id = str(row.get("schnCtnsId") or "").strip()
        snapshot.append(f"{row_name}:{schn_ctns_id}" if schn_ctns_id else row_name)
    return matched_platform, " | ".join(snapshot)


def fetch_detail_data(page: Any, cid: str) -> dict[str, Any]:
    detail_resp = axios_get_detail(page, cid)
    if not detail_resp.get("ok"):
        error_text = str(detail_resp.get("error") or detail_resp.get("data") or "")
        raise RuntimeError(f"detail fetch failed cid={cid}: {error_text[:300]}")
    return detail_resp.get("data") if isinstance(detail_resp.get("data"), dict) else {}


def add_platform_via_api(page: Any, cid: str, platform_name: str) -> dict[str, Any]:
    current_detail = fetch_detail_data(page, cid)
    matched_platform, snapshot = platform_snapshot(current_detail, platform_name)
    if matched_platform is not None:
        return {
            "addition_status": "already_present",
            "sales_channel_content_id": str(matched_platform.get("schnCtnsId") or "").strip(),
            "matched_platform_name": str(matched_platform.get("lwerSchnNm") or "").strip(),
            "existing_platform_snapshot": snapshot,
        }

    setup = page.evaluate(
        """
        async ({ cid, detailPath, templatePath, channelPath }) => {
          const axios = document.querySelector('#app').__vue_app__._context.provides['$axios'];
          const detailResp = await axios.get(detailPath.replace('{cid}', cid));
          const detail = detailResp.data || {};
          const cpr = detail.rversCprCd || detail.cprCd || '1000';
          const templateResp = await axios.get(templatePath, {
            params: {
              srchCntrId: 0,
              srcCntrClCd: '',
              srcCtnsId: String(cid),
              srcCprCd: cpr,
            },
          });
          const channelResp = await axios.get(channelPath);
          return {
            detail,
            templateRows: templateResp.data?.list || [],
            channels: channelResp.data || [],
          };
        }
        """,
        {
            "cid": cid,
            "detailPath": CONTENT_DETAIL_PATH,
            "templatePath": SETTLEMENT_TEMPLATE_PATH,
            "channelPath": CHANNEL_LIST_PATH,
        },
    )

    channel = select_channel_row(list(setup.get("channels") or []), platform_name)
    if channel is None:
        raise LookupError(f"판매채널 옵션을 찾지 못했습니다: {platform_name}")

    template_rows = list(setup.get("templateRows") or [])
    if not template_rows:
        raise RuntimeError("판매채널 정산 템플릿을 찾지 못했습니다.")
    base_row = next((row for row in template_rows if str(row.get("pymtStd") or "") == "지급"), template_rows[0])
    detail = setup.get("detail") or {}
    payload = {}
    for key in ADD_PAYLOAD_FIELDS:
        value = base_row.get(key)
        if value is None or value == "":
            value = ADD_PAYLOAD_DEFAULTS.get(key)
        payload[key] = value
    payload.update(
        {
            "schnId": channel.get("schnId"),
            "cntrId": base_row.get("cntrId") or 0,
            "ctnsId": cid,
            "ctnsStleCd": detail.get("ctnsStleCd") or current_detail.get("ctnsStleCd") or "",
        }
    )

    result = page.evaluate(
        """
        async ({ path, payload }) => {
          const axios = document.querySelector('#app').__vue_app__._context.provides['$axios'];
          try {
            const response = await axios.post(path, [payload]);
            return { ok: true, data: response?.data || null };
          } catch (error) {
            return {
              ok: false,
              status: error?.response?.status || null,
              data: error?.response?.data || null,
              message: String(error),
            };
          }
        }
        """,
        {"path": ADD_PLATFORM_PATH, "payload": payload},
    )
    if not result.get("ok"):
        raise RuntimeError(f"판매채널 API 추가 실패: {result}")

    page.wait_for_timeout(1_500)
    detail_data = fetch_detail_data(page, cid)
    matched_platform, snapshot = platform_snapshot(detail_data, platform_name)
    if matched_platform is None:
        raise RuntimeError(f"판매채널 저장 후에도 플랫폼이 보이지 않습니다: {platform_name}")

    return {
        "addition_status": "added",
        "sales_channel_content_id": str(matched_platform.get("schnCtnsId") or "").strip(),
        "matched_platform_name": str(matched_platform.get("lwerSchnNm") or "").strip(),
        "existing_platform_snapshot": snapshot,
    }


def add_platform_via_detail(page: Any, cid: str, platform_name: str) -> dict[str, Any]:
    page.goto(build_detail_view_url(cid), wait_until="domcontentloaded", timeout=25_000)
    page.wait_for_timeout(2_000)

    try:
        return add_platform_via_api(page, cid, platform_name)
    except Exception:  # noqa: BLE001
        # Some special settlement CIDs only expose billing-side templates to the
        # API endpoint. Fall back to the browser flow, which is what an operator
        # would do in IPS.
        try:
            click_visible_button(page, "확인")
            page.keyboard.press("Escape")
        except Exception:  # noqa: BLE001
            pass
        page.goto(build_detail_view_url(cid), wait_until="domcontentloaded", timeout=25_000)
        page.wait_for_timeout(2_000)

    click_tab(page, "정산정보")
    detail_data = fetch_detail_data(page, cid)
    matched_platform, snapshot = platform_snapshot(detail_data, platform_name)
    if matched_platform is not None:
        return {
            "addition_status": "already_present",
            "sales_channel_content_id": str(matched_platform.get("schnCtnsId") or "").strip(),
            "matched_platform_name": str(matched_platform.get("lwerSchnNm") or "").strip(),
            "existing_platform_snapshot": snapshot,
        }

    page.get_by_role("button", name="판매채널추가").click()
    page.wait_for_timeout(1_200)
    dialog = find_visible_dialog(page)

    first_row_cells = dialog.locator("#mgGrid .rg-body tbody tr .rg-data-cell")
    if first_row_cells.count() < 2:
        if not click_visible_button(dialog, "추가"):
            raise RuntimeError("판매채널 추가 모달의 추가 버튼을 찾지 못했습니다.")
        page.wait_for_timeout(1_000)
        first_row_cells = dialog.locator("#mgGrid .rg-body tbody tr .rg-data-cell")
    if first_row_cells.count() < 2:
        raise RuntimeError("판매채널 추가 모달의 지급액 그리드를 찾지 못했습니다.")

    channel_cell = first_row_cells.first
    channel_cell.click()
    page.wait_for_timeout(400)
    select_platform_option(page, platform_name)
    page.wait_for_timeout(600)

    # Commit the dropdown choice before saving.
    first_row_cells.nth(1).click()
    page.wait_for_timeout(400)

    if not click_visible_button(dialog, "저장"):
        raise RuntimeError("판매채널 추가 모달의 저장 버튼을 찾지 못했습니다.")

    page.wait_for_timeout(1_000)
    click_visible_button(page, "확인")
    page.wait_for_timeout(1_200)

    try:
        dialog.wait_for(state="hidden", timeout=8_000)
    except Exception:  # noqa: BLE001
        pass

    page.wait_for_timeout(2_000)
    detail_data = fetch_detail_data(page, cid)
    matched_platform, snapshot = platform_snapshot(detail_data, platform_name)
    if matched_platform is None:
        raise RuntimeError(f"판매채널 저장 후에도 플랫폼이 보이지 않습니다: {platform_name}")

    return {
        "addition_status": "added",
        "sales_channel_content_id": str(matched_platform.get("schnCtnsId") or "").strip(),
        "matched_platform_name": str(matched_platform.get("lwerSchnNm") or "").strip(),
        "existing_platform_snapshot": snapshot,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key in seen:
                continue
            seen.add(key)
            fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def process_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    input_rows = load_rows(Path(args.input))
    requests = build_requests(
        input_rows,
        cid_column=args.cid_column,
        platform_column=args.platform_column,
        action_column=args.action_column,
        required_action=args.required_action,
        limit=args.limit,
    )
    if not requests:
        return input_rows

    if not getattr(args, "write", False):
        for request in requests:
            row = input_rows[request.index]
            row["detail_view_url"] = build_detail_view_url(request.cid)
            row["addition_status"] = "dry_run"
            row["addition_error"] = ""
            row["next_action"] = request.row.get(args.action_column, args.required_action)
        return input_rows

    settings = BrowserSettings(
        headless=args.headless,
        slow_mo_ms=args.slow_mo_ms,
        timeout_ms=args.timeout_ms,
        artifacts_root=PROJECT_ROOT / "output" / "ips_harness",
    )
    env_path = resolve_env_path(args.env_file)
    site = get_site("kipm")

    with IPSHarness(site, settings=settings, env_path=env_path) as harness:
        harness.ensure_logged_in(path="/ip/cntsd/cntslt/ctns-list?pageNum=1&pageSize=10")
        page = harness.page
        for request in requests:
            row = input_rows[request.index]
            row["detail_view_url"] = build_detail_view_url(request.cid)
            try:
                result = add_platform_via_detail(page, request.cid, request.platform_name)
                row.update(result)
                row["detail_status"] = "loaded"
                row["platform_match_status"] = "found"
                row["next_action"] = "paste_sales_channel_content_id"
                row["addition_error"] = ""
            except Exception as exc:  # noqa: BLE001
                row["addition_status"] = "failed"
                row["addition_error"] = str(exc)
    return input_rows


def main() -> None:
    args = parse_args()
    rows = process_rows(args)
    main_output, json_output = build_output_paths(args)

    if main_output is not None:
        if main_output.suffix.lower() == ".json":
            main_output.parent.mkdir(parents=True, exist_ok=True)
            main_output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            write_csv(main_output, rows)
    if json_output is not None:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"rows": rows, "output": str(main_output) if main_output else "", "json_output": str(json_output) if json_output else ""}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
