from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from cleaning_rules import text


MATCH_OK = "matched"
MATCH_NONE = "no_match"
MATCH_AMBIGUOUS = "ambiguous"
MATCH_BLANK = "blank_key"

DETAIL_SHEET_NAME = "검토필요"
MAX_TITLE_LIST_ITEMS = 8
MAX_ROW_LIST_ITEMS = 20
LIST_SEPARATOR = " | "

WORK_ORDER_COLUMNS = [
    "작업상태",
    "담당PD",
    "S2_담당자명",
    "S2_담당부서명",
    "S2_담당자_근거",
    "S2 판매채널",
    "S2 검색어",
    "정제_상품명",
    "정산서_대표콘텐츠명",
    "S2_미매핑상세사유",
    "권장액션",
    "정산서_콘텐츠명목록",
    "정산서_콘텐츠명_고유수",
    "목록축약여부",
    "상세확인시트",
    "정산서 행 수",
    "플랫폼",
    "파일목록",
    "원본행번호목록",
    "엑셀행번호목록",
    "S2_매칭상태",
    "검토필요사유",
    "S2_판매채널콘텐츠ID",
    "S2_콘텐츠ID",
    "S2_콘텐츠명",
    "S2_후보수",
    "S2_후보ID목록",
    "S2_후보콘텐츠명목록",
    "S2_미매핑근거",
    "S2_정산정보누락_후보수",
    "S2_정산정보누락_판매채널콘텐츠ID목록",
    "S2_정산정보누락_콘텐츠ID목록",
    "청구정산_후보수",
    "청구정산마스터ID목록",
    "청구정산_계약ID목록",
    "S2_판매채널콘텐츠_후보수",
    "S2_판매채널콘텐츠_판매채널콘텐츠ID목록",
    "S2_판매채널콘텐츠_콘텐츠ID목록",
    "PD 확인 메모",
]

WORK_ORDER_SOURCE_COLUMNS = [
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

WORK_ORDER_GROUP_COLUMNS = [
    "S2 판매채널",
    "플랫폼",
    "정제_상품명",
    "S2_매칭상태",
    "검토필요사유",
    "S2_후보ID목록",
    "S2_후보콘텐츠명목록",
    "S2_담당자명",
    "S2_담당부서명",
    "S2_담당자_근거",
    "S2_분리사유",
    "S2_미매핑상세사유",
    "S2_미매핑근거",
    "S2_권장조치",
    "S2_정산정보누락_판매채널콘텐츠ID목록",
    "청구정산마스터ID목록",
    "S2_판매채널콘텐츠_판매채널콘텐츠ID목록",
]


def build_pd_work_order_frame_from_mapping_rows(
    rows: pd.DataFrame,
    *,
    source_name: str = "",
    s2_sales_channel: str = "",
    platform: str = "",
    detail_sheet_name: str = DETAIL_SHEET_NAME,
) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame(columns=WORK_ORDER_COLUMNS)

    prepared = _ensure_columns(rows, WORK_ORDER_SOURCE_COLUMNS)
    _fill_default(prepared, "파일", source_name)
    _fill_default(prepared, "S2 판매채널", s2_sales_channel)
    _fill_default(prepared, "플랫폼", platform)

    review_rows = prepared[prepared["검토필요(Y/N)"].map(text).eq("Y")].copy()
    if review_rows.empty:
        return pd.DataFrame(columns=WORK_ORDER_COLUMNS)

    grouped_rows: list[dict[str, Any]] = []
    for _, group in review_rows.groupby(WORK_ORDER_GROUP_COLUMNS, dropna=False, sort=False):
        first = group.iloc[0]
        title_list = _join_unique_limited(group["정산서_콘텐츠명"], max_items=MAX_TITLE_LIST_ITEMS)
        row_numbers = _join_unique_limited(group["정산서_원본행번호"], max_items=MAX_ROW_LIST_ITEMS)
        sheet_rows = _join_unique_limited(group["정산서원본_source_row"], max_items=MAX_ROW_LIST_ITEMS)
        unique_titles = _unique_texts(group["정산서_콘텐츠명"])
        grouped_rows.append(
            {
                "작업상태": "대기",
                "담당PD": first["S2_담당자명"],
                "S2_담당자명": first["S2_담당자명"],
                "S2_담당부서명": first["S2_담당부서명"],
                "S2_담당자_근거": first["S2_담당자_근거"],
                "S2 판매채널": first["S2 판매채널"],
                "S2 검색어": first["정제_상품명"],
                "플랫폼": first["플랫폼"],
                "정제_상품명": first["정제_상품명"],
                "정산서_대표콘텐츠명": first["정산서_콘텐츠명"],
                "정산서_콘텐츠명목록": title_list,
                "정산서_콘텐츠명_고유수": len(unique_titles),
                "목록축약여부": "Y" if len(unique_titles) > MAX_TITLE_LIST_ITEMS else "N",
                "상세확인시트": detail_sheet_name,
                "정산서 행 수": len(group),
                "파일목록": _join_unique_limited(group["파일"], max_items=MAX_TITLE_LIST_ITEMS),
                "원본행번호목록": row_numbers,
                "엑셀행번호목록": sheet_rows,
                "S2_매칭상태": first["S2_매칭상태"],
                "권장액션": _suggest_action(first),
                "검토필요사유": first["검토필요사유"],
                "S2_판매채널콘텐츠ID": first["S2_판매채널콘텐츠ID"],
                "S2_콘텐츠ID": first["S2_콘텐츠ID"],
                "S2_콘텐츠명": first["S2_콘텐츠명"],
                "S2_후보수": first["S2_후보수"],
                "S2_후보ID목록": first["S2_후보ID목록"],
                "S2_후보콘텐츠명목록": first["S2_후보콘텐츠명목록"],
                "S2_미매핑상세사유": first["S2_미매핑상세사유"],
                "S2_미매핑근거": first["S2_미매핑근거"],
                "S2_정산정보누락_후보수": first["S2_정산정보누락_후보수"],
                "S2_정산정보누락_판매채널콘텐츠ID목록": first["S2_정산정보누락_판매채널콘텐츠ID목록"],
                "S2_정산정보누락_콘텐츠ID목록": first["S2_정산정보누락_콘텐츠ID목록"],
                "청구정산_후보수": first["청구정산_후보수"],
                "청구정산마스터ID목록": first["청구정산마스터ID목록"],
                "청구정산_계약ID목록": first["청구정산_계약ID목록"],
                "S2_판매채널콘텐츠_후보수": first["S2_판매채널콘텐츠_후보수"],
                "S2_판매채널콘텐츠_판매채널콘텐츠ID목록": first["S2_판매채널콘텐츠_판매채널콘텐츠ID목록"],
                "S2_판매채널콘텐츠_콘텐츠ID목록": first["S2_판매채널콘텐츠_콘텐츠ID목록"],
                "PD 확인 메모": "",
            }
        )

    return pd.DataFrame(grouped_rows, columns=WORK_ORDER_COLUMNS)


def _ensure_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = ""
    return result[columns]


def _fill_default(frame: pd.DataFrame, column: str, value: str) -> None:
    value_text = text(value)
    if not value_text or column not in frame.columns:
        return
    empty = frame[column].map(text).eq("")
    frame.loc[empty, column] = value_text


def _unique_texts(values: Iterable[Any]) -> list[str]:
    seen: list[str] = []
    for value in values:
        value_text = text(value)
        if value_text and value_text not in seen:
            seen.append(value_text)
    return seen


def _join_unique_limited(values: Iterable[Any], *, max_items: int) -> str:
    seen = _unique_texts(values)
    if not seen:
        return ""
    shown = seen[:max_items]
    suffix = ""
    remaining = len(seen) - len(shown)
    if remaining > 0:
        suffix = f"{LIST_SEPARATOR}... 외 {remaining}개"
    return LIST_SEPARATOR.join(shown) + suffix


def _suggest_action(row: pd.Series) -> str:
    detailed_action = text(row.get("S2_권장조치"))
    if detailed_action:
        return detailed_action
    reason = text(row.get("검토필요사유"))
    status = text(row.get("S2_매칭상태"))
    if "청구정산 후보" in reason:
        return "청구정산 건인지 확인하고 지급정산 매핑 대상 제외/전환 여부 판단"
    if "S2 정산정보 누락 건 등재" in reason:
        return "S2 정산정보 누락 건 메뉴에서 확인 후 지급정산 보강 또는 제외 요청"
    if status == MATCH_NONE:
        return "S2 판매채널에서 정제 제목으로 검색, 없으면 판매채널콘텐츠ID 생성/보강 요청"
    if status == MATCH_AMBIGUOUS:
        return "S2 후보 ID 목록 중 실제 작품 선택"
    if status == MATCH_BLANK:
        return "정산서 원본 상품명 확인 후 제목 정제 규칙 또는 파일 헤더 보정"
    if status != MATCH_OK:
        return "매칭 상태 확인"
    return "검토필요사유 확인"
