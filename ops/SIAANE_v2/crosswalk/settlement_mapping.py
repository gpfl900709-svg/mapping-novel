from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


S2_TITLE_COL_CANDIDATES = ["콘텐츠명", "콘텐츠 제목", "Title", "ContentName", "제목"]
S2_ID_COL_CANDIDATES = ["판매채널콘텐츠ID", "콘텐츠ID", "ID", "ContentID"]
SETTLEMENT_TITLE_COL_CANDIDATES = [
    "컨텐츠",
    "타이틀",
    "작품명",
    "도서명",
    "작품 제목",
    "상품명",
    "이용상품명",
    "상품 제목",
    "ProductName",
    "Title",
    "제목",
    "컨텐츠명",
    "콘텐츠명",
    "시리즈명",
]
IPS_TITLE_COL_CANDIDATES = ["콘텐츠명", "콘텐츠 제목", "Title", "ContentName", "제목"]
IPS_ID_COL_CANDIDATES = ["콘텐츠ID", "판매채널콘텐츠ID", "ID", "ContentID"]

ANGLE_TITLE_PATTERNS = (
    re.compile(r"<([^<>]+)>"),
    re.compile(r"＜([^＜＞]+)＞"),
    re.compile(r"〈([^〈〉]+)〉"),
    re.compile(r"《([^《》]+)》"),
)


@dataclass
class MappingResult:
    rows: pd.DataFrame
    summary: pd.DataFrame
    unmatched: pd.DataFrame
    duplicate_keys: pd.DataFrame


def text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def pick_column(candidates: list[str], df: pd.DataFrame, label: str) -> str:
    for column in candidates:
        if column in df.columns:
            return column
    raise ValueError(f"{label} 컬럼을 찾지 못했습니다: {', '.join(candidates)}")


def normalize_key(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return f"{value.month}월{value.day}일".lower()

    raw = text(value)
    if not raw:
        return ""

    value_text = unicodedata.normalize("NFKC", raw)
    value_text = re.sub(r"\s*~[^~]+~\s*$", "", value_text)
    value_text = re.sub(r"\s+\d+부(?:\s*-\s*.*)?$", "", value_text)

    for exception in ("24/7", "실명마제", "라마대제"):
        if exception in value_text:
            return exception.lower()

    if re.fullmatch(r"\d{1,2}월\d{1,2}일", value_text):
        return value_text.lower()

    lowered = value_text.lower()
    lowered = re.sub(r"\s*\d+/\d+$", "", lowered)
    lowered = re.sub(r"\s*제\s*\d+[권화]", "", lowered)
    lowered = lowered.replace("Un-holyNight", "UnholyNight")
    lowered = re.sub(r"\([^)]*\)|\[[^\]]*\]|【[^】]*】|〖[^〗]*〗", "", lowered)

    for token in ("세트구매", "난세의 서 편", "초혼의 사자 편", "전설의 부활 편"):
        lowered = lowered.replace(token, "")

    lowered = unicodedata.normalize("NFKC", lowered)
    lowered = re.sub(r"\d+[권화부회]", "", lowered)
    for token in (
        "개정판 l",
        "개정판",
        "외전",
        "무삭제본",
        "무삭제판",
        "합본",
        "단행본",
        "시즌",
        "세트",
        "연재",
        "특별",
        "최종화",
        "완결",
        "2부",
        "무삭제",
        "완전판",
        "세개정판",
        "19세개정판",
    ):
        lowered = lowered.replace(token, "")
    lowered = re.sub(r"\d+", "", lowered).rstrip(".")
    lowered = re.sub(r"[\.\~\-–—!@#$%^&*_=+\\|/:;\"'’`<>?，｡､{}()\[\]]", "", lowered)
    lowered = re.sub(r"특별$", "", lowered)
    return "".join(lowered.split()).strip().lower()


def extract_ips_work_title(value: Any) -> tuple[str, str]:
    raw = text(value)
    if not raw:
        return "", "empty"

    normalized = unicodedata.normalize("NFKC", raw)
    for pattern in ANGLE_TITLE_PATTERNS:
        match = pattern.search(normalized)
        if match and text(match.group(1)):
            return text(match.group(1)), "angle_bracket"

    parts = [part.strip() for part in normalized.split("_") if part.strip()]
    if len(parts) >= 5 and normalize_key(parts[-1]) == normalize_key("확정"):
        legacy_title = "_".join(parts[:-4]).strip()
        if legacy_title:
            return legacy_title, "legacy_confirmed_suffix"

    return normalized, "raw"


def title_key(value: Any, *, ips_structured_name: bool = False) -> str:
    if ips_structured_name:
        title, _rule = extract_ips_work_title(value)
        return normalize_key(title)
    return normalize_key(value)


def read_excel_frames(source: Any, *, concat_sheets: bool = True) -> pd.DataFrame:
    sheets = pd.read_excel(source, sheet_name=None, dtype=object, engine="openpyxl")
    if not sheets:
        return pd.DataFrame()
    if concat_sheets:
        frames: list[pd.DataFrame] = []
        for sheet_name, frame in sheets.items():
            copied = frame.copy()
            copied["source_sheet"] = sheet_name
            frames.append(copied)
        return pd.concat(frames, ignore_index=True)
    return next(iter(sheets.values())).copy()


def read_excel_path(path: Path, *, concat_sheets: bool = True) -> pd.DataFrame:
    return read_excel_frames(path, concat_sheets=concat_sheets)


def _first_lookup(df: pd.DataFrame, key_col: str, value_col: str) -> dict[str, str]:
    valid = df[df[key_col].map(bool)].copy()
    valid = valid.drop_duplicates(key_col, keep="first")
    return dict(zip(valid[key_col], valid[value_col].map(text)))


def _duplicate_report(s2: pd.DataFrame, ips: pd.DataFrame, s2_title_col: str, ips_title_col: str) -> pd.DataFrame:
    reports: list[pd.DataFrame] = []
    for source_name, frame, title_col, key_col in (
        ("S2", s2, s2_title_col, "_s2_key"),
        ("IPS", ips, ips_title_col, "_ips_key"),
    ):
        grouped = (
            frame[frame[key_col].map(bool)]
            .groupby(key_col, dropna=False)
            .agg(
                중복행수=(title_col, "size"),
                원문목록=(title_col, lambda values: " | ".join(dict.fromkeys(text(v) for v in values if text(v)))),
            )
            .reset_index()
            .rename(columns={key_col: "정제키"})
        )
        grouped = grouped[grouped["중복행수"] > 1].copy()
        if grouped.empty:
            continue
        grouped.insert(0, "source", source_name)
        reports.append(grouped)
    if not reports:
        return pd.DataFrame(columns=["source", "정제키", "중복행수", "원문목록"])
    return pd.concat(reports, ignore_index=True)


def map_settlement(
    s2_df: pd.DataFrame,
    settlement_df: pd.DataFrame,
    ips_df: pd.DataFrame,
    *,
    s2_title_col: str | None = None,
    s2_id_col: str | None = None,
    settlement_title_col: str | None = None,
    ips_title_col: str | None = None,
    ips_id_col: str | None = None,
) -> MappingResult:
    s2_title_col = s2_title_col or pick_column(S2_TITLE_COL_CANDIDATES, s2_df, "S2 콘텐츠명")
    s2_id_col = s2_id_col or pick_column(S2_ID_COL_CANDIDATES, s2_df, "S2 콘텐츠ID")
    settlement_title_col = settlement_title_col or pick_column(
        SETTLEMENT_TITLE_COL_CANDIDATES,
        settlement_df,
        "정산서 상품명",
    )
    ips_title_col = ips_title_col or pick_column(IPS_TITLE_COL_CANDIDATES, ips_df, "IPS 콘텐츠명")
    ips_id_col = ips_id_col or pick_column(IPS_ID_COL_CANDIDATES, ips_df, "IPS 콘텐츠ID")

    s2 = s2_df.copy()
    settlement = settlement_df.copy()
    ips = ips_df.copy()

    s2["_s2_key"] = s2[s2_title_col].map(title_key)
    settlement["_settlement_key"] = settlement[settlement_title_col].map(title_key)
    extracted_titles = ips[ips_title_col].map(extract_ips_work_title)
    ips["_ips_extracted_title"] = extracted_titles.map(lambda item: item[0])
    ips["_ips_extract_rule"] = extracted_titles.map(lambda item: item[1])
    ips["_ips_key"] = ips["_ips_extracted_title"].map(normalize_key)

    s2_id_by_key = _first_lookup(s2, "_s2_key", s2_id_col)
    s2_title_by_key = _first_lookup(s2, "_s2_key", s2_title_col)
    ips_id_by_key = _first_lookup(ips, "_ips_key", ips_id_col)
    ips_name_by_key = _first_lookup(ips, "_ips_key", ips_title_col)
    ips_title_by_key = _first_lookup(ips, "_ips_key", "_ips_extracted_title")
    ips_rule_by_key = _first_lookup(ips, "_ips_key", "_ips_extract_rule")

    result = settlement_df.copy()
    result.insert(0, "정산서_콘텐츠명", settlement[settlement_title_col].map(text))
    result.insert(1, "정제_상품명", settlement["_settlement_key"])
    result["매핑_판매채널콘텐츠ID"] = settlement["_settlement_key"].map(s2_id_by_key).fillna("")
    result["S2_콘텐츠명"] = settlement["_settlement_key"].map(s2_title_by_key).fillna("")
    result["매핑_콘텐츠마스터ID"] = settlement["_settlement_key"].map(ips_id_by_key).fillna("")
    result["매핑_콘텐츠마스터명"] = settlement["_settlement_key"].map(ips_name_by_key).fillna("")
    result["IPS_추출작품명"] = settlement["_settlement_key"].map(ips_title_by_key).fillna("")
    result["IPS_작품명추출방식"] = settlement["_settlement_key"].map(ips_rule_by_key).fillna("")

    has_s2 = result["매핑_판매채널콘텐츠ID"].map(bool)
    has_ips = result["매핑_콘텐츠마스터ID"].map(bool)
    result["매핑상태"] = "미매핑"
    result.loc[has_s2 & has_ips, "매핑상태"] = "S2+IPS"
    result.loc[has_s2 & ~has_ips, "매핑상태"] = "S2만"
    result.loc[~has_s2 & has_ips, "매핑상태"] = "IPS만"

    duplicate_keys = _duplicate_report(s2, ips, s2_title_col, ips_title_col)
    duplicate_key_set = set(duplicate_keys["정제키"].map(text))
    result["검토필요사유"] = ""
    result.loc[result["정제_상품명"].isin(duplicate_key_set), "검토필요사유"] = "중복 정제키"
    result.loc[result["매핑상태"].eq("미매핑"), "검토필요사유"] = "S2/IPS 모두 미매핑"
    result.loc[result["매핑상태"].eq("S2만"), "검토필요사유"] = "IPS 미매핑"
    result.loc[result["매핑상태"].eq("IPS만"), "검토필요사유"] = "S2 미매핑"

    summary = pd.DataFrame(
        [
            ("정산서 행 수", len(result)),
            ("S2 매칭 행 수", int(has_s2.sum())),
            ("IPS 매칭 행 수", int(has_ips.sum())),
            ("S2+IPS 매칭 행 수", int((has_s2 & has_ips).sum())),
            ("S2만 매칭 행 수", int((has_s2 & ~has_ips).sum())),
            ("IPS만 매칭 행 수", int((~has_s2 & has_ips).sum())),
            ("미매핑 행 수", int((~has_s2 & ~has_ips).sum())),
            ("S2 중복 정제키 수", int((duplicate_keys["source"] == "S2").sum()) if not duplicate_keys.empty else 0),
            ("IPS 중복 정제키 수", int((duplicate_keys["source"] == "IPS").sum()) if not duplicate_keys.empty else 0),
        ],
        columns=["항목", "값"],
    )
    unmatched = result[result["매핑상태"].ne("S2+IPS")].copy()
    return MappingResult(rows=result, summary=summary, unmatched=unmatched, duplicate_keys=duplicate_keys)


def export_excel(mapping: MappingResult) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        mapping.summary.to_excel(writer, sheet_name="요약", index=False)
        mapping.rows.to_excel(writer, sheet_name="매핑결과", index=False)
        mapping.unmatched.to_excel(writer, sheet_name="검토필요", index=False)
        mapping.duplicate_keys.to_excel(writer, sheet_name="중복정제키", index=False)

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                max_length = max(len(text(cell.value)) for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 10), 60)
    return buffer.getvalue()
