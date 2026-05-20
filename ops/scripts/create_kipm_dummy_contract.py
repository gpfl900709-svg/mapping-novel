from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "SIAAN Project"

from ips.core.auth import resolve_env_path
from ips.core.browser import BrowserSettings
from ips.core.harness import IPSHarness, IPSHarnessError
from ips.sites import get_site


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "dummy_contract_runs"
DEFAULT_PDF_PATH = Path(__file__).resolve().parents[1] / "더미+계약서.pdf"
DEFAULT_KIPM_PATH = "/ip/cntr/cntrreg/cntr-trg-ctns-reg"

DEFAULT_SERVICE_CHANNEL = "외부유통"
DEFAULT_UPPER_CHANNEL = "서드유통-일반(국내)"
DEFAULT_LOWER_CHANNEL = "교보문고(소설)"
CONTRACT_BASE_CHANNEL_SELECTIONS = (
    ("서비스가능판매채널", DEFAULT_SERVICE_CHANNEL),
    ("상위판매채널", DEFAULT_UPPER_CHANNEL),
    ("하위판매채널", DEFAULT_LOWER_CHANNEL),
)
DEFAULT_SERVICE_TYPE = "연재"
DEFAULT_GRADE = "비성인"
DEFAULT_PUBLISHER = "포텐"
DEFAULT_GENRE = "남성향"
DEFAULT_DETAIL_GENRE = "기타"
DEFAULT_MANAGER_NAME = "조원재"
DEFAULT_MANAGER_DEPARTMENT = "소설편집팀"
KNOWN_MANAGER_NAMES = ("김성경", "이선근", "김정원", "윤혜리", "어정원")
DEFAULT_RELEASE_DATE = datetime.now().strftime("%Y-%m-%d")
DEFAULT_RENTAL_PRICE = "100"
DEFAULT_DUMMY_ISBN = "9780000000000"

DEFAULT_CONTRACT_PERIOD_TYPE = "계약체결일로부터"
DEFAULT_CONTRACT_PERIOD_YEARS = "1"
DEFAULT_CURRENCY = "한국원(KRW)"
DEFAULT_PAYMENT_DAY = "당월 말일"
DEFAULT_SETTLEMENT_CYCLE = "익분기(M+2)"
DEFAULT_BASIS = "키다리스튜디오"
DEFAULT_RS_METHOD = "순매출액대비RS율"
DEFAULT_MG_SETOFF_TARGET = "N"
COUNTERPARTY_SEARCH_ALIASES = {
    "apbooks": "AP 북스",
    "ap북스": "AP 북스",
    "ebook21": "조은커뮤니티",
    "이북21": "조은커뮤니티",
}


class DummyContractError(RuntimeError):
    pass


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def alias_key(value: Any) -> str:
    return re.sub(r"\s+", "", normalize_text(value)).lower()


def resolve_counterparty_search_name(holder_name: str) -> str:
    return COUNTERPARTY_SEARCH_ALIASES.get(alias_key(holder_name), normalize_text(holder_name))


@dataclass(frozen=True)
class DummyContractSpec:
    cid: str
    holder_name: str
    pdf_path: Path
    account_rights_code: str = ""
    account_rights_name: str = ""
    account_rs_rate: int = 0
    contract_name: str = ""
    counterparty_type: str = ""
    counterparty_code: str = ""
    pen_name: str = ""
    service_type: str = ""
    grade: str = ""
    publisher: str = ""
    genre: str = ""
    detail_genre: str = ""
    manager_name: str = ""
    manager_department: str = ""
    content_name: str = ""
    rs_rate: int = 0
    trace_steps: bool = False
    skip_manager_field: bool = False
    force_manager_field: bool = False
    skip_step1_required_fields: bool = False


@dataclass(frozen=True)
class DummyContractResult:
    cid: str
    holder_name: str
    account_rights_code: str
    account_rights_name: str
    account_rs_rate: int
    content_name: str
    contract_name: str
    grade_name: str
    rs_rate: int
    final_url: str
    contract_id: str
    saved_at: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create one KIPM dummy contract through [7111] 계약등록 by mapping a CID, "
            "adding the holder as counterparty, and copying the current settlement template."
        )
    )
    parser.add_argument("--cid", required=True, help="Target CID.")
    parser.add_argument("--holder-name", required=True, help="Counterparty holder name.")
    parser.add_argument(
        "--contract-name",
        default="",
        help="Optional explicit contract name. Defaults to YYYYMMDD_{콘텐츠명}_{예금주}.",
    )
    parser.add_argument(
        "--pdf-path",
        default=str(DEFAULT_PDF_PATH),
        help="PDF path for the dummy contract attachment.",
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
        "--account-rights-code",
        default="",
        help="account에서 확인한 저작권코드. 계약 등록 전 필수 확인값.",
    )
    parser.add_argument(
        "--account-rights-name",
        default="",
        help="account에서 확인한 저작권명/정산명. 예: 기본정산율.",
    )
    parser.add_argument(
        "--account-rs-rate",
        type=int,
        default=0,
        help="account에서 확인한 B2C/자체 RS율. --rs-rate와 같아야 합니다.",
    )
    parser.add_argument("--service-type", default="", help="Optional 서비스유형 default.")
    parser.add_argument("--grade", default="", help="Optional 등급 default.")
    parser.add_argument("--publisher", default="", help="Optional 출판사 default.")
    parser.add_argument("--genre", default="", help="Optional 장르 default.")
    parser.add_argument("--detail-genre", default="", help="Optional 세부장르 default.")
    parser.add_argument("--manager-name", default="", help="Optional 담당자명 default.")
    parser.add_argument("--manager-department", default="", help="Optional 담당자 소속 default.")
    parser.add_argument("--skip-manager-field", action="store_true", help="Keep the manager loaded from the mapped content.")
    parser.add_argument(
        "--force-manager-field",
        action="store_true",
        help="Set manager/department by direct input events and skip slow lookup popups.",
    )
    parser.add_argument(
        "--skip-step1-required-fields",
        action="store_true",
        help="Keep mapped content metadata/book rows as-is instead of filling release/ISBN defaults.",
    )
    parser.add_argument("--content-name", default="", help="Optional known content name to avoid rereading it from step 1.")
    parser.add_argument("--rs-rate", type=int, default=0, help="Optional RS rate override. Example: 50.")
    parser.add_argument("--trace-steps", action="store_true", help="Print major contract registration steps.")
    parser.add_argument(
        "--env-file",
        default="",
        help="Optional env file path for KIPM credentials.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for success/failure artifacts and JSON reports.",
    )
    parser.add_argument("--headless", action="store_true", help="Run Playwright headless.")
    parser.add_argument("--slow-mo-ms", type=int, default=0, help="Optional Playwright slow-mo.")
    parser.add_argument("--timeout-ms", type=int, default=20_000, help="Playwright timeout.")
    return parser.parse_args()


def click_text_button(scope: Any, text: str, *, exact: bool = True, last: bool = False) -> None:
    buttons = scope.locator("button").filter(
        has_text=re.compile(rf"^{re.escape(text)}$" if exact else re.escape(text))
    )
    locator = buttons.last if last else buttons.first
    try:
        locator.wait_for(state="visible", timeout=10_000)
        locator.scroll_into_view_if_needed(timeout=10_000)
        try:
            locator.click(timeout=10_000)
            return
        except Exception:
            pass
        try:
            locator.click(timeout=10_000, force=True)
            return
        except Exception:
            pass
        locator.evaluate("(el) => el.click()")
        return
    except Exception:
        pass

    # 대형 화면에서는 Playwright actionability가 자주 흔들려서 문서 레벨 click fallback을 둔다.
    if hasattr(scope, "evaluate") and hasattr(scope, "url"):
        clicked = scope.evaluate(
            """({ text, exact, last }) => {
                const buttons = Array.from(document.querySelectorAll("button")).filter((button) => {
                    const value = (button.innerText || button.textContent || "").trim();
                    return exact ? value === text : value.includes(text);
                });
                const target = last ? buttons.at(-1) : buttons[0];
                if (!target) {
                    return false;
                }
                target.scrollIntoView({ block: "center" });
                target.click();
                return true;
            }""",
            {"text": text, "exact": exact, "last": last},
        )
        if clicked:
            return

    raise DummyContractError(f"버튼 클릭 실패: {text}")


def visible_overlay(page: Any) -> Any:
    overlay = page.locator(".v-overlay__content:visible").last
    overlay.wait_for(state="visible", timeout=10_000)
    return overlay


def modal_overlay(page: Any, text_fragment: str) -> Any:
    overlay = page.locator(".v-overlay__content:visible").filter(has_text=text_fragment).last
    overlay.wait_for(state="visible", timeout=10_000)
    return overlay


def field_wrapper_by_label(scope: Any, label: str) -> Any:
    label_nodes = scope.locator("label").filter(has_text=re.compile(re.escape(label)))
    for exact_only in (True, False):
        for index in range(label_nodes.count()):
            label_node = label_nodes.nth(index)
            try:
                if not label_node.is_visible():
                    continue
                label_text = re.sub(r"\s+", " ", label_node.inner_text(timeout=1_000) or "").strip()
            except Exception:
                continue
            if exact_only and label_text != label:
                continue
            target_id = (label_node.get_attribute("for") or "").strip()
            label_id = (label_node.get_attribute("id") or "").strip()
            for selector in (
                f"#{target_id}" if target_id else "",
                f"[aria-labelledby='{label_id}']" if label_id else "",
            ):
                if not selector:
                    continue
                target = scope.locator(selector).first
                if not target.count():
                    continue
                wrapper = target.locator(
                    "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' v-field ')][1]"
                ).first
                if wrapper.count():
                    try:
                        wrapper.wait_for(state="attached", timeout=3_000)
                        return wrapper
                    except Exception:
                        continue

    for predicate in (
        f"normalize-space(.)='{label}'",
        f"contains(normalize-space(.), '{label}')",
    ):
        wrappers = scope.locator(
            "xpath=.//label["
            f"{predicate}"
            "]/ancestor-or-self::div[contains(concat(' ', normalize-space(@class), ' '), ' v-field ')][1]"
        )
        try:
            wrappers.first.wait_for(state="attached", timeout=10_000)
            for index in range(wrappers.count()):
                wrapper = wrappers.nth(index)
                if wrapper.is_visible():
                    return wrapper
            return wrappers.first
        except Exception:
            pass

    for predicate in (
        f"normalize-space(.)='{label}'",
        f"contains(normalize-space(.), '{label}')",
    ):
        labels = scope.locator(f"xpath=.//label[{predicate}]")
        try:
            labels.first.wait_for(state="attached", timeout=10_000)
        except Exception:
            continue
        for index in range(labels.count()):
            label_node = labels.nth(index)
            label_id = label_node.get_attribute("id") or ""
            if not label_id:
                continue
            wrapper = scope.locator(
                "xpath=.//*[@aria-labelledby="
                f"'{label_id}']/ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' v-field ')][1]"
            ).first
            if wrapper.count():
                try:
                    wrapper.wait_for(state="attached", timeout=3_000)
                    return wrapper
                except Exception:
                    continue

    return wrappers.first


def fill_field_by_label(scope: Any, label: str, value: str) -> None:
    wrapper = field_wrapper_by_label(scope, label)
    candidates = wrapper.locator("input:not([readonly]), textarea")
    target = candidates.first
    for index in range(candidates.count()):
        candidate = candidates.nth(index)
        try:
            if candidate.is_visible():
                target = candidate
                break
        except Exception:
            continue
    target.wait_for(state="visible", timeout=10_000)
    target.click()
    target.fill(value)
    target.evaluate(
        """(el) => {
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
        }"""
    )


def read_field_value(scope: Any, label: str) -> str:
    wrapper = field_wrapper_by_label(scope, label)
    inputs = wrapper.locator("input, textarea")
    input_locator = inputs.first
    for index in range(inputs.count()):
        candidate = inputs.nth(index)
        try:
            if candidate.is_visible():
                input_locator = candidate
                break
        except Exception:
            continue
    if input_locator.count():
        raw = (input_locator.input_value() or "").strip()
        if raw:
            return raw
    selection = wrapper.locator(".v-select__selection-text").first
    if selection.count():
        raw = (selection.inner_text(timeout=2_000) or "").strip()
        if raw:
            return raw
    return (wrapper.inner_text(timeout=2_000) or "").strip()


def choose_vuetify_option(page: Any, option_text: str) -> None:
    option = page.locator(".v-overlay-container [role='option']").filter(
        has_text=re.compile(rf"^{re.escape(option_text)}$")
    ).last
    option.wait_for(state="visible", timeout=10_000)
    option.click()


def choose_select_by_label(page: Any, scope: Any, label: str, option_text: str) -> None:
    wrapper = field_wrapper_by_label(scope, label)
    wrapper.scroll_into_view_if_needed(timeout=10_000)
    wrapper_classes = wrapper.get_attribute("class") or ""
    if "v-field--disabled" in wrapper_classes:
        return
    wrapper.click()
    choose_vuetify_option(page, option_text)
    if (wrapper.get_attribute("aria-expanded") or "").lower() == "true":
        page.keyboard.press("Tab")
    page.wait_for_timeout(150)


def read_select_value(scope: Any, label: str) -> str:
    wrapper = field_wrapper_by_label(scope, label)
    selections = wrapper.locator(".v-select__selection-text")
    for index in range(selections.count()):
        selection = selections.nth(index)
        try:
            if selection.is_visible():
                return (selection.inner_text(timeout=1_000) or "").strip()
        except Exception:
            continue
    return ""


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
            last_error = exc
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            page.wait_for_timeout(250 * attempt)
    if last_error is not None:
        raise last_error


def choose_select_if_empty(page: Any, scope: Any, label: str, option_text: str) -> None:
    option_text = option_text.strip()
    if not option_text:
        return
    try:
        if read_select_value(scope, label):
            return
    except Exception:
        pass
    try:
        display_value = read_field_value(scope, label)
        if option_text in display_value:
            return
        residual = re.sub(re.escape(label), "", display_value).replace("*", "").strip()
        if residual:
            return
    except Exception:
        pass
    choose_select_with_retry(page, scope, label, option_text)


def force_input_value_by_label(page: Any, label_patterns: list[str], value: str) -> bool:
    return bool(
        page.evaluate(
            """({ labelPatterns, value }) => {
                const visible = (el) => !!(el && (el.offsetParent || el.getClientRects().length));
                const setNativeValue = (el, nextValue) => {
                    const proto = Object.getPrototypeOf(el);
                    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
                    if (descriptor && descriptor.set) {
                        descriptor.set.call(el, nextValue);
                    } else {
                        el.value = nextValue;
                    }
                    el.dispatchEvent(new Event("input", { bubbles: true }));
                    el.dispatchEvent(new Event("change", { bubbles: true }));
                    el.dispatchEvent(new Event("blur", { bubbles: true }));
                };
                const labelTextFor = (input) => {
                    const parts = [];
                    const aria = input.getAttribute("aria-labelledby") || "";
                    for (const id of aria.split(/\\s+/).filter(Boolean)) {
                        const label = document.getElementById(id);
                        if (label) {
                            parts.push((label.innerText || label.textContent || "").trim());
                        }
                    }
                    if (input.id) {
                        const label = document.querySelector(`label[for="${CSS.escape(input.id)}"]`);
                        if (label) {
                            parts.push((label.innerText || label.textContent || "").trim());
                        }
                    }
                    const container = input.closest(".v-input, .v-field, .v-col, .v-row");
                    if (container) {
                        for (const label of Array.from(container.querySelectorAll("label"))) {
                            parts.push((label.innerText || label.textContent || "").trim());
                        }
                    }
                    return parts.join(" ");
                };
                let changed = false;
                for (const input of Array.from(document.querySelectorAll("input, textarea"))) {
                    if (!visible(input)) {
                        continue;
                    }
                    const labelText = labelTextFor(input);
                    if (!labelText || labelText.includes("담당부서")) {
                        continue;
                    }
                    if (!labelPatterns.some((pattern) => labelText.includes(pattern))) {
                        continue;
                    }
                    if ((input.value || "").trim() === value) {
                        changed = true;
                        continue;
                    }
                    setNativeValue(input, value);
                    changed = true;
                }
                return changed;
            }""",
            {"labelPatterns": label_patterns, "value": value},
        )
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
                    text: (wrapper.innerText || wrapper.textContent || '').trim().slice(0, 200),
                });
            }
            return rows;
        }"""
    )


def collect_visible_form_values(page: Any) -> list[dict[str, str]]:
    return page.evaluate(
        """() => {
            const visible = (el) => !!(el && (el.offsetParent || el.getClientRects().length));
            const rows = [];
            const inputs = Array.from(document.querySelectorAll('input, textarea')).filter(visible);
            for (const input of inputs) {
                const parts = [];
                const aria = input.getAttribute('aria-labelledby') || '';
                for (const id of aria.split(/\\s+/).filter(Boolean)) {
                    const label = document.getElementById(id);
                    if (label) {
                        parts.push((label.innerText || label.textContent || '').trim());
                    }
                }
                if (input.id) {
                    const label = document.querySelector(`label[for="${CSS.escape(input.id)}"]`);
                    if (label) {
                        parts.push((label.innerText || label.textContent || '').trim());
                    }
                }
                const wrapper = input.closest('.v-input, .v-field, .v-col');
                rows.push({
                    label: parts.filter(Boolean).join(' | '),
                    value: (input.value || '').trim(),
                    placeholder: input.getAttribute('placeholder') || '',
                    readonly: input.readOnly ? 'Y' : 'N',
                    disabled: input.disabled ? 'Y' : 'N',
                    text: wrapper ? (wrapper.innerText || wrapper.textContent || '').trim().slice(0, 160) : '',
                });
            }
            return rows;
        }"""
    )


def select_lookup_value_by_label(page: Any, label: str, value: str) -> bool:
    try:
        wrapper = field_wrapper_by_label(page, label)
    except Exception:
        return False

    clicked = False
    for selector in (
        "button",
        ".v-field__append-inner",
        ".v-input__append",
        ".mdi-magnify",
        ".mdi-menu-down",
    ):
        targets = wrapper.locator(selector)
        for index in range(targets.count()):
            target = targets.nth(index)
            try:
                if not target.is_visible():
                    continue
                target.click(timeout=2_000, force=True)
                clicked = True
                break
            except Exception:
                continue
        if clicked:
            break
    if not clicked:
        try:
            wrapper.click(timeout=2_000, force=True)
            clicked = True
        except Exception:
            return False

    page.wait_for_timeout(500)
    try:
        option = page.locator(".v-overlay-container [role='option']").filter(
            has_text=re.compile(rf"^{re.escape(value)}$")
        ).last
        option.wait_for(state="visible", timeout=2_000)
        option.click()
        page.wait_for_timeout(300)
        return True
    except Exception:
        pass

    try:
        overlay = visible_overlay(page)
    except Exception:
        return False

    for search_label in ("검색어", "사용자명", "사원명", "담당자명", "이름"):
        try:
            fill_field_by_label(overlay, search_label, value)
            break
        except Exception:
            continue
    try:
        click_text_button(overlay, "조회")
    except Exception:
        pass
    page.wait_for_timeout(800)

    rows = overlay.locator(".rg-data-row")
    row = rows.filter(has_text=value).first
    try:
        row.wait_for(state="visible", timeout=5_000)
        row.click()
    except Exception:
        return False

    for button_text in ("선택 가져오기", "선택", "확인"):
        try:
            click_text_button(overlay, button_text)
            page.wait_for_timeout(500)
            return True
        except Exception:
            continue
    return False


def fill_overlay_search_input(overlay: Any, value: str) -> bool:
    inputs = overlay.locator("input:not([readonly]), textarea")
    for index in range(inputs.count()):
        input_locator = inputs.nth(index)
        try:
            if not input_locator.is_visible():
                continue
            input_locator.click(timeout=2_000)
            input_locator.fill(value)
            input_locator.evaluate(
                """(el) => {
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                }"""
            )
            return True
        except Exception:
            continue
    return False


def choose_row_from_overlay(page: Any, overlay: Any, value: str) -> bool:
    for button_text in ("조회", "검색"):
        try:
            click_text_button(overlay, button_text)
            break
        except Exception:
            continue
    page.wait_for_timeout(800)

    rows = overlay.locator(".rg-data-row")
    row = rows.filter(has_text=value).first
    try:
        row.wait_for(state="visible", timeout=5_000)
        row.click()
    except Exception:
        return False

    for button_text in ("선택 가져오기", "선택", "확인"):
        try:
            click_text_button(overlay, button_text)
            page.wait_for_timeout(500)
            return True
        except Exception:
            continue
    return False


def replace_visible_manager_via_lookup(page: Any, manager_name: str) -> bool:
    target_id = page.evaluate(
        """({ managerName, knownManagers }) => {
            const visible = (el) => !!(el && (el.offsetParent || el.getClientRects().length));
            for (const input of Array.from(document.querySelectorAll("input"))) {
                const value = (input.value || "").trim();
                if (!visible(input) || !value || value === managerName) {
                    continue;
                }
                if (!knownManagers.includes(value)) {
                    continue;
                }
                if (!input.id) {
                    input.id = `codex-manager-${Math.random().toString(36).slice(2)}`;
                }
                return input.id;
            }
            return "";
        }""",
        {"managerName": manager_name, "knownManagers": list(KNOWN_MANAGER_NAMES)},
    )
    if not target_id:
        return False

    clicked = page.evaluate(
        """(targetId) => {
            const input = document.getElementById(targetId);
            if (!input) {
                return false;
            }
            const candidates = [];
            let node = input;
            for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) {
                candidates.push(node);
            }
            for (const root of candidates) {
                const icon = root.querySelector(".mdi-magnify");
                const button = icon ? icon.closest("button") : root.querySelector("button");
                if (button) {
                    button.scrollIntoView({ block: "center" });
                    button.click();
                    return true;
                }
            }
            return false;
        }""",
        target_id,
    )
    if not clicked:
        return False

    page.wait_for_timeout(700)
    try:
        overlay = visible_overlay(page)
    except Exception:
        return False
    if not fill_overlay_search_input(overlay, manager_name):
        return False
    return choose_row_from_overlay(page, overlay, manager_name)


def force_manager_and_department_fields(
    page: Any,
    *,
    manager_name: str,
    department_name: str,
) -> bool:
    return bool(
        page.evaluate(
            """({ managerName, departmentName, knownManagers }) => {
                const visible = (el) => !!(el && (el.offsetParent || el.getClientRects().length));
                const setNativeValue = (el, nextValue) => {
                    const proto = Object.getPrototypeOf(el);
                    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
                    if (descriptor && descriptor.set) {
                        descriptor.set.call(el, nextValue);
                    } else {
                        el.value = nextValue;
                    }
                    el.dispatchEvent(new Event("input", { bubbles: true }));
                    el.dispatchEvent(new Event("change", { bubbles: true }));
                    el.dispatchEvent(new Event("blur", { bubbles: true }));
                };
                const visibleInputs = () => Array.from(document.querySelectorAll("input, textarea"))
                    .filter((input) => visible(input));
                const textFor = (input) => {
                    const parts = [];
                    const aria = input.getAttribute("aria-labelledby") || "";
                    for (const id of aria.split(/\\s+/).filter(Boolean)) {
                        const label = document.getElementById(id);
                        if (label) {
                            parts.push((label.innerText || label.textContent || "").trim());
                        }
                    }
                    if (input.id) {
                        const label = document.querySelector(`label[for="${CSS.escape(input.id)}"]`);
                        if (label) {
                            parts.push((label.innerText || label.textContent || "").trim());
                        }
                    }
                    const cell = input.closest(".v-col, .v-input, .v-field");
                    if (cell) {
                        parts.push((cell.innerText || cell.textContent || "").trim());
                    }
                    return parts.join(" ");
                };

                let changed = false;
                const inputs = visibleInputs();
                for (const input of inputs) {
                    const labelText = textFor(input);
                    const value = (input.value || "").trim();
                    if (labelText.includes("담당부서") || labelText.includes("소속")) {
                        if (!value || knownManagers.includes(value)) {
                            setNativeValue(input, departmentName);
                            changed = true;
                        }
                    }
                    if (labelText.includes("담당자") && !labelText.includes("담당부서")) {
                        if (value !== managerName) {
                            setNativeValue(input, managerName);
                            changed = true;
                        }
                    }
                    if (knownManagers.includes(value)) {
                        setNativeValue(input, managerName);
                        changed = true;
                    }
                }

                const managerInput = visibleInputs().find((input) => (input.value || "").trim() === managerName);
                if (managerInput) {
                    const row = managerInput.closest(".v-row") || managerInput.parentElement;
                    if (row) {
                        const rowInputs = Array.from(row.querySelectorAll("input, textarea")).filter((input) => visible(input));
                        const managerIndex = rowInputs.indexOf(managerInput);
                        for (let index = managerIndex - 1; index >= 0; index -= 1) {
                            const input = rowInputs[index];
                            const value = (input.value || "").trim();
                            if (!value) {
                                setNativeValue(input, departmentName);
                                changed = true;
                                break;
                            }
                        }
                    }
                }
                return changed;
            }""",
            {
                "managerName": manager_name,
                "departmentName": department_name,
                "knownManagers": list(KNOWN_MANAGER_NAMES),
            },
        )
    )


def ensure_step1_manager_field(
    page: Any,
    manager_name: str,
    *,
    department_name: str = "",
) -> None:
    manager_name = (manager_name or DEFAULT_MANAGER_NAME).strip()
    if not manager_name:
        return
    department_name = (department_name or DEFAULT_MANAGER_DEPARTMENT).strip()

    for label in ("담당자명", "담당자"):
        try:
            if read_field_value(page, label) == manager_name:
                return
        except Exception:
            pass
        try:
            choose_select_with_retry(page, page, label, manager_name, attempts=1)
            if read_field_value(page, label) == manager_name:
                return
        except Exception:
            pass
        if select_lookup_value_by_label(page, label, manager_name):
            try:
                if read_field_value(page, label) == manager_name:
                    return
            except Exception:
                return

    if replace_visible_manager_via_lookup(page, manager_name):
        return

    # 일부 담당자 필드는 readonly input으로만 남아 있어 Vue 이벤트를 직접 발생시킨다.
    force_input_value_by_label(page, ["담당자명", "담당자"], manager_name)
    force_manager_and_department_fields(
        page,
        manager_name=manager_name,
        department_name=department_name,
    )


def open_content_mapping_modal(page: Any) -> Any:
    click_text_button(page, "콘텐츠 매핑")
    overlay = modal_overlay(page, "콘텐츠마스터 조회")
    overlay.locator("label:has-text('검색조건')").last.wait_for(state="visible", timeout=10_000)
    return overlay


def select_content_by_cid(page: Any, cid: str) -> None:
    overlay = open_content_mapping_modal(page)
    choose_select_by_label(page, overlay, "검색조건", "콘텐츠ID")
    fill_field_by_label(overlay, "검색어", cid)
    click_text_button(overlay, "조회")
    rows = overlay.locator(".rg-data-row")
    rows.first.wait_for(state="visible", timeout=10_000)
    row = rows.first if rows.count() == 1 else rows.filter(has_text=cid).first
    row.wait_for(state="visible", timeout=10_000)
    row.click()
    click_text_button(overlay, "선택 가져오기")
    page.wait_for_timeout(500)


def remove_isbn_row_if_present(page: Any) -> bool:
    rows = page.locator("button.remove")
    before_count = rows.count()
    remove_button = rows.last
    if before_count:
        remove_button.scroll_into_view_if_needed(timeout=10_000)
        remove_button.click()
        page.wait_for_timeout(300)
        return page.locator("button.remove").count() < before_count
    return False


def set_release_date(page: Any, release_date: str) -> None:
    wrapper = field_wrapper_by_label(page, "출시일")
    target_input = wrapper.locator("input[placeholder='YYYY-MM-DD']").first
    target_input.wait_for(state="visible", timeout=10_000)
    current_value = (target_input.input_value() or "").strip()
    if current_value.replace(".", "-") == release_date:
        return

    target_input.click(force=True)
    target_input.press("Control+A")
    target_input.fill("")
    target_input.fill(release_date)
    target_input.evaluate(
        """(el, value) => {
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        release_date,
    )
    page.keyboard.press("Tab")
    page.wait_for_timeout(250)
    if (target_input.input_value() or "").strip().replace(".", "-") == release_date:
        return

    date_obj = datetime.strptime(release_date, "%Y-%m-%d")

    picker_opened = False
    for selector in (
        "button:has(.mdi-calendar)",
        ".v-field__append-inner",
        ".v-input__append",
        ".mdi-calendar",
    ):
        try:
            trigger = wrapper.locator(selector).last
            if not trigger.count() or not trigger.is_visible():
                continue
            trigger.click(force=True, timeout=3_000)
            picker_opened = True
            break
        except Exception:
            continue
    if not picker_opened:
        target_input.click(force=True)
    page.wait_for_timeout(250)
    overlay = page.locator(".v-overlay__content:visible").last
    day_button = overlay.locator(
        "button.v-date-picker-month__day-btn"
        f"[aria-label*='{date_obj.year}년']"
        f"[aria-label*='{date_obj.month}월']"
        f"[aria-label*='{date_obj.day}일']"
    ).last
    if not day_button.count():
        day_button = overlay.locator(
            "button.v-date-picker-month__day-btn"
            f"[aria-label*='{date_obj.year}년']"
            f"[aria-label*='{date_obj.month:02d}월']"
            f"[aria-label*='{date_obj.day:02d}일']"
        ).last
    if not day_button.count():
        day_button = overlay.locator("button.v-date-picker-month__day-btn").filter(
            has_text=re.compile(rf"^\s*{date_obj.day}\s*$")
        ).first
    day_button.wait_for(state="visible", timeout=10_000)
    day_button.click()
    page.wait_for_timeout(250)
    for pattern in ("확인", "적용", "선택", "OK"):
        try:
            confirm = overlay.locator("button").filter(has_text=re.compile(pattern)).last
            if confirm.count() and confirm.is_visible():
                confirm.click()
                page.wait_for_timeout(250)
                break
        except Exception:
            continue

    if not (target_input.input_value() or "").strip():
        target_input.click()
        target_input.fill(release_date)
        page.keyboard.press("Tab")
        page.wait_for_timeout(150)


def release_date_value_present(page: Any) -> bool:
    inputs = page.locator("input[placeholder='YYYY-MM-DD']")
    for index in range(inputs.count()):
        target_input = inputs.nth(index)
        try:
            if target_input.is_visible() and (target_input.input_value() or "").strip():
                return True
        except Exception:
            continue
    return False


def force_release_date_inputs(page: Any, release_date: str) -> bool:
    changed = False
    inputs = page.locator("input[placeholder='YYYY-MM-DD']")
    for index in range(inputs.count()):
        target_input = inputs.nth(index)
        try:
            if not target_input.is_visible():
                continue
            if (target_input.input_value() or "").strip():
                continue
            target_input.click(timeout=3_000)
            target_input.fill(release_date)
            page.wait_for_timeout(100)
            if not (target_input.input_value() or "").strip():
                target_input.click(timeout=3_000)
                page.keyboard.press("Control+A")
                page.keyboard.type(release_date, delay=20)
            target_input.evaluate(
                """(el) => {
                    el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: el.value }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                }"""
            )
            page.keyboard.press("Tab")
            page.wait_for_timeout(400)
            if (target_input.input_value() or "").strip():
                changed = True
        except Exception:
            continue
    return changed


def ensure_release_date(page: Any, release_date: str) -> None:
    if release_date_value_present(page):
        return
    if force_release_date_inputs(page, release_date) and release_date_value_present(page):
        return
    try:
        set_release_date(page, release_date)
    except Exception:
        pass
    if not release_date_value_present(page):
        force_release_date_inputs(page, release_date)


def bulk_fill_step1_rows(page: Any) -> dict[str, int]:
    return page.evaluate(
        """({ releaseDate, rentalPrice, dummyIsbn }) => {
            const visible = (el) => !!(el && (el.offsetParent || el.getClientRects().length));
            const setNativeValue = (el, value) => {
                const descriptor = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
                descriptor?.set?.call(el, value);
                el.dispatchEvent(new Event("input", { bubbles: true }));
                el.dispatchEvent(new Event("change", { bubbles: true }));
                el.dispatchEvent(new Event("blur", { bubbles: true }));
            };
            const labelTextFor = (el) => {
                const labelledBy = (el.getAttribute("aria-labelledby") || "").trim();
                for (const id of labelledBy.split(/\\s+/).filter(Boolean)) {
                    const label = document.getElementById(id);
                    const text = (label?.textContent || "").trim();
                    if (text) {
                        return text;
                    }
                }
                const field = el.closest(".v-field");
                const label = field?.querySelector(".v-field__field label[id], .v-field__field label[for]");
                return (label?.textContent || "").trim();
            };

            const stats = {
                visibleInputs: 0,
                releaseDate: 0,
                rentalPrice: 0,
                isbn: 0,
            };

            for (const input of Array.from(document.querySelectorAll("input"))) {
                if (!visible(input) || input.readOnly || input.disabled) {
                    continue;
                }
                stats.visibleInputs += 1;
                const label = labelTextFor(input);
                const value = (input.value || "").trim();
                const placeholder = (input.getAttribute("placeholder") || "").trim();

                if (placeholder === "YYYY-MM-DD" && !value) {
                    // Date inputs need the Vuetify picker path; direct DOM values are cleared on validation.
                    continue;
                }
                if (label === "대여가" && !value) {
                    setNativeValue(input, rentalPrice);
                    stats.rentalPrice += 1;
                    continue;
                }
                if (label === "ISBN" && !value) {
                    setNativeValue(input, dummyIsbn);
                    stats.isbn += 1;
                }
            }

            return stats;
        }""",
        {
            "releaseDate": DEFAULT_RELEASE_DATE,
            "rentalPrice": DEFAULT_RENTAL_PRICE,
            "dummyIsbn": DEFAULT_DUMMY_ISBN,
        },
    )


def ensure_step1_required_fields(page: Any) -> None:
    remove_isbn_row_if_present(page)
    bulk_stats = bulk_fill_step1_rows(page)
    if bulk_stats.get("releaseDate", 0) == 0:
        try:
            set_release_date(page, DEFAULT_RELEASE_DATE)
        except Exception:
            pass
    ensure_release_date(page, DEFAULT_RELEASE_DATE)
    if bulk_stats.get("visibleInputs", 0) > 150:
        page.wait_for_timeout(500)
        return
    for label, value in (("대여가", DEFAULT_RENTAL_PRICE), ("ISBN", DEFAULT_DUMMY_ISBN)):
        try:
            wrapper = field_wrapper_by_label(page, label)
            wrapper_classes = wrapper.get_attribute("class") or ""
            if "v-field--disabled" in wrapper_classes:
                continue
            fill_field_by_label(page, label, value)
        except Exception:
            continue

    # 일부 콘텐츠는 권/식별자 행이 여러 줄이라 빈 ISBN 값이 반복해서 남는다.
    visible_inputs: list[Any] = []
    for index in range(page.locator("input").count()):
        input_locator = page.locator("input").nth(index)
        try:
            if input_locator.is_visible():
                visible_inputs.append(input_locator)
        except Exception:
            continue

    for index in range(1, len(visible_inputs)):
        previous = visible_inputs[index - 1]
        current = visible_inputs[index]
        try:
            previous_value = (previous.input_value() or "").strip()
            current_value = (current.input_value() or "").strip()
        except Exception:
            continue
        replacement = ""
        if previous_value == "ISBN" and not current_value:
            replacement = DEFAULT_DUMMY_ISBN
        elif not current_value:
            try:
                next_value = (visible_inputs[index + 1].input_value() or "").strip()
            except Exception:
                next_value = ""
            if next_value == "ISBN":
                replacement = DEFAULT_RENTAL_PRICE

        if not replacement:
            continue
        try:
            current.click()
            current.fill(replacement)
            current.evaluate(
                """(el) => {
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                }"""
            )
            page.wait_for_timeout(50)
        except Exception:
            continue


def ensure_step1_metadata_fields(page: Any, spec: DummyContractSpec) -> None:
    for label, option_text in (
        ("서비스유형", spec.service_type or DEFAULT_SERVICE_TYPE),
        ("출판사", spec.publisher or DEFAULT_PUBLISHER),
        ("등급", spec.grade or DEFAULT_GRADE),
        ("장르", spec.genre or DEFAULT_GENRE),
        ("세부장르", spec.detail_genre or DEFAULT_DETAIL_GENRE),
    ):
        try:
            if page.locator("label").filter(has_text=label).count() == 0:
                continue
        except Exception:
            pass
        try:
            choose_select_if_empty(page, page, label, option_text)
        except Exception:
            # Existing-content contract screens can omit these metadata controls
            # entirely; in that case the contract registration can still proceed.
            continue


def ensure_contract_base_channel_fields(page: Any) -> None:
    for label, option_text in CONTRACT_BASE_CHANNEL_SELECTIONS:
        try:
            if page.locator("label").filter(has_text=label).count() == 0:
                continue
            current_value = read_select_value(page, label)
        except Exception:
            current_value = ""
        if normalize_text(current_value) == normalize_text(option_text):
            continue
        choose_select_with_retry(page, page, label, option_text)


def resolve_contract_content_metadata(page: Any, spec: DummyContractSpec) -> tuple[str, str]:
    content_name = normalize_text(spec.content_name)
    if not content_name:
        content_name = read_field_value(page, "콘텐츠명")

    grade_name = normalize_text(spec.grade)
    if not grade_name:
        try:
            if page.locator("label").filter(has_text="등급").count() > 0:
                grade_name = read_field_value(page, "등급")
        except Exception:
            pass
    grade_name = grade_name or DEFAULT_GRADE

    if not content_name:
        raise DummyContractError(f"CID {spec.cid} 의 콘텐츠명을 읽지 못했습니다.")
    return content_name, grade_name


def add_counterparty(
    page: Any,
    holder_name: str,
    *,
    counterparty_type: str = "",
    counterparty_code: str = "",
    pen_name: str = "",
) -> None:
    search_name = resolve_counterparty_search_name(holder_name)
    click_text_button(page, "계약상대방 추가")
    overlay = modal_overlay(page, "거래처명")
    if counterparty_type.strip():
        choose_select_by_label(page, overlay, "거래처 구분", counterparty_type.strip())
    fill_field_by_label(overlay, "거래처명", search_name)
    click_text_button(overlay, "조회")
    page.wait_for_timeout(1_200)
    rows = overlay.locator(".rg-data-row")
    rows.first.wait_for(state="visible", timeout=10_000)
    if counterparty_code.strip():
        code_rows = rows.filter(has_text=counterparty_code.strip())
        if code_rows.count() == 1:
            rows = code_rows
    if pen_name.strip():
        pen_rows = rows.filter(has_text=pen_name.strip())
        if pen_rows.count() == 1:
            rows = pen_rows
    row_count = rows.count()
    if row_count != 1:
        row_texts = []
        for index in range(min(row_count, 10)):
            try:
                row_texts.append(" ".join(rows.nth(index).inner_text().split()))
            except Exception:
                continue
        raise DummyContractError(
            "예금주 검색 결과가 1건이 아닙니다. "
            "holder="
            f"{holder_name} search={search_name} type={counterparty_type or '-'} code={counterparty_code or '-'} "
            f"pen={pen_name or '-'} count={row_count} rows={row_texts}"
        )
    rows.first.click()
    click_text_button(overlay, "선택 가져오기")
    page.wait_for_timeout(400)


def maybe_confirm_popup(page: Any, *, timeout_ms: int = 1_500) -> bool:
    try:
        button = page.locator(".v-overlay__content:visible button").filter(
            has_text=re.compile(r"^확인$")
        ).last
        button.wait_for(state="visible", timeout=timeout_ms)
        button.click()
        page.wait_for_timeout(300)
        return True
    except Exception:
        return False


def confirm_popups(page: Any, *, timeout_ms: int = 1_500, max_clicks: int = 5) -> int:
    clicked = 0
    for _ in range(max_clicks):
        if not maybe_confirm_popup(page, timeout_ms=timeout_ms):
            break
        clicked += 1
    return clicked


def ensure_rs_section_open(page: Any) -> None:
    if page.locator(".contents-tit:has-text('RS - 개별')").count():
        return
    action_button = page.locator("button").filter(has_text=re.compile(r"^Y$")).first
    if action_button.count():
        action_button.click()
        page.wait_for_timeout(400)


def grid_section_by_title(page: Any, title: str) -> Any:
    heading = page.locator(f".contents-tit:has-text('{title}')").first
    heading.wait_for(state="visible", timeout=10_000)
    grid = heading.locator("xpath=following-sibling::div[1]").locator(".rg-root.rg-grid").first
    grid.wait_for(state="visible", timeout=10_000)
    return grid


def grid_row_cells(grid: Any) -> Any:
    row = grid.locator("tbody tr.rg-data-row").first
    row.wait_for(state="visible", timeout=10_000)
    return row.locator("td")


def grid_rows(grid: Any) -> Any:
    rows = grid.locator("tbody tr.rg-data-row")
    rows.first.wait_for(state="visible", timeout=10_000)
    return rows


def grid_cell_text(cells: Any, cell_index: int) -> str:
    return (cells.nth(cell_index).inner_text(timeout=2_000) or "").strip()


def select_grid_dropdown_value(page: Any, cells: Any, cell_index: int, option_text: str) -> None:
    target = cells.nth(cell_index)
    target.wait_for(state="visible", timeout=10_000)
    target.scroll_into_view_if_needed(timeout=10_000)
    target.click()
    dropdown = page.locator(".rg-dropdownlist").last
    dropdown.wait_for(state="visible", timeout=10_000)
    option = dropdown.locator(".rg-dropdown-item").filter(
        has_text=re.compile(rf"^{re.escape(option_text)}$")
    ).first
    option.wait_for(state="visible", timeout=10_000)
    option.click()
    page.wait_for_timeout(250)


def fill_grid_number_value(page: Any, cells: Any, cell_index: int, value: int | str) -> None:
    target = cells.nth(cell_index)
    target.wait_for(state="visible", timeout=10_000)
    target.scroll_into_view_if_needed(timeout=10_000)
    target.dblclick()
    editor = page.locator(".rg-editor.rg-number-editor:visible").last
    editor.wait_for(state="visible", timeout=10_000)
    editor.fill(str(value))
    page.keyboard.press("Enter")
    page.wait_for_timeout(250)


def extract_contract_id(url: str) -> str:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("cntrId", [])
    return values[0] if values else ""


def trace_step(spec: DummyContractSpec, message: str) -> None:
    if spec.trace_steps:
        print(f"[dummy-contract][cid={spec.cid}] {message}", flush=True)


def resolve_rs_rate(grade_name: str, explicit_rate: int = 0) -> int:
    if explicit_rate > 0:
        return explicit_rate
    return 80 if grade_name.strip() == "성인" else 70


def validate_account_rs_guard(spec: DummyContractSpec) -> None:
    missing: list[str] = []
    if not normalize_text(spec.account_rights_code):
        missing.append("--account-rights-code")
    if not normalize_text(spec.account_rights_name):
        missing.append("--account-rights-name")
    if spec.account_rs_rate <= 0:
        missing.append("--account-rs-rate")
    if spec.rs_rate <= 0:
        missing.append("--rs-rate")
    if missing:
        raise DummyContractError(
            "계약 등록 전 account에서 저작권코드/정산명/B2C RS율을 확인해야 합니다. "
            f"누락={', '.join(missing)}"
        )

    if spec.rs_rate != spec.account_rs_rate:
        raise DummyContractError(
            "입력 RS율이 account 확인값과 다릅니다. "
            f"--rs-rate={spec.rs_rate}, --account-rs-rate={spec.account_rs_rate}"
        )


def configure_step4(page: Any, grade_name: str, *, explicit_rs_rate: int = 0) -> int:
    choose_select_by_label(page, page, "지급액 여부", "N")
    choose_select_by_label(page, page, "RS여부", "Y")
    choose_select_by_label(page, page, "지급통화", DEFAULT_CURRENCY)
    choose_select_by_label(page, page, "원천통화", DEFAULT_CURRENCY)
    choose_select_by_label(page, page, "지급일", DEFAULT_PAYMENT_DAY)
    choose_select_by_label(page, page, "정산주기", DEFAULT_SETTLEMENT_CYCLE)
    choose_select_by_label(page, page, "기준선택", DEFAULT_BASIS)

    ensure_rs_section_open(page)
    rs_grid = grid_section_by_title(page, "RS - 개별")
    rs_rate = resolve_rs_rate(grade_name, explicit_rs_rate)
    rows = grid_rows(rs_grid)

    for row_index in range(rows.count()):
        cells = rows.nth(row_index).locator("td")

        # 지급/원천 통화는 빈 상태로 시작할 때만 보정한다.
        if not grid_cell_text(cells, 3):
            select_grid_dropdown_value(page, cells, 3, DEFAULT_CURRENCY)
        if not grid_cell_text(cells, 5):
            select_grid_dropdown_value(page, cells, 5, DEFAULT_CURRENCY)

        if grid_cell_text(cells, 7) != DEFAULT_MG_SETOFF_TARGET:
            select_grid_dropdown_value(page, cells, 7, DEFAULT_MG_SETOFF_TARGET)
        if grid_cell_text(cells, 8) != DEFAULT_RS_METHOD:
            select_grid_dropdown_value(page, cells, 8, DEFAULT_RS_METHOD)
        if grid_cell_text(cells, 9) != str(rs_rate):
            fill_grid_number_value(page, cells, 9, rs_rate)

    return rs_rate


def create_dummy_contract(page: Any, spec: DummyContractSpec) -> DummyContractResult:
    trace_step(spec, "open contract target content registration")
    page.goto(get_site("kipm").resolve_url(DEFAULT_KIPM_PATH), wait_until="domcontentloaded", timeout=20_000)
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except Exception:
        page.wait_for_timeout(1_000)

    trace_step(spec, "select content by cid")
    select_content_by_cid(page, spec.cid)
    if spec.skip_manager_field:
        trace_step(spec, "skip manager")
    elif spec.force_manager_field:
        trace_step(spec, "force manager")
        manager_name = spec.manager_name or DEFAULT_MANAGER_NAME
        department_name = spec.manager_department or DEFAULT_MANAGER_DEPARTMENT
        force_input_value_by_label(page, ["담당자명", "담당자"], manager_name)
        force_manager_and_department_fields(
            page,
            manager_name=manager_name,
            department_name=department_name,
        )
    else:
        trace_step(spec, "ensure manager")
        ensure_step1_manager_field(
            page,
            spec.manager_name or DEFAULT_MANAGER_NAME,
            department_name=spec.manager_department or DEFAULT_MANAGER_DEPARTMENT,
        )
    try:
        page.locator("label").filter(has_text="하위판매채널").first.wait_for(
            state="visible", timeout=15_000
        )
    except Exception:
        page.wait_for_timeout(1_000)
    trace_step(spec, "ensure base channel")
    ensure_contract_base_channel_fields(page)
    trace_step(spec, "ensure step1 metadata")
    ensure_step1_metadata_fields(page, spec)
    if spec.skip_step1_required_fields:
        trace_step(spec, "skip step1 required fields")
    else:
        trace_step(spec, "ensure step1 required fields")
        ensure_step1_required_fields(page)

    trace_step(spec, "resolve content metadata")
    content_name, grade_name = resolve_contract_content_metadata(page, spec)

    trace_step(spec, "move to counterparty step")
    click_text_button(page, "다음")
    page.wait_for_timeout(400)
    confirm_popups(page, timeout_ms=1_500, max_clicks=5)

    trace_step(spec, "add counterparty")
    add_counterparty(
        page,
        spec.holder_name,
        counterparty_type=spec.counterparty_type,
        counterparty_code=spec.counterparty_code,
        pen_name=spec.pen_name,
    )
    trace_step(spec, "move to contract info step")
    click_text_button(page, "다음")
    page.wait_for_timeout(400)

    contract_name = spec.contract_name.strip() or (
        f"{datetime.now():%Y%m%d}_{content_name}_{spec.holder_name}".strip()
    )
    try:
        fill_field_by_label(page, "계약명", contract_name)
    except Exception as exc:
        errors = collect_visible_error_fields(page)
        values = collect_visible_form_values(page)
        raise DummyContractError(
            "계약명 단계 진입 실패. "
            f"url={page.url} errors={json.dumps(errors, ensure_ascii=False)} "
            f"visible_values={json.dumps(values[:40], ensure_ascii=False)}"
        ) from exc
    file_input = page.locator("input[type='file']").last
    file_input.set_input_files(str(spec.pdf_path))

    page.get_by_label("본계약").check(force=True)
    choose_select_by_label(page, page, "계약기간유형", DEFAULT_CONTRACT_PERIOD_TYPE)
    fill_field_by_label(page, "계약기간 년단위 입력", DEFAULT_CONTRACT_PERIOD_YEARS)

    # 예시 계약과 동일하게 자동 갱신 정보를 채운다.
    try:
        choose_select_by_label(page, page, "계약기간 자동갱신대상 여부", "Y")
        fill_field_by_label(page, "자동갱신기간 년단위 입력", "1")
    except Exception:
        pass

    trace_step(spec, "move to settlement step")
    click_text_button(page, "다음")
    maybe_confirm_popup(page, timeout_ms=3_000)
    click_text_button(page, "다음")
    page.wait_for_timeout(600)

    trace_step(spec, "configure settlement")
    rs_rate = configure_step4(page, grade_name, explicit_rs_rate=spec.rs_rate)

    trace_step(spec, "save")
    save_response = None
    try:
        with page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and "/cntr/cntrreg/cntr-inf-reg" in response.url
            ),
            timeout=30_000,
        ) as response_info:
            click_text_button(page, "저장")
        save_response = response_info.value
    except Exception:
        click_text_button(page, "저장")
    page.wait_for_timeout(600)
    confirm_popups(page, timeout_ms=3_000, max_clicks=5)

    save_contract_id = ""
    if save_response is not None:
        try:
            payload = save_response.json()
            if isinstance(payload, dict):
                save_data = payload.get("data")
                if save_data is not None:
                    save_contract_id = str(save_data).strip()
        except Exception:
            save_contract_id = ""

    trace_step(spec, "wait final url")
    try:
        page.wait_for_url(
            re.compile(r".*/cntr/(cntrchg/cntr-chg-reg|cntrlt/cntr-detail)\?cntrId=\d+"),
            timeout=20_000,
        )
    except Exception as exc:
        if save_contract_id:
            detail_url = get_site("kipm").resolve_url(f"/ip/cntr/cntrlt/cntr-detail?cntrId={save_contract_id}")
            page.goto(detail_url, wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(1_000)
        else:
            errors = collect_visible_error_fields(page)
            values = collect_visible_form_values(page)
            raise DummyContractError(
                "저장 후 계약 상세/변경 페이지로 이동하지 않았습니다. "
                f"url={page.url} errors={json.dumps(errors, ensure_ascii=False)} "
                f"visible_values={json.dumps(values[:60], ensure_ascii=False)}"
            ) from exc

    contract_id = extract_contract_id(page.url) or save_contract_id
    if not contract_id:
        raise DummyContractError(f"저장 후 계약ID를 추출하지 못했습니다. url={page.url}")

    trace_step(spec, f"saved contract_id={contract_id}")
    return DummyContractResult(
        cid=spec.cid,
        holder_name=spec.holder_name,
        account_rights_code=spec.account_rights_code,
        account_rights_name=spec.account_rights_name,
        account_rs_rate=spec.account_rs_rate,
        content_name=content_name,
        contract_name=contract_name,
        grade_name=grade_name,
        rs_rate=rs_rate,
        final_url=page.url,
        contract_id=contract_id,
        saved_at=datetime.now().isoformat(timespec="seconds"),
    )


def main() -> None:
    args = parse_args()
    pdf_path = Path(args.pdf_path).resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF 파일이 없습니다: {pdf_path}")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    env_path = resolve_env_path(args.env_file)

    spec = DummyContractSpec(
        cid=str(args.cid).strip(),
        holder_name=args.holder_name.strip(),
        pdf_path=pdf_path,
        account_rights_code=args.account_rights_code.strip(),
        account_rights_name=args.account_rights_name.strip(),
        account_rs_rate=args.account_rs_rate,
        contract_name=args.contract_name.strip(),
        counterparty_type=args.counterparty_type.strip(),
        counterparty_code=args.counterparty_code.strip(),
        pen_name=args.pen_name.strip(),
        service_type=args.service_type.strip(),
        grade=args.grade.strip(),
        publisher=args.publisher.strip(),
        genre=args.genre.strip(),
        detail_genre=args.detail_genre.strip(),
        manager_name=args.manager_name.strip(),
        manager_department=args.manager_department.strip(),
        content_name=args.content_name.strip(),
        rs_rate=args.rs_rate,
        trace_steps=args.trace_steps,
        skip_manager_field=args.skip_manager_field,
        force_manager_field=args.force_manager_field,
        skip_step1_required_fields=args.skip_step1_required_fields,
    )
    validate_account_rs_guard(spec)
    settings = BrowserSettings(
        headless=args.headless,
        slow_mo_ms=args.slow_mo_ms,
        timeout_ms=args.timeout_ms,
        artifacts_root=output_dir,
    )

    site = get_site("kipm")
    report_path = output_dir / f"{datetime.now():%Y%m%d_%H%M%S}__dummy_contract_{spec.cid}.json"

    try:
        with IPSHarness(site, settings=settings, env_path=env_path) as harness:
            harness.ensure_logged_in(path=DEFAULT_KIPM_PATH)
            result = create_dummy_contract(harness.page, spec)
            report_path.write_text(
                json.dumps(asdict(result), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    except Exception as exc:
        failure_payload: dict[str, Any] = {
            "cid": spec.cid,
            "holder_name": spec.holder_name,
            "contract_name": spec.contract_name,
            "error": str(exc),
        }
        report_path.write_text(json.dumps(failure_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
