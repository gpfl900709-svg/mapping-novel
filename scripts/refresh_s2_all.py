from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OPS_SCRIPTS = ROOT / "ops" / "scripts"
if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

from secret_redaction import dumps_redacted  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh all local S2 reference files as one epoch.")
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--today", default="")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--manifest", default="")
    parser.add_argument("--skip-payment", action="store_true")
    parser.add_argument("--skip-sales-channel-contents", action="store_true")
    parser.add_argument("--skip-reference-guards", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_step(args: argparse.Namespace, name: str, command: list[str]) -> dict[str, Any]:
    started = datetime.now().isoformat(timespec="seconds")
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "name": name,
        "command": command,
        "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def write_lookup_meta(path: Path, *, manifest_id: str, step: str) -> dict[str, Any]:
    payload = {
        "manifest_id": manifest_id,
        "step": step,
        "path": str(path),
        "sha256": sha256_file(path),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    args = parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()
    manifest_id = f"{today.isoformat()}__s2_all__{datetime.now():%H%M%S}"
    steps: list[dict[str, Any]] = []

    if not args.skip_payment:
        steps.append(
            run_step(
                args,
                "payment_settlement",
                [
                    args.python,
                    "scripts/refresh_kiss_payment_settlement.py",
                    "--env-file",
                    args.env_file,
                    "--today",
                    today.isoformat(),
                    "--lookup-only",
                ],
            )
        )
    if not args.skip_sales_channel_contents:
        steps.append(
            run_step(
                args,
                "sales_channel_contents",
                [
                    args.python,
                    "scripts/refresh_s2_sales_channel_contents.py",
                    "--env-file",
                    args.env_file,
                    "--today",
                    today.isoformat(),
                ],
            )
        )
    if not args.skip_reference_guards:
        steps.append(
            run_step(
                args,
                "reference_guards",
                [
                    args.python,
                    "scripts/refresh_s2_reference_guards.py",
                    "--env-file",
                    args.env_file,
                    "--today",
                    today.isoformat(),
                ],
            )
        )

    outputs = [
        write_lookup_meta(ROOT / "data" / "kiss_payment_settlement_s2_lookup.csv", manifest_id=manifest_id, step="payment_settlement"),
        write_lookup_meta(ROOT / "data" / "s2_sales_channel_content_lookup.csv", manifest_id=manifest_id, step="sales_channel_contents"),
        write_lookup_meta(ROOT / "data" / "s2_payment_missing_lookup.csv", manifest_id=manifest_id, step="reference_guards"),
        write_lookup_meta(ROOT / "data" / "s2_billing_settlement_lookup.csv", manifest_id=manifest_id, step="reference_guards"),
    ]

    manifest = {
        "manifest_id": manifest_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "steps": steps,
        "outputs": outputs,
        "failed_steps": [step["name"] for step in steps if step["returncode"] != 0],
    }
    manifest_path = Path(args.manifest) if args.manifest else ROOT / "doc" / today.isoformat() / "s2_refresh_all_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(dumps_redacted(manifest), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "failed_steps": manifest["failed_steps"]}, ensure_ascii=False, indent=2))
    return 1 if manifest["failed_steps"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
