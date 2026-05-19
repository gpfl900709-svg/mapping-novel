from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
ACCOUNT_DIR = ROOT / "SIAANE_v2" / "account"
if str(ACCOUNT_DIR) not in sys.path:
    sys.path.insert(0, str(ACCOUNT_DIR))

from build_account_observation_bundle import MANAGER, normalize_text  # noqa: E402


ACCOUNT_DECISION_CSV = ROOT / "SIAANE_v2" / "account" / "exports" / f"latest__account_decision_queue_{MANAGER}.csv"
RIGHTS_REVIEW_CSV = ROOT / "SIAANE_v2" / "crosswalk" / "exports" / f"latest__account_cid_split_rights_review_{MANAGER}.csv"
WORK_REVIEW_CSV = ROOT / "SIAANE_v2" / "crosswalk" / "exports" / f"latest__account_cid_split_work_review_{MANAGER}.csv"

DECISION_NOTE = "기본 CID 분해안 일괄 승인"
RIGHTS_NOTE = "권리행 기준 기본 CID 분해안 승인"
WORK_NOTE = "작품 seed 기준 기본 CID 분해안 승인"


def main() -> None:
    decision_df = pd.read_csv(ACCOUNT_DECISION_CSV, dtype=str).fillna("")
    rights_df = pd.read_csv(RIGHTS_REVIEW_CSV, dtype=str).fillna("")
    work_df = pd.read_csv(WORK_REVIEW_CSV, dtype=str).fillna("")

    decision_mask = (
        decision_df["action_제안"].eq("CID분해필요")
        & decision_df["처리완료(Y/N)"].map(normalize_text).ne("Y")
    )
    rights_mask = rights_df["처리완료(Y/N)"].map(normalize_text).ne("Y")
    work_mask = work_df["처리완료(Y/N)"].map(normalize_text).ne("Y")

    decision_approved_rows = int(decision_mask.sum())
    rights_approved_rows = int(rights_mask.sum())
    work_approved_rows = int(work_mask.sum())

    if decision_approved_rows:
        existing_notes = decision_df.loc[decision_mask, "수동_메모"].map(normalize_text)
        decision_df.loc[decision_mask, "수동_메모"] = existing_notes.where(existing_notes.ne(""), DECISION_NOTE)
        decision_df.loc[decision_mask, "처리완료(Y/N)"] = "Y"

    if rights_approved_rows:
        existing_notes = rights_df.loc[rights_mask, "수동_메모"].map(normalize_text)
        rights_df.loc[rights_mask, "수동_메모"] = existing_notes.where(existing_notes.ne(""), RIGHTS_NOTE)
        rights_df.loc[rights_mask, "처리완료(Y/N)"] = "Y"

    if work_approved_rows:
        existing_keep = work_df.loc[work_mask, "수동_유지(Y/N)"].map(normalize_text)
        existing_notes = work_df.loc[work_mask, "수동_메모"].map(normalize_text)
        work_df.loc[work_mask, "수동_유지(Y/N)"] = existing_keep.where(existing_keep.ne(""), "Y")
        work_df.loc[work_mask, "수동_메모"] = existing_notes.where(existing_notes.ne(""), WORK_NOTE)
        work_df.loc[work_mask, "처리완료(Y/N)"] = "Y"

    decision_df.to_csv(ACCOUNT_DECISION_CSV, index=False, encoding="utf-8-sig")
    rights_df.to_csv(RIGHTS_REVIEW_CSV, index=False, encoding="utf-8-sig")
    work_df.to_csv(WORK_REVIEW_CSV, index=False, encoding="utf-8-sig")

    print("=== account CID split bulk approval applied ===")
    print(
        json.dumps(
            {
                "manager": MANAGER,
                "decision_approved_rows": decision_approved_rows,
                "rights_approved_rows": rights_approved_rows,
                "work_approved_rows": work_approved_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
