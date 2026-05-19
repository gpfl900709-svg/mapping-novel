from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values


DEFAULT_ENV_CANDIDATES = (
    Path("SIAAN Project/.env"),
    Path(".env"),
)
DEFAULT_TIMEOUT_SECONDS = 30


class IPSAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class SiteCredentials:
    username: str
    password: str
    env_path: Path
    company_code: str = "1000"


@dataclass(frozen=True)
class APIAuthResult:
    token: str
    user_info: dict[str, Any]
    login_payload: dict[str, Any]
    browser_cookies: tuple[dict[str, Any], ...]


def resolve_env_path(raw_path: str = "") -> Path:
    if raw_path.strip():
        path = Path(raw_path.strip())
        if not path.exists():
            raise FileNotFoundError(f"env 파일이 없습니다: {path}")
        return path

    for candidate in DEFAULT_ENV_CANDIDATES:
        if candidate.exists():
            return candidate

    return DEFAULT_ENV_CANDIDATES[0]


def _pick_value(values: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(values.get(key) or os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def load_site_credentials(
    env_path: Path,
    *,
    username_keys: tuple[str, ...],
    password_keys: tuple[str, ...],
    company_code: str = "1000",
) -> SiteCredentials:
    if not env_path.exists():
        raise FileNotFoundError(
            f"env 파일이 없습니다: {env_path}. 공용 로그인 정보를 먼저 채워 주세요."
        )

    values = dict(dotenv_values(env_path))
    username = _pick_value(values, *username_keys)
    password = _pick_value(values, *password_keys)
    if not username or not password:
        raise IPSAuthError(
            f"{env_path} 에서 사이트 로그인 정보를 찾지 못했습니다. "
            f"checked_id={username_keys} checked_pw={password_keys}"
        )

    return SiteCredentials(
        username=username,
        password=password,
        env_path=env_path,
        company_code=company_code,
    )


def _build_api_url(base_url: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url.rstrip('/')}{normalized_path}"


def _extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        code = str(payload.get("code") or "").strip()
        message = str(payload.get("message") or "").strip()
        parts = [part for part in (code, message) if part]
        if parts:
            return " | ".join(parts)

    return json.dumps(payload, ensure_ascii=False)


def _ensure_json_response(response: requests.Response, *, context: str) -> dict[str, Any]:
    if not response.ok:
        raise IPSAuthError(f"{context} 실패: {_extract_error_message(response)}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise IPSAuthError(f"{context} 응답이 JSON 이 아닙니다.") from exc

    if not isinstance(payload, dict):
        raise IPSAuthError(f"{context} 응답 형식이 예상과 다릅니다: {type(payload).__name__}")
    return payload


def unwrap_user_info(payload: dict[str, Any]) -> dict[str, Any]:
    nested_data = payload.get("data")
    if isinstance(nested_data, dict) and any(
        key in nested_data for key in ("userId", "userNm", "roles", "cprCd")
    ):
        return nested_data
    return payload


def extract_jwt(payload: dict[str, Any]) -> str:
    nested_data = payload.get("data")
    nested = nested_data if isinstance(nested_data, dict) else {}
    candidates = (
        payload.get("jwt"),
        payload.get("token"),
        payload.get("accessToken"),
        nested.get("jwt"),
        nested.get("token"),
        nested.get("accessToken"),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    raise IPSAuthError("로그인 응답에서 JWT 토큰을 찾지 못했습니다.")


def decode_jwt_expiry(token: str) -> datetime | None:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
        data = json.loads(decoded.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None

    exp = data.get("exp")
    if not isinstance(exp, (int, float)):
        return None
    return datetime.fromtimestamp(exp, tz=timezone.utc)


def snapshot_session_cookies(session: requests.Session) -> tuple[dict[str, Any], ...]:
    cookies: list[dict[str, Any]] = []
    for cookie in session.cookies:
        snapshot: dict[str, Any] = {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path or "/",
            "secure": bool(cookie.secure),
            "httpOnly": "HttpOnly" in getattr(cookie, "_rest", {}),
            "sameSite": "Lax",
        }
        if cookie.expires:
            snapshot["expires"] = int(cookie.expires)
        cookies.append(snapshot)
    return tuple(cookies)


def perform_api_login(
    *,
    api_base_url: str,
    login_path: str,
    user_info_path: str,
    credentials: SiteCredentials,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> APIAuthResult:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=utf-8",
            "X-Requested-With": "XMLHttpRequest",
        }
    )

    login_payload = {
        "username": credentials.username,
        "password": credentials.password,
        "cprCd": credentials.company_code,
    }
    login_response = session.post(
        _build_api_url(api_base_url, login_path),
        json=login_payload,
        timeout=timeout_seconds,
    )
    login_body = _ensure_json_response(login_response, context="API 로그인")
    token = extract_jwt(login_body)

    session.headers["Authorization"] = f"Bearer {token}"
    user_info_response = session.get(
        _build_api_url(api_base_url, user_info_path),
        params={"cprCd": credentials.company_code},
        timeout=timeout_seconds,
    )
    user_info_body = _ensure_json_response(user_info_response, context="로그인 검증")
    user_info = unwrap_user_info(user_info_body)
    if not any(user_info.get(key) for key in ("userId", "userNm", "roles", "cprCd")):
        raise IPSAuthError("로그인 검증 응답에 사용자 정보가 없습니다.")

    return APIAuthResult(
        token=token,
        user_info=user_info,
        login_payload=login_body,
        browser_cookies=snapshot_session_cookies(session),
    )
