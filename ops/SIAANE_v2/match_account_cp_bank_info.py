from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent
SIAAN_PROJECT_ROOT = REPO_ROOT / "SIAAN Project"
WORK_DIR = PROJECT_ROOT / "담당자없는작품_재정리"

sys.path.insert(0, str(SIAAN_PROJECT_ROOT))

from account_login import ACCOUNT_HOME_URL, MEMBER_LOGIN_URL  # noqa: E402


DEFAULT_AUDIT = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__admin_vs_IPS출판사_감리.csv"
DEFAULT_CP_LIST = WORK_DIR / "20260518_account_CP목록_live.csv"
DEFAULT_CP_DETAIL = WORK_DIR / "20260518_account_CP상세_계좌정보_snapshot.csv"
DEFAULT_HOLDER_OUT = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__일치9175_account계좌매칭_저작권자기준.csv"
DEFAULT_ROW_OUT = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__일치9175_account계좌매칭_CID행기준.csv"
DEFAULT_SUMMARY = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__일치9175_account계좌매칭_summary.csv"

CP_LIST_URL = "http://account.barobook.com/CpMgr/List"
LIST_URL = (
    "http://account.barobook.com/CpMgr/List"
    "?key=0&code=&searchItem=0&searchString="
    "&sortItem=0&sortMethod=0&page={page}&pageSize=20&groupSize=10"
    "&isDuration=False&startDt=&endDt=&cpClCd=&cpTypeCd=&isAdvCpr=false"
    "&srchTarget=1&srchKwrd="
)
DETAIL_URL = (
    "http://account.barobook.com/CpMgr/Detail"
    "?isDuration=False&cpClCd=&isAdvCpr=false&key={code}"
)


LIST_PAGE_JS = r"""
() => {
    const tables = document.querySelectorAll('table.tbl_type');
    const grid = tables[tables.length - 1];
    const rows = [];
    if (grid) {
        const trs = grid.querySelectorAll('tbody > tr');
        for (const tr of trs) {
            const tds = Array.from(tr.querySelectorAll('td')).map(
                td => td.innerText.replace(/\u00a0/g, ' ').trim()
            );
            if (tds.length >= 6) rows.push(tds);
        }
    }
    const lastLink = document.querySelector('div.paginate_complex a.direction.next[href*="page="]');
    let lastPage = 0;
    if (lastLink) {
        const m = lastLink.href.match(/page=(\d+)/);
        if (m) lastPage = parseInt(m[1], 10);
    }
    return { rows, lastPage };
}
"""


DETAIL_BATCH_JS = r"""
async ({ codes, concurrency }) => {
    const norm = (value) => (value || "")
        .replace(/\u00a0/g, " ")
        .replace(/\s+/g, " ")
        .trim();

    const parseOne = (html, code, url, status) => {
        const doc = new DOMParser().parseFromString(html, "text/html");
        const rows = Array.from(doc.querySelectorAll("table tr"));
        const getField = (label) => {
            for (const tr of rows) {
                const cells = Array.from(tr.querySelectorAll("th, td"));
                if (cells.length < 2) continue;
                const key = norm(cells[0].innerText);
                if (key === label || key.startsWith(label)) return norm(cells[1].innerText);
            }
            return "";
        };

        let accountCell = null;
        for (const td of Array.from(doc.querySelectorAll("td.item_l, td"))) {
            const text = norm(td.innerText);
            if (text.includes("예금주 :") && text.includes("은행명 :") && text.includes("계좌번호 :")) {
                accountCell = td;
                break;
            }
        }
        const accountText = accountCell ? norm(accountCell.innerText) : "";
        const bankbookLink = accountCell
            ? ((accountCell.querySelector('a[href*="/Files/CP/"]') || {}).href || "")
            : "";
        return {
            작가코드: String(code || ""),
            조회상태: "ok",
            http_status: String(status || ""),
            detail_url: url,
            cp_login_id: getField("ID"),
            이름: getField("이름"),
            필명: getField("필명"),
            저작권자_구분_타입: getField("저작권자 구분 | 타입"),
            주민_사업자번호: getField("주민등록번호/사업자 등록번호"),
            연락처: getField("연락처"),
            이메일: getField("이메일"),
            주소: getField("주소"),
            계좌정보_raw: accountText,
            통장사본링크: bankbookLink,
            정산기준: getField("정산기준"),
            서비스유형: getField("서비스 유형"),
            유통범위: getField("유통범위"),
            계약기간: getField("계약기간"),
            계약담당자: getField("계약 담당자"),
            계약서존재여부: getField("계약서 존재여부"),
            상태: getField("상태"),
            등록일시: getField("등록일시"),
            error: "",
        };
    };

    const results = new Array(codes.length);
    let cursor = 0;
    async function fetchOne(index) {
        const code = codes[index];
        const url = `/CpMgr/Detail?isDuration=False&cpClCd=&isAdvCpr=false&key=${encodeURIComponent(code)}`;
        try {
            const response = await fetch(url, { credentials: "include" });
            const html = await response.text();
            if (!response.ok) {
                results[index] = {
                    작가코드: String(code || ""),
                    조회상태: "failed",
                    http_status: String(response.status || ""),
                    detail_url: location.origin + url,
                    error: `HTTP ${response.status}`,
                };
                return;
            }
            results[index] = parseOne(html, code, location.origin + url, response.status);
        } catch (error) {
            results[index] = {
                작가코드: String(code || ""),
                조회상태: "failed",
                http_status: "",
                detail_url: location.origin + url,
                error: String((error && error.message) || error || ""),
            };
        }
    }
    async function worker() {
        while (cursor < codes.length) {
            const index = cursor++;
            await fetchOne(index);
        }
    }
    const workerCount = Math.max(1, Math.min(Number(concurrency || 1), codes.length));
    const workers = [];
    for (let i = 0; i < workerCount; i++) workers.push(worker());
    await Promise.all(workers);
    return results;
}
"""


ACCOUNT_LINE_RE = re.compile(
    r"예금주\s*:\s*(?P<holder>[^|]+?)\s*\|\s*"
    r"은행명\s*:\s*(?P<bank>[^|]+?)\s*\|\s*"
    r"계좌번호\s*:\s*(?P<account>[^|]+?)(?:\s+사본보기)?(?:\s*)$"
)

CORP_NOISE_RE = re.compile(
    r"\(주\)|㈜|주식회사|유한회사|도서출판|출판사|출판|"
    r"\binc\b|\bltd\b",
    re.I,
)
QUALIFIER_RE = re.compile(
    r"\((?:2015년신규|국내물|일본물|재계약|구작|사용안함|이전계정|"
    r"네이버\s*연재|연재공모|선인세[^)]*|단편\s*연재/선인세|"
    r"r/s해지|음자[^)]*|라이트노블1|성태민)\)",
    re.I,
)


def text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    raw = str(value).replace("\u00a0", " ").strip()
    if re.fullmatch(r"\d+\.0", raw):
        return raw[:-2]
    return re.sub(r"\s+", " ", raw)


def id_text(value: Any) -> str:
    raw = text(value)
    if re.fullmatch(r"\d+(?:\.0+)?", raw):
        return str(int(float(raw)))
    return raw


def split_pipe(value: Any) -> list[str]:
    return [part.strip() for part in re.split(r"\s*\|\s*", text(value)) if part.strip()]


def join_unique(values: list[Any]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = text(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return " | ".join(out)


def compact(value: Any, *, strip_corp: bool = True, strip_qualifier: bool = False) -> str:
    cleaned = unicodedata.normalize("NFKC", text(value)).lower().replace("㈜", "(주)")
    if strip_qualifier:
        cleaned = QUALIFIER_RE.sub("", cleaned)
    if strip_corp:
        cleaned = CORP_NOISE_RE.sub("", cleaned)
    return re.sub(r"[^0-9a-z가-힣\u4e00-\u9fff]+", "", cleaned)


def name_variants(value: Any) -> set[str]:
    raw = text(value)
    if not raw:
        return set()
    variants = {raw}
    no_qual = QUALIFIER_RE.sub("", raw).strip()
    if no_qual:
        variants.add(no_qual)
    parens = [text(match) for match in re.findall(r"\(([^)]*)\)", raw)]
    outside = text(re.sub(r"\([^)]*\)", " ", raw))
    if outside:
        variants.add(outside)
    for part in parens:
        if part:
            variants.add(part)
    if outside and parens:
        for part in parens:
            variants.add(f"{outside} {part}")
            variants.add(f"{part} {outside}")
    keys: set[str] = set()
    for variant in variants:
        for strip_corp in (False, True):
            for strip_qualifier in (False, True):
                key = compact(variant, strip_corp=strip_corp, strip_qualifier=strip_qualifier)
                if len(key) >= 2:
                    keys.add(key)
    return keys


def target_primary_key(value: Any) -> str:
    return compact(value, strip_corp=True, strip_qualifier=True)


def parse_account_line(raw: Any) -> tuple[str, str, str]:
    cleaned = text(raw)
    match = ACCOUNT_LINE_RE.search(cleaned)
    if not match:
        return "", "", ""
    return text(match.group("holder")), text(match.group("bank")), text(match.group("account"))


@dataclass(frozen=True)
class Config:
    username: str
    password: str
    env_path: Path
    headless: bool
    timeout_ms: int
    refresh_cp_list: bool
    refresh_details: bool
    detail_concurrency: int
    detail_batch_size: int
    include_statuses: set[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Match SSOT rights holders to account CP bank details.")
    parser.add_argument("--env-file", default=str(SIAAN_PROJECT_ROOT / ".env"))
    parser.add_argument("--audit-csv", default=str(DEFAULT_AUDIT))
    parser.add_argument("--cp-list-csv", default=str(DEFAULT_CP_LIST))
    parser.add_argument("--cp-detail-csv", default=str(DEFAULT_CP_DETAIL))
    parser.add_argument("--holder-output", default=str(DEFAULT_HOLDER_OUT))
    parser.add_argument("--row-output", default=str(DEFAULT_ROW_OUT))
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--detail-concurrency", type=int, default=12)
    parser.add_argument("--detail-batch-size", type=int, default=100)
    parser.add_argument("--include-status", action="append", default=["일치"])
    parser.add_argument("--reuse-cp-list", action="store_true")
    parser.add_argument("--reuse-details", action="store_true")
    return parser.parse_args()


def load_config(args: argparse.Namespace) -> Config:
    env_path = Path(args.env_file)
    if not env_path.exists():
        raise FileNotFoundError(env_path)
    load_dotenv(env_path, override=True)
    username = (os.getenv("BAROBOOK_ID") or os.getenv("KLD_LOGIN_ID") or "").strip()
    password = (os.getenv("BAROBOOK_PW") or os.getenv("KLD_LOGIN_PW") or "").strip()
    if not username or not password:
        raise RuntimeError(f"{env_path}에 BAROBOOK_ID/BAROBOOK_PW 또는 KLD_LOGIN_*가 없습니다.")
    return Config(
        username=username,
        password=password,
        env_path=env_path,
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        refresh_cp_list=not args.reuse_cp_list,
        refresh_details=not args.reuse_details,
        detail_concurrency=max(1, args.detail_concurrency),
        detail_batch_size=max(1, args.detail_batch_size),
        include_statuses={text(value) for value in args.include_status if text(value)},
    )


def login(page: Any, config: Config) -> None:
    from playwright.sync_api import TimeoutError as PWTimeout

    page.goto(ACCOUNT_HOME_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_url(
            lambda url: "member.barobook.com" in str(url) and "/auth/Login" in str(url),
            timeout=config.timeout_ms,
        )
    except PWTimeout:
        page.goto(MEMBER_LOGIN_URL, wait_until="domcontentloaded")
    page.wait_for_selector("#MBR_ID", timeout=config.timeout_ms)
    page.fill("#MBR_ID", config.username)
    page.fill("#MBR_PWD", config.password)
    try:
        with page.expect_navigation(timeout=config.timeout_ms, wait_until="domcontentloaded"):
            page.locator("#MBR_PWD").press("Enter")
    except PWTimeout:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=config.timeout_ms)
    except PWTimeout:
        pass
    if "/auth/login" in page.url.lower() or "member.barobook.com" in page.url.lower():
        raise RuntimeError(f"account login failed: {page.url}")


def scrape_cp_list(page: Any, output: Path) -> pd.DataFrame:
    all_rows: list[dict[str, str]] = []
    page_num = 1
    last_page = 1
    while True:
        page.goto(LIST_URL.format(page=page_num), wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:  # noqa: BLE001
            pass
        payload = page.evaluate(LIST_PAGE_JS)
        rows = payload.get("rows") or []
        detected_last = int(payload.get("lastPage") or 0)
        if detected_last:
            last_page = detected_last
        for row in rows:
            all_rows.append(
                {
                    "작가코드": id_text(row[0] if len(row) > 0 else ""),
                    "저작권자명_필명": text(row[1] if len(row) > 1 else ""),
                    "장르_타입": text(row[2] if len(row) > 2 else ""),
                    "연락처": text(row[3] if len(row) > 3 else ""),
                    "email": text(row[4] if len(row) > 4 else ""),
                    "등록일": text(row[5] if len(row) > 5 else ""),
                }
            )
        if page_num >= last_page or not rows:
            break
        page_num += 1
        if page_num % 25 == 0:
            print(f"[cp-list] page {page_num}/{last_page} rows={len(all_rows)}", flush=True)
    df = pd.DataFrame(all_rows).drop_duplicates(subset=["작가코드"], keep="first")
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"[cp-list] rows={len(df)} output={output}", flush=True)
    return df


DETAIL_FIELDS = [
    "작가코드",
    "조회상태",
    "http_status",
    "detail_url",
    "cp_login_id",
    "이름",
    "필명",
    "저작권자_구분_타입",
    "주민_사업자번호",
    "연락처",
    "이메일",
    "주소",
    "계좌정보_raw",
    "예금주",
    "은행명",
    "계좌번호",
    "통장사본링크",
    "정산기준",
    "서비스유형",
    "유통범위",
    "계약기간",
    "계약담당자",
    "계약서존재여부",
    "상태",
    "등록일시",
    "error",
]


def load_detail_snapshot(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=DETAIL_FIELDS)
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    for column in DETAIL_FIELDS:
        if column not in df.columns:
            df[column] = ""
    return df[DETAIL_FIELDS]


def write_detail_snapshot(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for column in DETAIL_FIELDS:
        if column not in out.columns:
            out[column] = ""
    out = out[DETAIL_FIELDS].drop_duplicates(subset=["작가코드"], keep="last")
    out.to_csv(path, index=False, encoding="utf-8-sig")


def fetch_details(page: Any, codes: list[str], detail_path: Path, config: Config) -> pd.DataFrame:
    existing = load_detail_snapshot(detail_path)
    existing_codes = set(existing.loc[existing["조회상태"].eq("ok"), "작가코드"].map(id_text))
    missing = [code for code in codes if code and (config.refresh_details or code not in existing_codes)]
    if not missing:
        return existing
    if config.refresh_details:
        existing = existing[~existing["작가코드"].map(id_text).isin(set(missing))].copy()

    rows: list[dict[str, str]] = []
    total = len(missing)
    for start in range(0, total, config.detail_batch_size):
        batch = missing[start : start + config.detail_batch_size]
        print(f"[detail] {start + 1}-{start + len(batch)} / {total}", flush=True)
        fetched = page.evaluate(
            DETAIL_BATCH_JS,
            {"codes": batch, "concurrency": config.detail_concurrency},
        )
        for item in fetched:
            row = {field: text(item.get(field)) for field in DETAIL_FIELDS}
            holder, bank, account_no = parse_account_line(row.get("계좌정보_raw"))
            row["예금주"] = holder
            row["은행명"] = bank
            row["계좌번호"] = account_no
            rows.append(row)
        combined = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
        write_detail_snapshot(detail_path, combined)
    return load_detail_snapshot(detail_path)


def build_cp_index(cp: pd.DataFrame) -> tuple[dict[str, list[str]], dict[str, set[str]]]:
    key_to_codes: dict[str, list[str]] = defaultdict(list)
    code_to_keys: dict[str, set[str]] = defaultdict(set)
    for _, row in cp.iterrows():
        code = id_text(row.get("작가코드"))
        if not code:
            continue
        keys = name_variants(row.get("저작권자명_필명"))
        for key in keys:
            key_to_codes[key].append(code)
            code_to_keys[code].add(key)
    return key_to_codes, code_to_keys


def find_candidate_codes(holder: str, cp: pd.DataFrame, key_to_codes: dict[str, list[str]]) -> tuple[list[str], str]:
    holder_keys = name_variants(holder)
    primary = target_primary_key(holder)
    exact_codes: list[str] = []
    for key in holder_keys:
        exact_codes.extend(key_to_codes.get(key, []))
    if exact_codes:
        return sorted(set(exact_codes), key=lambda code: int(code) if code.isdigit() else code), "key_exact"

    contains: list[str] = []
    if len(primary) >= 2:
        for _, row in cp.iterrows():
            code = id_text(row.get("작가코드"))
            cp_keys = name_variants(row.get("저작권자명_필명"))
            if any(primary in cp_key or cp_key in primary for cp_key in cp_keys if len(cp_key) >= 2):
                contains.append(code)
    if contains:
        return sorted(set(contains), key=lambda code: int(code) if code.isdigit() else code), "key_contains"
    return [], "no_match"


def account_group_status(details: pd.DataFrame) -> tuple[str, str, str, str]:
    if details.empty:
        return "no_cp_match", "", "", ""
    ok = details[details["조회상태"].eq("ok")].copy()
    if ok.empty:
        return "cp_detail_failed", "", "", ""
    account_keys = {
        (text(row["예금주"]), text(row["은행명"]), re.sub(r"\D+", "", text(row["계좌번호"])))
        for _, row in ok.iterrows()
        if text(row["예금주"]) and text(row["은행명"]) and text(row["계좌번호"])
    }
    codes = ok["작가코드"].map(id_text).tolist()
    if len(codes) == 1:
        if account_keys:
            return "account_unique", *next(iter(account_keys))
        return "account_unique_no_bank", "", "", ""
    if len(account_keys) == 1:
        return "account_multi_same_bank", *next(iter(account_keys))
    if not account_keys:
        return "account_multi_no_bank", "", "", ""
    return "account_multi_conflict", "", "", ""


def build_holder_mapping(
    audit: pd.DataFrame,
    cp: pd.DataFrame,
    details: pd.DataFrame,
    include_statuses: set[str],
) -> pd.DataFrame:
    target = audit[audit["출판사비교상태"].isin(include_statuses)].copy()
    refs: dict[str, dict[str, Any]] = {}
    key_to_codes, _ = build_cp_index(cp)
    cp_by_code = cp.set_index(cp["작가코드"].map(id_text)).to_dict("index")
    detail_by_code = details.set_index(details["작가코드"].map(id_text))
    for _, row in target.iterrows():
        for holder in split_pipe(row.get("저작권자_전체")):
            if not holder or "등록된 저작권 정보" in holder:
                continue
            item = refs.setdefault(
                holder,
                {
                    "저작권자": holder,
                    "참조_CID": [],
                    "참조_콘텐츠명": [],
                    "참조_정산명": [],
                    "참조_상품번호": [],
                },
            )
            item["참조_CID"].append(id_text(row.get("콘텐츠ID")))
            item["참조_콘텐츠명"].append(text(row.get("IPS_콘텐츠명")))
            item["참조_정산명"].append(text(row.get("정산명_전체")))
            item["참조_상품번호"].append(text(row.get("상품번호_후보")))

    out_rows: list[dict[str, Any]] = []
    for holder, item in refs.items():
        codes, rule = find_candidate_codes(holder, cp, key_to_codes)
        detail_rows = details[details["작가코드"].map(id_text).isin(codes)].copy()
        status, holder_name, bank, account_no = account_group_status(detail_rows)
        cp_names = [text(cp_by_code.get(code, {}).get("저작권자명_필명")) for code in codes]
        detail_names = [
            f"{code}:{text(detail_by_code.loc[code].get('이름'))}({text(detail_by_code.loc[code].get('필명'))})"
            for code in codes
            if code in detail_by_code.index
        ]
        account_lines = [
            f"{code}:{text(detail_by_code.loc[code].get('예금주'))}/{text(detail_by_code.loc[code].get('은행명'))}/{text(detail_by_code.loc[code].get('계좌번호'))}"
            for code in codes
            if code in detail_by_code.index and text(detail_by_code.loc[code].get("계좌번호"))
        ]
        out_rows.append(
            {
                "저작권자": holder,
                "계좌매칭상태": status,
                "매칭규칙": rule,
                "후보_작가코드수": len(codes),
                "후보_작가코드": join_unique(codes),
                "후보_CP명": join_unique(cp_names),
                "상세_이름필명": join_unique(detail_names),
                "확정가능_예금주": holder_name,
                "확정가능_은행명": bank,
                "확정가능_계좌번호": account_no,
                "후보_계좌정보": join_unique(account_lines),
                "참조_CID수": len(set(item["참조_CID"])),
                "참조_CID": join_unique(item["참조_CID"][:50]),
                "참조_콘텐츠명": join_unique(item["참조_콘텐츠명"][:50]),
                "참조_정산명": join_unique(item["참조_정산명"][:50]),
                "참조_상품번호": join_unique(item["참조_상품번호"][:50]),
            }
        )
    return pd.DataFrame(out_rows).sort_values(
        by=["계좌매칭상태", "저작권자"], kind="stable"
    )


def build_row_mapping(audit: pd.DataFrame, holder_map: pd.DataFrame, include_statuses: set[str]) -> pd.DataFrame:
    target = audit[audit["출판사비교상태"].isin(include_statuses)].copy()
    holder_by_name = holder_map.set_index("저작권자").to_dict("index") if not holder_map.empty else {}
    rows: list[dict[str, Any]] = []
    good_statuses = {"account_unique", "account_multi_same_bank"}
    for _, row in target.iterrows():
        holders = [holder for holder in split_pipe(row.get("저작권자_전체")) if "등록된 저작권 정보" not in holder]
        statuses = [text(holder_by_name.get(holder, {}).get("계좌매칭상태")) for holder in holders]
        if not holders:
            row_status = "저작권자없음"
        elif all(status in good_statuses for status in statuses):
            row_status = "전체확인"
        elif any(status in good_statuses for status in statuses):
            row_status = "일부확인"
        else:
            row_status = "미확인"
        rows.append(
            {
                "CID계좌매칭상태": row_status,
                "콘텐츠ID": id_text(row.get("콘텐츠ID")),
                "IPS_콘텐츠명": text(row.get("IPS_콘텐츠명")),
                "IPS_작가필명": text(row.get("IPS_작가필명")),
                "IPS_담당부서": text(row.get("IPS_담당부서")),
                "IPS_담당자명": text(row.get("IPS_담당자명")),
                "출판사비교상태": text(row.get("출판사비교상태")),
                "IPS_출판사": text(row.get("IPS_출판사")),
                "admin_출판사목록": text(row.get("admin_출판사목록")),
                "상품번호_후보": text(row.get("상품번호_후보")),
                "저작권자_전체": text(row.get("저작권자_전체")),
                "저작권자별_계좌매칭상태": " | ".join(
                    f"{holder}:{text(holder_by_name.get(holder, {}).get('계좌매칭상태'))}" for holder in holders
                ),
                "작가코드_전체": join_unique(
                    [text(holder_by_name.get(holder, {}).get("후보_작가코드")) for holder in holders]
                ),
                "예금주_전체": join_unique(
                    [text(holder_by_name.get(holder, {}).get("확정가능_예금주")) for holder in holders]
                ),
                "은행명_전체": join_unique(
                    [text(holder_by_name.get(holder, {}).get("확정가능_은행명")) for holder in holders]
                ),
                "계좌번호_전체": join_unique(
                    [text(holder_by_name.get(holder, {}).get("확정가능_계좌번호")) for holder in holders]
                ),
                "계약연결상태": text(row.get("계약연결상태")),
                "정산제외표시": text(row.get("정산제외표시")),
                "정산명_전체": text(row.get("정산명_전체")),
                "저작권정보_상이여부": text(row.get("저작권정보_상이여부")),
            }
        )
    return pd.DataFrame(rows)


def write_summary(path: Path, audit: pd.DataFrame, holder_map: pd.DataFrame, row_map: pd.DataFrame, cp: pd.DataFrame, details: pd.DataFrame) -> None:
    rows = [
        {"항목": "generated_at", "값": datetime.now().isoformat(timespec="seconds")},
        {"항목": "source_rows", "값": str(len(audit))},
        {"항목": "target_rows", "값": str(len(row_map))},
        {"항목": "unique_holders", "값": str(len(holder_map))},
        {"항목": "cp_list_rows", "값": str(len(cp))},
        {"항목": "detail_rows", "값": str(len(details))},
    ]
    for key, value in Counter(holder_map["계좌매칭상태"]).items():
        rows.append({"항목": f"저작권자기준.{key}", "값": str(value)})
    for key, value in Counter(row_map["CID계좌매칭상태"]).items():
        rows.append({"항목": f"CID행기준.{key}", "값": str(value)})
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    config = load_config(args)
    audit = pd.read_csv(args.audit_csv, encoding="utf-8-sig", dtype=str).fillna("")
    cp_list_path = Path(args.cp_list_csv)
    detail_path = Path(args.cp_detail_csv)

    from playwright.sync_api import sync_playwright

    if config.refresh_cp_list or not cp_list_path.exists():
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=config.headless)
            context = browser.new_context(ignore_https_errors=True, viewport={"width": 1400, "height": 900}, locale="ko-KR")
            page = context.new_page()
            page.set_default_timeout(config.timeout_ms)
            page.set_default_navigation_timeout(config.timeout_ms)
            login(page, config)
            page.goto(CP_LIST_URL, wait_until="domcontentloaded")
            cp = scrape_cp_list(page, cp_list_path)
            context.close()
            browser.close()
    else:
        cp = pd.read_csv(cp_list_path, encoding="utf-8-sig", dtype=str).fillna("")

    key_to_codes, _ = build_cp_index(cp)
    target = audit[audit["출판사비교상태"].isin(config.include_statuses)].copy()
    holder_names = sorted(
        {
            holder
            for value in target["저작권자_전체"].tolist()
            for holder in split_pipe(value)
            if holder and "등록된 저작권 정보" not in holder
        }
    )
    candidate_codes: set[str] = set()
    for holder in holder_names:
        codes, _ = find_candidate_codes(holder, cp, key_to_codes)
        candidate_codes.update(codes)
    sorted_codes = sorted(candidate_codes, key=lambda code: int(code) if code.isdigit() else code)
    print(f"[match] target_rows={len(target)} unique_holders={len(holder_names)} candidate_codes={len(sorted_codes)}", flush=True)

    if sorted_codes:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=config.headless)
            context = browser.new_context(ignore_https_errors=True, viewport={"width": 1400, "height": 900}, locale="ko-KR")
            page = context.new_page()
            page.set_default_timeout(config.timeout_ms)
            page.set_default_navigation_timeout(config.timeout_ms)
            login(page, config)
            page.goto(CP_LIST_URL, wait_until="domcontentloaded")
            details = fetch_details(page, sorted_codes, detail_path, config)
            context.close()
            browser.close()
    else:
        details = load_detail_snapshot(detail_path)

    holder_map = build_holder_mapping(audit, cp, details, config.include_statuses)
    row_map = build_row_mapping(audit, holder_map, config.include_statuses)
    holder_output = Path(args.holder_output)
    row_output = Path(args.row_output)
    summary_output = Path(args.summary_output)
    holder_output.parent.mkdir(parents=True, exist_ok=True)
    holder_map.to_csv(holder_output, index=False, encoding="utf-8-sig")
    row_map.to_csv(row_output, index=False, encoding="utf-8-sig")
    write_summary(summary_output, audit, holder_map, row_map, cp, details)

    print(f"holder_output={holder_output}")
    print(f"row_output={row_output}")
    print(f"summary_output={summary_output}")
    print(f"holder_status={dict(Counter(holder_map['계좌매칭상태']))}")
    print(f"row_status={dict(Counter(row_map['CID계좌매칭상태']))}")


if __name__ == "__main__":
    main()
