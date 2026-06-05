from __future__ import annotations

import argparse
import csv
import io
import json
import itertools
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from playwright.sync_api import Page, sync_playwright
import requests
import websocket

from chrome_debug_session import DEFAULT_SHORTCUT_PATH, ensure_debug_chrome
from ips_safety_contract import (
    SafetyDecision,
    apply_sheet_upload_gate_fields,
    classify_sheet_uploadable_sales_channel_row,
    id_text,
)


DEFAULT_CONNECT_URL = "http://127.0.0.1:9222"
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1jG0Q6LKzJ_q2VqdqtoDHSEwl8hfOEUrxRuxXq7KSazY/edit?gid=1569459807#gid=1569459807"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "SIAAN Project" / "output" / "sheet_uploader"
NAME_BOX_SELECTOR = "#t-name-box"
SINGLE_CELL_REF_RE = re.compile(r"^[A-Z]+[1-9][0-9]*$")
UNSAFE_UI_WRITE_MESSAGE = (
    "Refusing to write through the live Google Sheets UI. "
    "This script's legacy write path drives the active browser tab with keyboard events, "
    "which can delete or overwrite broad selections if focus moves. "
    "Use a Sheets API/batch-update writer, or pass --allow-dangerous-ui-write only for "
    "a disposable copy after creating an external backup."
)


@dataclass
class UploadRow:
    row_number: int
    cell_ref: str
    value: str
    input_title: str
    platform: str
    next_action: str


@dataclass
class UploadPlan:
    uploads: list[UploadRow]
    blocked_rows: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write 판매채널콘텐츠ID values from harness output into a Google Sheet via Chrome remote debugging.",
    )
    parser.add_argument("--input", required=True, help="Harness CSV or JSON output path.")
    parser.add_argument("--sheet-url", default=DEFAULT_SHEET_URL)
    parser.add_argument("--connect-url", default=DEFAULT_CONNECT_URL)
    parser.add_argument("--column-letter", default="E", help="Target sheet column letter. Default is S2_판매채널콘텐츠ID column E.")
    parser.add_argument("--value-column", default="sales_channel_content_id")
    parser.add_argument("--action-column", default="next_action")
    parser.add_argument("--row-id-columns", default="__row_id,row_index,row_id", help="Comma-separated row id column fallbacks.")
    parser.add_argument("--required-action", default="paste_sales_channel_content_id")
    parser.add_argument(
        "--allow-unverified-id",
        action="store_true",
        help="Allow a numeric ID without contract/S2 verification. Requires --unverified-id-reason; off by default.",
    )
    parser.add_argument("--unverified-id-reason", default="", help="Required when --allow-unverified-id is used.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of rows to write.")
    parser.add_argument("--settle-ms", type=int, default=500)
    parser.add_argument("--chrome-shortcut", default=str(DEFAULT_SHORTCUT_PATH))
    parser.add_argument("--chrome-path", default="")
    parser.add_argument("--user-data-dir", default="")
    parser.add_argument("--chrome-start-wait-ms", type=int, default=30_000)
    parser.add_argument("--ensure-debug-chrome", dest="ensure_debug_chrome", action="store_true")
    parser.add_argument("--no-ensure-debug-chrome", dest="ensure_debug_chrome", action="store_false")
    parser.add_argument("--skip-verify", action="store_true", help="Skip post-write export verification.")
    parser.add_argument(
        "--allow-dangerous-ui-write",
        action="store_true",
        help=(
            "Permit the legacy Chrome UI keyboard write path. "
            "Unsafe for live spreadsheets; blocked by default."
        ),
    )
    parser.add_argument("--verify-wait-ms", type=int, default=2500, help="Wait before second verification pass when first pass mismatches.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default="", help="Optional JSON report output path.")
    parser.set_defaults(ensure_debug_chrome=True)
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


def first_non_empty(row: dict[str, Any], names: list[str]) -> str:
    for name in names:
        value = str(row.get(name) or "").strip()
        if value:
            return value
    return ""


def is_safe_sales_channel_content_id(value: str) -> bool:
    value = str(value or "").strip()
    if not value.isdigit():
        return False
    return int(value) > 0


def build_upload_rows(
    rows: list[dict[str, Any]],
    *,
    value_column: str,
    action_column: str,
    required_action: str,
    row_id_columns: list[str],
    column_letter: str,
    limit: int,
    allow_unverified_id: bool = False,
    unverified_id_reason: str = "",
) -> list[UploadRow]:
    return build_upload_plan(
        rows,
        value_column=value_column,
        action_column=action_column,
        required_action=required_action,
        row_id_columns=row_id_columns,
        column_letter=column_letter,
        limit=limit,
        allow_unverified_id=allow_unverified_id,
        unverified_id_reason=unverified_id_reason,
    ).uploads


def build_upload_plan(
    rows: list[dict[str, Any]],
    *,
    value_column: str,
    action_column: str,
    required_action: str,
    row_id_columns: list[str],
    column_letter: str,
    limit: int,
    allow_unverified_id: bool = False,
    unverified_id_reason: str = "",
) -> UploadPlan:
    uploads: list[UploadRow] = []
    blocked_rows: list[dict[str, Any]] = []
    effective_allow_unverified = allow_unverified_id and bool(str(unverified_id_reason or "").strip())
    for row in rows:
        action = str(row.get(action_column) or "").strip()
        value = str(row.get(value_column) or "").strip()
        row_id_value = first_non_empty(row, row_id_columns)
        if action != required_action or not value or not row_id_value:
            continue
        if required_action == "paste_sales_channel_content_id":
            decision = classify_sheet_uploadable_sales_channel_row(
                row,
                value_column=value_column,
                action_column=action_column,
                required_action=required_action,
                allow_unverified_id=effective_allow_unverified,
            )
        else:
            decision = SafetyDecision(True, "passed", "non-sales-channel upload action")
        if not decision.allowed:
            blocked_rows.append(apply_sheet_upload_gate_fields(row, decision))
            continue
        try:
            row_number = int(float(row_id_value))
        except ValueError:
            blocked = dict(row)
            blocked["sheet_upload_gate_status"] = "blocked_invalid_row_id"
            blocked["sheet_upload_gate_reason"] = f"invalid row id: {row_id_value}"
            blocked_rows.append(blocked)
            continue
        uploads.append(
            UploadRow(
                row_number=row_number,
                cell_ref=f"{column_letter.upper()}{row_number}",
                value=id_text(value),
                input_title=str(row.get("input_title") or row.get("미매핑_콘텐츠마스터명") or "").strip(),
                platform=str(row.get("input_platform") or row.get("채널") or "").strip(),
                next_action=action,
            )
        )
        if limit and len(uploads) >= limit:
            break
    return UploadPlan(uploads=uploads, blocked_rows=blocked_rows)


def find_target_page(browser, target_url: str) -> Page:
    for context in browser.contexts:
        for page in context.pages:
            if page.url.startswith(target_url):
                return page
    raise RuntimeError(f"Open Google Sheet tab not found for URL prefix: {target_url}")


def wait_for_sheet_ready(page: Page) -> None:
    page.wait_for_selector(NAME_BOX_SELECTOR, timeout=20_000)
    page.wait_for_timeout(500)


def normalize_cell_ref(value: str) -> str:
    return value.replace("$", "").strip().upper()


def validate_single_cell_ref(cell_ref: str) -> str:
    normalized = normalize_cell_ref(cell_ref)
    if not SINGLE_CELL_REF_RE.fullmatch(normalized):
        raise ValueError(f"Unsafe cell reference for UI write: {cell_ref!r}")
    return normalized


def wait_for_selected_cell(page: Page, cell_ref: str, settle_ms: int) -> None:
    expected = validate_single_cell_ref(cell_ref)
    deadline = time.time() + max(1.0, settle_ms / 1000 * 4)
    actual = ""
    name_box = page.locator(NAME_BOX_SELECTOR)
    while time.time() < deadline:
        try:
            actual = normalize_cell_ref(name_box.input_value())
        except Exception:  # noqa: BLE001
            actual = ""
        if actual == expected:
            return
        time.sleep(0.1)
    raise RuntimeError(f"Selection mismatch before write: expected {expected}, actual {actual or '<empty>'}")


def write_cell(page: Page, cell_ref: str, value: str, settle_ms: int) -> None:
    validate_single_cell_ref(cell_ref)
    page.keyboard.press("Escape")
    page.wait_for_timeout(100)
    name_box = page.locator(NAME_BOX_SELECTOR)
    name_box.click()
    try:
        name_box.fill("")
    except Exception:
        pass
    name_box.fill(cell_ref)
    name_box.press("Enter")
    page.wait_for_timeout(settle_ms)
    wait_for_selected_cell(page, cell_ref, settle_ms)
    if value.isascii():
        page.keyboard.type(value, delay=20)
        page.keyboard.press("Enter")
    else:
        page.keyboard.press("Enter")
        page.wait_for_timeout(100)
        page.keyboard.press("Control+A")
        page.keyboard.insert_text(value)
        page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    page.wait_for_timeout(settle_ms)


def build_report(rows: list[UploadRow], *, dry_run: bool, blocked_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    blocked_rows = blocked_rows or []
    return {
        "written_count": len(rows),
        "blocked_count": len(blocked_rows),
        "dry_run": dry_run,
        "rows": [
            {
                "row_number": row.row_number,
                "cell_ref": row.cell_ref,
                "value": row.value,
                "input_title": row.input_title,
                "platform": row.platform,
                "next_action": row.next_action,
            }
            for row in rows
        ],
        "blocked_rows": blocked_rows,
    }


class RawCDPSheetWriter:
    def __init__(self, connect_url: str, sheet_url: str) -> None:
        self.connect_url = connect_url
        self.sheet_url = sheet_url
        self.ws: websocket.WebSocket | None = None
        self._seq = itertools.count(1)

    def __enter__(self) -> "RawCDPSheetWriter":
        target = self._find_target()
        self.ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=20, suppress_origin=True)
        self.call("Page.enable")
        self.call("Runtime.enable")
        self.call("Input.setIgnoreInputEvents", {"ignore": False})
        self.call("Page.bringToFront")
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.ws is not None:
            self.ws.close()
        self.ws = None

    def _http_base(self) -> str:
        parsed = urlparse(self.connect_url)
        if parsed.scheme in {"http", "https"}:
            return f"{parsed.scheme}://{parsed.netloc}"
        if parsed.scheme in {"ws", "wss"}:
            http_scheme = "https" if parsed.scheme == "wss" else "http"
            return f"{http_scheme}://{parsed.netloc}"
        raise ValueError(f"Unsupported connect URL: {self.connect_url}")

    def _find_target(self) -> dict[str, Any]:
        target_prefix = self.sheet_url.split("#")[0]
        for allow_open in (False, True):
            pages = json.load(urlopen(f"{self._http_base()}/json/list"))
            for page in pages:
                if page.get("type") != "page":
                    continue
                if str(page.get("url") or "").startswith(target_prefix):
                    return page
            if allow_open:
                break
            self._open_target()
            time.sleep(1.0)
        raise RuntimeError(f"Open Google Sheet tab not found for URL prefix: {target_prefix}")

    def _open_target(self) -> None:
        encoded = quote(self.sheet_url, safe="")
        for method in ("PUT", "GET"):
            try:
                request = Request(f"{self._http_base()}/json/new?{encoded}", method=method)
                with urlopen(request, timeout=5):
                    return
            except Exception:  # noqa: BLE001
                continue

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.ws is None:
            raise RuntimeError("Raw CDP websocket is not connected.")
        request_id = next(self._seq)
        self.ws.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error']}")
            return message.get("result", {})

    def eval_js(self, expression: str) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        )
        return result.get("result", {}).get("value")

    def _press_enter(self) -> None:
        self._press_key("Enter", 13, "")

    def _press_escape(self) -> None:
        self._press_key("Escape", 27, "")

    def _press_key(self, key: str, key_code: int, text: str = "") -> None:
        for key_type in ("keyDown", "keyUp"):
            self.call(
                "Input.dispatchKeyEvent",
                {
                    "type": key_type,
                    "windowsVirtualKeyCode": key_code,
                    "nativeVirtualKeyCode": key_code,
                    "code": key,
                    "key": key,
                    "text": text if key_type == "keyDown" else "",
                    "unmodifiedText": text,
                },
            )

    def wait_for_sheet_ready(self) -> None:
        for _ in range(40):
            if self.eval_js("Boolean(document.querySelector('#t-name-box'))"):
                return
            time.sleep(0.5)
        raise RuntimeError("Google Sheet name box (#t-name-box) not found.")

    def write_cell(self, cell_ref: str, value: str, settle_ms: int) -> None:
        validate_single_cell_ref(cell_ref)
        self._press_escape()
        time.sleep(0.1)
        self.eval_js(
            """
            (() => {
              const box = document.querySelector('#t-name-box');
              if (!box) return false;
              box.focus();
              box.select();
              return true;
            })()
            """
        )
        self.call("Input.insertText", {"text": cell_ref})
        time.sleep(settle_ms / 1000)
        self._press_enter()
        time.sleep(max(0.8, settle_ms / 1000 * 2))
        selected_cell = str(self.eval_js("document.querySelector('#t-name-box')?.value || ''") or "")
        if validate_single_cell_ref(selected_cell) != validate_single_cell_ref(cell_ref):
            raise RuntimeError(
                "Selection mismatch before write: "
                f"expected {normalize_cell_ref(cell_ref)}, actual {normalize_cell_ref(selected_cell) or '<empty>'}"
            )
        self._press_key("Delete", 46, "")
        time.sleep(0.1)
        self.call("Input.insertText", {"text": value})
        time.sleep(settle_ms / 1000)
        self._press_enter()
        self._press_escape()
        time.sleep(max(1.2, settle_ms / 1000 * 2))

    def get_cookies(self, urls: list[str]) -> list[dict[str, Any]]:
        self.call("Network.enable")
        result = self.call("Network.getCookies", {"urls": urls})
        cookies = result.get("cookies")
        return cookies if isinstance(cookies, list) else []


def column_letter_to_index(column_letter: str) -> int:
    index = 0
    for char in column_letter.strip().upper():
        if not ("A" <= char <= "Z"):
            continue
        index = index * 26 + (ord(char) - 64)
    if index <= 0:
        raise ValueError(f"Invalid column letter: {column_letter}")
    return index - 1


def extract_sheet_id_and_gid(sheet_url: str) -> tuple[str, str]:
    parsed = urlparse(sheet_url)
    parts = [part for part in parsed.path.split("/") if part]
    sheet_id = ""
    if "d" in parts:
        pivot = parts.index("d")
        if pivot + 1 < len(parts):
            sheet_id = parts[pivot + 1]
    query = parse_qs(parsed.query)
    gid = (query.get("gid") or [None])[0]
    if not gid and parsed.fragment:
        gid = (parse_qs(parsed.fragment).get("gid") or [None])[0]
    if not sheet_id or not gid:
        raise ValueError(f"Could not parse sheet id/gid from URL: {sheet_url}")
    return sheet_id, gid


def download_sheet_csv_via_cdp(connect_url: str, sheet_url: str) -> str:
    base_url = sheet_url.split("#")[0]
    with RawCDPSheetWriter(connect_url, sheet_url) as writer:
        cookies = writer.get_cookies([base_url])

    sheet_id, gid = extract_sheet_id_and_gid(sheet_url)
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path"),
        )
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    response = session.get(export_url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def verify_written_values(csv_text: str, upload_rows: list[UploadRow], column_letter: str) -> dict[str, Any]:
    rows = list(csv.reader(io.StringIO(csv_text)))
    column_index = column_letter_to_index(column_letter)
    matches: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for upload_row in upload_rows:
        actual = ""
        if 0 < upload_row.row_number <= len(rows):
            row = rows[upload_row.row_number - 1]
            if column_index < len(row):
                actual = str(row[column_index] or "")
        payload = {
            "row_number": upload_row.row_number,
            "cell_ref": upload_row.cell_ref,
            "expected": upload_row.value,
            "actual": actual,
            "input_title": upload_row.input_title,
        }
        if actual == upload_row.value:
            matches.append(payload)
        else:
            mismatches.append(payload)

    return {
        "match_count": len(matches),
        "mismatch_count": len(mismatches),
        "matches": matches,
        "mismatches": mismatches,
    }


def resolve_output_path(explicit_path: str) -> Path:
    if explicit_path:
        return Path(explicit_path)
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return DEFAULT_OUTPUT_DIR / f"{timestamp}__google_sheet_generated_id_uploader.json"


def run_upload(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "allow_unverified_id", False) and not str(getattr(args, "unverified_id_reason", "") or "").strip():
        raise SystemExit("--allow-unverified-id requires --unverified-id-reason.")
    input_path = Path(args.input)
    rows = load_rows(input_path)
    plan = build_upload_plan(
        rows,
        value_column=args.value_column,
        action_column=args.action_column,
        required_action=args.required_action,
        row_id_columns=[item.strip() for item in args.row_id_columns.split(",") if item.strip()],
        column_letter=args.column_letter,
        limit=args.limit,
        allow_unverified_id=args.allow_unverified_id,
        unverified_id_reason=args.unverified_id_reason,
    )
    upload_rows = plan.uploads
    if not upload_rows:
        report = build_report(upload_rows, dry_run=args.dry_run, blocked_rows=plan.blocked_rows)
        report["write_method"] = "no_uploadable_rows"
        report["verification"] = {}
        report["debug_chrome"] = {}
        return report

    report = build_report(upload_rows, dry_run=args.dry_run, blocked_rows=plan.blocked_rows)
    report["write_method"] = "dry_run" if args.dry_run else ""
    report["verification"] = {}
    report["debug_chrome"] = {}

    if not args.dry_run:
        if not getattr(args, "allow_dangerous_ui_write", False):
            report["write_method"] = "blocked_unsafe_ui_write"
            report["blocked_reason"] = UNSAFE_UI_WRITE_MESSAGE
            raise RuntimeError(UNSAFE_UI_WRITE_MESSAGE)
        if getattr(args, "ensure_debug_chrome", True):
            launch = ensure_debug_chrome(
                connect_url=args.connect_url,
                sheet_url=args.sheet_url,
                shortcut_path=Path(args.chrome_shortcut) if args.chrome_shortcut else None,
                chrome_path=args.chrome_path,
                user_data_dir=args.user_data_dir,
                start_wait_ms=args.chrome_start_wait_ms,
            )
            report["debug_chrome"] = launch.to_dict()
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(args.connect_url, timeout=60_000)
            page = find_target_page(browser, args.sheet_url.split("#")[0])
            page.bring_to_front()
            wait_for_sheet_ready(page)
            for upload_row in upload_rows:
                write_cell(page, upload_row.cell_ref, upload_row.value, args.settle_ms)
        report["write_method"] = "playwright_cdp"

        if not args.skip_verify:
            first_csv = download_sheet_csv_via_cdp(args.connect_url, args.sheet_url)
            first_pass = verify_written_values(first_csv, upload_rows, args.column_letter)
            report["verification"]["first_pass"] = first_pass
            final_pass = first_pass
            if first_pass["mismatch_count"]:
                time.sleep(max(0, args.verify_wait_ms) / 1000)
                second_csv = download_sheet_csv_via_cdp(args.connect_url, args.sheet_url)
                second_pass = verify_written_values(second_csv, upload_rows, args.column_letter)
                report["verification"]["second_pass"] = second_pass
                final_pass = second_pass
            report["verified_count"] = final_pass["match_count"]
            report["mismatch_count"] = final_pass["mismatch_count"]
        else:
            report["verified_count"] = 0
            report["mismatch_count"] = 0
    return report


def main() -> int:
    args = parse_args()
    report = run_upload(args)
    output_path = resolve_output_path(args.output)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report_path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
