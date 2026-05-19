from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ips.core.auth import (
    IPSAuthError,
    decode_jwt_expiry,
    load_site_credentials,
    perform_api_login,
    resolve_env_path,
)
from ips.core.browser import BrowserHarness, BrowserRuntime, BrowserSettings, seed_browser_auth_state
from ips.sites.base import SiteAdapter, SiteLoginError


if TYPE_CHECKING:
    from playwright.sync_api import Page


class IPSHarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class HarnessLoginResult:
    site: str
    display_name: str
    method: str
    final_url: str
    token_present: bool
    username: str
    user_info: dict[str, Any] | None = None

    def to_dict(self, *, include_user_info: bool = False) -> dict[str, Any]:
        payload = {
            "site": self.site,
            "display_name": self.display_name,
            "method": self.method,
            "final_url": self.final_url,
            "token_present": self.token_present,
            "username": self.username,
        }
        if include_user_info:
            payload["user_info"] = self.user_info
        return payload


class IPSHarness:
    def __init__(
        self,
        site: SiteAdapter,
        *,
        settings: BrowserSettings | None = None,
        env_path: Path | None = None,
    ) -> None:
        self.site = site
        self.settings = settings or BrowserSettings()
        self.env_path = env_path or resolve_env_path("")
        self.runtime: BrowserRuntime | None = None
        self._browser_guard: BrowserHarness | None = None
        self._last_login_result: HarnessLoginResult | None = None

    def __enter__(self) -> "IPSHarness":
        self._browser_guard = BrowserHarness(site_name=self.site.name, settings=self.settings)
        self.runtime = self._browser_guard.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._browser_guard is not None:
            self._browser_guard.__exit__(exc_type, exc, tb)
        self.runtime = None
        self._browser_guard = None

    @property
    def page(self) -> "Page":
        if self.runtime is None:
            raise IPSHarnessError("브라우저 런타임이 아직 열리지 않았습니다.")
        return self.runtime.page

    def navigate(self, path: str = "") -> str:
        if self.runtime is None:
            raise IPSHarnessError("브라우저 런타임이 아직 열리지 않았습니다.")
        target_url = self.site.resolve_url(path)
        self.runtime.page.goto(target_url, wait_until="domcontentloaded", timeout=self.settings.timeout_ms)
        try:
            self.runtime.page.wait_for_load_state("networkidle", timeout=min(self.settings.timeout_ms, 8_000))
        except Exception:  # noqa: BLE001
            pass
        return self.runtime.page.url

    def ensure_logged_in(self, path: str = "") -> HarnessLoginResult:
        if self.runtime is None:
            raise IPSHarnessError("브라우저 런타임이 아직 열리지 않았습니다.")

        target_url = self.site.resolve_url(path)
        credentials = load_site_credentials(
            self.env_path,
            username_keys=self.site.username_env_keys,
            password_keys=self.site.password_env_keys,
            company_code=self.site.company_code,
        )

        if self.site.appears_logged_in(self.runtime.page):
            result = HarnessLoginResult(
                site=self.site.name,
                display_name=self.site.display_name,
                method="existing",
                final_url=self.runtime.page.url,
                token_present=False,
                username=credentials.username,
            )
            self._last_login_result = result
            return result

        api_errors: list[str] = []

        try:
            api_result = perform_api_login(
                api_base_url=self.site.api_base_url,
                login_path=self.site.api_login_path,
                user_info_path=self.site.api_user_info_path,
                credentials=credentials,
            )
            expiry = decode_jwt_expiry(api_result.token)
            session_date = expiry.isoformat() if expiry else datetime.now().isoformat()
            seed_browser_auth_state(
                self.runtime,
                token=api_result.token,
                cookie_domain=self.site.cookie_domain,
                auth_env=self.site.auth_env_value,
                session_date_value=session_date,
                additional_cookies=api_result.browser_cookies,
            )
            self.navigate(target_url)
            if self.site.appears_logged_in(self.runtime.page):
                result = HarnessLoginResult(
                    site=self.site.name,
                    display_name=self.site.display_name,
                    method="api-seeded",
                    final_url=self.runtime.page.url,
                    token_present=True,
                    username=credentials.username,
                    user_info=api_result.user_info,
                )
                self._last_login_result = result
                return result
            api_errors.append("API 로그인은 성공했지만 브라우저가 로그인 페이지에 머물렀습니다.")
        except Exception as exc:  # noqa: BLE001
            api_errors.append(f"api: {exc}")

        try:
            selector_info = self.site.ui_login(
                self.runtime.page,
                credentials,
                timeout_ms=self.settings.timeout_ms,
            )
            if path:
                self.navigate(path)
            if not self.site.appears_logged_in(self.runtime.page):
                raise SiteLoginError("UI 로그인 후에도 로그인 상태가 확인되지 않았습니다.")
            result = HarnessLoginResult(
                site=self.site.name,
                display_name=self.site.display_name,
                method="ui-fallback",
                final_url=self.runtime.page.url,
                token_present=False,
                username=credentials.username,
            )
            self._last_login_result = result
            return result
        except Exception as exc:  # noqa: BLE001
            error_text = "\n".join(api_errors + [f"ui: {exc}"]) if api_errors else str(exc)
            artifact_dir = self.runtime.save_failure(
                "login_failure",
                error_text=error_text,
                extra={
                    "site": self.site.name,
                    "target_url": target_url,
                },
            )
            raise IPSHarnessError(f"{error_text}\nartifacts={artifact_dir}") from exc

    def run_task(self, task: Callable[["Page"], Any], *, path: str = "") -> Any:
        self.ensure_logged_in(path=path)
        return task(self.page)
