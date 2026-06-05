from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPTS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_ROOT.parents[1]
for path in (str(SCRIPTS_ROOT), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from ips_safety_contract import (
    NextAction,
    apply_sheet_upload_gate_fields,
    classify_sheet_uploadable_sales_channel_row,
    id_text,
    is_nonzero_contract_id,
    is_positive_numeric_id,
    text,
)
from kiss_payment_settlement import CONTRACT_ID_COLUMN, normalize_payment_contract_id_column, pick_payment_contract_id_column


DEFAULT_S2_LOOKUP = REPO_ROOT / "data" / "kiss_payment_settlement_s2_lookup.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify sales-channel content IDs against S2 payment lookup with nonzero contract IDs.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--s2-lookup", default=str(DEFAULT_S2_LOOKUP))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--id-column", default="sales_channel_content_id")
    parser.add_argument("--platform-column", default="input_platform")
    parser.add_argument("--title-column", default="input_title")
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [dict(item) for item in payload]
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            return [dict(item) for item in payload["rows"]]
        raise ValueError(f"Unsupported JSON shape: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_s2_lookup(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=object).fillna("")
    frame = normalize_payment_contract_id_column(frame)
    pick_payment_contract_id_column(frame, required=True)
    frame["판매채널콘텐츠ID"] = frame["판매채널콘텐츠ID"].map(id_text)
    frame[CONTRACT_ID_COLUMN] = frame[CONTRACT_ID_COLUMN].map(id_text)
    return frame[frame[CONTRACT_ID_COLUMN].map(is_nonzero_contract_id)].copy()


def verify_rows(
    rows: list[dict[str, Any]],
    s2: pd.DataFrame,
    *,
    id_column: str,
    platform_column: str,
    title_column: str,
) -> list[dict[str, Any]]:
    by_id = {id_text(row["판매채널콘텐츠ID"]): row for _, row in s2.iterrows()}
    verified: list[dict[str, Any]] = []
    for row in rows:
        output = dict(row)
        sales_channel_content_id = id_text(row.get(id_column))
        output["s2_payment_contract_status"] = "invalid_id"
        output["s2_통합계약ID"] = ""
        output["s2_판매채널명"] = ""
        output["s2_콘텐츠명"] = ""
        if is_positive_numeric_id(sales_channel_content_id):
            matched = by_id.get(sales_channel_content_id)
            if matched is not None:
                output["s2_payment_contract_status"] = "contract_nonzero"
                output["s2_통합계약ID"] = id_text(matched.get(CONTRACT_ID_COLUMN))
                output["s2_판매채널명"] = text(matched.get("판매채널명"))
                output["s2_콘텐츠명"] = text(matched.get("콘텐츠명"))
            else:
                output["s2_payment_contract_status"] = "missing_or_contract_zero"
        if text(output.get("next_action")) == NextAction.PASTE_SALES_CHANNEL_CONTENT_ID:
            decision = classify_sheet_uploadable_sales_channel_row(output, value_column=id_column)
            output.update(apply_sheet_upload_gate_fields(output, decision))
            if not decision.allowed:
                output["next_action"] = NextAction.CHECK_SOURCE_CONTRACT_ID
        verified.append(output)
    return verified


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    rows = load_rows(Path(args.input))
    s2 = load_s2_lookup(Path(args.s2_lookup))
    verified = verify_rows(
        rows,
        s2,
        id_column=args.id_column,
        platform_column=args.platform_column,
        title_column=args.title_column,
    )
    output = Path(args.output)
    write_csv(output, verified)
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input": args.input,
        "s2_lookup": args.s2_lookup,
        "output": str(output),
        "rows": len(verified),
        "status_counts": dict(Counter(text(row.get("s2_payment_contract_status")) for row in verified)),
    }
    summary_path = Path(args.summary) if args.summary else output.with_suffix(".summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
