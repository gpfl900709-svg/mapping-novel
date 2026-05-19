from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from google_sheet_generated_id_uploader import DEFAULT_SHEET_URL, download_sheet_csv_via_cdp, run_upload
from ips_sales_channel_adder import process_rows
from ips_sales_channel_harness import (
    DEFAULT_MANUAL_OVERRIDES_PATH,
    run_lookup,
    write_csv,
)
from work_cid_utils import DEFAULT_WORK_CID_REGISTRY_PATH


PROJECT_ROOT = Path(__file__).resolve().parents[1] / "SIAAN Project"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "ips_sales_channel_pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "One-shot pipeline: title/CID resolve -> IPS 판매채널추가 -> Google Sheet 생성 ID 입력."
        ),
    )
    parser.add_argument("--input", default="", help="Google Sheet CSV/TSV/XLSX export path.")
    parser.add_argument(
        "--download-sheet",
        action="store_true",
        help="Download the current Google Sheet CSV through the debug Chrome session before lookup.",
    )
    parser.add_argument(
        "--preset",
        choices=("jo_blank_generated_id",),
        default="",
        help="Apply a known sheet-fill preset. jo_blank_generated_id = A platform, 조원재 only, blank 생성 ID -> D.",
    )
    parser.add_argument("--sheet", default="", help="Optional sheet name for XLSX input.")
    parser.add_argument("--sheet-url", default=DEFAULT_SHEET_URL)
    parser.add_argument("--title-column", default="")
    parser.add_argument("--platform-column", default="")
    parser.add_argument("--manager-column", default="")
    parser.add_argument("--row-id-column", default="")
    parser.add_argument("--default-manager", default="")
    parser.add_argument("--filter-manager", default="")
    parser.add_argument("--only-empty-column", default="")
    parser.add_argument("--registry", default=str(DEFAULT_WORK_CID_REGISTRY_PATH))
    parser.add_argument("--manual-overrides", default=str(DEFAULT_MANUAL_OVERRIDES_PATH))
    parser.add_argument("--env-file", default="")
    parser.add_argument("--connect-url", default="http://127.0.0.1:9222")
    parser.add_argument("--chrome-shortcut", default="")
    parser.add_argument("--chrome-path", default="")
    parser.add_argument("--user-data-dir", default="")
    parser.add_argument("--chrome-start-wait-ms", type=int, default=30_000)
    parser.add_argument("--column-letter", default="D")
    parser.add_argument("--value-column", default="sales_channel_content_id")
    parser.add_argument("--action-column", default="next_action")
    parser.add_argument("--required-action", default="paste_sales_channel_content_id")
    parser.add_argument("--settle-ms", type=int, default=500)
    parser.add_argument("--verify-wait-ms", type=int, default=2500)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=25_000)
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0, help="Optional max rows for the final sheet uploader.")
    parser.add_argument("--skip-add", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


def apply_preset(args: argparse.Namespace) -> None:
    if args.preset != "jo_blank_generated_id":
        return
    if not args.platform_column:
        args.platform_column = "A"
    if not args.manager_column:
        args.manager_column = "담당자(없을 시 공란)"
    if not args.filter_manager:
        args.filter_manager = "조원재"
    if not args.only_empty_column:
        args.only_empty_column = "생성 ID"
    if not args.column_letter:
        args.column_letter = "D"
    if not args.value_column:
        args.value_column = "sales_channel_content_id"
    if not args.required_action:
        args.required_action = "paste_sales_channel_content_id"


def count_rows(rows: list[dict[str, object]], key: str, value: str) -> int:
    return sum(1 for row in rows if str(row.get(key) or "").strip() == value)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    apply_preset(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.download_sheet:
        downloaded_input = output_dir / f"{stamp}__current_sheet.csv"
        downloaded_input.write_text(
            download_sheet_csv_via_cdp(args.connect_url, args.sheet_url),
            encoding="utf-8-sig",
        )
        args.input = str(downloaded_input)

    if not args.input:
        raise SystemExit("Provide --input, or use --download-sheet to fetch the current Google Sheet CSV.")

    lookup_csv = output_dir / f"{stamp}__pipeline_lookup.csv"
    lookup_json = output_dir / f"{stamp}__pipeline_lookup.json"
    additions_csv = output_dir / f"{stamp}__pipeline_additions.csv"
    additions_json = output_dir / f"{stamp}__pipeline_additions.json"
    uploader_json = output_dir / f"{stamp}__pipeline_sheet_upload.json"
    summary_json = output_dir / f"{stamp}__pipeline_summary.json"

    lookup_args = argparse.Namespace(
        title="",
        platform="",
        manager="",
        cid="",
        input=args.input,
        sheet=args.sheet,
        title_column=args.title_column,
        platform_column=args.platform_column,
        manager_column=args.manager_column,
        row_id_column=args.row_id_column,
        default_manager=args.default_manager,
        filter_manager=args.filter_manager,
        only_empty_column=args.only_empty_column,
        registry=args.registry,
        manual_overrides=args.manual_overrides,
        env_file=args.env_file,
        output="",
        json_output="",
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        slow_mo_ms=args.slow_mo_ms,
        max_candidates=args.max_candidates,
    )
    lookup_rows = run_lookup(lookup_args)
    write_csv(lookup_csv, lookup_rows)
    write_json(lookup_json, lookup_rows)

    addition_rows = lookup_rows
    if not args.dry_run and not args.skip_add and count_rows(lookup_rows, "next_action", "add_platform_in_ips"):
        add_args = argparse.Namespace(
            input=str(lookup_csv),
            output="",
            json_output="",
            cid_column="work_cid",
            platform_column="input_platform",
            action_column="next_action",
            required_action="add_platform_in_ips",
            limit=0,
            env_file=args.env_file,
            headless=args.headless,
            timeout_ms=args.timeout_ms,
            slow_mo_ms=args.slow_mo_ms,
            write=True,
        )
        addition_rows = process_rows(add_args)

    write_csv(additions_csv, addition_rows)
    write_json(additions_json, addition_rows)

    upload_report: dict[str, object] = {}
    uploadable_count = count_rows(addition_rows, args.action_column, args.required_action)
    if not args.dry_run and not args.skip_upload and uploadable_count:
        upload_args = argparse.Namespace(
            input=str(additions_csv),
            sheet_url=args.sheet_url,
            connect_url=args.connect_url,
            column_letter=args.column_letter,
            value_column=args.value_column,
            action_column=args.action_column,
            row_id_columns="__row_id,row_index,row_id",
            required_action=args.required_action,
            limit=args.limit,
            settle_ms=args.settle_ms,
            chrome_shortcut=args.chrome_shortcut,
            chrome_path=args.chrome_path,
            user_data_dir=args.user_data_dir,
            chrome_start_wait_ms=args.chrome_start_wait_ms,
            ensure_debug_chrome=True,
            skip_verify=args.skip_verify,
            verify_wait_ms=args.verify_wait_ms,
            dry_run=args.dry_run,
            output=str(uploader_json),
        )
        upload_report = run_upload(upload_args)
        write_json(uploader_json, upload_report)

    summary = {
        "input": args.input,
        "lookup_csv": str(lookup_csv),
        "lookup_json": str(lookup_json),
        "additions_csv": str(additions_csv),
        "additions_json": str(additions_json),
        "uploader_json": str(uploader_json) if upload_report else "",
        "lookup_count": len(lookup_rows),
        "lookup_missing_platform_count": count_rows(lookup_rows, "next_action", "add_platform_in_ips"),
        "lookup_review_count": count_rows(lookup_rows, "next_action", "review_title_match"),
        "after_add_paste_count": count_rows(addition_rows, "next_action", "paste_sales_channel_content_id"),
        "addition_added_count": count_rows(addition_rows, "addition_status", "added"),
        "addition_already_present_count": count_rows(addition_rows, "addition_status", "already_present"),
        "addition_failed_count": count_rows(addition_rows, "addition_status", "failed"),
        "upload_written_count": int(upload_report.get("written_count") or 0) if upload_report else 0,
        "upload_verified_count": int(upload_report.get("verified_count") or 0) if upload_report else 0,
        "upload_mismatch_count": int(upload_report.get("mismatch_count") or 0) if upload_report else 0,
        "dry_run": args.dry_run,
    }
    write_json(summary_json, summary)
    print(json.dumps({"summary": summary, "upload_report": upload_report}, ensure_ascii=False, indent=2))
    print(f"summary_path={summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
