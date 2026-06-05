from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "SIAAN Project"
SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from create_kipm_dummy_contract import (
    DEFAULT_DUMMY_ISBN,
    DEFAULT_KIPM_PATH,
    DEFAULT_RENTAL_PRICE,
    DummyContractSpec,
    click_text_button,
    create_dummy_contract,
    choose_select_by_label,
    fill_field_by_label,
    maybe_confirm_popup,
    open_content_mapping_modal,
    read_select_value,
    set_release_date,
)
from ips.core.auth import resolve_env_path
from ips.core.browser import BrowserSettings
from ips.core.harness import IPSHarness
from ips.sites import get_site
from secret_redaction import dumps_redacted
from work_cid_utils import DEFAULT_WORK_CID_REGISTRY_PATH


DEFAULT_CONTENT_REG_PATH = "/ip/cntsd/cntsreg/ctns-reg"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "content_contract_runs"
DEFAULT_CONTENT_TYPE = "소설"
DEFAULT_SERVICE_CHANNEL = "외부유통"
DEFAULT_UPPER_CHANNEL = "서드유통-일반(국내)"
DEFAULT_LOWER_CHANNEL = "교보문고(소설)"
DEFAULT_SERVICE_TYPE = "연재"
DEFAULT_GENRE = "남성향"
DEFAULT_DETAIL_GENRE = "기타"
DEFAULT_BOOK_PRICE = "100"
DEFAULT_SPECIAL_KIND = "일반"
DEFAULT_RELEASE_DATE = datetime.now().strftime("%Y-%m-%d")
ADULT_PATH_TOKEN = "\\02_연재\\02_01_성인_epub\\"
GENERAL_PATH_TOKEN = "\\02_연재\\"


class ContentContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistryMatch:
    folder_path: str
    source_group: str
    manager: str
    work_cid: str


@dataclass(frozen=True)
class NasProfile:
    source_group: str
    display_grade: str
    kipm_grade_option: str
    publisher: str


@dataclass(frozen=True)
class ContentContractSpec:
    title: str
    author: str
    copyright_code: str
    special_kind: str
    folder_path: str
    holder_name: str
    pdf_path: Path
    release_date: str
    book_price: str
    rental_price: str
    isbn: str
    contract_name: str = ""
    counterparty_type: str = ""
    counterparty_code: str = ""
    pen_name: str = ""
    existing_cid: str = ""
    account_rights_code: str = ""
    account_rights_name: str = ""
    account_rs_rate: int = 0
    rs_rate: int = 0
    allow_zero_rs: bool = False


@dataclass(frozen=True)
class ContentCreateResult:
    status: str
    content_name: str
    content_id: str
    request_url: str
    request_payload: dict[str, Any] | None
    response_payload: dict[str, Any] | None
    final_url: str
    saved_at: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Register a new KIPM novel content row from the SSOT canonical naming rule "
            "and optionally continue into 계약등록 with the downloaded child contract PDF."
        )
    )
    parser.add_argument("--title", required=True, help="작품명")
    parser.add_argument("--author", required=True, help="작가명")
    parser.add_argument("--copyright-code", required=True, help="저작권코드")
    parser.add_argument(
        "--special-kind",
        default=DEFAULT_SPECIAL_KIND,
        help=f"특수 구분. Default: {DEFAULT_SPECIAL_KIND}",
    )
    parser.add_argument(
        "--folder-path",
        default="",
        help="Optional NAS folder path. If omitted, the registry is searched by title/author.",
    )
    parser.add_argument(
        "--registry-path",
        default=str(DEFAULT_WORK_CID_REGISTRY_PATH),
        help="Path to work_cid_registry.local.csv used for folder/source lookup.",
    )
    parser.add_argument(
        "--manager",
        default="",
        help="Optional manager filter when resolving the registry row.",
    )
    parser.add_argument(
        "--holder-name",
        required=True,
        help="예금주명 / 거래처명 검색용 텍스트.",
    )
    parser.add_argument(
        "--pdf-path",
        required=True,
        help="Actual child contract PDF path to upload.",
    )
    parser.add_argument(
        "--contract-name",
        default="",
        help="Optional explicit 계약명. Defaults to YYYYMMDD_{콘텐츠명}_{예금주}.",
    )
    parser.add_argument(
        "--counterparty-type",
        default="",
        help="Optional 거래처 구분. Example: 개인, 사업자.",
    )
    parser.add_argument(
        "--counterparty-code",
        default="",
        help="Optional 거래처코드 used to disambiguate duplicate rows.",
    )
    parser.add_argument(
        "--pen-name",
        default="",
        help="Optional 필명 used to disambiguate duplicate counterparty rows.",
    )
    parser.add_argument(
        "--existing-cid",
        default="",
        help="Skip content creation and continue with this existing CID on write mode.",
    )
    parser.add_argument("--rs-rate", type=int, default=0, help="Optional RS rate override for dummy contract registration.")
    parser.add_argument("--account-rights-code", default="", help="account에서 확인한 저작권코드.")
    parser.add_argument("--account-rights-name", default="", help="account에서 확인한 정산명/저작권명.")
    parser.add_argument("--account-rs-rate", type=int, default=0, help="account에서 확인한 B2C/자체 RS율.")
    parser.add_argument("--allow-zero-rs", action="store_true", help="account 근거가 0% RS임을 명시적으로 허용.")
    parser.add_argument(
        "--release-date",
        default=DEFAULT_RELEASE_DATE,
        help=f"출시일. Default: {DEFAULT_RELEASE_DATE}",
    )
    parser.add_argument(
        "--book-price",
        default=DEFAULT_BOOK_PRICE,
        help=f"권별정보 도서정가. Default: {DEFAULT_BOOK_PRICE}",
    )
    parser.add_argument(
        "--rental-price",
        default=DEFAULT_RENTAL_PRICE,
        help=f"권별정보 대여가. Default: {DEFAULT_RENTAL_PRICE}",
    )
    parser.add_argument(
        "--isbn",
        default=DEFAULT_DUMMY_ISBN,
        help=f"권별정보 ISBN. Default: {DEFAULT_DUMMY_ISBN}",
    )
    parser.add_argument(
        "--env-file",
        default="",
        help="Optional env file path for KIPM credentials.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for JSON reports and browser artifacts.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional explicit JSON report path.",
    )
    parser.add_argument("--headless", action="store_true", help="Run Playwright headless.")
    parser.add_argument("--slow-mo-ms", type=int, default=0, help="Optional Playwright slow-mo.")
    parser.add_argument("--timeout-ms", type=int, default=20_000, help="Playwright timeout.")
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Actually create the content and then register the contract. "
            "Default is browser-backed dry-run for the content create payload only."
        ),
    )
    return parser.parse_args()


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def emit_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")
        return
    print(text)


def normalize_lookup_key(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", normalize_text(value)).lower()


def safe_suffix(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣]+", "_", normalize_text(value)).strip("_")
    return cleaned or "content_contract"


def parse_json_text(raw_value: str | None) -> dict[str, Any] | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
    return payload if isinstance(payload, dict) else {"data": payload}


def build_content_name(title: str, author: str, copyright_code: str, special_kind: str) -> str:
    parts = [
        normalize_text(title),
        normalize_text(author),
        normalize_text(copyright_code),
        normalize_text(special_kind) or DEFAULT_SPECIAL_KIND,
    ]
    if any(not part for part in parts[:3]):
        raise ContentContractError("작품명/작가명/저작권코드는 비어 있을 수 없습니다.")
    return "_".join(parts)


def load_registry_matches(
    path: Path,
    *,
    title: str,
    author: str,
    manager: str,
) -> list[RegistryMatch]:
    if not path.exists():
        raise FileNotFoundError(f"레지스트리 파일이 없습니다: {path}")

    title_key = normalize_lookup_key(title)
    author_key = normalize_lookup_key(author)
    manager_name = normalize_text(manager)
    matches: list[RegistryMatch] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            row_title = row.get("title_final") or ""
            row_author = row.get("author_final") or ""
            row_manager = normalize_text(row.get("manager"))
            folder_path = normalize_text(row.get("folder_path"))
            if not folder_path:
                continue
            if normalize_lookup_key(row_title) != title_key:
                continue
            if normalize_lookup_key(row_author) != author_key:
                continue
            if manager_name and row_manager != manager_name:
                continue
            matches.append(
                RegistryMatch(
                    folder_path=folder_path,
                    source_group=normalize_text(row.get("source_group")),
                    manager=row_manager,
                    work_cid=normalize_text(row.get("work_cid")),
                )
            )
    return matches


def resolve_registry_match(
    *,
    folder_path: str,
    registry_path: Path,
    title: str,
    author: str,
    manager: str,
) -> RegistryMatch | None:
    explicit_folder = normalize_text(folder_path).strip('"')
    if explicit_folder:
        return RegistryMatch(folder_path=explicit_folder, source_group="", manager=normalize_text(manager), work_cid="")

    matches = load_registry_matches(
        registry_path,
        title=title,
        author=author,
        manager=manager,
    )
    if not matches:
        raise ContentContractError(
            "레지스트리에서 작품/작가 기준 NAS 폴더를 찾지 못했습니다. "
            "folder-path를 직접 넘기거나 registry를 보강해 주세요."
        )
    if len(matches) > 1:
        folder_list = "\n".join(f"- {match.folder_path}" for match in matches[:5])
        raise ContentContractError(
            "레지스트리 매칭이 여러 건입니다. folder-path를 직접 지정해 주세요.\n"
            f"{folder_list}"
        )
    return matches[0]


def derive_nas_profile(*, folder_path: str, source_group: str = "") -> NasProfile:
    normalized_path = normalize_text(folder_path).replace("/", "\\").lower()
    source_group = normalize_text(source_group).lower()

    if ADULT_PATH_TOKEN.lower() in normalized_path or source_group == "adult":
        return NasProfile(
            source_group="adult",
            display_grade="성인",
            kipm_grade_option="성인",
            publisher="올나이트노벨",
        )
    if GENERAL_PATH_TOKEN.lower() in normalized_path or source_group in {"", "general"}:
        return NasProfile(
            source_group="general",
            display_grade="전체연령가",
            kipm_grade_option="비성인",
            publisher="포텐",
        )
    raise ContentContractError(
        "NAS 폴더 기준을 해석하지 못했습니다. "
        "02_연재 또는 02_01_성인_epub 경로가 필요합니다."
    )


def collect_visible_error_fields(page: Any) -> list[dict[str, str]]:
    return page.evaluate(
        """() => {
            const visible = (el) => !!(el && (el.offsetParent || el.getClientRects().length));
            const rows = [];
            for (const field of Array.from(document.querySelectorAll('.v-input.v-input--error, .v-field.v-field--error'))) {
                const wrapper = field.closest('.v-input') || field;
                if (!visible(wrapper)) {
                    continue;
                }
                const label = (wrapper.querySelector('label')?.textContent || '').trim();
                const message = Array.from(wrapper.querySelectorAll('.v-messages__message'))
                    .map((el) => (el.textContent || '').trim())
                    .filter(Boolean)
                    .join(' | ');
                const input = wrapper.querySelector('input, textarea');
                rows.push({
                    label,
                    message,
                    value: input ? (input.value || '').trim() : '',
                });
            }
            return rows;
        }"""
    )


def extract_numeric_candidates(payload: Any, *, preferred: list[str] | None = None) -> list[str]:
    preferred = preferred or []
    strong: list[str] = []
    weak: list[str] = []

    def walk(value: Any, *, parent_key: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, parent_key=str(key))
            return
        if isinstance(value, list):
            for child in value:
                walk(child, parent_key=parent_key)
            return

        text = normalize_text(value)
        if not re.fullmatch(r"\d+", text):
            return
        bucket = strong if any(token.lower() in parent_key.lower() for token in preferred) else weak
        if text not in bucket:
            bucket.append(text)

    walk(payload)
    return strong + [item for item in weak if item not in strong]


def extract_content_id_from_payload(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    candidates = extract_numeric_candidates(
        payload,
        preferred=["ctnsId", "parCtnsId", "contentId", "data", "obj"],
    )
    return candidates[0] if candidates else ""


def extract_content_id_from_mapping_row(cells: list[str], *, content_name: str) -> str:
    normalized_target = normalize_lookup_key(content_name)
    normalized_cells = [normalize_lookup_key(cell) for cell in cells]
    if normalized_target not in normalized_cells:
        return ""

    numeric_cells = [normalize_text(cell) for cell in cells if re.fullmatch(r"\d+", normalize_text(cell))]
    return numeric_cells[0] if numeric_cells else ""


def extract_content_id_from_mapping_rows(rows: list[list[str]], *, content_name: str) -> str:
    candidates: list[str] = []
    for cells in rows:
        content_id = extract_content_id_from_mapping_row(cells, content_name=content_name)
        if content_id and content_id not in candidates:
            candidates.append(content_id)

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        return ""
    raise ContentContractError(
        "콘텐츠명 재조회 결과가 여러 CID 로 잡혔습니다. "
        f"content_name={content_name} cids={', '.join(candidates)}"
    )


def lookup_content_id_by_name(page: Any, *, content_name: str) -> str:
    page.goto(get_site("kipm").resolve_url(DEFAULT_KIPM_PATH), wait_until="domcontentloaded", timeout=20_000)
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except Exception:
        page.wait_for_timeout(1_000)

    overlay = open_content_mapping_modal(page)
    choose_select_by_label(page, overlay, "검색조건", "콘텐츠명")
    fill_field_by_label(overlay, "검색어", content_name)
    click_text_button(overlay, "조회")
    page.wait_for_timeout(1_200)

    rows = overlay.locator(".rg-data-row")
    rows.first.wait_for(state="visible", timeout=10_000)

    extracted_rows: list[list[str]] = []
    for index in range(rows.count()):
        row = rows.nth(index)
        cells = row.locator("td").evaluate_all(
            """(els) => els
                .map((el) => (el.innerText || el.textContent || '').trim())
                .filter(Boolean)"""
        )
        extracted_rows.append([normalize_text(cell) for cell in cells])

    content_id = extract_content_id_from_mapping_rows(extracted_rows, content_name=content_name)
    if content_id:
        return content_id

    raise ContentContractError(
        "콘텐츠 저장 후 콘텐츠명으로 재조회했지만 신규 CID 를 찾지 못했습니다. "
        f"content_name={content_name} rows={json.dumps(extracted_rows, ensure_ascii=False)}"
    )


def build_report_path(output_dir: Path, json_output: str, title: str) -> Path:
    if json_output:
        return Path(json_output).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_dir / f"{stamp}__content_contract_{safe_suffix(title)}.json"


def build_browser_settings(args: argparse.Namespace, output_dir: Path) -> BrowserSettings:
    return BrowserSettings(
        headless=args.headless,
        slow_mo_ms=args.slow_mo_ms,
        timeout_ms=args.timeout_ms,
        artifacts_root=output_dir,
    )


def choose_select_with_retry(
    page: Any,
    scope: Any,
    label: str,
    option_text: str,
    *,
    attempts: int = 3,
) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            choose_select_by_label(page, scope, label, option_text)
            return
        except Exception as exc:
            try:
                current_value = read_select_value(scope, label)
            except Exception:
                current_value = ""
            if normalize_text(current_value) == normalize_text(option_text):
                return
            last_error = exc
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            page.wait_for_timeout(250 * attempt)
    if last_error is not None:
        raise last_error


def fill_content_form(page: Any, spec: ContentContractSpec, nas_profile: NasProfile) -> None:
    choose_select_with_retry(page, page, "콘텐츠형태", DEFAULT_CONTENT_TYPE)
    fill_field_by_label(page, "콘텐츠명", build_content_name(spec.title, spec.author, spec.copyright_code, spec.special_kind))
    choose_select_with_retry(page, page, "서비스가능판매채널", DEFAULT_SERVICE_CHANNEL)
    choose_select_with_retry(page, page, "상위판매채널", DEFAULT_UPPER_CHANNEL)
    choose_select_with_retry(page, page, "하위판매채널", DEFAULT_LOWER_CHANNEL)
    choose_select_with_retry(page, page, "서비스유형", DEFAULT_SERVICE_TYPE)
    set_release_date(page, spec.release_date)
    choose_select_with_retry(page, page, "등급", nas_profile.kipm_grade_option)
    choose_select_with_retry(page, page, "출판사", nas_profile.publisher)
    choose_select_with_retry(page, page, "장르", DEFAULT_GENRE)
    try:
        choose_select_with_retry(page, page, "세부장르", DEFAULT_DETAIL_GENRE)
    except Exception:
        pass
    fill_field_by_label(page, "도서정가", spec.book_price)
    fill_field_by_label(page, "대여가", spec.rental_price)
    fill_field_by_label(page, "ISBN", spec.isbn)
    page.wait_for_timeout(500)


def open_content_reg(page: Any) -> None:
    page.goto(get_site("kipm").resolve_url(DEFAULT_CONTENT_REG_PATH), wait_until="domcontentloaded", timeout=20_000)
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except Exception:
        page.wait_for_timeout(1_000)


def create_content(
    page: Any,
    spec: ContentContractSpec,
    nas_profile: NasProfile,
    *,
    write: bool,
) -> ContentCreateResult:
    open_content_reg(page)
    fill_content_form(page, spec, nas_profile)
    content_name = build_content_name(spec.title, spec.author, spec.copyright_code, spec.special_kind)

    if not write:
        captured: dict[str, Any] = {}

        def intercept_create(route: Any) -> None:
            captured["request_url"] = route.request.url
            captured["request_payload"] = parse_json_text(route.request.post_data)
            route.abort()

        page.route("**/cntsd/cntsreg/ctns-reg/add-ctns-main", intercept_create)
        try:
            click_text_button(page, "저장")
            page.wait_for_timeout(1_200)
        finally:
            page.unroute("**/cntsd/cntsreg/ctns-reg/add-ctns-main", intercept_create)

        if not captured:
            errors = collect_visible_error_fields(page)
            raise ContentContractError(
                "콘텐츠 등록 dry-run 요청이 생성되지 않았습니다. "
                f"errors={json.dumps(errors, ensure_ascii=False)}"
            )
        while maybe_confirm_popup(page, timeout_ms=1_000):
            pass
        return ContentCreateResult(
            status="dry_run_ready",
            content_name=content_name,
            content_id="",
            request_url=str(captured.get("request_url") or ""),
            request_payload=captured.get("request_payload"),
            response_payload=None,
            final_url=page.url,
            saved_at=datetime.now().isoformat(timespec="seconds"),
        )

    save_response = None
    try:
        with page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and "/cntsd/cntsreg/ctns-reg/add-ctns-main" in response.url
            ),
            timeout=30_000,
        ) as response_info:
            click_text_button(page, "저장")
        save_response = response_info.value
    except Exception as exc:
        errors = collect_visible_error_fields(page)
        raise ContentContractError(
            "콘텐츠 등록 저장 요청을 기다리지 못했습니다. "
            f"errors={json.dumps(errors, ensure_ascii=False)}"
        ) from exc

    page.wait_for_timeout(800)
    while maybe_confirm_popup(page, timeout_ms=2_000):
        pass

    response_payload: dict[str, Any] | None = None
    try:
        raw_payload = save_response.json()
        if isinstance(raw_payload, dict):
            response_payload = raw_payload
        else:
            response_payload = {"data": raw_payload}
    except Exception:
        response_payload = None

    content_id = extract_content_id_from_payload(response_payload)
    status = "created"
    if not content_id:
        content_id = lookup_content_id_by_name(page, content_name=content_name)
        status = "created_lookup"

    return ContentCreateResult(
        status=status,
        content_name=content_name,
        content_id=content_id,
        request_url=save_response.url,
        request_payload=None,
        response_payload=response_payload,
        final_url=page.url,
        saved_at=datetime.now().isoformat(timespec="seconds"),
    )


def build_spec(args: argparse.Namespace, registry_match: RegistryMatch | None) -> ContentContractSpec:
    folder_path = normalize_text(args.folder_path).strip('"')
    if not folder_path and registry_match is not None:
        folder_path = registry_match.folder_path

    pdf_path = Path(args.pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 파일이 없습니다: {pdf_path}")

    return ContentContractSpec(
        title=normalize_text(args.title),
        author=normalize_text(args.author),
        copyright_code=normalize_text(args.copyright_code),
        special_kind=normalize_text(args.special_kind) or DEFAULT_SPECIAL_KIND,
        folder_path=folder_path,
        holder_name=normalize_text(args.holder_name),
        pdf_path=pdf_path,
        release_date=normalize_text(args.release_date) or DEFAULT_RELEASE_DATE,
        book_price=normalize_text(args.book_price) or DEFAULT_BOOK_PRICE,
        rental_price=normalize_text(args.rental_price) or DEFAULT_RENTAL_PRICE,
        isbn=normalize_text(args.isbn) or DEFAULT_DUMMY_ISBN,
        contract_name=normalize_text(args.contract_name),
        counterparty_type=normalize_text(args.counterparty_type),
        counterparty_code=normalize_text(args.counterparty_code),
        pen_name=normalize_text(args.pen_name),
        existing_cid=normalize_text(args.existing_cid),
        account_rights_code=normalize_text(args.account_rights_code),
        account_rights_name=normalize_text(args.account_rights_name),
        account_rs_rate=args.account_rs_rate,
        rs_rate=args.rs_rate,
        allow_zero_rs=args.allow_zero_rs,
    )


def build_report_payload(
    *,
    args: argparse.Namespace,
    spec: ContentContractSpec,
    registry_match: RegistryMatch | None,
    nas_profile: NasProfile,
    content_result: ContentCreateResult | dict[str, Any],
    contract_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "write" if args.write else "dry_run",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input": {
            "title": spec.title,
            "author": spec.author,
            "copyright_code": spec.copyright_code,
            "special_kind": spec.special_kind,
            "folder_path": spec.folder_path,
            "holder_name": spec.holder_name,
            "pdf_path": str(spec.pdf_path),
            "release_date": spec.release_date,
            "book_price": spec.book_price,
            "rental_price": spec.rental_price,
            "isbn": spec.isbn,
            "contract_name": spec.contract_name,
            "counterparty_type": spec.counterparty_type,
            "counterparty_code": spec.counterparty_code,
            "pen_name": spec.pen_name,
            "existing_cid": spec.existing_cid,
            "account_rights_code": spec.account_rights_code,
            "account_rights_name": spec.account_rights_name,
            "account_rs_rate": spec.account_rs_rate,
            "rs_rate": spec.rs_rate,
            "allow_zero_rs": spec.allow_zero_rs,
            "content_name": build_content_name(spec.title, spec.author, spec.copyright_code, spec.special_kind),
        },
        "registry_match": asdict(registry_match) if registry_match is not None else None,
        "nas_profile": asdict(nas_profile),
        "content": asdict(content_result) if isinstance(content_result, ContentCreateResult) else content_result,
        "contract": contract_result,
    }


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    registry_match = resolve_registry_match(
        folder_path=args.folder_path,
        registry_path=Path(args.registry_path).resolve(),
        title=args.title,
        author=args.author,
        manager=args.manager,
    )
    spec = build_spec(args, registry_match)
    nas_profile = derive_nas_profile(
        folder_path=spec.folder_path,
        source_group=registry_match.source_group if registry_match is not None else "",
    )
    report_path = build_report_path(output_dir, args.json_output, spec.title)

    content_result: ContentCreateResult | dict[str, Any]
    contract_result: dict[str, Any] = {"status": "skipped"}

    settings = build_browser_settings(args, output_dir)
    env_path = resolve_env_path(args.env_file)
    site = get_site("kipm")

    try:
        with IPSHarness(site, settings=settings, env_path=env_path) as harness:
            initial_path = DEFAULT_KIPM_PATH if args.write and spec.existing_cid else DEFAULT_CONTENT_REG_PATH
            harness.ensure_logged_in(path=initial_path)

            if spec.existing_cid and args.write:
                content_result = {
                    "status": "skipped_existing_cid",
                    "content_name": build_content_name(spec.title, spec.author, spec.copyright_code, spec.special_kind),
                    "content_id": spec.existing_cid,
                    "request_url": "",
                    "request_payload": None,
                    "response_payload": None,
                    "final_url": harness.page.url,
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                }
            else:
                content_result = create_content(
                    harness.page,
                    spec,
                    nas_profile,
                    write=args.write,
                )

            if args.write:
                target_cid = (
                    content_result.content_id
                    if isinstance(content_result, ContentCreateResult)
                    else normalize_text(content_result.get("content_id"))
                )
                if not target_cid:
                    raise ContentContractError("계약 등록 대상으로 사용할 CID 가 없습니다.")

                contract_content_name = (
                    content_result.content_name
                    if isinstance(content_result, ContentCreateResult)
                    else normalize_text(content_result.get("content_name")) or spec.title
                )
                if spec.existing_cid:
                    contract_content_name = spec.title

                harness.page.wait_for_timeout(2_000)
                contract = create_dummy_contract(
                    harness.page,
                    DummyContractSpec(
                        cid=target_cid,
                        holder_name=spec.holder_name,
                        pdf_path=spec.pdf_path,
                        account_rights_code=spec.account_rights_code,
                        account_rights_name=spec.account_rights_name,
                        account_rs_rate=spec.account_rs_rate,
                        contract_name=spec.contract_name,
                        counterparty_type=spec.counterparty_type,
                        counterparty_code=spec.counterparty_code,
                        pen_name=spec.pen_name,
                        service_type=DEFAULT_SERVICE_TYPE,
                        grade=nas_profile.kipm_grade_option,
                        publisher=nas_profile.publisher,
                        genre=DEFAULT_GENRE,
                        detail_genre=DEFAULT_DETAIL_GENRE,
                        content_name=contract_content_name,
                        rs_rate=spec.rs_rate,
                        allow_zero_rs=spec.allow_zero_rs,
                    ),
                )
                contract_result = {"status": "created", **asdict(contract)}
            else:
                contract_result = {
                    "status": "skipped_dry_run",
                    "reason": "dry-run 에서는 신규 CID 가 실제로 생성되지 않으므로 계약 등록 단계는 실행하지 않습니다.",
                }

        report_payload = build_report_payload(
            args=args,
            spec=spec,
            registry_match=registry_match,
            nas_profile=nas_profile,
            content_result=content_result,
            contract_result=contract_result,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(dumps_redacted(report_payload), encoding="utf-8")
        emit_json(report_payload)
    except Exception as exc:
        failure_payload = {
            "mode": "write" if args.write else "dry_run",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "error": str(exc),
            "input": {
                "title": normalize_text(args.title),
                "author": normalize_text(args.author),
                "copyright_code": normalize_text(args.copyright_code),
                "special_kind": normalize_text(args.special_kind) or DEFAULT_SPECIAL_KIND,
                "folder_path": normalize_text(args.folder_path),
                "holder_name": normalize_text(args.holder_name),
                "pdf_path": str(Path(args.pdf_path).resolve()),
                "existing_cid": normalize_text(args.existing_cid),
            },
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(dumps_redacted(failure_payload), encoding="utf-8")
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
