from __future__ import annotations

import json

import pandas as pd

from build_account_decision_queue import OUTPUT_CSV
from build_account_observation_bundle import MANAGER, normalize_text


APPROVAL_NOTE = "권장안 일괄 승인"


def main() -> None:
    df = pd.read_csv(OUTPUT_CSV, dtype=str).fillna("")
    mask = (
        df["action_제안"].eq("이름수정검토")
        & df["처리완료(Y/N)"].map(normalize_text).ne("Y")
    )

    approved_rows = int(mask.sum())
    if approved_rows:
        df.loc[mask, "수동_최종저작권명"] = df.loc[mask, "canonical_저작권명_제안"].map(normalize_text)
        df.loc[mask, "처리완료(Y/N)"] = "Y"
        existing_notes = df.loc[mask, "수동_메모"].map(normalize_text)
        df.loc[mask, "수동_메모"] = existing_notes.where(
            existing_notes.ne(""),
            APPROVAL_NOTE,
        )

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print("=== account name review bulk approval applied ===")
    print(
        json.dumps(
            {
                "manager": MANAGER,
                "approved_rows": approved_rows,
                "decision_csv": str(OUTPUT_CSV),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
