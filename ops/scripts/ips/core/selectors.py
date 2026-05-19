from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page


@dataclass(frozen=True)
class SelectorGroup:
    name: str
    candidates: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedSelector:
    locator: "Locator"
    selector: str


def wait_for_first(
    page: "Page",
    group: SelectorGroup,
    *,
    timeout_ms: int = 1_500,
    state: str = "visible",
) -> ResolvedSelector:
    last_error: Exception | None = None
    candidate_count = max(1, len(group.candidates))
    per_selector_timeout = max(250, timeout_ms // candidate_count)

    for selector in group.candidates:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state=state, timeout=per_selector_timeout)
            return ResolvedSelector(locator=locator, selector=selector)
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    if last_error is None:
        raise LookupError(f"{group.name} 후보 셀렉터가 비어 있습니다.")

    raise LookupError(
        f"{group.name} 요소를 찾지 못했습니다. tried={group.candidates}"
    ) from last_error


def is_any_visible(page: "Page", group: SelectorGroup, *, timeout_ms: int = 400) -> bool:
    try:
        wait_for_first(page, group, timeout_ms=timeout_ms, state="visible")
    except Exception:  # noqa: BLE001
        return False
    return True


def fill_first(page: "Page", group: SelectorGroup, value: str, *, timeout_ms: int = 1_500) -> str:
    resolved = wait_for_first(page, group, timeout_ms=timeout_ms, state="visible")
    resolved.locator.fill(value)
    return resolved.selector


def click_first(page: "Page", group: SelectorGroup, *, timeout_ms: int = 1_500) -> str:
    resolved = wait_for_first(page, group, timeout_ms=timeout_ms, state="visible")
    resolved.locator.click()
    return resolved.selector
