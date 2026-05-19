from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ips.core.selectors import (
    SelectorGroup,
    click_first,
    fill_first,
    is_any_visible,
    wait_for_first,
)


if TYPE_CHECKING:
    from playwright.sync_api import Page

    from ips.core.auth import SiteCredentials


class SiteLoginError(RuntimeError):
    pass


@dataclass(frozen=True)
class SiteAdapter:
    name: str
    display_name: str
    web_base_url: str
    api_base_url: str
    login_path: str
    api_login_path: str
    api_user_info_path: str
    company_code: str
    cookie_domain: str
    auth_env_value: str
    username_env_keys: tuple[str, ...]
    password_env_keys: tuple[str, ...]
    username_selectors: SelectorGroup
    password_selectors: SelectorGroup
    submit_selectors: SelectorGroup

    @property
    def login_url(self) -> str:
        return self.resolve_url(self.login_path)

    def resolve_url(self, path: str = "") -> str:
        if not path:
            return self.web_base_url.rstrip("/")
        if path.startswith("http://") or path.startswith("https://"):
            return path
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self.web_base_url.rstrip('/')}{normalized}"

    def is_login_page(self, page: "Page") -> bool:
        current_url = page.url.lower()
        if self.login_path.lower() in current_url:
            return True
        return is_any_visible(page, self.username_selectors, timeout_ms=300) and is_any_visible(
            page, self.password_selectors, timeout_ms=300
        )

    def appears_logged_in(self, page: "Page") -> bool:
        current_url = page.url.lower()
        if not current_url.startswith(self.web_base_url.lower()):
            return False
        return not self.is_login_page(page)

    def ui_login(
        self,
        page: "Page",
        credentials: "SiteCredentials",
        *,
        timeout_ms: int,
    ) -> dict[str, str]:
        page.goto(self.login_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_load_state("load", timeout=timeout_ms)

        used_selectors: dict[str, str] = {}
        wait_for_first(page, self.username_selectors, timeout_ms=timeout_ms)
        wait_for_first(page, self.password_selectors, timeout_ms=timeout_ms)

        used_selectors["username"] = fill_first(
            page,
            self.username_selectors,
            credentials.username,
            timeout_ms=timeout_ms,
        )
        used_selectors["password"] = fill_first(
            page,
            self.password_selectors,
            credentials.password,
            timeout_ms=timeout_ms,
        )

        try:
            used_selectors["submit"] = click_first(page, self.submit_selectors, timeout_ms=1_200)
        except Exception:  # noqa: BLE001
            password_locator = wait_for_first(page, self.password_selectors, timeout_ms=timeout_ms)
            password_locator.locator.press("Enter")
            used_selectors["submit"] = "ENTER(password)"

        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 8_000))
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(1_000)

        if self.is_login_page(page):
            raise SiteLoginError("UI 로그인 후에도 로그인 페이지에 머물러 있습니다.")

        return used_selectors
