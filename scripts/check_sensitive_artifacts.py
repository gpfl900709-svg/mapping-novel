from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DEFAULT_ROOTS = ("output", "ops/SIAAN Project/output", "doc")
SECRET_PATTERNS = {
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    "jwt": re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),
    "clickup_token": re.compile(r"\bpk_[A-Za-z0-9_]{16,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{16,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b"),
    "atlassian_like_token": re.compile(r"\bAT[A-Z0-9]{8,}_[A-Za-z0-9_-]{16,}\b"),
}
TEXT_SUFFIXES = {".csv", ".json", ".md", ".txt", ".html", ".xml", ".log", ".env", ".toml", ".yaml", ".yml"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan local artifacts for obvious secret/token patterns.")
    parser.add_argument("paths", nargs="*", help="Files or directories to scan. Defaults to output/doc roots.")
    parser.add_argument("--max-bytes", type=int, default=5_000_000)
    return parser.parse_args()


def iter_files(paths: list[str]) -> list[Path]:
    roots = [Path(path) for path in (paths or list(DEFAULT_ROOTS))]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                files.append(path)
    return files


def scan_file(path: Path, *, max_bytes: int) -> list[tuple[str, int]]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    if len(data) > max_bytes:
        data = data[:max_bytes]
    text = data.decode("utf-8", errors="ignore")
    findings: list[tuple[str, int]] = []
    for name, pattern in SECRET_PATTERNS.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append((name, line))
    return findings


def main() -> int:
    args = parse_args()
    findings: list[str] = []
    for path in iter_files(args.paths):
        for name, line in scan_file(path, max_bytes=args.max_bytes):
            findings.append(f"{path}:{line}: {name}")
    if findings:
        print("Sensitive artifact patterns found:", file=sys.stderr)
        for finding in findings:
            print(finding, file=sys.stderr)
        return 1
    print("sensitive_artifact_scan=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
