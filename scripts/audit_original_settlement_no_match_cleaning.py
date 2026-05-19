from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cleaning_rules import clean_title, drop_disabled_rows, text
from mapping_core import MATCH_NONE, build_mapping, build_s2_mapping_reference
from matching_rules import (
    S2ChannelFilterResult,
    detect_s2_sales_channel,
    filter_s2_by_platform,
    filter_s2_by_sales_channel,
    platform_for_s2_sales_channel,
)
from s2_reference_guards import apply_missing_exclusions, load_s2_reference_guards
from settlement_adapters import (
    STANDARD_TITLE_COLUMN,
    adapter_blocking_messages,
    adapter_warning_messages,
    detect_platform,
    normalize_settlement,
    summarize_normalization,
)


DEFAULT_ROOT = r"\\172.16.10.120\소설사업부\판무팀_ssot\100_계산서_매출등록_자료"
DEFAULT_S2_LOOKUP = REPO_ROOT / "data" / "kiss_payment_settlement_s2_lookup.csv"
DEFAULT_MISSING_LOOKUP = REPO_ROOT / "data" / "s2_payment_missing_lookup.csv"
DEFAULT_BILLING_LOOKUP = REPO_ROOT / "data" / "s2_billing_settlement_lookup.csv"
DEFAULT_SERVICE_LOOKUP = REPO_ROOT / "data" / "s2_sales_channel_content_lookup.csv"
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}
EXCLUDED_FILENAME_TOKENS = (
    "_매핑",
    "판매채널콘텐츠",
    "판매채널 콘텐츠",
    "lookup",
    "LOOKUP",
)


@dataclass(frozen=True)
class LookupBundle:
    payment: pd.DataFrame
    missing: pd.DataFrame
    billing: pd.DataFrame
    service: pd.DataFrame
    payment_by_channel_key: dict[tuple[str, str], list[dict[str, Any]]]
    payment_by_key: dict[str, list[dict[str, Any]]]
    missing_by_channel_key: dict[tuple[str, str], list[dict[str, Any]]]
    billing_by_channel_key: dict[tuple[str, str], list[dict[str, Any]]]
    service_by_channel_key: dict[tuple[str, str], list[dict[str, Any]]]
    service_by_key: dict[str, list[dict[str, Any]]]


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=object).fillna("")


def add_audit_key(frame: pd.DataFrame, title_col: str, existing_key_col: str = "") -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    if existing_key_col and existing_key_col in out.columns:
        out["_audit_key"] = out[existing_key_col].map(text)
    elif title_col in out.columns:
        out["_audit_key"] = out[title_col].map(clean_title)
    else:
        out["_audit_key"] = ""
    return out


def index_by_channel_key(frame: pd.DataFrame) -> dict[tuple[str, str], list[dict[str, Any]]]:
    if frame.empty or "_audit_key" not in frame.columns or "판매채널명" not in frame.columns:
        return {}
    result: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in frame.to_dict("records"):
        key = text(record.get("_audit_key"))
        channel = text(record.get("판매채널명"))
        if not key:
            continue
        result.setdefault((channel, key), []).append(record)
    return result


def index_by_key(frame: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if frame.empty or "_audit_key" not in frame.columns:
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for record in frame.to_dict("records"):
        key = text(record.get("_audit_key"))
        if not key:
            continue
        result.setdefault(key, []).append(record)
    return result


def load_lookups(args: argparse.Namespace) -> tuple[pd.DataFrame, LookupBundle]:
    guards = load_s2_reference_guards(
        missing_path=args.missing_lookup,
        billing_path=args.billing_lookup,
        service_contents_path=args.service_lookup,
    )
    raw_s2 = read_csv(Path(args.s2_lookup))
    guard_filter = apply_missing_exclusions(raw_s2, guards)
    payment = add_audit_key(drop_disabled_rows(guard_filter.frame), "콘텐츠명")
    missing = add_audit_key(drop_disabled_rows(guards.missing), "콘텐츠명", "정제_콘텐츠명")
    billing = add_audit_key(drop_disabled_rows(guards.billing), "대표콘텐츠명", "정제_대표콘텐츠명")
    service = add_audit_key(drop_disabled_rows(guards.service_contents), "콘텐츠명", "정제_콘텐츠명")
    return payment, LookupBundle(
        payment=payment,
        missing=missing,
        billing=billing,
        service=service,
        payment_by_channel_key=index_by_channel_key(payment),
        payment_by_key=index_by_key(payment),
        missing_by_channel_key=index_by_channel_key(missing),
        billing_by_channel_key=index_by_channel_key(billing),
        service_by_channel_key=index_by_channel_key(service),
        service_by_key=index_by_key(service),
    )


def iter_original_settlement_files(
    root: Path,
    *,
    month_token: str,
    platform: str,
    limit: int,
) -> list[Path]:
    platform_filter = text(platform)
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith("~$"):
            continue
        if path.suffix.lower() not in EXCEL_SUFFIXES:
            continue
        path_text = str(path)
        name = path.name
        if month_token and month_token not in path_text:
            continue
        if platform_filter:
            try:
                rel_first = path.relative_to(root).parts[0]
            except ValueError:
                rel_first = ""
            if rel_first != platform_filter:
                continue
        if any(token in name for token in EXCLUDED_FILENAME_TOKENS):
            continue
        files.append(path)
    files.sort(
        key=lambda item: (
            "정산상세" in item.name,
            item.stat().st_mtime,
        ),
        reverse=True,
    )
    return files[:limit] if limit > 0 else files


def platform_from_path(path: Path, root: Path) -> str:
    try:
        first = path.relative_to(root).parts[0]
    except ValueError:
        first = ""
    return detect_platform(first) or detect_platform(path) or first


def filter_s2_for_file(path: Path, root: Path, s2_df: pd.DataFrame) -> tuple[str, str, S2ChannelFilterResult]:
    detection = detect_s2_sales_channel(path.name)
    if detection:
        result = filter_s2_by_sales_channel(s2_df, sales_channel=detection.sales_channel, source_name=str(path))
        return detection.platform, detection.sales_channel, result

    platform = platform_from_path(path, root)
    result = filter_s2_by_platform(s2_df, platform=platform, source_name=str(path))
    if len(result.matched_channels) == 1:
        channel = result.matched_channels[0]
    else:
        channel = " | ".join(result.matched_channels)
    if not platform and channel:
        platform = platform_for_s2_sales_channel(channel) or ""
    return platform, channel, result


def unique_join(values: Iterable[Any], limit: int = 10) -> str:
    seen: list[str] = []
    for value in values:
        value_text = text(value)
        if value_text and value_text not in seen:
            seen.append(value_text)
        if len(seen) >= limit:
            break
    return " | ".join(seen)


def scoped_exact(frame: pd.DataFrame, keys: set[str], channels: tuple[str, ...]) -> pd.DataFrame:
    if frame.empty or "_audit_key" not in frame.columns or not keys:
        return frame.iloc[0:0].copy()
    scoped = frame[frame["_audit_key"].map(text).isin(keys)].copy()
    if channels and "판매채널명" in scoped.columns:
        scoped = scoped[scoped["판매채널명"].map(text).isin(channels)]
    return scoped.reset_index(drop=True)


def other_channel_exact(frame: pd.DataFrame, keys: set[str], channels: tuple[str, ...]) -> pd.DataFrame:
    if frame.empty or "_audit_key" not in frame.columns or not keys:
        return frame.iloc[0:0].copy()
    scoped = frame[frame["_audit_key"].map(text).isin(keys)].copy()
    if channels and "판매채널명" in scoped.columns:
        scoped = scoped[~scoped["판매채널명"].map(text).isin(channels)]
    return scoped.reset_index(drop=True)


def records_for_channel_keys(
    index: dict[tuple[str, str], list[dict[str, Any]]],
    keys: set[str],
    channels: tuple[str, ...],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for channel in channels:
        for key in keys:
            records.extend(index.get((channel, key), []))
    return records


def records_for_other_channels(
    index: dict[str, list[dict[str, Any]]],
    keys: set[str],
    channels: tuple[str, ...],
) -> list[dict[str, Any]]:
    channel_set = {text(channel) for channel in channels if text(channel)}
    records: list[dict[str, Any]] = []
    for key in keys:
        for record in index.get(key, []):
            if text(record.get("판매채널명")) not in channel_set:
                records.append(record)
    return records


def records_for_keys(index: dict[str, list[dict[str, Any]]], keys: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key in keys:
        records.extend(index.get(key, []))
    return records


def frame_from_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(records) if records else pd.DataFrame()


def candidate_tuple(row: pd.Series, *, title_col: str) -> tuple[str, str, str, str]:
    return (
        text(row.get("판매채널명")),
        text(row.get(title_col)),
        text(row.get("_audit_key")),
        text(row.get("판매채널콘텐츠ID") or row.get("청구정산마스터ID")),
    )


def fuzzy_candidates(
    frame: pd.DataFrame,
    keys: set[str],
    *,
    channels: tuple[str, ...],
    title_col: str,
    threshold: float,
    limit: int = 5,
) -> list[tuple[float, str, str, str, str]]:
    if frame.empty or "_audit_key" not in frame.columns or not keys:
        return []
    scoped = frame
    if channels and "판매채널명" in frame.columns:
        scoped = frame[frame["판매채널명"].map(text).isin(channels)]
    best: list[tuple[float, str, str, str, str]] = []
    for _, candidate in scoped.iterrows():
        candidate_key = text(candidate.get("_audit_key"))
        if not candidate_key:
            continue
        scores: list[float] = []
        candidate_len = len(candidate_key)
        for key in keys:
            key_len = len(key)
            if key_len <= 0 or candidate_len <= 0:
                continue
            max_possible = (2 * min(key_len, candidate_len)) / (key_len + candidate_len)
            if max_possible < threshold:
                continue
            scores.append(SequenceMatcher(None, key, candidate_key).ratio())
        if not scores:
            continue
        score = max(scores)
        if score < threshold:
            continue
        channel, title, audit_key, identifier = candidate_tuple(candidate, title_col=title_col)
        best.append((score, channel, title, audit_key, identifier))
    best.sort(key=lambda item: item[0], reverse=True)
    return best[:limit]


def fuzzy_label(candidates: list[tuple[float, str, str, str, str]]) -> str:
    return " || ".join(
        f"{score:.3f}:{channel}:{title}:key={key}:id={identifier}"
        for score, channel, title, key, identifier in candidates
    )


def decide(
    *,
    same_missing: pd.DataFrame,
    same_billing: pd.DataFrame,
    same_service: pd.DataFrame,
    other_payment: pd.DataFrame,
    other_service: pd.DataFrame,
    fuzzy_payment: list[tuple[float, str, str, str, str]],
    fuzzy_service: list[tuple[float, str, str, str, str]],
) -> tuple[str, str]:
    if len(same_missing):
        return "동일채널_정산정보누락", "정제 문제가 아니라 S2 지급정산 보강/제외 판단 대상"
    if len(same_service):
        return "동일채널_판매채널콘텐츠만_존재", "판매채널콘텐츠ID는 있으나 지급정산 기준이 없어 연결/생성 판단 대상"
    if len(same_billing):
        return "동일채널_청구정산후보", "청구정산 건인지 확인하고 지급정산 매핑 대상 여부 판단"
    if len(other_payment):
        return "타채널_지급정산_exact", "제목 정제는 대체로 맞고 해당 판매채널 지급정산이 없는 상태"
    if len(other_service):
        return "타채널_판매채널콘텐츠_exact", "타채널 콘텐츠 증거만 있으므로 현재 채널 생성/연결 여부 확인"
    if fuzzy_payment and fuzzy_payment[0][0] >= 0.9:
        return "정제규칙_강후보", "동일채널 지급정산에 고유사도 후보가 있어 alias/특수규칙 검토"
    if fuzzy_service and fuzzy_service[0][0] >= 0.9:
        return "정제규칙_판매채널콘텐츠_강후보", "동일채널 판매채널콘텐츠에 고유사도 후보가 있어 alias/특수규칙 검토"
    if fuzzy_payment or fuzzy_service:
        return "정제규칙_약후보", "유사도 후보는 있으나 수동 확인 전 규칙 반영 금지"
    return "S2_부재_가능성", "S2/콘텐츠마스터 실검색 후 신규/제외 여부 판단"


def decide_all_s2(
    *,
    all_payment: pd.DataFrame,
    all_service: pd.DataFrame,
    all_fuzzy_payment: list[tuple[float, str, str, str, str]],
    all_fuzzy_service: list[tuple[float, str, str, str, str]],
) -> tuple[str, str]:
    if len(all_payment):
        return "전체S2_지급정산_exact", "정제키는 S2 전체 지급정산에 존재. 정제 로직 문제가 아니라 해당 판매채널 기준/정산 설정 문제로 분리"
    if len(all_service):
        return "전체S2_판매채널콘텐츠_exact", "정제키는 S2 전체 판매채널콘텐츠에 존재. 지급정산 기준 생성/연결 여부 확인"
    if all_fuzzy_payment and all_fuzzy_payment[0][0] >= 0.9:
        return "정제규칙_전체S2_강후보", "S2 전체 지급정산에 고유사도 후보가 있어 단순 오탈자/표기 차이 alias 검토"
    if all_fuzzy_service and all_fuzzy_service[0][0] >= 0.9:
        return "정제규칙_전체S2_판매채널콘텐츠_강후보", "S2 전체 판매채널콘텐츠에 고유사도 후보가 있어 단순 오탈자/표기 차이 alias 검토"
    if all_fuzzy_payment or all_fuzzy_service:
        return "정제규칙_전체S2_약후보", "유사도 후보는 있으나 수동 확인 전 규칙 반영 금지"
    return "전체S2_부재_가능성", "S2 전체 제목 풀에도 exact/fuzzy 근거 없음. 신규/제외/정산서 원문 확인 대상"


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


def audit_file(
    path: Path,
    *,
    root: Path,
    s2_df: pd.DataFrame,
    lookups: LookupBundle,
    reference_cache: dict[tuple[str, ...], Any],
    fuzzy_threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    platform, channel_label, filter_result = filter_s2_for_file(path, root, s2_df)
    channels = tuple(filter_result.matched_channels)
    summary: dict[str, Any] = {
        "file": str(path),
        "platform": platform,
        "s2_sales_channel": channel_label,
        "status": "failed",
        "parsed_rows": 0,
        "mapping_rows": 0,
        "no_match_rows": 0,
        "error": "",
    }
    if not platform:
        summary.update(status="blocked", error="platform_detection_failed")
        return [], summary

    try:
        normalized = normalize_settlement(path, platform=platform, source_name=str(path))
        adapter_summary = summarize_normalization(normalized)
        summary.update(
            parsed_rows=adapter_summary.get("parsed_rows", 0),
            default_feed_rows=adapter_summary.get("default_feed_rows", 0),
            file_status=adapter_summary.get("file_status", ""),
        )
        blocking = adapter_blocking_messages(normalized)
        if blocking:
            summary.update(status="blocked", error=" | ".join(blocking))
            return [], summary

        settlement_df = normalized.default_feed_rows.copy()
        if settlement_df.empty:
            summary.update(status="blocked", error="no_default_feed_rows")
            return [], summary

        cache_key = channels or (channel_label,)
        s2_reference = reference_cache.get(cache_key)
        if s2_reference is None:
            s2_reference = build_s2_mapping_reference(filter_result.frame)
            reference_cache[cache_key] = s2_reference

        mapping = build_mapping(filter_result.frame, settlement_df, s2_reference=s2_reference)
        rows = mapping.rows.copy()
        summary.update(
            status="success",
            mapping_rows=len(rows),
            no_match_rows=int(rows["S2_매칭상태"].map(text).eq(MATCH_NONE).sum()),
            warnings=" | ".join(adapter_warning_messages(normalized)),
            s2_filter_before=filter_result.before_rows,
            s2_filter_after=filter_result.after_rows,
            s2_filter_channels=" | ".join(channels),
        )
    except Exception as exc:
        summary.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        return [], summary

    output_rows: list[dict[str, Any]] = []
    no_match_rows = rows[rows["S2_매칭상태"].map(text).eq(MATCH_NONE)].copy()
    for _, row in no_match_rows.iterrows():
        original_title = text(row.get("정산서_콘텐츠명"))
        cleaned_key = text(row.get("정제_상품명"))
        keys = {cleaned_key, clean_title(original_title)}
        keys = {key for key in keys if key}

        all_payment = frame_from_records(records_for_keys(lookups.payment_by_key, keys))
        all_service = frame_from_records(records_for_keys(lookups.service_by_key, keys))
        same_missing = frame_from_records(records_for_channel_keys(lookups.missing_by_channel_key, keys, channels))
        same_billing = frame_from_records(records_for_channel_keys(lookups.billing_by_channel_key, keys, channels))
        same_service = frame_from_records(records_for_channel_keys(lookups.service_by_channel_key, keys, channels))
        other_payment = frame_from_records(records_for_other_channels(lookups.payment_by_key, keys, channels))
        other_service = frame_from_records(records_for_other_channels(lookups.service_by_key, keys, channels))
        all_fuzzy_payment: list[tuple[float, str, str, str, str]] = []
        all_fuzzy_service: list[tuple[float, str, str, str, str]] = []
        fuzzy_payment: list[tuple[float, str, str, str, str]] = []
        fuzzy_service: list[tuple[float, str, str, str, str]] = []
        has_all_exact_evidence = len(all_payment) or len(all_service)
        if not has_all_exact_evidence:
            all_fuzzy_payment = fuzzy_candidates(
                lookups.payment,
                keys,
                channels=(),
                title_col="콘텐츠명",
                threshold=fuzzy_threshold,
            )
            if not all_fuzzy_payment:
                all_fuzzy_service = fuzzy_candidates(
                    lookups.service,
                    keys,
                    channels=(),
                    title_col="콘텐츠명",
                    threshold=fuzzy_threshold,
                )
        has_exact_evidence = any(
            len(frame)
            for frame in (same_missing, same_billing, same_service, other_payment, other_service)
        )
        if not has_exact_evidence:
            fuzzy_payment = fuzzy_candidates(
                lookups.payment,
                keys,
                channels=channels,
                title_col="콘텐츠명",
                threshold=fuzzy_threshold,
            )
            if not fuzzy_payment:
                fuzzy_service = fuzzy_candidates(
                    lookups.service,
                    keys,
                    channels=channels,
                    title_col="콘텐츠명",
                    threshold=fuzzy_threshold,
                )
        channel_decision, channel_action = decide(
            same_missing=same_missing,
            same_billing=same_billing,
            same_service=same_service,
            other_payment=other_payment,
            other_service=other_service,
            fuzzy_payment=fuzzy_payment,
            fuzzy_service=fuzzy_service,
        )
        decision, action = decide_all_s2(
            all_payment=all_payment,
            all_service=all_service,
            all_fuzzy_payment=all_fuzzy_payment,
            all_fuzzy_service=all_fuzzy_service,
        )
        output_rows.append(
            {
                "파일": str(path),
                "플랫폼": platform,
                "S2 판매채널": channel_label,
                "S2 필터채널목록": " | ".join(channels),
                "원본시트": text(row.get("정산서원본_source_sheet")),
                "원본행번호": text(row.get("정산서원본_source_row")),
                "정산서_콘텐츠명": original_title,
                "정제_상품명": cleaned_key,
                "판정": decision,
                "권장조치": action,
                "채널기준_판정": channel_decision,
                "채널기준_권장조치": channel_action,
                "전체S2_지급정산_채널": unique_join(all_payment.get("판매채널명", [])),
                "전체S2_지급정산_ID": unique_join(all_payment.get("판매채널콘텐츠ID", [])),
                "전체S2_지급정산_콘텐츠명": unique_join(all_payment.get("콘텐츠명", [])),
                "전체S2_판매채널콘텐츠_채널": unique_join(all_service.get("판매채널명", [])),
                "전체S2_판매채널콘텐츠_ID": unique_join(all_service.get("판매채널콘텐츠ID", [])),
                "전체S2_판매채널콘텐츠_콘텐츠명": unique_join(all_service.get("콘텐츠명", [])),
                "전체S2_fuzzy_지급정산": fuzzy_label(all_fuzzy_payment),
                "전체S2_fuzzy_판매채널콘텐츠": fuzzy_label(all_fuzzy_service),
                "동일채널_정산정보누락_ID": unique_join(same_missing.get("판매채널콘텐츠ID", [])),
                "동일채널_판매채널콘텐츠_ID": unique_join(same_service.get("판매채널콘텐츠ID", [])),
                "동일채널_청구정산_ID": unique_join(same_billing.get("청구정산마스터ID", [])),
                "타채널_지급정산_채널": unique_join(other_payment.get("판매채널명", [])),
                "타채널_지급정산_ID": unique_join(other_payment.get("판매채널콘텐츠ID", [])),
                "타채널_지급정산_콘텐츠명": unique_join(other_payment.get("콘텐츠명", [])),
                "타채널_판매채널콘텐츠_채널": unique_join(other_service.get("판매채널명", [])),
                "타채널_판매채널콘텐츠_ID": unique_join(other_service.get("판매채널콘텐츠ID", [])),
                "타채널_판매채널콘텐츠_콘텐츠명": unique_join(other_service.get("콘텐츠명", [])),
                "동일채널_fuzzy_지급정산": fuzzy_label(fuzzy_payment),
                "동일채널_fuzzy_판매채널콘텐츠": fuzzy_label(fuzzy_service),
            }
        )
    return output_rows, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit original settlement no-match rows for title-cleaning misses.")
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--file", action="append", default=[], help="Specific settlement file path. Can be repeated.")
    parser.add_argument("--month-token", default="")
    parser.add_argument("--platform", default="", help="Optional first-level platform folder name.")
    parser.add_argument("--limit-files", type=int, default=0, help="0 means no limit.")
    parser.add_argument("--fuzzy-threshold", type=float, default=0.82)
    parser.add_argument("--s2-lookup", default=str(DEFAULT_S2_LOOKUP))
    parser.add_argument("--missing-lookup", default=str(DEFAULT_MISSING_LOOKUP))
    parser.add_argument("--billing-lookup", default=str(DEFAULT_BILLING_LOOKUP))
    parser.add_argument("--service-lookup", default=str(DEFAULT_SERVICE_LOOKUP))
    parser.add_argument("--output", default="")
    parser.add_argument("--summary-output", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    today = datetime.now().strftime("%Y-%m-%d")
    output = Path(args.output) if args.output else REPO_ROOT / "temp" / f"original_settlement_no_match_cleaning_audit_{today}.csv"
    summary_output = (
        Path(args.summary_output)
        if args.summary_output
        else output.with_name(output.stem + "_summary.json")
    )

    s2_df, lookups = load_lookups(args)
    files = [Path(value) for value in args.file]
    if not files:
        files = iter_original_settlement_files(
            root,
            month_token=args.month_token,
            platform=args.platform,
            limit=args.limit_files,
        )
    rows: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    reference_cache: dict[tuple[str, ...], Any] = {}
    for index, path in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] {path}", flush=True)
        file_rows, file_summary = audit_file(
            path,
            root=root,
            s2_df=s2_df,
            lookups=lookups,
            reference_cache=reference_cache,
            fuzzy_threshold=args.fuzzy_threshold,
        )
        rows.extend(file_rows)
        file_summaries.append(file_summary)

    write_csv(output, rows)
    decision_counts = pd.Series([row["판정"] for row in rows]).value_counts().to_dict() if rows else {}
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "month_token": args.month_token,
        "platform": args.platform,
        "files_scanned": len(files),
        "output": str(output),
        "no_match_rows": len(rows),
        "decision_counts": decision_counts,
        "file_status_counts": pd.Series([row["status"] for row in file_summaries]).value_counts().to_dict()
        if file_summaries
        else {},
        "files": file_summaries,
    }
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "files"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
