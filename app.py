from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from cleaning_rules import text
from mapping_core import build_mapping
from matching_rules import detect_s2_sales_channel, filter_s2_by_sales_channel, s2_sales_channel_to_platform
from public_mapping import (
    PublicMappingSecurityError,
    build_public_zip,
    export_public_mapping,
    load_public_reference,
    project_public_mapping_result,
    upload_signature,
    validate_xlsx_archive,
)
from settlement_adapters import (
    adapter_blocking_messages,
    adapter_warning_messages,
    normalize_settlement,
)


REPO_ROOT = Path(__file__).resolve().parent
PUBLIC_REFERENCE_PATH = REPO_ROOT / "data" / "public_s2_mapping_reference.csv"
AUTO_CHANNEL = "엑셀 파일명으로 자동감지"
MAX_UPLOAD_FILES = 20
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_UPLOAD_BYTES_PER_RUN = 200 * 1024 * 1024
MAX_MAPPING_ROWS_PER_FILE = 250_000
MAX_MAPPING_ROWS_PER_RUN = 500_000


def safe_output_name(source_name: str) -> str:
    stem = Path(source_name).stem
    safe = "".join(char if char.isalnum() or char in (" ", "-", "_", "(", ")") else "_" for char in stem)
    return f"{safe.strip() or 'mapping'}_매핑.xlsx"


def resolve_channel(source_name: str, selected_channel: str) -> tuple[str, str]:
    if selected_channel != AUTO_CHANNEL:
        platform = s2_sales_channel_to_platform().get(selected_channel, "")
        if not platform:
            raise ValueError(f"판매채널에 대응하는 플랫폼이 없습니다: {selected_channel}")
        return selected_channel, platform
    detected = detect_s2_sales_channel(source_name)
    if detected is None:
        raise ValueError("파일명에서 S2 판매채널을 찾지 못했습니다. 판매채널을 직접 선택해 주세요.")
    return detected.sales_channel, detected.platform


@st.cache_data(show_spinner=False)
def cached_public_reference(path: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    return load_public_reference(path)


class RunBudgetExceeded(ValueError):
    pass


def process_upload(
    uploaded_file: object,
    selected_channel: str,
    reference: pd.DataFrame,
    *,
    remaining_rows: int,
) -> dict[str, object]:
    source_name = text(getattr(uploaded_file, "name", "")) or "uploaded.xlsx"
    payload = uploaded_file.getvalue()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError(f"파일 크기가 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB 제한을 넘었습니다.")
    validate_xlsx_archive(payload)
    channel, platform = resolve_channel(source_name, selected_channel)
    normalized = normalize_settlement(io.BytesIO(payload), platform=platform, source_name=source_name)
    blocking = adapter_blocking_messages(normalized)
    if blocking:
        raise ValueError(" | ".join(blocking))
    feed = normalized.to_mapping_feed().loc[:, ["상품명"]].copy()
    if len(feed) > MAX_MAPPING_ROWS_PER_FILE:
        raise ValueError(f"매핑 입력 행이 {MAX_MAPPING_ROWS_PER_FILE:,}행 제한을 넘었습니다.")
    if len(feed) > remaining_rows:
        raise RunBudgetExceeded(f"1회 총 매핑 행이 {MAX_MAPPING_ROWS_PER_RUN:,}행 제한을 넘었습니다.")
    channel_reference = filter_s2_by_sales_channel(
        reference,
        sales_channel=channel,
        source_name=source_name,
    )
    mapping = build_mapping(channel_reference.frame, feed, None)
    public_mapping = project_public_mapping_result(mapping)
    output = export_public_mapping(public_mapping)
    summary = dict(zip(public_mapping.summary["항목"], public_mapping.summary["값"]))
    return {
        "source_name": source_name,
        "channel": channel,
        "platform": platform,
        "rows": public_mapping.rows,
        "output_name": safe_output_name(source_name),
        "output": output,
        "warnings": adapter_warning_messages(normalized),
        "input_rows": len(feed),
        "matched": int(summary.get("S2 matched", 0)),
        "review": int(summary.get("검토필요 행 수", 0)),
    }


st.set_page_config(page_title="S2 소설 매핑", layout="wide")
st.title("S2 소설 매핑")
st.caption("공개 안전 모드 · 제목/채널 기반 매핑만 수행하며 담당자·부서·정산 운영정보는 처리하지 않습니다.")

if not PUBLIC_REFERENCE_PATH.is_file():
    st.error("공개용 S2 기준 파일이 없습니다. 관리자가 sanitized reference를 생성해야 합니다.")
    st.stop()

try:
    public_reference = cached_public_reference(
        str(PUBLIC_REFERENCE_PATH),
        PUBLIC_REFERENCE_PATH.stat().st_mtime_ns,
    )
except PublicMappingSecurityError as exc:
    st.error("공개용 S2 기준이 보안 검사를 통과하지 못했습니다.")
    st.code(str(exc))
    st.stop()

with st.sidebar:
    st.subheader("공개 안전 경계")
    st.metric("S2 기준 행", f"{len(public_reference):,}")
    st.caption("외부 시스템 쓰기, 원본 첨부, PD 작업지시, 내부 guard는 이 앱에 없습니다.")

channels = sorted(s2_sales_channel_to_platform())
selected_channel = st.selectbox("S2 판매채널", [AUTO_CHANNEL, *channels])
uploaded_files = st.file_uploader(
    "플랫폼 정산서 엑셀",
    type=["xlsx"],
    accept_multiple_files=True,
    help="파일명 자동감지가 실패하면 판매채널을 직접 선택하세요.",
)

if len(uploaded_files) > MAX_UPLOAD_FILES:
    st.error(f"한 번에 최대 {MAX_UPLOAD_FILES}개 파일만 처리할 수 있습니다.")
    st.stop()

upload_payloads = [item.getvalue() for item in uploaded_files]
if sum(map(len, upload_payloads)) > MAX_UPLOAD_BYTES_PER_RUN:
    st.error(f"전체 업로드 크기가 {MAX_UPLOAD_BYTES_PER_RUN // (1024 * 1024)}MB 제한을 넘었습니다.")
    st.stop()

signature = upload_signature(
    selected_channel,
    (
        (text(getattr(item, "name", "")), payload)
        for item, payload in zip(uploaded_files, upload_payloads)
    ),
)

if st.button("안전 매핑 실행", type="primary", disabled=not uploaded_files):
    successes: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    with st.spinner("정산서 정규화와 제목 매핑을 수행하는 중..."):
        total_input_rows = 0
        for uploaded_file in uploaded_files:
            try:
                result = process_upload(
                    uploaded_file,
                    selected_channel,
                    public_reference,
                    remaining_rows=MAX_MAPPING_ROWS_PER_RUN - total_input_rows,
                )
                total_input_rows += int(result["input_rows"])
                successes.append(result)
            except RunBudgetExceeded as exc:
                failures.append(
                    {
                        "파일": text(getattr(uploaded_file, "name", "")),
                        "오류": f"{type(exc).__name__}: {exc}",
                    }
                )
                break
            except Exception as exc:
                failures.append(
                    {
                        "파일": text(getattr(uploaded_file, "name", "")),
                        "오류": f"{type(exc).__name__}: {exc}",
                    }
                )
    st.session_state["public_mapping_result"] = {
        "signature": signature,
        "successes": successes,
        "failures": failures,
    }

state = st.session_state.get("public_mapping_result")
if not isinstance(state, dict) or state.get("signature") != signature:
    st.stop()

successes = state.get("successes", [])
failures = state.get("failures", [])
summary_rows = [
    {
        "파일": result["source_name"],
        "판매채널": result["channel"],
        "플랫폼": result["platform"],
        "매칭": result["matched"],
        "검토필요": result["review"],
        "경고": " | ".join(result["warnings"]),
    }
    for result in successes
]
if summary_rows:
    st.subheader("처리 결과")
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
if failures:
    st.subheader("차단·실패")
    st.dataframe(pd.DataFrame(failures), use_container_width=True, hide_index=True)

if len(successes) == 1:
    result = successes[0]
    st.download_button(
        "안전 매핑 결과 다운로드",
        result["output"],
        file_name=result["output_name"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click="ignore",
    )
elif len(successes) > 1:
    archive = build_public_zip(
        (f"{index:02d}_{result['output_name']}", result["output"])
        for index, result in enumerate(successes, start=1)
    )
    st.download_button(
        "안전 매핑 결과 모두 받기",
        archive,
        file_name="public_mapping_results.zip",
        mime="application/zip",
        on_click="ignore",
    )
