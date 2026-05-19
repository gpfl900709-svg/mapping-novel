from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from settlement_mapping import export_excel, map_settlement, read_excel_frames, read_excel_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_S2_PATH = PROJECT_ROOT / "콘텐츠+목록.xlsx"
DEFAULT_IPS_PATH = PROJECT_ROOT / "update_ips.xlsx"


def load_default_or_upload(default_path: Path, uploaded_file, *, concat_sheets: bool) -> pd.DataFrame:
    if uploaded_file is not None:
        return read_excel_frames(uploaded_file, concat_sheets=concat_sheets)
    if default_path.exists():
        return read_excel_path(default_path, concat_sheets=concat_sheets)
    return pd.DataFrame()


st.set_page_config(page_title="SIAANE 매핑", layout="wide")
st.title("판매채널 / IPS 콘텐츠 매핑")

with st.sidebar:
    st.subheader("입력 파일")
    s2_file = st.file_uploader("S2 콘텐츠 리스트", type=["xlsx"], key="s2")
    settlement_file = st.file_uploader("플랫폼 정산서", type=["xlsx"], key="settlement")
    ips_file = st.file_uploader("IPS 콘텐츠 목록", type=["xlsx"], key="ips")
    output_name = st.text_input(
        "저장 파일명",
        value=f"settlement_mapping_{datetime.now().strftime('%Y%m%d_%H%M')}",
    )

s2_df = load_default_or_upload(DEFAULT_S2_PATH, s2_file, concat_sheets=False)
ips_df = load_default_or_upload(DEFAULT_IPS_PATH, ips_file, concat_sheets=False)

left, right = st.columns(2)
with left:
    st.metric("S2 기본 파일", "있음" if DEFAULT_S2_PATH.exists() else "없음")
    st.caption(str(DEFAULT_S2_PATH))
with right:
    st.metric("IPS 기본 파일", "있음" if DEFAULT_IPS_PATH.exists() else "없음")
    st.caption(str(DEFAULT_IPS_PATH))

if settlement_file is None:
    st.info("플랫폼 정산서를 업로드하면 매핑을 실행할 수 있습니다.")
    st.stop()

settlement_df = read_excel_frames(settlement_file, concat_sheets=True)

if s2_df.empty:
    st.error("S2 콘텐츠 리스트가 없습니다. 기본 파일을 두거나 업로드해 주세요.")
    st.stop()
if ips_df.empty:
    st.error("IPS 콘텐츠 목록이 없습니다. 기본 파일을 두거나 업로드해 주세요.")
    st.stop()

if st.button("매핑 실행", type="primary"):
    try:
        mapping = map_settlement(s2_df, settlement_df, ips_df)
    except Exception as exc:
        st.exception(exc)
        st.stop()

    summary_values = dict(zip(mapping.summary["항목"], mapping.summary["값"]))
    cols = st.columns(4)
    cols[0].metric("정산서 행", summary_values.get("정산서 행 수", 0))
    cols[1].metric("S2+IPS", summary_values.get("S2+IPS 매칭 행 수", 0))
    cols[2].metric("검토필요", len(mapping.unmatched))
    cols[3].metric("중복키", len(mapping.duplicate_keys))

    st.dataframe(mapping.rows, use_container_width=True, height=420)

    if not mapping.unmatched.empty:
        with st.expander("검토필요 행"):
            st.dataframe(mapping.unmatched, use_container_width=True)

    if not mapping.duplicate_keys.empty:
        with st.expander("중복 정제키"):
            st.dataframe(mapping.duplicate_keys, use_container_width=True)

    file_name = output_name.strip() or "settlement_mapping"
    if not file_name.lower().endswith(".xlsx"):
        file_name += ".xlsx"
    st.download_button(
        "결과 엑셀 다운로드",
        data=export_excel(mapping),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
