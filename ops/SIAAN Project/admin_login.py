"""Authenticated session harness for http://admin.barobook.com.

Usage:
    python "SIAAN Project/admin_login.py"           # headful (recommended first run)
    python "SIAAN Project/admin_login.py" --headless
    python "SIAAN Project/admin_login.py" --probe-only   # just save login page HTML and quit

Design notes:
- The target is classic Korean business software; do NOT assume JWT SPA.
- We open the root URL with Playwright, capture whatever login page appears,
  save artifacts, try a couple of common selector shapes, and submit.
- On success we save URL/title/cookies + HTML + screenshot under
  SIAAN Project/output/admin_harness/<timestamp>_postlogin/.
- On failure we save the same artifacts under _fail_<step>/ so the next
  iteration has something to look at.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
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
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "output" / "admin_harness"
DEFAULT_BASE_URL = "http://admin.barobook.com"
DEFAULT_TIMEOUT_MS = 20_000

USERNAME_SELECTORS = (
    # Barobook / KLD member portal uses MBR_ID / MBR_PWD
    "input[name='MBR_ID']",
    "input#MBR_ID",
    "input[name='userId']",
    "input[name='user_id']",
    "input[name='username']",
    "input[name='id']",
    "input[name='loginId']",
    "input[name='login_id']",
    "input[name='mb_id']",
    "input[name='memId']",
    "input[name='mem_id']",
    "input#userId",
    "input#user_id",
    "input#username",
    "input#loginId",
    "input#login_id",
    "input#mb_id",
    "input#id",
    "input[type='text']",
)

PASSWORD_SELECTORS = (
    "input[name='MBR_PWD']",
    "input#MBR_PWD",
    "input[name='userPw']",
    "input[name='user_pw']",
    "input[name='password']",
    "input[name='passwd']",
    "input[name='pw']",
    "input[name='loginPw']",
    "input[name='login_pw']",
    "input[name='mb_password']",
    "input[name='memPw']",
    "input[name='mem_pw']",
    "input#userPw",
    "input#user_pw",
    "input#password",
    "input#passwd",
    "input#pw",
    "input#mb_password",
    "input[type='password']",
)

SUBMIT_SELECTORS = (
    # Barobook uses <input type="image" ... title="로그인"> inside frmLogin
    "form#frmLogin input[type='image']",
    "input[type='image'][title='로그인']",
    "input[type='image'][alt='로그인']",
    "button[type='submit']",
    "input[type='submit']",
    "button:has-text('로그인')",
    "a:has-text('로그인')",
    "button:has-text('Login')",
    "button#btnLogin",
    "button.btn_login",
    "button.login",
    "#btnLogin",
    ".btn_login",
)


class AdminLoginError(RuntimeError):
    pass


@dataclass
class AdminConfig:
    username: str
    password: str
    base_url: str = DEFAULT_BASE_URL
    headless: bool = False
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT
    probe_only: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default="", help="Optional path to .env")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--headless", action="store_true", help="Run headless (default: headful)")
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    parser.add_argument(
        "--probe-only",
        action="store_true",
        help="Only open the login page and save HTML; do not submit.",
    )
    return parser.parse_args()


def resolve_env_path(raw: str) -> Path:
    if raw.strip():
        p = Path(raw.strip())
        if not p.exists():
            raise FileNotFoundError(f"env not found: {p}")
        return p
    if DEFAULT_ENV_PATH.exists():
        return DEFAULT_ENV_PATH
    raise FileNotFoundError(f"env not found at default: {DEFAULT_ENV_PATH}")


def load_config_from_args(args: argparse.Namespace) -> AdminConfig:
    """Resolve credentials.

    Preference order:
        1. BAROBOOK_ID / BAROBOOK_PW         (site-specific, if present)
        2. KLD_LOGIN_ID / KLD_LOGIN_PW       (shared KLD/KISS/KIPM creds)

    Barobook member portal (member.barobook.com) rejects the shared KLD
    credentials (user handle there is 'barobook7994' per project memory
    notes). When the dedicated env vars are not provided we still fall back
    to KLD creds so the harness remains runnable for probing.
    """
    env_path = resolve_env_path(args.env_file)
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
        raise AdminLoginError(
            f"{env_path} 에 BAROBOOK_ID/BAROBOOK_PW (또는 KLD_LOGIN_ID/KLD_LOGIN_PW) 가 비어 있습니다."
        )

    return AdminConfig(
        username=username,
        password=password,
        base_url=args.base_url.rstrip("/"),
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        probe_only=args.probe_only,
        extra={"credential_source": source},
    )


def make_artifact_dir(config: AdminConfig, suffix: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = config.artifact_root / f"{ts}_{suffix}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_artifacts(
    page: Any,
    context: Any,
    directory: Path,
    *,
    note: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(directory / "page.png"), full_page=True)
    except Exception as exc:  # noqa: BLE001
        (directory / "screenshot_error.txt").write_text(str(exc), encoding="utf-8")
    try:
        (directory / "page.html").write_text(redact_string(page.content()), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        (directory / "html_error.txt").write_text(str(exc), encoding="utf-8")
    try:
        cookies = context.cookies()
        (directory / "cookies.json").write_text(dumps_redacted(cookies), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    meta = {
        "url": getattr(page, "url", ""),
        "title": _safe_title(page),
        "note": note,
        "extra": extra or {},
        "saved_at": datetime.now().isoformat(),
    }
    (directory / "meta.json").write_text(dumps_redacted(meta), encoding="utf-8")


def _safe_title(page: Any) -> str:
    try:
        return page.title()
    except Exception:  # noqa: BLE001
        return ""


def try_fill_first(page: Any, selectors: tuple[str, ...], value: str) -> str:
    """Try each selector; fill the first visible one. Return the matched selector."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.wait_for(state="visible", timeout=800)
            loc.fill(value)
            return sel
        except Exception:  # noqa: BLE001
            continue
    raise AdminLoginError(
        f"입력 필드를 찾지 못했습니다. tried={selectors}"
    )


def try_submit(page: Any, password_selector: str) -> str:
    """Try to submit the login form. Prefer Enter on the password field, then click buttons."""
    # First try pressing Enter on password field — works for most classic forms.
    try:
        page.locator(password_selector).first.press("Enter")
        return f"Enter on {password_selector}"
    except Exception:  # noqa: BLE001
        pass

    for sel in SUBMIT_SELECTORS:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.click()
            return sel
        except Exception:  # noqa: BLE001
            continue
    raise AdminLoginError(f"제출 버튼을 찾지 못했습니다. tried={SUBMIT_SELECTORS}")


def looks_like_login_page(url: str, html: str) -> bool:
    lowered = (url or "").lower()
    if "login" in lowered or "signin" in lowered or "auth" in lowered:
        return True
    lowered_html = html.lower()
    indicators = ("type=\"password\"", "type='password'", "입력", "아이디", "비밀번호")
    hits = sum(1 for ind in indicators if ind in lowered_html)
    return hits >= 2


def collect_user_identifying_text(page: Any) -> list[str]:
    """Pull short bits of text that likely identify the logged-in user/menu."""
    out: list[str] = []
    for sel in (
        "text=로그아웃",
        "text=logout",
        "text=Logout",
        "text=LOGOUT",
        "text=마이페이지",
        "text=님",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                try:
                    txt = loc.inner_text(timeout=500).strip()
                    if txt:
                        out.append(f"{sel}: {txt}")
                except Exception:  # noqa: BLE001
                    out.append(f"{sel}: (present)")
        except Exception:  # noqa: BLE001
            continue
    # Pull header-ish regions
    for sel in ("header", ".header", "#header", ".top", ".user", ".userinfo"):
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                try:
                    txt = loc.inner_text(timeout=500).strip()
                    if txt and len(txt) < 400:
                        out.append(f"{sel}: {txt!r}")
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            continue
    return out


def run(config: AdminConfig) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # noqa: BLE001
        raise AdminLoginError(
            "Playwright 가 설치되어 있지 않습니다. `pip install playwright` 후 "
            "`playwright install chromium`."
        ) from exc

    config.artifact_root.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"base_url": config.base_url}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless,
            args=["--disable-web-security"],
        )
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1600, "height": 1000},
        )
        page = context.new_page()
        page.set_default_timeout(config.timeout_ms)
        page.set_default_navigation_timeout(config.timeout_ms)

        # Capture any login POST we might see, so we can report the endpoint.
        login_posts: list[dict[str, Any]] = []

        def _on_request(req: Any) -> None:
            try:
                if req.method.upper() == "POST":
                    login_posts.append(
                        {
                            "url": req.url,
                            "method": req.method,
                            "post_data": req.post_data,
                            "headers": dict(req.headers),
                        }
                    )
            except Exception:  # noqa: BLE001
                pass

        page.on("request", _on_request)

        try:
            # Step 1: open root
            page.goto(config.base_url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=5_000)
            except Exception:  # noqa: BLE001
                pass

            initial_url = page.url
            initial_title = _safe_title(page)
            initial_html = page.content()

            loginpage_dir = make_artifact_dir(config, "loginpage")
            save_artifacts(
                page,
                context,
                loginpage_dir,
                note="after first goto",
                extra={
                    "initial_url": initial_url,
                    "initial_title": initial_title,
                    "looks_like_login": looks_like_login_page(initial_url, initial_html),
                },
            )
            result["loginpage_dir"] = str(loginpage_dir)
            result["initial_url"] = initial_url
            result["initial_title"] = initial_title

            if config.probe_only:
                result["probe_only"] = True
                return result

            # Step 2: fill credentials. If the page is already NOT a login page
            # (we might be already authenticated via a stored session), skip.
            if not looks_like_login_page(initial_url, initial_html):
                # Try to find a password field anyway; if none exists we treat
                # this as 'already logged in' (unlikely on first run but safe).
                has_password = page.locator("input[type='password']").count() > 0
                if not has_password:
                    result["auth_mechanism"] = "already authenticated on first visit (no login form)"
                    _finalize_postlogin(page, context, config, result, login_posts)
                    return result

            user_sel = try_fill_first(page, USERNAME_SELECTORS, config.username)
            pwd_sel = try_fill_first(page, PASSWORD_SELECTORS, config.password)
            result["username_selector"] = user_sel
            result["password_selector"] = pwd_sel

            # Step 3: submit. Try to capture the login POST for reporting.
            try:
                with page.expect_response(
                    lambda r: r.request.method.upper() == "POST",
                    timeout=min(config.timeout_ms, 12_000),
                ) as resp_info:
                    submit_how = try_submit(page, pwd_sel)
                login_response = resp_info.value
                result["login_response_url"] = login_response.url
                result["login_response_status"] = login_response.status
            except Exception:
                # Form might do a full navigation without a capturable XHR.
                submit_how = try_submit(page, pwd_sel) if "submit_how" not in locals() else submit_how
            result["submit_method"] = submit_how

            # Step 4: wait for navigation/settle
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:  # noqa: BLE001
                pass
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5_000)
            except Exception:  # noqa: BLE001
                pass

            # Step 5: verify
            post_url = page.url
            post_title = _safe_title(page)
            post_html = page.content()
            result["post_url"] = post_url
            result["post_title"] = post_title

            if looks_like_login_page(post_url, post_html):
                # Try to read any server-emitted ErrorMsg for a clearer reason.
                server_error = ""
                try:
                    err_loc = page.locator("#ErrorMsg").first
                    if err_loc.count() > 0:
                        server_error = err_loc.get_attribute("value") or ""
                except Exception:  # noqa: BLE001
                    pass
                fail_dir = make_artifact_dir(config, "fail_stillonlogin")
                save_artifacts(
                    page,
                    context,
                    fail_dir,
                    note="still on login page after submit",
                    extra={
                        "login_posts": login_posts[-5:],
                        "server_error": server_error,
                        "credential_source": config.extra.get("credential_source"),
                    },
                )
                result["failure_dir"] = str(fail_dir)
                result["server_error"] = server_error
                raise AdminLoginError(
                    "로그인 후에도 로그인 페이지에 머물러 있습니다. "
                    f"url={post_url} server_error={server_error!r}"
                )

            _finalize_postlogin(page, context, config, result, login_posts)
            return result

        except Exception as exc:
            # Catch-all: save state for debugging
            fail_dir = make_artifact_dir(config, "fail_exception")
            save_artifacts(
                page,
                context,
                fail_dir,
                note="unhandled exception",
                extra={"error": str(exc), "login_posts": login_posts[-5:]},
            )
            result["failure_dir"] = str(fail_dir)
            result["error"] = str(exc)
            raise
        finally:
            try:
                context.close()
            finally:
                browser.close()


def _finalize_postlogin(
    page: Any,
    context: Any,
    config: AdminConfig,
    result: dict[str, Any],
    login_posts: list[dict[str, Any]],
) -> None:
    post_dir = make_artifact_dir(config, "postlogin")
    identifying = collect_user_identifying_text(page)
    save_artifacts(
        page,
        context,
        post_dir,
        note="post-login landing page",
        extra={
            "identifying_text": identifying,
            "login_posts": login_posts[-5:],
        },
    )
    cookies = context.cookies()
    cookie_names = sorted({c.get("name", "") for c in cookies})
    result["postlogin_dir"] = str(post_dir)
    result["post_url"] = page.url
    result["post_title"] = _safe_title(page)
    result["identifying_text"] = identifying
    result["cookie_names"] = cookie_names
    # Best-effort auth mechanism summary
    if not result.get("auth_mechanism"):
        posted = [p for p in login_posts if "login" in p["url"].lower() or p["post_data"]]
        endpoint = posted[-1]["url"] if posted else "(no POST captured)"
        session_cookie = next(
            (n for n in cookie_names if "sess" in n.lower() or "phpsessid" in n.lower()),
            (cookie_names[0] if cookie_names else "(none)"),
        )
        result["auth_mechanism"] = (
            f"form-POST to {endpoint}; session cookie candidate: {session_cookie}"
        )


def main() -> int:
    args = parse_args()
    try:
        config = load_config_from_args(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[admin_login] config error: {exc}", file=sys.stderr)
        return 2

    print(f"[admin_login] base_url       = {config.base_url}")
    print(f"[admin_login] headless       = {config.headless}")
    print(f"[admin_login] artifact_root  = {config.artifact_root}")
    print(f"[admin_login] username       = {config.username}")
    print(f"[admin_login] cred_source    = {config.extra.get('credential_source')}")

    try:
        result = run(config)
    except AdminLoginError as exc:
        print(f"[admin_login] FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[admin_login] UNEXPECTED: {exc}", file=sys.stderr)
        return 1

    # Pretty report
    print("")
    print("=== admin.barobook.com login result ===")
    print(f"auth_mechanism : {result.get('auth_mechanism', '(unknown)')}")
    print(f"initial_url    : {result.get('initial_url')}")
    print(f"post_url       : {result.get('post_url')}")
    print(f"post_title     : {result.get('post_title')}")
    print(f"username_sel   : {result.get('username_selector')}")
    print(f"password_sel   : {result.get('password_selector')}")
    print(f"submit_method  : {result.get('submit_method')}")
    print(f"cookie_names   : {result.get('cookie_names')}")
    print("identifying_text:")
    for line in result.get("identifying_text") or []:
        print(f"  - {line}")
    print(f"loginpage_dir  : {result.get('loginpage_dir')}")
    print(f"postlogin_dir  : {result.get('postlogin_dir')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
