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
RS_PAYLOAD_FIELDS = (
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

NEEDS_CONTRACT_MESSAGE = "판매채널 추가 보류 : source 통합 계약 ID 확인 필요"
NEEDS_EXPLICIT_CONTRACT_MESSAGE = "인간 판단 필요 : 통합 계약 ID 복수"
NEEDS_HUMAN_JUDGMENT_MESSAGE = "인간 판단 필요 : 판매채널 추가 실패"


@dataclass(frozen=True)
class AddRequest:
    index: int
    row: dict[str, Any]
    cid: str
    platform_name: str
    source_contract_id: int = 0
    source_payment_setup_id: int = 0
    source_platform_name: str = ""
    force_add_existing_platform: bool = False


def row_has_approved_status(row_text: str) -> bool:
    tokens = [token.strip() for token in row_text.replace("\t", "\n").splitlines()]
    return any(token == "승인" for token in tokens)


def _parse_int_token(value: Any) -> int:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _parse_bool_token(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "y", "yes", "force", "강제", "예", "ㅇㅇ"}


def extract_unified_contract_id(row_text: str) -> int:
    tokens = [token.strip() for token in row_text.replace("\t", "\n").splitlines() if token.strip()]
    for index, token in enumerate(tokens):
        if token not in {"승인", "미승인"}:
            continue
        for candidate in tokens[index + 1 :]:
            contract_id = _parse_int_token(candidate)
            if contract_id or candidate == "0":
                return contract_id
    return 0


def row_has_unified_contract_id(row_text: str) -> bool:
    return extract_unified_contract_id(row_text) > 0


def choose_settlement_source_row_index(row_texts: list[str], preferred_contract_id: int = 0) -> int:
    indexed_rows = [(index, text.strip()) for index, text in enumerate(row_texts) if text.strip()]
    if not indexed_rows:
        return -1
    if preferred_contract_id > 0:
        for index, row_text in reversed(indexed_rows):
            if extract_unified_contract_id(row_text) == preferred_contract_id:
                return index
        return -1

    linked_rows = [
        (index, extract_unified_contract_id(row_text))
        for index, row_text in indexed_rows
        if row_has_unified_contract_id(row_text)
    ]
    linked_contract_ids = sorted({contract_id for _, contract_id in linked_rows})
    if len(linked_contract_ids) > 1:
        raise RuntimeError(
            "통합 계약 ID가 여러 개라 자동 선택을 중단합니다. "
            f"contract_ids={linked_contract_ids}. source_contract_id를 명시하세요."
        )
    for index, row_text in reversed(indexed_rows):
        if row_has_unified_contract_id(row_text):
            return index
    for index, row_text in reversed(indexed_rows):
        if row_has_approved_status(row_text):
            return index
    return indexed_rows[-1][0]


def get_row_contract_id(row: dict[str, Any]) -> int:
    for key in ("cntrId", "unityCntrId", "srcCntrId"):
        contract_id = _parse_int_token(row.get(key))
        if contract_id > 0:
            return contract_id
    return 0


def get_row_payment_setup_id(row: dict[str, Any]) -> int:
    for key in ("pymtSetlSetmId", "pymtSetlId"):
        setup_id = _parse_int_token(row.get(key))
        if setup_id > 0:
            return setup_id
    return 0


def get_row_channel_id(row: dict[str, Any]) -> int:
    for key in ("schnId", "lwerSchnCd", "lewrSchnCd", "lwerSchnId"):
        channel_id = _parse_int_token(row.get(key))
        if channel_id > 0:
            return channel_id
    return 0


def choose_settlement_template_row(
    template_rows: list[dict[str, Any]],
    *,
    preferred_contract_id: int = 0,
    preferred_payment_setup_id: int = 0,
    preferred_platform_name: str = "",
) -> dict[str, Any]:
    if not template_rows:
        raise RuntimeError("판매채널 정산 템플릿을 찾지 못했습니다.")

    payment_rows = [row for row in template_rows if str(row.get("pymtStd") or "") == "지급"]
    candidates = payment_rows or template_rows
    if preferred_payment_setup_id > 0:
        for row in candidates:
            if get_row_payment_setup_id(row) == preferred_payment_setup_id:
                return row
        raise RuntimeError(f"source_payment_setup_id={preferred_payment_setup_id} 정산 템플릿 행을 찾지 못했습니다.")
    if preferred_platform_name:
        requested_keys = platform_match_keys(preferred_platform_name)
        for row in candidates:
            row_name = str(row.get("schnNm") or row.get("lwerSchnNm") or "").strip()
            if platform_key(row_name) in requested_keys:
                return row
        raise RuntimeError(f"source_platform={preferred_platform_name} 정산 템플릿 행을 찾지 못했습니다.")
    if preferred_contract_id > 0:
        for row in candidates:
            if get_row_contract_id(row) == preferred_contract_id:
                return row
        raise RuntimeError(
            f"명시한 source_contract_id={preferred_contract_id} 정산 기준행을 찾지 못했습니다."
        )

    linked_rows = [row for row in candidates if get_row_contract_id(row) > 0]
    if linked_rows:
        linked_contract_ids = sorted({get_row_contract_id(row) for row in linked_rows})
        if len(linked_contract_ids) > 1:
            raise RuntimeError(
                "통합 계약 ID가 여러 개라 자동 선택을 중단합니다. "
                f"contract_ids={linked_contract_ids}. source_contract_id를 명시하세요."
            )
        return linked_rows[-1]

    setup_rows = [row for row in candidates if get_row_payment_setup_id(row) > 0]
    if setup_rows:
        setup_ids = sorted({get_row_payment_setup_id(row) for row in setup_rows})
        if len(setup_ids) > 1:
            raise RuntimeError(
                "지급정산 설정 ID가 여러 개라 자동 선택을 중단합니다. "
                f"payment_setup_ids={setup_ids}. source_payment_setup_id 또는 source_platform을 명시하세요."
            )
        return setup_rows[-1]

    raise RuntimeError(
        "판매채널 추가에는 통합 계약 ID가 있는 정산 기준행이 필요합니다. "
        "현재 정산 템플릿의 통합 계약 ID와 지급정산 설정 ID가 모두 0입니다. "
        "계약변경등록(/ip/cntr/cntrchg/cntr-chg-reg?cntrId=...)에서 계약/정산 연결을 먼저 보강하세요."
    )


def classify_unresolved_generated_id(error_text: str) -> tuple[str, str]:
    text = str(error_text or "")
    if not text:
        return "", ""
    if "통합 계약 ID가 여러 개" in text or "source_contract_id" in text:
        return "needs_explicit_contract", NEEDS_EXPLICIT_CONTRACT_MESSAGE
    if (
        "통합 계약 ID가 모두 0" in text
        or "통합 계약 ID가 있는 정산 기준행" in text
        or "계약변경등록" in text
    ):
        return "needs_contract", NEEDS_CONTRACT_MESSAGE
    if "판매채널 옵션을 찾지 못했습니다" in text:
        return "needs_human_judgment", "인간 판단 필요 : 판매채널 옵션 없음"
    if "지급정산 설정 ID가 여러 개" in text or "source_payment_setup_id" in text:
        return "needs_human_judgment", "인간 판단 필요 : 지급정산 설정 ID 확인"
    return "", ""


def next_action_for_unresolved_status(status: str) -> str:
    if status in {"needs_contract", "needs_explicit_contract"}:
        return "check_source_contract_id"
    if status:
        return "manual_review"
    return ""


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
    parser.add_argument("--source-contract-id", default="", help="Optional explicit source 통합 계약 ID.")
    parser.add_argument("--source-contract-id-column", default="source_contract_id")
    parser.add_argument("--source-payment-setup-id", default="", help="Optional explicit source 지급정산 설정 ID.")
    parser.add_argument("--source-payment-setup-id-column", default="source_payment_setup_id")
    parser.add_argument("--source-platform-column", default="source_platform")
    parser.add_argument(
        "--force-add-existing-platform",
        action="store_true",
        help="Add a new settlement row even when the sales channel content already exists.",
    )
    parser.add_argument("--force-add-existing-platform-column", default="force_add_existing_platform")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--env-file", default="")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=25_000)
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--include-rs-fields", action="store_true", help="Also populate RS grid/payload fields. Default skips RS.")
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
    source_contract_id: int,
    source_contract_id_column: str,
    source_payment_setup_id: int,
    source_payment_setup_id_column: str,
    source_platform_column: str,
    force_add_existing_platform: bool,
    force_add_existing_platform_column: str,
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
        row_source_contract_id = source_contract_id or _parse_int_token(row.get(source_contract_id_column))
        row_source_payment_setup_id = source_payment_setup_id or _parse_int_token(
            row.get(source_payment_setup_id_column)
        )
        row_source_platform = str(row.get(source_platform_column) or "").strip()
        row_force_add_existing = force_add_existing_platform or _parse_bool_token(
            row.get(force_add_existing_platform_column)
        )
        requests.append(
            AddRequest(
                index=index,
                row=row,
                cid=cid,
                platform_name=platform_name,
                source_contract_id=row_source_contract_id,
                source_payment_setup_id=row_source_payment_setup_id,
                source_platform_name=row_source_platform,
                force_add_existing_platform=row_force_add_existing,
            )
        )
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


def add_payload_fields(*, include_rs_fields: bool) -> tuple[str, ...]:
    if include_rs_fields:
        return ADD_PAYLOAD_FIELDS
    rs_fields = set(RS_PAYLOAD_FIELDS)
    return tuple(field for field in ADD_PAYLOAD_FIELDS if field not in rs_fields)


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


def select_grid_platform(page: Any, dialog: Any, grid_id: str, platform_name: str) -> None:
    first_row_cells = dialog.locator(f"#{grid_id} tr.rg-data-row .rg-data-cell")
    if first_row_cells.count() < 2:
        raise RuntimeError(f"판매채널 추가 모달의 {grid_id} 지급액 그리드를 찾지 못했습니다.")

    channel_cell = first_row_cells.first
    channel_cell.click()
    page.wait_for_timeout(400)
    select_platform_option(page, platform_name)
    page.wait_for_timeout(600)

    # Commit the dropdown choice before saving.
    first_row_cells.nth(1).click()
    page.wait_for_timeout(400)


def pick_channel_for_company(channels: list[dict[str, Any]], company_code: str = "") -> dict[str, Any] | None:
    if not channels:
        return None
    normalized_company_code = str(company_code or "").strip()
    if normalized_company_code:
        same_company = [
            channel for channel in channels
            if str(channel.get("cprCd") or "").strip() == normalized_company_code
        ]
        if same_company:
            return same_company[0]
        if any(str(channel.get("cprCd") or "").strip() for channel in channels):
            return None
    if len(channels) > 1 and len({str(channel.get("cprCd") or "").strip() for channel in channels}) > 1:
        return None
    return channels[0]


def select_channel_row(
    channels: list[dict[str, Any]],
    platform_name: str,
    *,
    company_code: str = "",
) -> dict[str, Any] | None:
    requested_keys = platform_match_keys(platform_name)
    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    for channel in channels:
        option_key = platform_key(str(channel.get("schnNm") or ""))
        if not option_key:
            continue
        if option_key in requested_keys:
            exact.append(channel)
        if any(requested in option_key or option_key in requested for requested in requested_keys):
            partial.append(channel)
    return pick_channel_for_company(exact, company_code) or pick_channel_for_company(partial, company_code)


def channel_from_existing_platform_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    channel_id = str(
        row.get("schnId")
        or row.get("lwerSchnCd")
        or row.get("lewrSchnCd")
        or row.get("lwerSchnId")
        or ""
    ).strip()
    if not channel_id:
        return None
    return {
        "schnId": channel_id,
        "schnNm": str(row.get("lwerSchnNm") or row.get("schnNm") or "").strip(),
    }


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


def click_settlement_row_checkbox(row: Any, *, grid: Any | None = None, row_index: int | None = None) -> None:
    for selector in ("input[type='checkbox']", "[role='checkbox']", ".rg-checkbox"):
        controls = row.locator(selector)
        for index in range(controls.count()):
            control = controls.nth(index)
            if not control.is_visible():
                continue
            try:
                if control.is_checked():
                    return
            except Exception:  # noqa: BLE001
                if str(control.get_attribute("aria-checked") or "").lower() == "true":
                    return
            control.click(force=True)
            return

    if grid is not None and row_index is not None:
        row_bar_controls = grid.locator(
            "tr.rg-row-bar input.rg-checkbox, "
            "tr.rg-row-bar input[type='checkbox'], "
            "tr.rg-row-bar [role='checkbox'], "
            "tr.rg-row-bar .rg-checkbox"
        )
        if row_index < row_bar_controls.count():
            control = row_bar_controls.nth(row_index)
            try:
                if control.is_visible():
                    control.click(force=True)
                    return
            except Exception:  # noqa: BLE001
                control.click(force=True)
                return

    cells = row.locator(".rg-data-cell, td")
    cell_count = cells.count()
    for index in range(min(cell_count, 4)):
        cell = cells.nth(index)
        if not cell.is_visible():
            continue
        if not cell.inner_text().strip():
            cell.click()
            return
    if cell_count:
        cells.nth(min(1, cell_count - 1)).click()
        return
    row.click()


def select_settlement_source_row(page: Any, *, preferred_contract_id: int = 0) -> dict[str, Any]:
    grid = page.locator("#setlGridId").first
    rows = grid.locator("tr.rg-data-row")
    if rows.count() == 0:
        grid = page
        rows = page.locator("tr.rg-data-row")
    if rows.count() == 0:
        rows = page.locator(".rg-body tbody tr")
    visible_rows: list[Any] = []
    row_texts: list[str] = []
    for index in range(rows.count()):
        row = rows.nth(index)
        if not row.is_visible():
            continue
        row_text = row.inner_text().strip()
        if not row_text:
            continue
        visible_rows.append(row)
        row_texts.append(row_text)

    selected_index = choose_settlement_source_row_index(
        row_texts,
        preferred_contract_id=preferred_contract_id,
    )
    if selected_index < 0:
        if preferred_contract_id > 0:
            raise RuntimeError(f"source_contract_id={preferred_contract_id} 정산 기준행을 찾지 못했습니다.")
        raise RuntimeError("정산정보 기준 행을 찾지 못했습니다. 판매채널추가 전에 선택할 정산 행이 필요합니다.")

    contract_id = extract_unified_contract_id(row_texts[selected_index])
    if contract_id <= 0:
        raise RuntimeError(
            "판매채널 추가에는 통합 계약 ID가 0이 아닌 정산 기준행 체크가 필요합니다. "
            "현재 화면에서 선택 가능한 정산행의 통합 계약 ID가 0입니다."
        )
    selected_row = visible_rows[selected_index]
    click_settlement_row_checkbox(selected_row, grid=grid, row_index=selected_index)
    page.wait_for_timeout(300)
    return {
        "settlement_source_row_number": selected_index + 1,
        "settlement_source_row_status": (
            "contract_linked" if contract_id > 0 else "approved" if row_has_approved_status(row_texts[selected_index]) else "fallback_last"
        ),
        "settlement_source_contract_id": str(contract_id),
        "settlement_source_row_snapshot": " | ".join(
            token.strip() for token in row_texts[selected_index].splitlines() if token.strip()
        )[:500],
    }


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


def find_platform_row_for_contract(
    detail_data: dict[str, Any],
    platform_name: str,
    contract_id: int,
    *,
    expected_channel_id: int = 0,
) -> dict[str, Any] | None:
    requested_keys = platform_match_keys(platform_name)
    if not requested_keys:
        return None
    rows = [
        item for item in (detail_data.get("schnCtnsInfoList") or [])
        if isinstance(item, dict)
    ]
    matches: list[dict[str, Any]] = []
    for row in rows:
        row_name = str(row.get("lwerSchnNm") or "").strip()
        if platform_key(row_name) not in requested_keys:
            continue
        matches.append(row)
        if contract_id > 0 and get_row_contract_id(row) == contract_id:
            continue
    if contract_id > 0:
        matches = [row for row in matches if get_row_contract_id(row) == contract_id]
    if expected_channel_id > 0:
        channel_matches = [row for row in matches if get_row_channel_id(row) == expected_channel_id]
        if channel_matches:
            return channel_matches[-1]
        if any(get_row_channel_id(row) > 0 for row in matches) or len(matches) > 1:
            return None
    return matches[-1] if matches else None


def fetch_detail_data(page: Any, cid: str) -> dict[str, Any]:
    detail_resp = axios_get_detail(page, cid)
    if not detail_resp.get("ok"):
        error_text = str(detail_resp.get("error") or detail_resp.get("data") or "")
        raise RuntimeError(f"detail fetch failed cid={cid}: {error_text[:300]}")
    return detail_resp.get("data") if isinstance(detail_resp.get("data"), dict) else {}


def add_platform_via_api(
    page: Any,
    cid: str,
    platform_name: str,
    *,
    source_contract_id: int = 0,
    source_payment_setup_id: int = 0,
    source_platform_name: str = "",
    force_add_existing_platform: bool = False,
    include_rs_fields: bool = False,
) -> dict[str, Any]:
    current_detail = fetch_detail_data(page, cid)
    setup = page.evaluate(
        """
        async ({ cid, detailPath, templatePath, channelPath }) => {
          const axios = document.querySelector('#app').__vue_app__._context.provides['$axios'];
          const detailResp = await axios.get(detailPath.replace('{cid}', cid));
          const detail = detailResp.data || {};
          const cpr = detail.rversCprCd || detail.cprCd || '1000';
          const templateResp = await axios.get(templatePath, {
            params: {
              pageNum: 1,
              pageSize: 1000,
              srchCntrId: 0,
              srcCntrClCd: '',
              srcCtnsId: String(cid),
              srcCprCd: cpr,
              srcBcncCd: '',
              pymtSetlSetmId: '',
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

    detail = setup.get("detail") or {}
    detail_company_code = str(detail.get("rversCprCd") or detail.get("cprCd") or "").strip()
    matched_platform, snapshot = platform_snapshot(current_detail, platform_name)
    channel = (
        channel_from_existing_platform_row(matched_platform)
        if force_add_existing_platform and matched_platform is not None
        else None
    )
    if channel is None:
        channel = select_channel_row(
            list(setup.get("channels") or []),
            platform_name,
            company_code=detail_company_code,
        )
    if channel is None:
        raise LookupError(f"판매채널 옵션을 찾지 못했습니다: {platform_name} cprCd={detail_company_code or '-'}")
    selected_channel_id = get_row_channel_id(channel)

    template_rows = list(setup.get("templateRows") or [])
    base_row = choose_settlement_template_row(
        template_rows,
        preferred_contract_id=source_contract_id,
        preferred_payment_setup_id=source_payment_setup_id,
        preferred_platform_name=source_platform_name,
    )
    source_contract_id = get_row_contract_id(base_row)
    source_payment_setup_id = get_row_payment_setup_id(base_row)

    existing_platform = find_platform_row_for_contract(
        current_detail,
        platform_name,
        source_contract_id,
        expected_channel_id=selected_channel_id,
    )
    if existing_platform is not None and not force_add_existing_platform:
        return {
            "addition_status": "already_present",
            "sales_channel_content_id": str(existing_platform.get("schnCtnsId") or "").strip(),
            "matched_platform_name": str(existing_platform.get("lwerSchnNm") or "").strip(),
            "existing_platform_snapshot": snapshot,
            "selected_channel_id": str(selected_channel_id or ""),
            "settlement_source_contract_id": str(source_contract_id),
            "settlement_source_payment_setup_id": str(source_payment_setup_id),
        }

    payload = {}
    needs_setup_pass_through = source_contract_id <= 0 and source_payment_setup_id > 0
    for key in add_payload_fields(include_rs_fields=include_rs_fields or needs_setup_pass_through):
        value = base_row.get(key)
        if value is None or value == "":
            value = ADD_PAYLOAD_DEFAULTS.get(key)
        payload[key] = value
    if needs_setup_pass_through:
        for key in (
            "pymtSetlId",
            "pymtSetlDtlId",
            "pymtSetlSetmId",
            "pymtSetlSetmYn",
            "pymtSetlStsCd",
            "cnfmStsCd",
            "bcncCd",
            "cprCd",
            "setlCyclCd",
            "setlPymtDtCd",
        ):
            if base_row.get(key) not in (None, ""):
                payload[key] = base_row.get(key)
    payload.update(
        {
            "schnId": channel.get("schnId"),
            "cntrId": source_contract_id,
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
    matched_platform = find_platform_row_for_contract(
        detail_data,
        platform_name,
        source_contract_id,
        expected_channel_id=selected_channel_id,
    )
    _, snapshot = platform_snapshot(detail_data, platform_name)
    if matched_platform is None:
        raise RuntimeError(
            f"판매채널 저장 후에도 선택한 플랫폼/채널이 보이지 않습니다: "
            f"{platform_name} schnId={selected_channel_id or '-'} cntrId={source_contract_id or '-'}"
        )

    return {
        "addition_status": "added" if not force_add_existing_platform else "added_existing_platform_settlement",
        "sales_channel_content_id": str(matched_platform.get("schnCtnsId") or "").strip(),
        "matched_platform_name": str(matched_platform.get("lwerSchnNm") or "").strip(),
        "existing_platform_snapshot": snapshot,
        "selected_channel_id": str(selected_channel_id or ""),
        "settlement_source_contract_id": str(source_contract_id),
        "settlement_source_payment_setup_id": str(source_payment_setup_id),
        "settlement_source_row_status": "contract_linked" if source_contract_id > 0 else "payment_setup_linked",
    }


def add_platform_via_detail(
    page: Any,
    cid: str,
    platform_name: str,
    *,
    source_contract_id: int = 0,
    source_payment_setup_id: int = 0,
    source_platform_name: str = "",
    force_add_existing_platform: bool = False,
    include_rs_fields: bool = False,
) -> dict[str, Any]:
    page.goto(build_detail_view_url(cid), wait_until="domcontentloaded", timeout=25_000)
    page.wait_for_timeout(2_000)

    click_tab(page, "정산정보")
    detail_data = fetch_detail_data(page, cid)
    matched_platform, snapshot = platform_snapshot(detail_data, platform_name)
    if matched_platform is not None and not force_add_existing_platform:
        return add_platform_via_api(
            page,
            cid,
            platform_name,
            source_contract_id=source_contract_id,
            source_payment_setup_id=source_payment_setup_id,
            source_platform_name=source_platform_name,
            force_add_existing_platform=False,
            include_rs_fields=include_rs_fields,
        )
    if matched_platform is not None and force_add_existing_platform:
        return add_platform_via_api(
            page,
            cid,
            platform_name,
            source_contract_id=source_contract_id,
            source_payment_setup_id=source_payment_setup_id,
            source_platform_name=source_platform_name,
            force_add_existing_platform=True,
            include_rs_fields=include_rs_fields,
        )
    if source_contract_id > 0 or source_payment_setup_id > 0 or source_platform_name:
        return add_platform_via_api(
            page,
            cid,
            platform_name,
            source_contract_id=source_contract_id,
            source_payment_setup_id=source_payment_setup_id,
            source_platform_name=source_platform_name,
            force_add_existing_platform=force_add_existing_platform,
            include_rs_fields=include_rs_fields,
        )

    source_row = select_settlement_source_row(page, preferred_contract_id=source_contract_id)
    page.get_by_role("button", name="판매채널추가").click()
    page.wait_for_timeout(1_200)
    dialog = find_visible_dialog(page)

    select_grid_platform(page, dialog, "mgGrid", platform_name)
    if include_rs_fields:
        select_grid_platform(page, dialog, "rsGrid", platform_name)

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
    matched_platform = find_platform_row_for_contract(detail_data, platform_name, source_contract_id)
    _, snapshot = platform_snapshot(detail_data, platform_name)
    if matched_platform is None:
        raise RuntimeError(f"판매채널 저장 후에도 플랫폼이 보이지 않습니다: {platform_name}")

    return {
        "addition_status": "added" if not force_add_existing_platform else "added_existing_platform_settlement",
        "sales_channel_content_id": str(matched_platform.get("schnCtnsId") or "").strip(),
        "matched_platform_name": str(matched_platform.get("lwerSchnNm") or "").strip(),
        "existing_platform_snapshot": snapshot,
        **source_row,
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
        source_contract_id=_parse_int_token(args.source_contract_id),
        source_contract_id_column=args.source_contract_id_column,
        source_payment_setup_id=_parse_int_token(getattr(args, "source_payment_setup_id", "")),
        source_payment_setup_id_column=args.source_payment_setup_id_column,
        source_platform_column=args.source_platform_column,
        force_add_existing_platform=getattr(args, "force_add_existing_platform", False),
        force_add_existing_platform_column=args.force_add_existing_platform_column,
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
                result = add_platform_via_detail(
                    page,
                    request.cid,
                    request.platform_name,
                    source_contract_id=request.source_contract_id,
                    source_payment_setup_id=request.source_payment_setup_id,
                    source_platform_name=request.source_platform_name,
                    force_add_existing_platform=request.force_add_existing_platform,
                    include_rs_fields=getattr(args, "include_rs_fields", False),
                )
                row.update(result)
                row["detail_status"] = "loaded"
                row["platform_match_status"] = "found"
                row["next_action"] = "paste_sales_channel_content_id"
                row["addition_error"] = ""
            except Exception as exc:  # noqa: BLE001
                unresolved_status, unresolved_value = classify_unresolved_generated_id(str(exc))
                row["addition_status"] = "failed"
                row["addition_error"] = str(exc)
                if unresolved_value:
                    row["addition_status"] = unresolved_status
                    row["sales_channel_content_id"] = ""
                    row["addition_review_note"] = unresolved_value
                    row["next_action"] = next_action_for_unresolved_status(unresolved_status)
                    row["platform_match_status"] = unresolved_status
                    if unresolved_status in {"needs_contract", "needs_explicit_contract"}:
                        row["contract_gate"] = "source_contract_id_required"
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
