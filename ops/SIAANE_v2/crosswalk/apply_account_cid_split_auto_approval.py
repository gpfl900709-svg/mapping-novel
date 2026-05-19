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

APPROVAL_NOTE = "2026-04-24 auto-approved: 작품별 CID seed 기본 분해 유지"
WORK_APPROVAL_NOTE = "2026-04-24 auto-approved: 작품 seed 유지"
DECISION_APPROVAL_NOTE = "2026-04-24 auto-approved: CID분해필요 기본 분해 유지"
AUTO_NOTE_TOKENS = (
    "기본 CID 분해안 승인",
    "auto-approved",
)
HOLD_CODES = {
    "1003122": "확인필요: 핵무기도 만들어 드릴까요/핵무기도 만들어 드림/외전 병합 여부",
    "1003371": "확인필요: 준장 로사 카니발 외전증보판 CID 분리 여부",
    "1005013": "확인필요: 플라스틱 생호라비/생활비 오타 병합 여부",
    "1005540": "확인필요: 네임드/네임드 플레이어 병합 여부",
}


def mark_note(series: pd.Series, note: str) -> pd.Series:
    existing = series.map(normalize_text)
    return existing.where(existing.ne(""), note)


def is_auto_note(value: object) -> bool:
    note = normalize_text(value)
    return any(token in note for token in AUTO_NOTE_TOKENS)


def main() -> None:
    decision_df = pd.read_csv(ACCOUNT_DECISION_CSV, dtype=str).fillna("")
    rights_df = pd.read_csv(RIGHTS_REVIEW_CSV, dtype=str).fillna("")
    work_df = pd.read_csv(WORK_REVIEW_CSV, dtype=str).fillna("")

    rights_pending_mask = rights_df["처리완료(Y/N)"].map(normalize_text).ne("Y")
    held_mask = rights_df["account_저작권코드"].map(normalize_text).isin(HOLD_CODES)
    held_work_mask = work_df["account_저작권코드"].map(normalize_text).isin(HOLD_CODES)
    held_work_auto_mask = held_work_mask & work_df["수동_메모"].map(is_auto_note)
    if int(held_work_auto_mask.sum()):
        work_df.loc[held_work_auto_mask, ["수동_유지(Y/N)", "수동_메모", "처리완료(Y/N)"]] = ""

    rights_approved_mask = rights_df["처리완료(Y/N)"].map(normalize_text).eq("Y")
    approve_codes = set(
        rights_df.loc[(rights_pending_mask & ~held_mask) | (rights_approved_mask & ~held_mask), "account_저작권코드"].map(
            normalize_text
        )
    )

    decision_mask = (
        decision_df["account_저작권코드"].map(normalize_text).isin(approve_codes)
        & decision_df["action_제안"].eq("CID분해필요")
        & decision_df["처리완료(Y/N)"].map(normalize_text).ne("Y")
    )
    rights_mask = rights_df["account_저작권코드"].map(normalize_text).isin(approve_codes) & rights_pending_mask
    work_mask = (
        work_df["account_저작권코드"].map(normalize_text).isin(approve_codes)
        & work_df["처리완료(Y/N)"].map(normalize_text).ne("Y")
    )

    if int(decision_mask.sum()):
        decision_df.loc[decision_mask, "수동_메모"] = mark_note(
            decision_df.loc[decision_mask, "수동_메모"],
            DECISION_APPROVAL_NOTE,
        )
        decision_df.loc[decision_mask, "처리완료(Y/N)"] = "Y"

    if int(rights_mask.sum()):
        rights_df.loc[rights_mask, "수동_메모"] = mark_note(
            rights_df.loc[rights_mask, "수동_메모"],
            APPROVAL_NOTE,
        )
        rights_df.loc[rights_mask, "처리완료(Y/N)"] = "Y"

    if int(work_mask.sum()):
        existing_keep = work_df.loc[work_mask, "수동_유지(Y/N)"].map(normalize_text)
        work_df.loc[work_mask, "수동_유지(Y/N)"] = existing_keep.where(existing_keep.ne(""), "Y")
        work_df.loc[work_mask, "수동_메모"] = mark_note(
            work_df.loc[work_mask, "수동_메모"],
            WORK_APPROVAL_NOTE,
        )
        work_df.loc[work_mask, "처리완료(Y/N)"] = "Y"

    decision_df.to_csv(ACCOUNT_DECISION_CSV, index=False, encoding="utf-8-sig")
    rights_df.to_csv(RIGHTS_REVIEW_CSV, index=False, encoding="utf-8-sig")
    work_df.to_csv(WORK_REVIEW_CSV, index=False, encoding="utf-8-sig")

    print("=== account CID split auto approval applied ===")
    print(
        json.dumps(
            {
                "manager": MANAGER,
                "approved_rights_rows": int(rights_mask.sum()),
                "approved_work_rows": int(work_mask.sum()),
                "approved_decision_rows": int(decision_mask.sum()),
                "held_codes": sorted(HOLD_CODES),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
