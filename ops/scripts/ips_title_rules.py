from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from build_work_index import clean_title_for_display, normalize_text, split_folder_name


PROJECT_ROOT = Path(__file__).resolve().parents[1] / "SIAAN Project"
LATEST_IPS_EXPORT_PATH = PROJECT_ROOT / "00_콘텐츠+목록 (1).xlsx"
FALLBACK_IPS_EXPORT_PATH = PROJECT_ROOT / "data" / "exports" / "ips" / "콘텐츠+목록.xlsx"
CAUTION_CIDS = {
    "107853",
    "278175",
    "308297",
    "320883",
    "320886",
    "322020",
    "322451",
    "322717",
}

ACCOUNT_SUFFIX_PATTERN = re.compile(r"^(?P<base>.+?)_(?P<account>\d+)$")
TITLE_SPLIT_PATTERN = re.compile(r"[·_]")
EPISODE_SUFFIX_PATTERN = re.compile(r"\s*\(?\d+(?:\s*[~\-]\s*\d+)?화(?:\s*완결)?\)?\s*$")

_CATEGORY_ALIASES = {
    normalize_text("일반"): "일반",
    normalize_text("원작"): "원작",
    normalize_text("카카오"): "원작",
    normalize_text("네이버"): "원작",
    normalize_text("카카오 MG"): "카카오MG",
    normalize_text("카카오MG"): "카카오MG",
    normalize_text("카카오선투자"): "카카오MG",
    normalize_text("네이버 MG"): "네이버MG",
    normalize_text("네이버MG"): "네이버MG",
    normalize_text("네이버광고수익"): "네이버광고수익",
    normalize_text("카카오광고수익"): "카카오광고수익",
    normalize_text("창작지원금"): "카카오창작지원금",
    normalize_text("카카오창작지원금"): "카카오창작지원금",
    normalize_text("부속합의(KST-작가)"): "부속합의(KST-작가)",
    normalize_text("부속합의(KST-NAVER)"): "부속합의(KST-NAVER)",
    normalize_text("부속합의(KST-KAKAO)"): "부속합의(KST-KAKAO)",
    normalize_text("작가선인세"): "작가선인세",
    normalize_text("작품선인세"): "작품선인세",
}
_AUTHOR_WIDE_CATEGORY_KEYS = {
    normalize_text("카카오MG"),
    normalize_text("네이버광고수익"),
    normalize_text("카카오광고수익"),
}


def resolve_default_ips_export_path() -> Path:
    if LATEST_IPS_EXPORT_PATH.exists():
        return LATEST_IPS_EXPORT_PATH
    return FALLBACK_IPS_EXPORT_PATH


def merge_unique_titles(*title_groups: Iterable[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in title_groups:
        for raw_value in group:
            cleaned = clean_title_for_display(str(raw_value or "")).strip()
            dedupe_base = cleaned
            while True:
                updated = EPISODE_SUFFIX_PATTERN.sub("", dedupe_base).strip()
                if updated == dedupe_base:
                    break
                dedupe_base = updated
            dedupe_base = dedupe_base.rstrip("!?., ")
            normalized = normalize_text(dedupe_base)
            if not normalized or normalized in seen:
                continue
            merged.append(cleaned)
            seen.add(normalized)
    return merged


def canonicalize_ips_category(raw_remark: str) -> str:
    cleaned = str(raw_remark or "").strip()
    if not cleaned:
        return ""
    return _CATEGORY_ALIASES.get(normalize_text(cleaned), cleaned)


def split_remark_account_suffix(raw_remark: str) -> tuple[str, str]:
    cleaned = str(raw_remark or "").strip()
    if not cleaned:
        return "", ""
    match = ACCOUNT_SUFFIX_PATTERN.match(cleaned)
    if not match:
        return canonicalize_ips_category(cleaned), ""
    return canonicalize_ips_category(match.group("base")), match.group("account")


def canonicalize_full_remark(raw_remark: str) -> str:
    category, account_suffix = split_remark_account_suffix(raw_remark)
    if category and account_suffix:
        return f"{category}_{account_suffix}"
    return category or account_suffix


def is_author_wide_category(raw_remark: str) -> bool:
    category, _ = split_remark_account_suffix(raw_remark)
    return normalize_text(category) in _AUTHOR_WIDE_CATEGORY_KEYS


def parse_titles_from_legacy_target(target_title: str, author_name: str, remark: str) -> list[str]:
    raw = str(target_title or "").strip()
    if not raw:
        return []

    if raw.startswith("0_"):
        raw = raw[2:].strip()
    if raw.startswith("(사용안함)_"):
        raw = raw[len("(사용안함)_") :].strip()

    clean_author = clean_title_for_display(author_name)
    clean_category, account_suffix = split_remark_account_suffix(remark)
    if clean_author and clean_category:
        prefix = f"{clean_author}_{clean_category}_"
        if raw.startswith(prefix):
            working = raw[len(prefix) :].strip()
            if account_suffix:
                account_token = f"_{account_suffix}"
                if working.endswith(account_token):
                    working = working[: -len(account_token)].strip()
            return merge_unique_titles(TITLE_SPLIT_PATTERN.split(working))

    suffix_candidates: list[str] = []
    for value in (
        canonicalize_full_remark(remark),
        clean_title_for_display(remark),
        clean_category,
    ):
        if value and value not in suffix_candidates:
            suffix_candidates.append(value)

    working = raw
    for suffix in sorted(suffix_candidates, key=len, reverse=True):
        token = f"_{suffix}"
        if working.endswith(token):
            working = working[: -len(token)].strip()
            break

    if clean_author:
        author_token = f"_{clean_author}"
        if working.endswith(author_token):
            working = working[: -len(author_token)].strip()

    return merge_unique_titles(TITLE_SPLIT_PATTERN.split(working))


def build_canonical_target_title(
    author_name: str,
    remark: str,
    titles: Iterable[str],
    *,
    account_suffix: str | None = None,
) -> str:
    clean_author = clean_title_for_display(author_name)
    category, derived_account = split_remark_account_suffix(remark)
    final_account = account_suffix if account_suffix is not None else derived_account
    clean_titles = merge_unique_titles(titles)

    parts: list[str] = []
    if clean_author:
        parts.append(clean_author)
    if category:
        parts.append(category)
    parts.extend(clean_titles)
    if final_account:
        parts.append(final_account)
    return "_".join(part for part in parts if part)


def _add_catalog_entry(
    titles_by_cid: dict[str, list[str]],
    titles_by_author: dict[str, list[str]],
    work_cid: str,
    author_name: str,
    title: str,
) -> None:
    clean_title = clean_title_for_display(title)
    clean_author = clean_title_for_display(author_name)
    if not clean_title:
        return
    if work_cid:
        titles_by_cid[work_cid] = merge_unique_titles(titles_by_cid.get(work_cid, []), [clean_title])
    if clean_author:
        titles_by_author[clean_author] = merge_unique_titles(titles_by_author.get(clean_author, []), [clean_title])


def build_title_catalog_from_overrides(
    manual_overrides_payload: dict[str, Any],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    titles_by_cid: dict[str, list[str]] = {}
    titles_by_author: dict[str, list[str]] = {}

    for item in manual_overrides_payload.get("ips_cid_overrides", []) or []:
        work_cid = str(item.get("work_cid") or "").strip()
        folder_path = str(item.get("work_folder_path") or "").strip()
        if not work_cid or not folder_path:
            continue
        source_title, author_name = split_folder_name(Path(folder_path).name)
        _add_catalog_entry(titles_by_cid, titles_by_author, work_cid, author_name, source_title)

    for item in manual_overrides_payload.get("ips_explicit_targets", []) or []:
        author_name = clean_title_for_display(str(item.get("author_name") or "").strip())
        remark = str(item.get("remark") or "").strip()
        if not author_name:
            continue
        category, _ = split_remark_account_suffix(remark)
        if not (is_author_wide_category(remark) or normalize_text(category) == normalize_text("작가선인세")):
            continue
        titles = parse_titles_from_legacy_target(
            str(item.get("target_title") or ""),
            author_name,
            remark,
        )
        if titles:
            titles_by_author[author_name] = merge_unique_titles(titles, titles_by_author.get(author_name, []))

    return titles_by_cid, titles_by_author


def compute_explicit_target_title(
    entry: dict[str, Any],
    titles_by_cid: dict[str, list[str]] | None = None,
    titles_by_author: dict[str, list[str]] | None = None,
) -> str:
    work_cid = str(entry.get("work_cid") or "").strip()
    author_name = clean_title_for_display(str(entry.get("author_name") or "").strip())
    remark = str(entry.get("remark") or "").strip()
    legacy_titles = parse_titles_from_legacy_target(
        str(entry.get("target_title") or ""),
        author_name,
        remark,
    )
    cid_titles = (titles_by_cid or {}).get(work_cid, [])
    author_titles = (titles_by_author or {}).get(author_name, [])

    if is_author_wide_category(remark):
        titles = merge_unique_titles(legacy_titles, author_titles, cid_titles)
    else:
        titles = merge_unique_titles(legacy_titles, cid_titles)

    if not titles and entry.get("source_title"):
        titles = merge_unique_titles([str(entry.get("source_title") or "").strip()])

    computed = build_canonical_target_title(author_name, remark, titles)
    return computed or clean_title_for_display(str(entry.get("target_title") or "").strip())
