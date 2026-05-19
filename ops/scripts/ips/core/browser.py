from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright


@dataclass(frozen=True)
class BrowserSettings:
    headless: bool = True
    slow_mo_ms: int = 0
    timeout_ms: int = 15_000
    artifacts_root: Path = Path("output/ips_harness")
    trace: bool = False
    launch_args: tuple[str, ...] = ("--disable-web-security",)


@dataclass
class BrowserRuntime:
    site_name: str
    settings: BrowserSettings
    playwright: "Playwright"
    browser: "Browser"
    context: "BrowserContext"
    page: "Page"
    artifact_root: Path

    def save_failure(
        self,
        prefix: str,
        *,
        error_text: str = "",
        extra: dict[str, Any] | None = None,
    ) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        directory = self.artifact_root / self.site_name / f"{timestamp}_{prefix}"
        directory.mkdir(parents=True, exist_ok=True)

        screenshot_path = directory / "page.png"
        html_path = directory / "page.html"
        meta_path = directory / "meta.json"

        try:
            self.page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:  # noqa: BLE001
            pass

        try:
            html_path.write_text(self.page.content(), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

        metadata = {
            "site": self.site_name,
            "url": getattr(self.page, "url", ""),
            "error": error_text,
            "extra": extra or {},
        }
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return directory


class BrowserHarness:
    def __init__(self, *, site_name: str, settings: BrowserSettings) -> None:
        self.site_name = site_name
        self.settings = settings
        self.runtime: BrowserRuntime | None = None

    def __enter__(self) -> BrowserRuntime:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright 가 설치되어 있지 않습니다. "
                "`pip install playwright` 후 `playwright install chromium` 을 실행해 주세요."
            ) from exc

        artifact_root = self.settings.artifacts_root.resolve()
        artifact_root.mkdir(parents=True, exist_ok=True)

        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=self.settings.headless,
            slow_mo=self.settings.slow_mo_ms or None,
            args=list(self.settings.launch_args),
        )
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1600, "height": 1000},
        )
        if self.settings.trace:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = context.new_page()
        page.set_default_timeout(self.settings.timeout_ms)
        page.set_default_navigation_timeout(self.settings.timeout_ms)

        self.runtime = BrowserRuntime(
            site_name=self.site_name,
            settings=self.settings,
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
            artifact_root=artifact_root,
        )
        return self.runtime

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.runtime is None:
            return

        if self.settings.trace:
            trace_path = self.runtime.artifact_root / self.site_name / "last-trace.zip"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.runtime.context.tracing.stop(path=str(trace_path))
            except Exception:  # noqa: BLE001
                pass

        try:
            self.runtime.context.close()
        finally:
            try:
                self.runtime.browser.close()
            finally:
                self.runtime.playwright.stop()


def seed_browser_auth_state(
    runtime: BrowserRuntime,
    *,
    token: str,
    cookie_domain: str,
    auth_env: str,
    session_date_value: str = "",
    additional_cookies: tuple[dict[str, Any], ...] = (),
) -> None:
    cookies = [
        {
            "name": "Authorization",
            "value": token,
            "domain": cookie_domain,
            "path": "/",
            "secure": True,
            "sameSite": "Lax",
        },
        {
            "name": "env",
            "value": auth_env,
            "domain": cookie_domain,
            "path": "/",
            "secure": True,
            "sameSite": "Lax",
        },
    ]
    if session_date_value:
        cookies.append(
            {
                "name": "sessionDate",
                "value": session_date_value,
                "domain": cookie_domain,
                "path": "/",
                "secure": True,
                "sameSite": "Lax",
            }
        )
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for cookie in [*additional_cookies, *cookies]:
        normalized = dict(cookie)
        normalized.setdefault("path", "/")
        normalized.setdefault("sameSite", "Lax")
        key = (
            str(normalized.get("name") or ""),
            str(normalized.get("domain") or normalized.get("url") or ""),
            str(normalized.get("path") or "/"),
        )
        deduped[key] = normalized
    runtime.context.add_cookies(list(deduped.values()))

    init_script = f"""
        (() => {{
            const token = {json.dumps(token)};
            window.localStorage.setItem("isAuthenticated", "true");
            window.localStorage.setItem("token", token);
        }})();
    """
    runtime.context.add_init_script(script=init_script)
