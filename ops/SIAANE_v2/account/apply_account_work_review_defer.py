from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

SIAANE_ROOT = Path(__file__).resolve().parents[1]
if str(SIAANE_ROOT) not in sys.path:
    sys.path.insert(0, str(SIAANE_ROOT))

from build_account_decision_queue import OUTPUT_CSV
from build_account_observation_bundle import MANAGER, normalize_text
from local_state_mutator import add_write_flags, backup_files, resolve_write_mode, write_receipt


DEFER_ACTION = "IPS_CID생성보류"
DEFER_NOTE = "2026-04-24 user-confirmed: 미래 용도 optional CID 후보라 현재 IPS CID 없어도 됨"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Defer account work review rows in the local latest decision CSV.")
    add_write_flags(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    live_write = resolve_write_mode(args)
    df = pd.read_csv(OUTPUT_CSV, dtype=str).fillna("")
    mask = (
        df["action_제안"].eq("작품확인")
        & df["처리완료(Y/N)"].map(normalize_text).ne("Y")
    )

    deferred_rows = int(mask.sum())
    if deferred_rows:
        df.loc[mask, "수동_action"] = DEFER_ACTION
        existing_notes = df.loc[mask, "수동_메모"].map(normalize_text)
        df.loc[mask, "수동_메모"] = existing_notes.where(existing_notes.ne(""), DEFER_NOTE)
        df.loc[mask, "처리완료(Y/N)"] = "Y"

    backup_dir, before_hashes = (Path(""), {})
    if live_write:
        backup_dir, before_hashes = backup_files([OUTPUT_CSV], script_name=Path(__file__).stem)
        df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    receipt = write_receipt(
        args,
        script_name=Path(__file__).stem,
        live_write=live_write,
        output_paths=[OUTPUT_CSV],
        backup_dir=backup_dir,
        before_hashes=before_hashes,
    )
    print("=== account work review defer applied ===")
    print(
        json.dumps(
            {
                "manager": MANAGER,
                "mode": "write" if live_write else "dry_run",
                "deferred_rows": deferred_rows,
                "decision_csv": str(OUTPUT_CSV),
                "receipt": str(receipt),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
