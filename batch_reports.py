from __future__ import annotations

from typing import Any

import pandas as pd

from cleaning_rules import text
from work_order_reports import WORK_ORDER_COLUMNS, build_pd_work_order_frame_from_mapping_rows


COMBINED_REPORT_COLUMNS = [
    "파일",
    "S2 판매채널",
    "플랫폼",
    "정산서_원본행번호",
    "정산서원본_source_row",
    "정산서_콘텐츠명",
    "정제_상품명",
    "S2_매칭상태",
    "S2_판매채널콘텐츠ID",
    "S2_콘텐츠ID",
    "S2_콘텐츠명",
    "S2_담당자명",
    "S2_담당부서명",
    "S2_담당자_근거",
    "S2_후보수",
    "S2_후보ID목록",
    "S2_후보콘텐츠명목록",
    "S2_정산정보누락_후보수",
    "S2_정산정보누락_판매채널콘텐츠ID목록",
    "S2_정산정보누락_콘텐츠ID목록",
    "청구정산_후보수",
    "청구정산마스터ID목록",
    "청구정산_계약ID목록",
    "S2_판매채널콘텐츠_후보수",
    "S2_판매채널콘텐츠_판매채널콘텐츠ID목록",
    "S2_판매채널콘텐츠_콘텐츠ID목록",
    "S2_분리사유",
    "S2_미매핑상세사유",
    "S2_미매핑근거",
    "S2_권장조치",
    "검토필요사유",
    "검토필요(Y/N)",
]

def build_combined_mapping_report_frame(results: list[dict[str, Any]]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for result in results:
        mapping = result.get("mapping")
        if text(result.get("status")) != "success" or mapping is None:
            continue
        rows = getattr(mapping, "rows", pd.DataFrame()).copy()
        if rows.empty:
            continue
        rows.insert(0, "플랫폼", text(result.get("platform")))
        rows.insert(0, "S2 판매채널", text(result.get("s2_sales_channel")))
        rows.insert(0, "파일", text(result.get("source_name")))
        frames.append(_ensure_columns(rows, COMBINED_REPORT_COLUMNS))

    if not frames:
        return pd.DataFrame(columns=COMBINED_REPORT_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    return _sort_combined_report(_ensure_columns(combined, COMBINED_REPORT_COLUMNS))


def build_pd_work_order_report_frame(results: list[dict[str, Any]]) -> pd.DataFrame:
    combined = build_combined_mapping_report_frame(results)
    return build_pd_work_order_report_frame_from_combined(combined)


def build_pd_work_order_report_frame_from_combined(combined: pd.DataFrame) -> pd.DataFrame:
    return build_pd_work_order_frame_from_mapping_rows(combined)


def _ensure_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = ""
    return result[columns]


def _sort_combined_report(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "S2_매칭상태" not in frame.columns:
        return frame
    return frame.sort_values("S2_매칭상태", ascending=False, kind="mergesort").reset_index(drop=True)
