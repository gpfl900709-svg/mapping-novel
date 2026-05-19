from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from create_kipm_dummy_contract import (
    DEFAULT_KIPM_PATH,
    DEFAULT_LOWER_CHANNEL,
    DEFAULT_SERVICE_CHANNEL,
    DEFAULT_UPPER_CHANNEL,
    DummyContractSpec,
    choose_select_by_label,
    choose_select_with_retry,
    click_text_button,
    collect_visible_form_values,
    confirm_popups,
    ensure_step1_manager_field,
    ensure_step1_metadata_fields,
    ensure_step1_required_fields,
    fill_field_by_label,
    modal_overlay,
    select_content_by_cid,
)
from ips.core.auth import resolve_env_path
from ips.core.browser import BrowserSettings
from ips.core.harness import IPSHarness
from ips.sites import get_site


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cid", required=True)
    parser.add_argument("--terms", nargs="+", required=True)
    parser.add_argument("--counterparty-type", default="")
    parser.add_argument("--env-file", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    return parser.parse_args()


def row_texts(overlay, limit: int = 10) -> list[str]:
    rows = overlay.locator(".rg-data-row")
    texts: list[str] = []
    count = rows.count()
    for index in range(min(count, limit)):
        try:
            texts.append(" ".join(rows.nth(index).inner_text(timeout=1_000).split()))
        except Exception:
            continue
    return texts


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    site = get_site("kipm")
    settings = BrowserSettings(
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        artifacts_root=output_dir,
    )

    result: dict[str, object] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cid": args.cid,
        "counterparty_type": args.counterparty_type,
        "terms": [],
    }

    with IPSHarness(site, settings=settings, env_path=resolve_env_path(args.env_file)) as harness:
        page = harness.page
        harness.ensure_logged_in(path=DEFAULT_KIPM_PATH)
        page.goto(site.resolve_url(DEFAULT_KIPM_PATH), wait_until="domcontentloaded", timeout=20_000)
        select_content_by_cid(page, args.cid)
        ensure_step1_manager_field(page, "조원재", department_name="소설편집팀")
        choose_select_with_retry(page, page, "서비스가능판매채널", DEFAULT_SERVICE_CHANNEL)
        choose_select_with_retry(page, page, "상위판매채널", DEFAULT_UPPER_CHANNEL)
        choose_select_with_retry(page, page, "하위판매채널", DEFAULT_LOWER_CHANNEL)
        ensure_step1_metadata_fields(
            page,
            DummyContractSpec(
                cid=args.cid,
                holder_name="debug",
                pdf_path=Path("debug.pdf"),
                grade="성인",
            ),
        )
        ensure_step1_required_fields(page)
        click_text_button(page, "다음")
        page.wait_for_timeout(400)
        confirm_popups(page, timeout_ms=1_500, max_clicks=5)
        click_text_button(page, "계약상대방 추가")
        overlay = modal_overlay(page, "거래처명")
        if args.counterparty_type:
            choose_select_by_label(page, overlay, "거래처 구분", args.counterparty_type)

        for term in args.terms:
            fill_field_by_label(overlay, "거래처명", term)
            click_text_button(overlay, "조회")
            page.wait_for_timeout(2_000)
            entry = {
                "term": term,
                "row_count": overlay.locator(".rg-data-row").count(),
                "rows": row_texts(overlay),
                "visible_values": collect_visible_form_values(overlay)[:40],
            }
            result["terms"].append(entry)

        artifact_dir = harness.runtime.save_failure(
            "counterparty_modal_debug",
            error_text="debug snapshot",
            extra={"cid": args.cid, "terms": args.terms},
        )
        result["artifact_dir"] = str(artifact_dir)

    output_path = output_dir / f"{datetime.now():%Y%m%d_%H%M%S}__counterparty_modal_debug_{args.cid}.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
