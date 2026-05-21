from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cleaning_rules import clean_title


SHEET_ID = "1jG0Q6LKzJ_q2VqdqtoDHSEwl8hfOEUrxRuxXq7KSazY"
SHEET_GID = "1569459807"
DEFAULT_SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"

DATA_DIR = Path("data")
S2_PAYMENT_PATH = DATA_DIR / "kiss_payment_settlement_s2_lookup.csv"
S2_SALES_CHANNEL_PATH = DATA_DIR / "s2_sales_channel_content_lookup.csv"
S2_MISSING_PATH = DATA_DIR / "s2_payment_missing_lookup.csv"
S2_BILLING_PATH = DATA_DIR / "s2_billing_settlement_lookup.csv"

SHEET_COLUMNS = (
    "S2 판매채널",
    "정제_상품명",
    "정산서_대표콘텐츠명",
    "S2_미매핑상세사유",
    "S2_판매채널콘텐츠ID",
    "담당자(없을 시 공란)",
    "비고",
)
ID_COLUMN_CANDIDATES = ("S2_판매채널콘텐츠ID", "생성 ID")
OTHER_PAYMENT_ACTION = (
    "현재 S2 판매채널 지급정산은 없음. 타채널 ID 입력 금지. "
    "IPS 정산정보 source 통합 계약 ID 확인 후 판매채널 추가 가능/계약·정산 연결 선행 여부 판단"
)


@dataclass(frozen=True)
class LookupBundle:
    payment: pd.DataFrame
    sales_channel: pd.DataFrame
    missing: pd.DataFrame
    billing: pd.DataFrame


def text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def add_key(frame: pd.DataFrame, source_col: str) -> pd.DataFrame:
    if frame.empty or source_col not in frame.columns:
        return frame.copy()
    out = frame.copy()
    out["_triage_key"] = out[source_col].map(clean_title)
    return out


def read_sheet(input_value: str) -> pd.DataFrame:
    source = input_value or DEFAULT_SHEET_CSV_URL
    if source.startswith("http://") or source.startswith("https://"):
        with urlopen(source, timeout=30) as response:
            payload = response.read()
        return pd.read_csv(io.BytesIO(payload), dtype=str).fillna("")

    path = Path(source)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, dtype=str).fillna("")
    return pd.read_csv(path, dtype=str).fillna("")


def load_lookups() -> LookupBundle:
    payment = add_key(read_table(S2_PAYMENT_PATH), "콘텐츠명")
    sales_channel = add_key(read_table(S2_SALES_CHANNEL_PATH), "콘텐츠명")
    missing = add_key(read_table(S2_MISSING_PATH), "콘텐츠명")
    billing = add_key(read_table(S2_BILLING_PATH), "대표콘텐츠명")
    return LookupBundle(payment=payment, sales_channel=sales_channel, missing=missing, billing=billing)


def unique_join(values: Any, limit: int = 8) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
        if len(out) >= limit:
            break
    return " | ".join(out)


def key_candidates(row: pd.Series) -> list[str]:
    raw_values = [
        text(row.get("정제_상품명")),
        text(row.get("정산서_대표콘텐츠명")),
        text(row.get("미매핑_콘텐츠마스터명")),
    ]
    candidates: list[str] = []
    for value in raw_values:
        for candidate in (value, clean_title(value)):
            cleaned = text(candidate)
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)
    return candidates


def sheet_id_column(sheet: pd.DataFrame) -> str:
    for column in ID_COLUMN_CANDIDATES:
        if column in sheet.columns:
            return column
    raise ValueError(f"sheet must contain one of {ID_COLUMN_CANDIDATES}. columns={list(sheet.columns)}")


def filter_channel(frame: pd.DataFrame, channel: str) -> pd.DataFrame:
    if frame.empty or "판매채널명" not in frame.columns or not channel:
        return frame
    return frame.loc[frame["판매채널명"].map(text).eq(channel)].reset_index(drop=True)


def known_sales_channels(lookups: LookupBundle) -> set[str]:
    channels: set[str] = set()
    for frame in (lookups.payment, lookups.sales_channel, lookups.missing, lookups.billing):
        if frame.empty or "판매채널명" not in frame.columns:
            continue
        channels.update(value for value in frame["판매채널명"].map(text) if value)
    return channels


def normalize_sales_channel(value: Any, channels: set[str]) -> str:
    raw = text(value)
    if raw in channels:
        return raw
    without_trailing_code = re.sub(r"\(\d{6,}\)$", "", raw).strip()
    if without_trailing_code in channels:
        return without_trailing_code
    return raw


def exact_matches(frame: pd.DataFrame, keys: list[str], channel: str = "") -> pd.DataFrame:
    if frame.empty or "_triage_key" not in frame.columns:
        return frame.iloc[0:0].copy()
    scoped = filter_channel(frame, channel)
    return scoped.loc[scoped["_triage_key"].isin(keys)].reset_index(drop=True)


def fuzzy_top(frame: pd.DataFrame, keys: list[str], channel: str = "", limit: int = 5) -> str:
    if frame.empty or "_triage_key" not in frame.columns or not keys:
        return ""
    scoped = filter_channel(frame, channel)
    if scoped.empty and channel:
        return ""
    if scoped.empty and not channel:
        scoped = frame
    best: list[tuple[float, str, str, str]] = []
    for _, candidate in scoped.iterrows():
        target_key = text(candidate.get("_triage_key"))
        if not target_key:
            continue
        score = max(SequenceMatcher(None, key, target_key).ratio() for key in keys)
        if score < 0.82:
            continue
        best.append(
            (
                score,
                text(candidate.get("판매채널명")),
                text(candidate.get("콘텐츠명") or candidate.get("대표콘텐츠명")),
                text(candidate.get("판매채널콘텐츠ID") or candidate.get("청구정산마스터ID")),
            )
        )
    best.sort(reverse=True, key=lambda item: item[0])
    return " || ".join(f"{score:.3f}:{channel}:{title}:{identifier}" for score, channel, title, identifier in best[:limit])


def exclude_channel(frame: pd.DataFrame, channel: str) -> pd.DataFrame:
    if frame.empty or "판매채널명" not in frame.columns or not channel:
        return frame
    return frame.loc[~frame["판매채널명"].map(text).eq(channel)].reset_index(drop=True)


def decide(
    payment: pd.DataFrame,
    sales_channel: pd.DataFrame,
    missing: pd.DataFrame,
    billing: pd.DataFrame,
    other_payment: pd.DataFrame,
    other_sales_channel: pd.DataFrame,
    fuzzy: str,
) -> tuple[str, str]:
    if len(payment):
        return "S2_지급정산_존재", "정제/채널 필터 또는 기존 시트 반영 누락을 확인하고 생성 ID 입력 후보로 검토"
    if len(missing):
        return "S2_정산정보누락", "S2 지급정산 설정/누락 사유 확인. 더미계약보다 S2 정산정보 보강 우선"
    if len(billing):
        return "S2_청구정산후보", "청구정산 계약/상태를 확인. 지급정산 전송용으로 바로 쓰지 않음"
    if len(sales_channel):
        return "S2_판매채널콘텐츠만_존재", "S2에는 판매채널콘텐츠가 있으나 지급정산 기준 없음. IPS/S2 정산 설정 확인"
    if len(other_payment):
        return "S2_타채널지급정산_존재", OTHER_PAYMENT_ACTION
    if len(other_sales_channel):
        return "S2_타채널판매채널콘텐츠만_존재", "타채널 판매채널콘텐츠만 있는 보조 증거. 현재 채널 지급정산 ID로 입력하지 않음"
    if fuzzy:
        return "정제규칙_검토필요", "fuzzy 후보를 보고 제목 정제 alias 또는 특수 규칙 추가 여부 판단"
    return "S2_부재_가능성", "IPS live lookup 후 없으면 admin/account에서 거래처/저작권자 근거 확인"


def build_report(sheet: pd.DataFrame, lookups: LookupBundle) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    id_column = sheet_id_column(sheet)
    channels = known_sales_channels(lookups)

    content_columns = [
        column
        for column in ("S2 판매채널", "정제_상품명", "정산서_대표콘텐츠명", "S2_미매핑상세사유", "담당자(없을 시 공란)", "비고")
        if column in sheet.columns
    ]
    has_content = pd.Series(False, index=sheet.index)
    for column in content_columns:
        has_content = has_content | sheet[column].map(text).ne("")
    blanks = sheet.loc[sheet[id_column].map(text).eq("") & has_content].copy()
    for idx, row in blanks.iterrows():
        raw_channel = text(row.get("S2 판매채널") or row.get("플랫폼"))
        channel = normalize_sales_channel(raw_channel, channels)
        keys = key_candidates(row)
        payment = exact_matches(lookups.payment, keys, channel)
        sales_channel = exact_matches(lookups.sales_channel, keys, channel)
        missing = exact_matches(lookups.missing, keys, channel)
        billing = exact_matches(lookups.billing, keys, channel)
        other_payment = exclude_channel(exact_matches(lookups.payment, keys), channel)
        other_sales_channel = exclude_channel(exact_matches(lookups.sales_channel, keys), channel)
        fuzzy = ""
        if not (len(payment) or len(sales_channel) or len(missing) or len(billing) or len(other_payment) or len(other_sales_channel)):
            fuzzy = fuzzy_top(lookups.payment, keys, channel) or fuzzy_top(lookups.sales_channel, keys, channel)
        decision, action = decide(payment, sales_channel, missing, billing, other_payment, other_sales_channel, fuzzy)

        rows.append(
            {
                "sheet_row_number": idx + 2,
                "S2 판매채널": channel,
                "S2 판매채널_원문": raw_channel if raw_channel != channel else "",
                "정제_상품명": text(row.get("정제_상품명")),
                "정산서_대표콘텐츠명": text(row.get("정산서_대표콘텐츠명")),
                "S2_미매핑상세사유": text(row.get("S2_미매핑상세사유")),
                "담당자(없을 시 공란)": text(row.get("담당자(없을 시 공란)")),
                "비고": text(row.get("비고")),
                "key_candidates": " | ".join(keys),
                "판정": decision,
                "권장_다음조치": action,
                "S2_지급정산_exact_count": len(payment),
                "S2_지급정산_ID목록": unique_join(payment.get("판매채널콘텐츠ID", [])),
                "S2_지급정산_콘텐츠명목록": unique_join(payment.get("콘텐츠명", [])),
                "S2_판매채널콘텐츠_exact_count": len(sales_channel),
                "S2_판매채널콘텐츠_ID목록": unique_join(sales_channel.get("판매채널콘텐츠ID", [])),
                "S2_판매채널콘텐츠_콘텐츠명목록": unique_join(sales_channel.get("콘텐츠명", [])),
                "S2_정산정보누락_count": len(missing),
                "S2_청구정산_count": len(billing),
                "S2_타채널지급정산_count": len(other_payment),
                "S2_타채널지급정산_채널목록": unique_join(other_payment.get("판매채널명", [])),
                "S2_타채널지급정산_ID목록": unique_join(other_payment.get("판매채널콘텐츠ID", [])),
                "S2_타채널지급정산_콘텐츠명목록": unique_join(other_payment.get("콘텐츠명", [])),
                "S2_타채널판매채널콘텐츠_count": len(other_sales_channel),
                "S2_타채널판매채널콘텐츠_채널목록": unique_join(other_sales_channel.get("판매채널명", [])),
                "S2_타채널판매채널콘텐츠_ID목록": unique_join(other_sales_channel.get("판매채널콘텐츠ID", [])),
                "S2_타채널판매채널콘텐츠_콘텐츠명목록": unique_join(other_sales_channel.get("콘텐츠명", [])),
                "S2_fuzzy_top": fuzzy,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key in seen:
                continue
            seen.add(key)
            fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Triage Google Sheet rows whose 생성 ID is blank.")
    parser.add_argument("--input", default="", help="Google Sheet CSV/XLSX path or export URL. Defaults to the configured Sheet CSV export.")
    parser.add_argument("--output", default="", help="Output CSV path.")
    parser.add_argument("--json-output", default="", help="Optional JSON summary path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sheet = read_sheet(args.input)
    lookups = load_lookups()
    rows = build_report(sheet, lookups)

    today = datetime.now().strftime("%Y-%m-%d")
    output = Path(args.output) if args.output else Path("doc") / today / "generated_id_gap_triage.csv"
    json_output = Path(args.json_output) if args.json_output else output.with_suffix(".json")
    write_csv(output, rows)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input": args.input or DEFAULT_SHEET_CSV_URL,
        "id_column": sheet_id_column(sheet),
        "output": str(output),
        "blank_id_rows": len(rows),
        "decision_counts": pd.Series([row["판정"] for row in rows]).value_counts().to_dict() if rows else {},
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
