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

from build_work_index import clean_title_for_display, split_folder_name
from ips_title_rules import (
    CAUTION_CIDS,
    build_canonical_target_title,
    build_title_catalog_from_overrides,
    canonicalize_full_remark,
    compute_explicit_target_title,
)
from ips.core.auth import resolve_env_path
from ips.core.browser import BrowserSettings
from ips.core.harness import IPSHarness
from ips.sites import get_site


DEFAULT_MANUAL_OVERRIDES_PATH = PROJECT_ROOT / "config" / "manual_overrides.local.json"
DEFAULT_REVIEW_QUEUE_PATH = PROJECT_ROOT / "data" / "catalog" / "ips_override_review_queue.json"
DEFAULT_REPORT_CSV_PATH = PROJECT_ROOT / "data" / "exports" / "ips" / "ips_title_change_general_report.csv"
DEFAULT_REPORT_JSON_PATH = PROJECT_ROOT / "data" / "catalog" / "ips_title_change_general_report.json"
SPECIAL_CASE_TOKENS = ("원작", "광고수익", "창작지원금", "카카오MG", "네이버MG", "작가선인세", "작품선인세", "부속합의")
EXPECTED_MANAGER_NAMES = {"조원재", "이선근", "윤혜리", "김성경", "김정원"}


@dataclass(frozen=True)
class RenameCandidate:
    work_cid: str
    folder_path: str
    source_title: str
    author_name: str
    remark: str
    target_title: str
    note: str


@dataclass
class RenameResult:
    work_cid: str
    folder_path: str
    source_title: str
    author_name: str
    target_title: str
    current_title: str = ""
    manager_name: str = ""
    department_name: str = ""
    service_type: str = ""
    upper_channels: str = ""
    lower_channels: str = ""
    status: str = ""
    reason: str = ""
    final_title: str = ""
    dialogs: list[str] | None = None

    def to_row(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["dialogs"] = " | ".join(self.dialogs or [])
        return payload


class DialogCapture:
    def __init__(self, page: Any) -> None:
        self.page = page
        self.messages: list[str] = []
        page.on("dialog", self._handle)

    def _handle(self, dialog: Any) -> None:
        self.messages.append(dialog.message)
        dialog.accept()

    def detach(self) -> None:
        self.page.remove_listener("dialog", self._handle)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rename safe IPS 콘텐츠명 entries to the canonical `{작품명}_{작가명}_{비고}` format."
    )
    parser.add_argument(
        "--manual-overrides",
        default=str(DEFAULT_MANUAL_OVERRIDES_PATH),
        help="Path to manual_overrides.local.json.",
    )
    parser.add_argument(
        "--review-queue",
        default=str(DEFAULT_REVIEW_QUEUE_PATH),
        help="Path to ips_override_review_queue.json.",
    )
    parser.add_argument(
        "--env-file",
        default="",
        help="Optional path to the shared .env file.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless.",
    )
    parser.add_argument(
        "--slow-mo-ms",
        type=int,
        default=0,
        help="Optional Playwright slow-mo delay in milliseconds.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=20_000,
        help="Playwright timeout in milliseconds.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Enable Playwright tracing.",
    )
    parser.add_argument(
        "--artifacts-root",
        default=str(PROJECT_ROOT / "output" / "ips_harness"),
        help="Directory for screenshots, HTML dumps, and traces on failure.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of candidates to process.",
    )
    parser.add_argument(
        "--content-id",
        action="append",
        default=[],
        help="Optional IPS 콘텐츠ID filter. Repeatable.",
    )
    parser.add_argument(
        "--csv-output",
        default=str(DEFAULT_REPORT_CSV_PATH),
        help="CSV report path.",
    )
    parser.add_argument(
        "--json-output",
        default=str(DEFAULT_REPORT_JSON_PATH),
        help="JSON report path.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually click save and verify persistence. Default is preview only.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_cid_flags(review_payload: dict[str, Any]) -> dict[str, set[str]]:
    flags_by_cid: dict[str, set[str]] = {}
    for row in review_payload.get("rows", []):
        work_cid = str(row.get("work_cid") or "").strip()
        if not work_cid:
            continue
        raw = str(row.get("flags") or "")
        flag_set = {part.strip() for part in raw.split("|") if part.strip()}
        flags_by_cid.setdefault(work_cid, set()).update(flag_set)
    return flags_by_cid


def extract_review_blocklist(
    review_payload: dict[str, Any],
    *,
    whitelist_cids: set[str] | None = None,
) -> tuple[set[str], set[str]]:
    flags_by_cid = extract_cid_flags(review_payload)
    whitelist = whitelist_cids or set()
    blocked_paths: set[str] = set()
    blocked_cids: set[str] = set()
    for row in review_payload.get("rows", []):
        priority = str(row.get("priority") or "").strip()
        if priority not in {"P0", "P1"}:
            continue
        work_cid = str(row.get("work_cid") or "").strip()
        if work_cid in whitelist:
            continue
        cid_flags = flags_by_cid.get(work_cid, set())
        # bundle_cid only (not mixed with bucket_cid) is unblocked — handled by bundle rule
        if "bundle_cid" in cid_flags and "bucket_cid" not in cid_flags:
            continue
        folder_path = str(row.get("folder_path") or "").strip()
        if folder_path:
            blocked_paths.add(folder_path)
        if work_cid:
            blocked_cids.add(work_cid)
    return blocked_paths, blocked_cids


def build_safe_candidates(
    manual_overrides_payload: dict[str, Any],
    review_payload: dict[str, Any],
) -> list[RenameCandidate]:
    bundle_whitelist = {
        str(cid).strip()
        for cid in manual_overrides_payload.get("ips_bundle_whitelist", [])
        if str(cid).strip()
    }
    abandon_cids_set = {
        str(entry.get("work_cid") or "").strip()
        for entry in manual_overrides_payload.get("ips_abandon_cids", []) or []
        if entry.get("work_cid")
    }
    explicit_cids_set = {
        str(entry.get("work_cid") or "").strip()
        for entry in manual_overrides_payload.get("ips_explicit_targets", []) or []
        if entry.get("work_cid")
    }
    blocked_paths, blocked_cids = extract_review_blocklist(
        review_payload,
        whitelist_cids=bundle_whitelist | abandon_cids_set | explicit_cids_set,
    )
    flags_by_cid = extract_cid_flags(review_payload)
    override_items = manual_overrides_payload.get("ips_cid_overrides", [])

    items_by_cid: dict[str, list[dict[str, Any]]] = {}
    for item in override_items:
        work_cid = str(item.get("work_cid") or "").strip()
        folder_path = str(item.get("work_folder_path") or "").strip()
        if not work_cid or not folder_path:
            continue
        items_by_cid.setdefault(work_cid, []).append(item)

    candidates: list[RenameCandidate] = []
    for work_cid, items in items_by_cid.items():
        if work_cid in blocked_cids:
            continue
        if work_cid in abandon_cids_set or work_cid in explicit_cids_set:
            # 명시적 abandon/explicit 타깃이 있으면 safe 처리 건너뜀
            continue

        parsed: list[tuple[dict[str, Any], str, str]] = []
        for item in items:
            folder_path = str(item.get("work_folder_path") or "").strip()
            if folder_path in blocked_paths:
                continue
            folder_name = Path(folder_path).name
            source_title, author_name = split_folder_name(folder_name)
            source_title = clean_title_for_display(source_title)
            author_name = clean_title_for_display(author_name)
            if not source_title or not author_name:
                continue
            parsed.append((item, source_title, author_name))

        if not parsed:
            continue

        cid_flags = flags_by_cid.get(work_cid, set())
        is_whitelisted = work_cid in bundle_whitelist
        is_bundle = len(parsed) > 1 and (
            is_whitelisted or ("bundle_cid" in cid_flags and "bucket_cid" not in cid_flags)
        )

        if is_bundle:
            authors = {author for _, _, author in parsed}
            if len(authors) != 1:
                # 번들 규칙은 동일 작가 전제 — 작가 다르면 수동 검토
                continue
            author_name = next(iter(authors))
            titles = [title for _, title, _ in parsed]
            remark = "일반"
            target_title = build_canonical_target_title(author_name, remark, titles)
            first_item = parsed[0][0]
            candidates.append(
                RenameCandidate(
                    work_cid=work_cid,
                    folder_path=str(first_item.get("work_folder_path") or "").strip(),
                    source_title="_".join(titles),
                    author_name=author_name,
                    remark=remark,
                    target_title=target_title,
                    note=f"bundle:{len(titles)}works | " + str(first_item.get("note") or "").strip(),
                )
            )
            continue

        if len(parsed) != 1:
            # 여러 row인데 번들 플래그 없음 — 기존처럼 skip (수동 분리 대상)
            continue

        item, source_title, author_name = parsed[0]
        folder_path = str(item.get("work_folder_path") or "").strip()
        remark = "일반"
        target_title = build_canonical_target_title(author_name, remark, [source_title])
        candidates.append(
            RenameCandidate(
                work_cid=work_cid,
                folder_path=folder_path,
                source_title=source_title,
                author_name=author_name,
                remark=remark,
                target_title=target_title,
                note=str(item.get("note") or "").strip(),
            )
        )

    return sorted(candidates, key=lambda item: (item.author_name, item.source_title, item.work_cid))


def build_explicit_candidates(manual_overrides_payload: dict[str, Any]) -> list[RenameCandidate]:
    """Build candidates from `ips_explicit_targets` — user-provided exact target titles.

    Each entry: `{work_cid, target_title, source_title?, author_name?, remark?, note?}`.
    """
    entries = manual_overrides_payload.get("ips_explicit_targets", []) or []
    titles_by_cid, titles_by_author = build_title_catalog_from_overrides(manual_overrides_payload)
    candidates: list[RenameCandidate] = []
    for entry in entries:
        cid = str(entry.get("work_cid") or "").strip()
        target = compute_explicit_target_title(entry, titles_by_cid, titles_by_author)
        if not cid or not target:
            continue
        candidates.append(
            RenameCandidate(
                work_cid=cid,
                folder_path=str(entry.get("folder_path") or "").strip(),
                source_title=str(entry.get("source_title") or "").strip(),
                author_name=str(entry.get("author_name") or "").strip(),
                remark=canonicalize_full_remark(str(entry.get("remark") or "일반").strip()),
                target_title=target,
                note=str(entry.get("note") or "").strip(),
            )
        )
    return candidates


def build_abandon_candidates(manual_overrides_payload: dict[str, Any]) -> list[RenameCandidate]:
    """Build rename candidates for CIDs marked as mis-assigned/unused.

    Target format: `(사용안함)_{작품명}·{작가명}_중복`
    """
    entries = manual_overrides_payload.get("ips_abandon_cids", []) or []
    candidates: list[RenameCandidate] = []
    for entry in entries:
        cid = str(entry.get("work_cid") or "").strip()
        title = str(entry.get("original_title") or "").strip()
        author = str(entry.get("original_author") or "").strip()
        if not cid or not title:
            continue
        middle = f"{title}·{author}" if author else title
        target_title = f"(사용안함)_{middle}_중복"
        candidates.append(
            RenameCandidate(
                work_cid=cid,
                folder_path="",
                source_title=title,
                author_name=author,
                remark="중복",
                target_title=target_title,
                note=str(entry.get("note") or "").strip(),
            )
        )
    return candidates


def filter_candidates(candidates: list[RenameCandidate], content_ids: list[str], limit: int) -> list[RenameCandidate]:
    filtered = candidates
    requested = {str(value).strip() for value in content_ids if str(value).strip()}
    if requested:
        filtered = [candidate for candidate in filtered if candidate.work_cid in requested]
    else:
        filtered = [candidate for candidate in filtered if candidate.work_cid not in CAUTION_CIDS]
    if limit > 0:
        filtered = filtered[:limit]
    return filtered


def get_label_value(page: Any, label: str, *, nth: int = 0) -> str:
    locator = page.get_by_label(label, exact=True).nth(nth)
    try:
        locator.wait_for(state="attached", timeout=2_000)
        return locator.input_value().strip()
    except Exception:  # noqa: BLE001
        return ""


def get_content_name_input(page: Any) -> Any:
    try:
        locator = page.get_by_label("콘텐츠명", exact=True).first
        locator.wait_for(state="visible", timeout=3_000)
        return locator
    except Exception:  # noqa: BLE001
        label = page.locator("label").filter(has_text="콘텐츠명").first
        label.wait_for(state="visible", timeout=3_000)
        label_id = label.get_attribute("id") or ""
        if label_id:
            fallback = page.locator(f'input[aria-labelledby="{label_id}"]').first
            fallback.wait_for(state="visible", timeout=3_000)
            return fallback
        raise


def is_special_case(result: RenameResult) -> tuple[bool, str]:
    haystacks = [
        result.current_title,
        result.upper_channels,
        result.lower_channels,
    ]
    for haystack in haystacks:
        for token in SPECIAL_CASE_TOKENS:
            if token and token in haystack:
                return True, f"special_token:{token}"
    return False, ""


def click_active_dialog_button(page: Any) -> bool:
    overlay_button = page.locator(".v-overlay--active button").filter(has_text="확인").first
    try:
        overlay_button.wait_for(state="visible", timeout=400)
        overlay_button.click()
        return True
    except Exception:  # noqa: BLE001
        pass

    for text in ("저장", "예", "확인"):
        candidate = page.locator(".v-overlay--active button").filter(has_text=text).first
        try:
            candidate.wait_for(state="visible", timeout=300)
            candidate.click()
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def trigger_save(page: Any) -> None:
    page.get_by_role("button", name="저장").first.click()
    for _ in range(5):
        page.wait_for_timeout(500)
        clicked = click_active_dialog_button(page)
        if not clicked:
            break


def inspect_candidate(page: Any, candidate: RenameCandidate) -> RenameResult:
    content_name_input = get_content_name_input(page)
    current_title = content_name_input.input_value().strip()
    return RenameResult(
        work_cid=candidate.work_cid,
        folder_path=candidate.folder_path,
        source_title=candidate.source_title,
        author_name=candidate.author_name,
        target_title=candidate.target_title,
        current_title=current_title,
        manager_name=get_label_value(page, "담당자명"),
        department_name=get_label_value(page, "담당부서"),
        service_type=get_label_value(page, "서비스유형"),
        upper_channels=get_label_value(page, "상위판매채널"),
        lower_channels=get_label_value(page, "하위판매채널"),
        dialogs=[],
    )


def process_candidate(harness: IPSHarness, candidate: RenameCandidate, *, write: bool) -> RenameResult:
    edit_path = f"/ip/cntsd/cntschg/ctns-chg-edit?parCtnsId={candidate.work_cid}"
    harness.navigate(edit_path)
    harness.page.wait_for_timeout(1_000)
    result = inspect_candidate(harness.page, candidate)

    if result.manager_name and result.manager_name not in EXPECTED_MANAGER_NAMES:
        result.status = "skipped_unexpected_manager"
        result.reason = f"manager={result.manager_name}"
        result.final_title = result.current_title
        return result

    special_case, special_reason = is_special_case(result)
    if special_case:
        result.status = "skipped_special_case"
        result.reason = special_reason
        result.final_title = result.current_title
        return result

    if result.current_title == result.target_title:
        result.status = "already_named"
        result.reason = "current_title_matches_target"
        result.final_title = result.current_title
        return result

    if not write:
        result.status = "ready_general"
        result.reason = "preview_only"
        result.final_title = result.current_title
        return result

    dialog_capture = DialogCapture(harness.page)
    try:
        content_name_input = get_content_name_input(harness.page)
        content_name_input.fill(result.target_title)
        harness.page.wait_for_timeout(300)
        trigger_save(harness.page)
        harness.page.wait_for_timeout(1_500)
        harness.navigate(edit_path)
        harness.page.wait_for_timeout(1_000)
        verified_title = get_content_name_input(harness.page).input_value().strip()
    finally:
        dialog_capture.detach()

    result.dialogs = dialog_capture.messages
    result.final_title = verified_title
    if verified_title == result.target_title:
        result.status = "updated"
        result.reason = "verified_after_reload"
    else:
        result.status = "verify_failed"
        result.reason = "title_not_persisted_after_reload"
    return result


def write_reports(rows: list[RenameResult], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload_rows = [row.to_row() for row in rows]
    fieldnames = list(payload_rows[0].keys()) if payload_rows else list(RenameResult("", "", "", "", "").to_row().keys())

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(payload_rows)

    summary = Counter(row.status for row in rows)
    json_payload = {
        "generated_at": datetime.now().isoformat(),
        "summary": dict(summary),
        "rows": payload_rows,
    }
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    manual_overrides_path = Path(args.manual_overrides)
    review_queue_path = Path(args.review_queue)
    csv_output = Path(args.csv_output)
    json_output = Path(args.json_output)

    manual_overrides_payload = load_json(manual_overrides_path)
    review_payload = load_json(review_queue_path)
    candidates = build_safe_candidates(manual_overrides_payload, review_payload)
    selected_candidates = filter_candidates(candidates, args.content_id, args.limit)

    settings = BrowserSettings(
        headless=args.headless,
        slow_mo_ms=args.slow_mo_ms,
        timeout_ms=args.timeout_ms,
        artifacts_root=Path(args.artifacts_root),
        trace=args.trace,
    )
    env_path = resolve_env_path(args.env_file)
    site = get_site("kipm")

    rows: list[RenameResult] = []
    with IPSHarness(site, settings=settings, env_path=env_path) as harness:
        harness.ensure_logged_in(path="/ip/cntsd/cntschg/ctns-chg-list?pageNum=1&pageSize=10")
        for index, candidate in enumerate(selected_candidates, start=1):
            print(f"[{index}/{len(selected_candidates)}] {candidate.work_cid} {candidate.target_title}")
            rows.append(process_candidate(harness, candidate, write=args.write))

    write_reports(rows, csv_output, json_output)
    summary = Counter(row.status for row in rows)
    print(
        json.dumps(
            {
                "write": args.write,
                "candidate_count": len(candidates),
                "processed_count": len(rows),
                "summary": dict(summary),
                "csv_output": str(csv_output),
                "json_output": str(json_output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
