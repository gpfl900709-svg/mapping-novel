from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


class LocalStateMutationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalStateMutationReceipt:
    script: str
    mode: str
    created_at: str
    output_paths: list[str]
    backup_dir: str
    before_hashes: dict[str, str]
    after_hashes: dict[str, str]


def add_write_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true", help="Preview only. This is also the default.")
    parser.add_argument("--write", action="store_true", help="Actually overwrite latest local CSV files.")
    parser.add_argument("--receipt", default="", help="Optional mutation receipt JSON path.")


def resolve_write_mode(args: argparse.Namespace) -> bool:
    if getattr(args, "write", False) and getattr(args, "dry_run", False):
        raise LocalStateMutationError("Use either --write or --dry-run, not both.")
    return bool(getattr(args, "write", False))


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_files(paths: Iterable[Path], *, script_name: str) -> tuple[Path, dict[str, str]]:
    existing = [Path(path) for path in paths if Path(path).exists()]
    backup_root = Path(__file__).resolve().parent / "exports" / ".backup" / f"{datetime.now():%Y%m%d_%H%M%S}__{script_name}"
    before_hashes = {str(path): sha256_file(path) for path in existing}
    if existing:
        backup_root.mkdir(parents=True, exist_ok=True)
        for path in existing:
            shutil.copy2(path, backup_root / path.name)
    return backup_root, before_hashes


def receipt_path(args: argparse.Namespace, *, script_name: str) -> Path:
    if getattr(args, "receipt", ""):
        return Path(args.receipt)
    return Path(__file__).resolve().parent / "exports" / ".backup" / f"{datetime.now():%Y%m%d_%H%M%S}__{script_name}_receipt.json"


def write_receipt(
    args: argparse.Namespace,
    *,
    script_name: str,
    live_write: bool,
    output_paths: Iterable[Path],
    backup_dir: Path,
    before_hashes: dict[str, str],
) -> Path:
    outputs = [Path(path) for path in output_paths]
    receipt = LocalStateMutationReceipt(
        script=script_name,
        mode="write" if live_write else "dry_run",
        created_at=datetime.now().isoformat(timespec="seconds"),
        output_paths=[str(path) for path in outputs],
        backup_dir=str(backup_dir) if live_write else "",
        before_hashes=before_hashes if live_write else {},
        after_hashes={str(path): sha256_file(path) for path in outputs} if live_write else {},
    )
    target = receipt_path(args, script_name=script_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
