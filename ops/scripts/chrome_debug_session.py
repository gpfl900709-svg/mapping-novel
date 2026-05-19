from __future__ import annotations

import json
import shlex
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


DEFAULT_CONNECT_URL = "http://127.0.0.1:9222"
DEFAULT_SHORTCUT_PATH = Path.home() / "Desktop" / "크롬디버깅.lnk"
DEFAULT_USER_DATA_DIR = Path("C:/ChromeTemp")
DEFAULT_CHROME_PATHS = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
)


@dataclass(frozen=True)
class DebugChromeLaunchResult:
    launched: bool
    connect_url: str
    http_base: str
    chrome_path: str
    working_directory: str
    shortcut_path: str
    sheet_url: str
    port_ready: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "launched": self.launched,
            "connect_url": self.connect_url,
            "http_base": self.http_base,
            "chrome_path": self.chrome_path,
            "working_directory": self.working_directory,
            "shortcut_path": self.shortcut_path,
            "sheet_url": self.sheet_url,
            "port_ready": self.port_ready,
        }


def connect_http_base(connect_url: str) -> str:
    parsed = urlparse(connect_url)
    if parsed.scheme in {"http", "https"}:
        return f"{parsed.scheme}://{parsed.netloc}"
    if parsed.scheme in {"ws", "wss"}:
        http_scheme = "https" if parsed.scheme == "wss" else "http"
        return f"{http_scheme}://{parsed.netloc}"
    raise ValueError(f"Unsupported connect URL: {connect_url}")


def _connect_host_port(connect_url: str) -> tuple[str, int]:
    parsed = urlparse(connect_url)
    host = parsed.hostname or "127.0.0.1"
    if parsed.port:
        return host, parsed.port
    return host, 443 if parsed.scheme in {"https", "wss"} else 80


def _port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def _fetch_json(url: str) -> Any:
    with urlopen(url, timeout=3) as handle:
        return json.load(handle)


def debug_endpoint_ready(connect_url: str) -> bool:
    host, port = _connect_host_port(connect_url)
    if not _port_is_open(host, port):
        return False
    try:
        _fetch_json(f"{connect_http_base(connect_url)}/json/version")
        return True
    except Exception:  # noqa: BLE001
        return False


def _inspect_shortcut(shortcut_path: Path) -> dict[str, str]:
    if not shortcut_path.exists():
        return {}
    escaped_path = str(shortcut_path).replace("'", "''")
    command = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$shortcut = $shell.CreateShortcut('{escaped_path}'); "
        "[PSCustomObject]@{"
        "TargetPath=$shortcut.TargetPath;"
        "Arguments=$shortcut.Arguments;"
        "WorkingDirectory=$shortcut.WorkingDirectory"
        "} | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return {}
    payload = json.loads(completed.stdout)
    return {
        "TargetPath": str(payload.get("TargetPath") or "").strip(),
        "Arguments": str(payload.get("Arguments") or "").strip(),
        "WorkingDirectory": str(payload.get("WorkingDirectory") or "").strip(),
    }


def _resolve_chrome_path(shortcut_info: dict[str, str], explicit_path: str = "") -> Path:
    if explicit_path:
        path = Path(explicit_path)
        if path.exists():
            return path
    shortcut_target = Path(shortcut_info.get("TargetPath") or "")
    if shortcut_target.exists():
        return shortcut_target
    for candidate in DEFAULT_CHROME_PATHS:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Chrome executable not found. Provide --chrome-path or recreate 크롬디버깅.lnk.")


def _split_arguments(arguments: str) -> list[str]:
    if not arguments.strip():
        return []
    return [token.strip('"') for token in shlex.split(arguments, posix=False)]


def _find_argument_index(arguments: list[str], prefix: str) -> int:
    for index, token in enumerate(arguments):
        if token.startswith(prefix):
            return index
    return -1


def _upsert_argument(arguments: list[str], prefix: str, value: str) -> None:
    token = f"{prefix}{value}"
    index = _find_argument_index(arguments, prefix)
    if index >= 0:
        arguments[index] = token
    else:
        arguments.append(token)


def _ensure_flag(arguments: list[str], flag: str) -> None:
    if flag not in arguments:
        arguments.append(flag)


def _open_sheet_target(http_base: str, sheet_url: str) -> None:
    encoded = quote(sheet_url, safe="")
    for method in ("PUT", "GET"):
        try:
            request = Request(f"{http_base}/json/new?{encoded}", method=method)
            with urlopen(request, timeout=5):
                return
        except Exception:  # noqa: BLE001
            continue


def _target_exists(http_base: str, target_url: str) -> bool:
    try:
        pages = _fetch_json(f"{http_base}/json/list")
    except Exception:  # noqa: BLE001
        return False
    target_prefix = target_url.split("#")[0]
    for page in pages:
        if page.get("type") != "page":
            continue
        if str(page.get("url") or "").startswith(target_prefix):
            return True
    return False


def ensure_debug_chrome(
    *,
    connect_url: str = DEFAULT_CONNECT_URL,
    sheet_url: str = "",
    shortcut_path: Path | None = None,
    chrome_path: str = "",
    user_data_dir: str = "",
    start_wait_ms: int = 30_000,
) -> DebugChromeLaunchResult:
    http_base = connect_http_base(connect_url)
    resolved_shortcut = shortcut_path or DEFAULT_SHORTCUT_PATH

    if debug_endpoint_ready(connect_url):
        if sheet_url and not _target_exists(http_base, sheet_url):
            _open_sheet_target(http_base, sheet_url)
        return DebugChromeLaunchResult(
            launched=False,
            connect_url=connect_url,
            http_base=http_base,
            chrome_path="",
            working_directory="",
            shortcut_path=str(resolved_shortcut),
            sheet_url=sheet_url,
            port_ready=True,
        )

    shortcut_info = _inspect_shortcut(resolved_shortcut)
    executable = _resolve_chrome_path(shortcut_info, chrome_path)
    arguments = _split_arguments(shortcut_info.get("Arguments", ""))
    working_directory = shortcut_info.get("WorkingDirectory") or str(executable.parent)

    host, port = _connect_host_port(connect_url)
    _upsert_argument(arguments, "--remote-debugging-port=", str(port))
    _upsert_argument(arguments, "--user-data-dir=", user_data_dir or str(DEFAULT_USER_DATA_DIR))
    _upsert_argument(arguments, "--remote-allow-origins=", "*")
    _ensure_flag(arguments, "--no-first-run")
    _ensure_flag(arguments, "--no-default-browser-check")

    launch_command = [str(executable), *arguments]
    if sheet_url:
        launch_command.append(sheet_url)

    subprocess.Popen(
        launch_command,
        cwd=working_directory,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + max(1, start_wait_ms) / 1000
    while time.time() < deadline:
        if debug_endpoint_ready(connect_url):
            if sheet_url and not _target_exists(http_base, sheet_url):
                _open_sheet_target(http_base, sheet_url)
            return DebugChromeLaunchResult(
                launched=True,
                connect_url=connect_url,
                http_base=http_base,
                chrome_path=str(executable),
                working_directory=working_directory,
                shortcut_path=str(resolved_shortcut),
                sheet_url=sheet_url,
                port_ready=True,
            )
        time.sleep(1.0)

    raise TimeoutError(f"Chrome remote debugging did not become ready at {host}:{port}.")
