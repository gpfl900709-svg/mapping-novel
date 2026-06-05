from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
ACCOUNT_DIR = ROOT / "SIAANE_v2" / "account"
if str(ACCOUNT_DIR) not in sys.path:
    sys.path.insert(0, str(ACCOUNT_DIR))
SIAANE_ROOT = ROOT / "SIAANE_v2"
if str(SIAANE_ROOT) not in sys.path:
    sys.path.insert(0, str(SIAANE_ROOT))

from build_account_observation_bundle import MANAGER, normalize_text  # noqa: E402
from local_state_mutator import add_write_flags, backup_files, resolve_write_mode, write_receipt  # noqa: E402


ACCOUNT_DECISION_CSV = ROOT / "SIAANE_v2" / "account" / "exports" / f"latest__account_decision_queue_{MANAGER}.csv"
RIGHTS_REVIEW_CSV = ROOT / "SIAANE_v2" / "crosswalk" / "exports" / f"latest__account_cid_split_rights_review_{MANAGER}.csv"
WORK_REVIEW_CSV = ROOT / "SIAANE_v2" / "crosswalk" / "exports" / f"latest__account_cid_split_work_review_{MANAGER}.csv"

APPROVE_NOTES = {
    "1005540": "2026-04-24 user-confirmed: 네임드 / 네임드 플레이어 별도 CID, seed 유지",
    "1003122": "2026-04-24 user-confirmed: 핵무기도 만들어 드릴까요? / 핵무기도 만들어 드림 2개 CID",
    "1005013": "2026-04-24 user-confirmed: 생호라비는 생활비 오탈자, 병합 후 seed 유지",
}
EXCLUDE_NOTES = {
    "1003371": "2026-04-24 user-confirmed: 카니발 로사는 담당 작품 아님, CID seed 제외",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply local account CID split manual decisions.")
    add_write_flags(parser)
    return parser.parse_args()


def apply_decision_csv(*, live_write: bool) -> dict[str, int]:
    decision_df = pd.read_csv(ACCOUNT_DECISION_CSV, dtype=str).fillna("")
    approve_mask = decision_df["account_저작권코드"].map(normalize_text).isin(APPROVE_NOTES)
    exclude_mask = decision_df["account_저작권코드"].map(normalize_text).isin(EXCLUDE_NOTES)

    if int(approve_mask.sum()):
        decision_df.loc[approve_mask, "수동_메모"] = decision_df.loc[approve_mask, "account_저작권코드"].map(
            lambda code: APPROVE_NOTES.get(normalize_text(code), "")
        )
        decision_df.loc[approve_mask, "처리완료(Y/N)"] = "Y"

    if int(exclude_mask.sum()):
        decision_df.loc[exclude_mask, "수동_action"] = "담당제외"
        decision_df.loc[exclude_mask, "수동_메모"] = decision_df.loc[exclude_mask, "account_저작권코드"].map(
            lambda code: EXCLUDE_NOTES.get(normalize_text(code), "")
        )
        decision_df.loc[exclude_mask, "처리완료(Y/N)"] = "Y"

    if live_write:
        decision_df.to_csv(ACCOUNT_DECISION_CSV, index=False, encoding="utf-8-sig")
    return {
        "decision_approved_rows": int(approve_mask.sum()),
        "decision_excluded_rows": int(exclude_mask.sum()),
    }


def apply_review_csvs(*, live_write: bool) -> dict[str, int]:
    stats = {
        "rights_approved_rows": 0,
        "work_approved_rows": 0,
    }
    if RIGHTS_REVIEW_CSV.exists():
        rights_df = pd.read_csv(RIGHTS_REVIEW_CSV, dtype=str).fillna("")
        rights_mask = rights_df["account_저작권코드"].map(normalize_text).isin(APPROVE_NOTES)
        if int(rights_mask.sum()):
            rights_df.loc[rights_mask, "수동_메모"] = rights_df.loc[rights_mask, "account_저작권코드"].map(
                lambda code: APPROVE_NOTES.get(normalize_text(code), "")
            )
            rights_df.loc[rights_mask, "처리완료(Y/N)"] = "Y"
        if live_write:
            rights_df.to_csv(RIGHTS_REVIEW_CSV, index=False, encoding="utf-8-sig")
        stats["rights_approved_rows"] = int(rights_mask.sum())

    if WORK_REVIEW_CSV.exists():
        work_df = pd.read_csv(WORK_REVIEW_CSV, dtype=str).fillna("")
        work_mask = work_df["account_저작권코드"].map(normalize_text).isin(APPROVE_NOTES)
        if int(work_mask.sum()):
            work_df.loc[work_mask, "수동_유지(Y/N)"] = "Y"
            work_df.loc[work_mask, "수동_메모"] = work_df.loc[work_mask, "account_저작권코드"].map(
                lambda code: APPROVE_NOTES.get(normalize_text(code), "")
            )
            work_df.loc[work_mask, "처리완료(Y/N)"] = "Y"
        if live_write:
            work_df.to_csv(WORK_REVIEW_CSV, index=False, encoding="utf-8-sig")
        stats["work_approved_rows"] = int(work_mask.sum())

    return stats


def main() -> None:
    args = parse_args()
    live_write = resolve_write_mode(args)
    output_paths = [
        path
        for path in (ACCOUNT_DECISION_CSV, RIGHTS_REVIEW_CSV, WORK_REVIEW_CSV)
        if Path(path).exists()
    ]
    backup_dir, before_hashes = (Path(""), {})
    if live_write:
        backup_dir, before_hashes = backup_files(output_paths, script_name=Path(__file__).stem)
    stats = {}
    stats.update(apply_decision_csv(live_write=live_write))
    stats.update(apply_review_csvs(live_write=live_write))
    receipt = write_receipt(
        args,
        script_name=Path(__file__).stem,
        live_write=live_write,
        output_paths=output_paths,
        backup_dir=backup_dir,
        before_hashes=before_hashes,
    )
    print("=== account CID split manual decisions applied ===")
    print(json.dumps({"manager": MANAGER, "mode": "write" if live_write else "dry_run", **stats, "receipt": str(receipt)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
