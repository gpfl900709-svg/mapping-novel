from __future__ import annotations

import json

import pandas as pd

from build_account_decision_queue import OUTPUT_CSV
from build_account_observation_bundle import MANAGER, normalize_text


DEFER_ACTION = "IPS_CID생성보류"
DEFER_NOTE = "2026-04-24 user-confirmed: 미래 용도 optional CID 후보라 현재 IPS CID 없어도 됨"


def main() -> None:
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

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print("=== account work review defer applied ===")
    print(
        json.dumps(
            {
                "manager": MANAGER,
                "deferred_rows": deferred_rows,
                "decision_csv": str(OUTPUT_CSV),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
