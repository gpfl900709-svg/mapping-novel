"""Authenticated session harness for http://account.barobook.com.

Background (probed 2026-04-17):
    * http://account.barobook.com/ responds with a tiny HTML page whose only
      purpose is a `top.location.href = 'http://member.barobook.com/auth/Login?...'`
      JS redirect. So the login itself happens on member.barobook.com.
    * The login page is classic ASP.NET MVC (IIS 8.5 / ASP.NET MVC 5.2) with a
      jQuery-submitted form. Submit handler POSTs to
      `https://member.barobook.com:443/Auth/Login` with fields:
        MBR_ID, MBR_PWD, svcCD, KEEP_SESSION, RedirectURL.
    * On success the server sets ASP.NET session cookies (incl. ASP.NET_SessionId
      and a `.AUTH` / `membership` cookie family) and redirects back to the
      RedirectURL, i.e. http://account.barobook.com/.
    * No JWT, no SPA. Classic form-POST + session cookie auth.

This harness uses Playwright (headed by default) to:
    1. Navigate to account.barobook.com (triggers the JS redirect).
    2. Wait for the member.barobook.com login form, save the raw login page
       HTML for later selector work.
    3. Fill MBR_ID / MBR_PWD and submit the form.
    4. Wait for navigation back to account.barobook.com (i.e. NOT /auth/Login).
    5. Capture post-login URL, title, a heuristic user-name snippet, and save
       screenshot + HTML to output/account_harness/<ts>_postlogin/.

Run:
    python "SIAAN Project/account_login.py"
    python "SIAAN Project/account_login.py" --headless        # quiet mode
    python "SIAAN Project/account_login.py" --keep-open       # keep browser
                                                              # open for
                                                              # manual probe
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
SCRIPTS_ROOT = PROJECT_ROOT.parent / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from secret_redaction import dumps_redacted, redact_string  # noqa: E402

DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
ARTIFACTS_ROOT = PROJECT_ROOT / "output" / "account_harness"

ACCOUNT_HOME_URL = "http://account.barobook.com/"
MEMBER_LOGIN_URL = (
    "http://member.barobook.com/auth/Login?svcCD=0&redirectURL="
    "http%3A%2F%2Faccount.barobook.com%2F"
)

DEFAULT_TIMEOUT_MS = 20_000
MAX_LOGIN_ATTEMPTS = 5


class AccountLoginError(RuntimeError):
    pass


@dataclass(frozen=True)
class AccountConfig:
    username: str
    password: str
    env_path: Path
    credential_source: str = ""
    timeout_ms: int = DEFAULT_TIMEOUT_MS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Log in to account.barobook.com and save post-login artifacts.",
    )
    parser.add_argument(
        "--env-file",
        default="",
        help="Optional path to the .env file. Defaults to SIAAN Project/.env.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help="Playwright default timeout in milliseconds.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Playwright headless. Default is headed so you can see the flow.",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Leave the browser open after login for interactive inspection.",
    )
    return parser.parse_args()


def resolve_env_path(raw: str) -> Path:
    if raw.strip():
        path = Path(raw.strip())
        if not path.exists():
            raise FileNotFoundError(f"env 파일이 없습니다: {path}")
        return path
    if not DEFAULT_ENV_PATH.exists():
        raise FileNotFoundError(
            f"env 파일이 없습니다: {DEFAULT_ENV_PATH}. KLD_LOGIN_ID/KLD_LOGIN_PW 필요."
        )
    return DEFAULT_ENV_PATH


def load_config(env_path: Path, *, timeout_ms: int) -> AccountConfig:
    load_dotenv(env_path, override=True)
    barobook_id = os.getenv("BAROBOOK_ID", "").strip()
    barobook_pw = os.getenv("BAROBOOK_PW", "").strip()
    kld_id = os.getenv("KLD_LOGIN_ID", "").strip()
    kld_pw = os.getenv("KLD_LOGIN_PW", "").strip()

    if barobook_id and barobook_pw:
        username, password, source = barobook_id, barobook_pw, "BAROBOOK_*"
    elif kld_id and kld_pw:
        username, password, source = kld_id, kld_pw, "KLD_LOGIN_* (fallback)"
    else:
        raise AccountLoginError(
            f"{env_path} 에 BAROBOOK_ID/BAROBOOK_PW (또는 KLD_LOGIN_ID/KLD_LOGIN_PW) 가 비어 있습니다."
        )

    return AccountConfig(
        username=username,
        password=password,
        env_path=env_path,
        credential_source=source,
        timeout_ms=timeout_ms,
    )


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _artifact_dir(prefix: str) -> Path:
    directory = ARTIFACTS_ROOT / f"{_timestamp()}_{prefix}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _save_artifacts(
    page: Any,
    directory: Path,
    *,
    meta: dict[str, Any] | None = None,
) -> None:
    screenshot_path = directory / "page.png"
    html_path = directory / "page.html"
    meta_path = directory / "meta.json"

    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] screenshot 실패: {exc}", file=sys.stderr)

    try:
        html_path.write_text(redact_string(page.content()), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] html 저장 실패: {exc}", file=sys.stderr)

    metadata: dict[str, Any] = {
        "url": getattr(page, "url", ""),
        "title": "",
    }
    try:
        metadata["title"] = page.title()
    except Exception:  # noqa: BLE001
        pass
    if meta:
        metadata.update(meta)
    meta_path.write_text(dumps_redacted(metadata), encoding="utf-8")


def _wait_for_login_form(page: Any, *, timeout_ms: int) -> None:
    # Wait for the top-level redirect to land us on member.barobook.com.
    page.wait_for_url(
        lambda url: "member.barobook.com" in str(url) and "/auth/Login" in str(url),
        timeout=timeout_ms,
    )
    page.wait_for_selector("#MBR_ID", state="visible", timeout=timeout_ms)
    page.wait_for_selector("#MBR_PWD", state="visible", timeout=timeout_ms)


def _extract_user_hint(page: Any) -> str:
    """Best-effort scrape of any user-identifying text on the landing page."""
    selectors = [
        "text=/로그아웃/",  # "logout" link proves we are logged in
        ".user, .username, #username, #userName",
        "text=/님/",  # "홍길동님" style greeting
        "header a[href*='mypage'], header a[href*='member']",
    ]
    hints: list[str] = []
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            text = (locator.inner_text(timeout=1500) or "").strip()
            if text:
                hints.append(f"{selector} -> {text}")
        except Exception:  # noqa: BLE001
            continue
    return " | ".join(hints)


def login_account(config: AccountConfig, *, headless: bool, keep_open: bool) -> dict[str, Any]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise AccountLoginError(
            "Playwright 가 설치되어 있지 않습니다. "
            "`pip install playwright` 후 `playwright install chromium`."
        ) from exc

    ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1400, "height": 900},
            locale="ko-KR",
        )
        page = context.new_page()
        page.set_default_timeout(config.timeout_ms)
        page.set_default_navigation_timeout(config.timeout_ms)

        try:
            # 1. Navigate to the account root. Server returns an HTML doc that
            #    JS-redirects to member.barobook.com via top.location.href. We
            #    follow that redirect by just waiting for the URL change.
            page.goto(ACCOUNT_HOME_URL, wait_until="domcontentloaded")

            try:
                _wait_for_login_form(page, timeout_ms=config.timeout_ms)
            except PlaywrightTimeoutError:
                # Fallback: hard-navigate to the login page directly.
                page.goto(MEMBER_LOGIN_URL, wait_until="domcontentloaded")
                _wait_for_login_form(page, timeout_ms=config.timeout_ms)

            login_dir = _artifact_dir("loginpage")
            _save_artifacts(page, login_dir, meta={"stage": "login_form"})
            print(f"[info] login page artifacts: {login_dir}")

            # 2. Fill and submit.
            page.fill("#MBR_ID", config.username)
            page.fill("#MBR_PWD", config.password)

            attempts = 0
            while attempts < MAX_LOGIN_ATTEMPTS:
                attempts += 1
                try:
                    with page.expect_navigation(
                        timeout=config.timeout_ms,
                        wait_until="domcontentloaded",
                    ):
                        page.locator("#MBR_PWD").press("Enter")
                    break
                except PlaywrightTimeoutError:
                    # Some flows don't navigate the top frame on submit; fall
                    # through and just check the URL below.
                    print(
                        f"[warn] submit 시도 {attempts}: navigation 이벤트 없음, "
                        "URL 상태 재확인 후 재시도",
                        file=sys.stderr,
                    )
                    if "member.barobook.com" not in page.url:
                        # Already navigated; we're fine.
                        break
            else:
                fail_dir = _artifact_dir("loginfail_submit")
                _save_artifacts(page, fail_dir, meta={"stage": "submit_no_nav"})
                raise AccountLoginError(
                    f"로그인 submit 후 navigation 이벤트를 {MAX_LOGIN_ATTEMPTS}회 "
                    f"시도했지만 실패. artifact: {fail_dir}"
                )

            # Give any JS redirect back to account.barobook.com time to land.
            try:
                page.wait_for_url(
                    lambda url: "/auth/login" not in str(url).lower(),
                    timeout=config.timeout_ms,
                )
            except PlaywrightTimeoutError:
                pass

            try:
                page.wait_for_load_state("networkidle", timeout=config.timeout_ms)
            except PlaywrightTimeoutError:
                pass

            # 3. Verify: we must NOT be on the login page.
            current_url = page.url
            if "/auth/login" in current_url.lower() or "member.barobook.com" in current_url.lower():
                server_error = ""
                try:
                    server_error = (
                        page.locator("#ErrorMsg").first.get_attribute("value") or ""
                    ).strip()
                except Exception:  # noqa: BLE001
                    pass
                fail_dir = _artifact_dir("loginfail_stuck")
                _save_artifacts(
                    page,
                    fail_dir,
                    meta={
                        "stage": "still_on_login",
                        "current_url": current_url,
                        "server_error_msg": server_error,
                        "username_tried": config.username,
                    },
                )
                raise AccountLoginError(
                    f"로그인 후에도 로그인 페이지에 머물러 있음. URL={current_url}. "
                    f"server_error={server_error or '(empty)'}. artifact: {fail_dir}"
                )

            title = ""
            try:
                title = page.title()
            except Exception:  # noqa: BLE001
                pass

            user_hint = _extract_user_hint(page)

            # 4. Save post-login artifacts.
            post_dir = _artifact_dir("postlogin")
            cookies = context.cookies()
            _save_artifacts(
                page,
                post_dir,
                meta={
                    "stage": "postlogin",
                    "username": config.username,
                    "user_hint": user_hint,
                    "cookies": [
                        {k: c.get(k) for k in ("name", "domain", "path", "httpOnly", "secure")}
                        for c in cookies
                    ],
                },
            )

            result = {
                "post_login_url": current_url,
                "title": title,
                "user_hint": user_hint,
                "artifact_dir": str(post_dir),
                "cookie_names": sorted({c.get("name", "") for c in cookies if c.get("name")}),
            }

            print("")
            print("=== account.barobook.com 로그인 성공 ===")
            print(f"post_login_url : {result['post_login_url']}")
            print(f"title          : {result['title']}")
            print(f"user_hint      : {result['user_hint'] or '(user-identifying text not detected — inspect HTML)'}")
            print(f"artifact_dir   : {result['artifact_dir']}")
            print(f"cookies        : {', '.join(result['cookie_names'])}")

            if keep_open:
                print("")
                print("[info] --keep-open: 브라우저를 열어 둡니다. Enter 를 누르면 종료합니다.")
                try:
                    input()
                except EOFError:
                    pass

            return result
        finally:
            try:
                context.close()
            finally:
                browser.close()


def main() -> None:
    args = parse_args()
    env_path = resolve_env_path(args.env_file)
    config = load_config(env_path, timeout_ms=args.timeout_ms)
    try:
        login_account(config, headless=args.headless, keep_open=args.keep_open)
    except AccountLoginError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
