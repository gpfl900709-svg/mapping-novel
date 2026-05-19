from __future__ import annotations

import json

import pandas as pd

from build_account_decision_queue import OUTPUT_CSV
from build_account_observation_bundle import MANAGER, normalize_text


DEFERRED_AUTHOR_REVIEW_CODES = {
    "1005127": "2026-04-24 user-confirmed: 백락/승윤 신작1 작가 확정 보류",
}


def main() -> None:
    df = pd.read_csv(OUTPUT_CSV, dtype=str).fillna("")
    mask = (
        df["account_저작권코드"].map(normalize_text).isin(DEFERRED_AUTHOR_REVIEW_CODES)
        & df["action_제안"].eq("작가확인")
        & df["처리완료(Y/N)"].map(normalize_text).ne("Y")
    )

    deferred_rows = int(mask.sum())
    if deferred_rows:
        df.loc[mask, "수동_action"] = "작가확정보류"
        df.loc[mask, "수동_메모"] = df.loc[mask, "account_저작권코드"].map(
            lambda code: DEFERRED_AUTHOR_REVIEW_CODES.get(normalize_text(code), "")
        )
        df.loc[mask, "처리완료(Y/N)"] = "Y"

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print("=== account author review decisions applied ===")
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
