from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from public_mapping import load_public_reference


DEFAULT_OUTPUT = REPO_ROOT / ".codex_tmp" / "public_deploy_bundle"

PUBLIC_DEPLOY_FILES = (
    "app.py",
    "public_mapping.py",
    "mapping_core.py",
    "cleaning_rules.py",
    "matching_rules.py",
    "settlement_adapters.py",
    "requirements.txt",
    "data/public_s2_mapping_reference.csv",
)

FORBIDDEN_BUNDLE_NAMES = (
    ".env",
    "internal_app.py",
    "notion_tasks.py",
    "github_notifications.py",
    "s2_auth.py",
    "s2_direct_refresh.py",
    "s2_reference_guards.py",
    "kiss_payment_settlement.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a minimal anonymous Streamlit deployment bundle.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def validate_bundle(output: Path) -> None:
    actual = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    expected = set(PUBLIC_DEPLOY_FILES)
    if actual != expected:
        raise RuntimeError(f"public bundle file allowlist mismatch: expected={sorted(expected)}, actual={sorted(actual)}")
    lower_names = {path.name.casefold() for path in output.rglob("*") if path.is_file()}
    forbidden = sorted(name for name in FORBIDDEN_BUNDLE_NAMES if name.casefold() in lower_names)
    if forbidden:
        raise RuntimeError(f"forbidden internal files in public bundle: {forbidden}")


def resolve_safe_output(requested: Path) -> Path:
    output = requested.resolve()
    safe_root = (REPO_ROOT / ".codex_tmp").resolve()
    if output == safe_root or safe_root not in output.parents:
        raise RuntimeError("public bundle output must be a dedicated child of .codex_tmp")
    return output


def main() -> int:
    args = parse_args()
    output = resolve_safe_output(args.output)
    if output.exists():
        shutil.rmtree(output)
    for relative in PUBLIC_DEPLOY_FILES:
        source = REPO_ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    load_public_reference(output / "data" / "public_s2_mapping_reference.csv")
    validate_bundle(output)
    print(f"ok files={len(PUBLIC_DEPLOY_FILES)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
