from __future__ import annotations

import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
SIAAN_PROJECT = ROOT.parent / "SIAAN Project"
WORK_DIR = ROOT / "담당자없는작품_재정리"
DEFAULT_ENV = SIAAN_PROJECT / ".env"
DEFAULT_INPUT = (
    WORK_DIR
    / "20260518_admin_ips_contractless_title_95plus__일치9175_account계좌매칭_CID행기준.csv"
)

ACCOUNT_HOME_URL = "http://account.barobook.com/"
MEMBER_LOGIN_URL = (
    "http://member.barobook.com/auth/Login?svcCD=0&redirectURL="
    "http%3A%2F%2Faccount.barobook.com%2F"
)
CPCPR_URL = (
    "http://account.barobook.com/CpMgr/CpCprShareMgr"
    "?key={cp_code}&code=&searchItem=0&searchString="
    "&page={page}&pageSize=1000&sortItem=0&sortMethod=0"
    "&isDuration=False&isAdvCpr=False&cpClCd=&tabIndex=3"
)
MAPPING_URL = (
    "http://account.barobook.com/Popup/CpCprMappProdList"
    "?cpCprShareRtSq={rights_code}&page={page}&pageSize=500"
)

TIMEOUT_MS = 30_000
REQ_TIMEOUT = 25
SPACE_RE = re.compile(r"\s+")
PAGE_RE = re.compile(r"[?&]page=(\d+)")
NUMBER_RE = re.compile(r"\d+")
NON_WORD_RE = re.compile(r"[^0-9A-Za-z가-힣]+")
SERIES_PREFIX_RE = re.compile(r"^[(\[]\s*연재\s*[)\]]\s*")
SERIES_TRAIL_NUM_UNIT_RE = re.compile(r"\s+\d+(?:-\d+)?\s*(?:화|권|회)(?:\s+완결)?\s*$")
SERIES_TRAIL_COMPLETION_RE = re.compile(r"\s+완결\s*$")


@dataclass(frozen=True)
class Config:
    input_path: Path
    output_dir: Path
    env_path: Path
    username: str
    password: str
    headless: bool
    limit_cp: int
    limit_rows: int
    workers: int


def text(value: Any) -> str:
    return SPACE_RE.sub(" ", str(value or "").replace("\u00a0", " ")).strip()


def compact(value: Any) -> str:
    return NON_WORD_RE.sub("", text(value)).lower()


def normalize_series(value: Any) -> str:
    current = text(value).replace("_", " ")
    for _ in range(5):
        before = current
        current = SERIES_PREFIX_RE.sub("", current)
        current = SERIES_TRAIL_NUM_UNIT_RE.sub("", current)
        current = SERIES_TRAIL_COMPLETION_RE.sub("", current)
        current = text(current).strip(" -_")
        if current == before:
            break
    return current


def normalize_publisher(value: Any) -> str:
    current = text(value)
    for token in (
        "㈜",
        "(주)",
        "（주）",
        "주식회사",
        "유한회사",
        "(유)",
        "도서출판",
        "출판사",
    ):
        current = current.replace(token, "")
    return compact(current)


def split_values(raw: Any) -> list[str]:
    if raw is None:
        return []
    parts = re.split(r"\s*[|;]\s*", str(raw))
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        cleaned = text(part)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def split_product_ids(raw: Any) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for part in split_values(raw):
        match = NUMBER_RE.search(part)
        if not match:
            continue
        product_id = match.group(0)
        if product_id in seen:
            continue
        seen.add(product_id)
        ids.append(product_id)
    return ids


def pipe_join(values: list[Any]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return " | ".join(ordered)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strict account copyright mapping audit for dummy-contract candidates.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(WORK_DIR))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--limit-cp", type=int, default=0)
    parser.add_argument("--limit-rows", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def load_config(args: argparse.Namespace) -> Config:
    env_path = Path(args.env_file)
    if not env_path.exists():
        raise FileNotFoundError(f"env 파일 없음: {env_path}")
    load_dotenv(env_path, override=True)
    username = (os.getenv("BAROBOOK_ID") or os.getenv("KLD_LOGIN_ID") or "").strip()
    password = (os.getenv("BAROBOOK_PW") or os.getenv("KLD_LOGIN_PW") or "").strip()
    if not username or not password:
        raise SystemExit("BAROBOOK_ID/BAROBOOK_PW 또는 KLD_LOGIN_ID/KLD_LOGIN_PW가 필요합니다.")
    return Config(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        env_path=env_path,
        username=username,
        password=password,
        headless=args.headless,
        limit_cp=args.limit_cp,
        limit_rows=args.limit_rows,
        workers=max(1, int(args.workers)),
    )


def login_and_make_session(config: Config) -> requests.Session:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless)
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1400, "height": 900},
            locale="ko-KR",
        )
        page = context.new_page()
        page.set_default_timeout(TIMEOUT_MS)
        page.set_default_navigation_timeout(TIMEOUT_MS)
        page.goto(ACCOUNT_HOME_URL, wait_until="domcontentloaded")
        try:
            page.wait_for_url(
                lambda url: "member.barobook.com" in str(url) and "/auth/Login" in str(url),
                timeout=TIMEOUT_MS,
            )
        except PlaywrightTimeoutError:
            page.goto(MEMBER_LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_selector("#MBR_ID", timeout=TIMEOUT_MS)
        page.fill("#MBR_ID", config.username)
        page.fill("#MBR_PWD", config.password)
        try:
            with page.expect_navigation(timeout=TIMEOUT_MS, wait_until="domcontentloaded"):
                page.locator("#MBR_PWD").press("Enter")
        except PlaywrightTimeoutError:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass
        if "/auth/login" in page.url.lower() or "member.barobook.com" in page.url.lower():
            browser.close()
            raise SystemExit(f"account 로그인 실패: {page.url}")

        cookies = context.cookies()
        browser.close()

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
        }
    )
    for cookie in cookies:
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain") or "",
            path=cookie.get("path") or "/",
        )

    resp = session.get("http://account.barobook.com/CpMgr/List", timeout=REQ_TIMEOUT)
    if resp.status_code >= 400 or "auth/Login" in resp.url or "MBR_ID" in resp.text:
        raise SystemExit(f"requests 세션 검증 실패: status={resp.status_code} url={resp.url}")
    return session


def clone_session(source: requests.Session) -> requests.Session:
    session = requests.Session()
    session.headers.update(source.headers)
    for cookie in source.cookies:
        session.cookies.set(
            cookie.name,
            cookie.value,
            domain=cookie.domain,
            path=cookie.path,
        )
    return session


def get_html(session: requests.Session, url: str) -> str:
    resp = session.get(url, timeout=REQ_TIMEOUT)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def max_page(soup: BeautifulSoup) -> int:
    pages = [1]
    for tag in soup.find_all(href=True):
        match = PAGE_RE.search(str(tag.get("href") or ""))
        if match:
            pages.append(int(match.group(1)))
    return max(pages)


def clean_cell(cell: Any) -> str:
    if cell is None:
        return ""
    for removable in cell.select("input[type='button'], button, a.button"):
        removable.extract()
    return text(cell.get_text(" ", strip=True))


def parse_copyright_table(html: str, cp_code: str) -> tuple[list[dict[str, str]], int]:
    soup = BeautifulSoup(html, "html.parser")
    target = None
    for table in soup.select("table.tbl_type, table"):
        table_text = text(table.get_text(" ", strip=True))
        if "저작권코드" in table_text and "저작권명" in table_text:
            target = table
            break
    if target is None:
        return [], max_page(soup)

    rows: list[dict[str, str]] = []
    for tr in target.select("tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        rights_code = clean_cell(tds[0])
        if not rights_code or not rights_code.isdigit():
            continue
        title_input = tds[1].find("input", id=re.compile(r"CP_CPR_SHARE_TITLE_"))
        rights_name = text(title_input.get("value") if title_input else clean_cell(tds[1]))
        b2c = tr.find("input", id=re.compile(r"B2C_SHARE_RT_"))
        b2bc = tr.find("input", id=re.compile(r"B2BC_SHARE_RT_"))
        b2b = tr.find("input", id=re.compile(r"B2B_SHARE_RT_"))
        rows.append(
            {
                "작가코드": cp_code,
                "account_저작권코드": rights_code,
                "account_저작권명": rights_name,
                "기본정산율여부": "Y" if rights_name == "기본정산율" else "",
                "B2C_정산율": text(b2c.get("value") if b2c else ""),
                "B2BC_정산율": text(b2bc.get("value") if b2bc else ""),
                "B2B_정산율": text(b2b.get("value") if b2b else ""),
                "선인세_원문": clean_cell(tds[3]),
            }
        )
    return rows, max_page(soup)


def parse_mapping_table(html: str, rights_code: str) -> tuple[list[dict[str, str]], int]:
    soup = BeautifulSoup(html, "html.parser")
    target = None
    for table in soup.select("table.tbl_type, table"):
        table_text = text(table.get_text(" ", strip=True))
        if "상품번호" in table_text and "제목" in table_text and "출판사" in table_text:
            target = table
            break
    if target is None:
        return [], max_page(soup)

    rows: list[dict[str, str]] = []
    for tr in target.select("tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        product_id = clean_cell(tds[0])
        if not product_id.isdigit():
            continue
        product_title = clean_cell(tds[1])
        rows.append(
            {
                "account_저작권코드": rights_code,
                "매핑_상품번호": product_id,
                "매핑_제목": product_title,
                "매핑_시리즈명": normalize_series(product_title),
                "매핑_저자": clean_cell(tds[2]),
                "매핑_출판사": clean_cell(tds[3]),
                "매핑_판매여부": clean_cell(tds[4]),
            }
        )
    return rows, max_page(soup)


def fetch_copyright_rows(session: requests.Session, cp_code: str) -> list[dict[str, str]]:
    all_rows: list[dict[str, str]] = []
    page = 1
    while True:
        html = get_html(session, CPCPR_URL.format(cp_code=cp_code, page=page))
        rows, last = parse_copyright_table(html, cp_code)
        all_rows.extend(rows)
        if page >= max(last, 1) or not rows:
            break
        page += 1
    return all_rows


def fetch_mapping_rows(session: requests.Session, rights_code: str) -> list[dict[str, str]]:
    all_rows: list[dict[str, str]] = []
    page = 1
    while True:
        html = get_html(session, MAPPING_URL.format(rights_code=rights_code, page=page))
        rows, last = parse_mapping_table(html, rights_code)
        all_rows.extend(rows)
        if page >= max(last, 1) or not rows:
            break
        page += 1
    return all_rows


def build_prefilter(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    audit_rows: list[dict[str, Any]] = []
    keep_indices: list[int] = []

    for idx, row in df.iterrows():
        reasons: list[str] = []
        holders = split_values(row.get("저작권자_전체"))
        cp_codes = split_values(row.get("작가코드_전체"))
        bank_accounts = split_values(row.get("계좌번호_전체"))
        banks = split_values(row.get("은행명_전체"))
        depositors = split_values(row.get("예금주_전체"))
        product_ids = split_product_ids(row.get("상품번호_후보"))

        if text(row.get("출판사비교상태")) != "일치":
            reasons.append("IPS_admin_출판사불일치")
        if text(row.get("계약연결상태")) != "정산행있음_계약ID없음":
            reasons.append("더미계약서_직접대상아님")
        if text(row.get("정산제외표시")) == "Y":
            reasons.append("정산제외")
        if len(holders) != 1:
            reasons.append(f"저작권자수_{len(holders)}")
        if text(row.get("거래처코드단일확정여부")) != "Y" or len(cp_codes) != 1:
            reasons.append(f"거래처코드수_{len(cp_codes)}")
        if not product_ids:
            reasons.append("후보상품번호없음")
        if len(bank_accounts) != 1 or len(banks) != 1 or len(depositors) != 1:
            reasons.append("계좌정보단일아님")
        if "account_unique" not in text(row.get("저작권자별_계좌매칭상태")):
            reasons.append("거래처매칭_account_unique아님")

        row_dict = row.to_dict()
        row_dict["저작권자수"] = str(len(holders))
        row_dict["거래처코드수"] = str(len(cp_codes))
        row_dict["후보상품수"] = str(len(product_ids))
        row_dict["감리단계"] = "1차필터"
        row_dict["제외사유"] = " | ".join(reasons)

        if reasons:
            audit_rows.append(row_dict)
        else:
            keep_indices.append(idx)

    return df.loc[keep_indices].copy(), pd.DataFrame(audit_rows)


def evaluate_mapping(row: pd.Series, product_to_mapping: dict[str, list[dict[str, str]]]) -> tuple[str, dict[str, str]]:
    product_ids = split_product_ids(row.get("상품번호_후보"))
    hits_by_product = {pid: product_to_mapping.get(pid, []) for pid in product_ids}
    hit_products = [pid for pid, hits in hits_by_product.items() if hits]
    all_hits = [hit for hits in hits_by_product.values() for hit in hits]

    if not all_hits:
        return "후보상품번호_매핑없음", {
            "매핑된_후보상품번호": "",
            "미매핑_후보상품번호": pipe_join(product_ids),
        }

    if len(hit_products) != len(product_ids):
        return "후보상품번호_일부만매핑", {
            "매핑된_후보상품번호": pipe_join(hit_products),
            "미매핑_후보상품번호": pipe_join([pid for pid in product_ids if pid not in hit_products]),
        }

    rights_codes = sorted({text(hit.get("account_저작권코드")) for hit in all_hits if text(hit.get("account_저작권코드"))})
    if len(rights_codes) != 1:
        return "매핑저작권코드_복수", {
            "매핑된_후보상품번호": pipe_join(hit_products),
            "미매핑_후보상품번호": "",
            "account_저작권코드": pipe_join(rights_codes),
        }

    ips_pub = normalize_publisher(row.get("IPS_출판사"))
    admin_pubs = [normalize_publisher(value) for value in split_values(row.get("admin_출판사목록"))]
    publisher_bad: list[str] = []
    for hit in all_hits:
        mapped_pub = normalize_publisher(hit.get("매핑_출판사"))
        if mapped_pub and ips_pub and mapped_pub != ips_pub and mapped_pub not in admin_pubs:
            publisher_bad.append(text(hit.get("매핑_출판사")))
    if publisher_bad:
        return "매핑도서_출판사불일치", {
            "매핑된_후보상품번호": pipe_join(hit_products),
            "미매핑_후보상품번호": "",
            "매핑_출판사": pipe_join(publisher_bad),
        }

    first = all_hits[0]
    return "확정", {
        "매핑된_후보상품번호": pipe_join(hit_products),
        "미매핑_후보상품번호": "",
        "account_저작권코드": rights_codes[0],
        "매핑_상품번호": pipe_join([hit.get("매핑_상품번호") for hit in all_hits]),
        "매핑_제목": pipe_join([hit.get("매핑_제목") for hit in all_hits]),
        "매핑_시리즈명": pipe_join([hit.get("매핑_시리즈명") for hit in all_hits]),
        "매핑_저자": pipe_join([hit.get("매핑_저자") for hit in all_hits]),
        "매핑_출판사": pipe_join([hit.get("매핑_출판사") for hit in all_hits]),
        "매핑_판매여부": pipe_join([hit.get("매핑_판매여부") for hit in all_hits]),
        "매핑검증_근거": (
            "단일저작권자+단일거래처+단일계좌+후보상품번호전부_동일account저작권코드_매핑"
        ),
        "_first_rights_code": text(first.get("account_저작권코드")),
    }


def main() -> None:
    args = parse_args()
    config = load_config(args)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(config.input_path, encoding="utf-8-sig", dtype=str).fillna("")
    if config.limit_rows:
        df = df.head(config.limit_rows).copy()
    print(f"[input] rows={len(df)} file={config.input_path}")

    candidates, pre_excluded = build_prefilter(df)
    if config.limit_cp:
        allowed_cp = set(split_values("|".join(candidates["작가코드_전체"].head(config.limit_cp).tolist())))
        candidates = candidates[candidates["작가코드_전체"].map(lambda raw: bool(set(split_values(raw)) & allowed_cp))].copy()
    cp_codes = sorted(
        {split_values(raw)[0] for raw in candidates["작가코드_전체"].tolist() if split_values(raw)},
        key=lambda value: int(value) if value.isdigit() else 10**18,
    )
    print(f"[filter] strict pre-mapping rows={len(candidates)} cp_codes={len(cp_codes)}")

    session = login_and_make_session(config)
    print("[login] account session ok")

    copyright_rows: list[dict[str, str]] = []
    cp_failures: dict[str, str] = {}
    for index, cp_code in enumerate(cp_codes, start=1):
        started = time.time()
        try:
            rows = fetch_copyright_rows(session, cp_code)
            copyright_rows.extend(rows)
            status = f"rights={len(rows)}"
        except Exception as exc:  # noqa: BLE001
            cp_failures[cp_code] = str(exc)
            status = f"FAIL {exc}"
        if index % 10 == 0 or index == len(cp_codes):
            print(f"[rights {index}/{len(cp_codes)}] cp={cp_code} {status} {time.time()-started:.1f}s", flush=True)

    rights_by_code = {row["account_저작권코드"]: row for row in copyright_rows}
    rights_codes = sorted(
        rights_by_code.keys(),
        key=lambda value: int(value) if value.isdigit() else 10**18,
    )
    print(f"[rights] rows={len(copyright_rows)} unique_rights={len(rights_codes)} failures={len(cp_failures)}")

    product_to_mapping: dict[str, list[dict[str, str]]] = {}
    rights_failures: dict[str, str] = {}

    def fetch_mapping_job(rights_code: str) -> tuple[str, list[dict[str, str]], float, str]:
        started = time.time()
        try:
            rows = fetch_mapping_rows(clone_session(session), rights_code)
            return rights_code, rows, time.time() - started, ""
        except Exception as exc:  # noqa: BLE001
            return rights_code, [], time.time() - started, str(exc)

    print(f"[mapping] workers={config.workers}", flush=True)
    with ThreadPoolExecutor(max_workers=config.workers) as executor:
        futures = [executor.submit(fetch_mapping_job, rights_code) for rights_code in rights_codes]
        for index, future in enumerate(as_completed(futures), start=1):
            rights_code, rows, elapsed, error = future.result()
            if error:
                rights_failures[rights_code] = error
                status = f"FAIL {error}"
            else:
                rights_meta = rights_by_code.get(rights_code, {})
                for item in rows:
                    item.update(
                        {
                            "작가코드": text(rights_meta.get("작가코드")),
                            "account_저작권명": text(rights_meta.get("account_저작권명")),
                            "기본정산율여부": text(rights_meta.get("기본정산율여부")),
                            "B2C_정산율": text(rights_meta.get("B2C_정산율")),
                            "B2BC_정산율": text(rights_meta.get("B2BC_정산율")),
                            "B2B_정산율": text(rights_meta.get("B2B_정산율")),
                        }
                    )
                    product_to_mapping.setdefault(text(item.get("매핑_상품번호")), []).append(item)
                status = f"products={len(rows)}"
            print(
                f"[mapping {index}/{len(rights_codes)}] rights={rights_code} {status} {elapsed:.1f}s",
                flush=True,
            )

    confirmed_rows: list[dict[str, Any]] = []
    mapping_excluded_rows: list[dict[str, Any]] = []
    for _, row in candidates.iterrows():
        cp_code = split_values(row.get("작가코드_전체"))[0]
        if cp_code in cp_failures:
            reason = "거래처_저작권코드조회실패"
            extra = {"조회실패": cp_failures[cp_code]}
        else:
            reason, extra = evaluate_mapping(row, product_to_mapping)

        row_dict = row.to_dict()
        row_dict["저작권자수"] = "1"
        row_dict["거래처코드수"] = "1"
        row_dict["후보상품수"] = str(len(split_product_ids(row.get("상품번호_후보"))))
        row_dict.update({key: value for key, value in extra.items() if not key.startswith("_")})

        rights_code = text(extra.get("_first_rights_code") or extra.get("account_저작권코드"))
        rights_meta = rights_by_code.get(rights_code, {})
        if rights_meta:
            row_dict.update(
                {
                    "account_저작권코드": rights_code,
                    "account_저작권명": text(rights_meta.get("account_저작권명")),
                    "기본정산율여부": text(rights_meta.get("기본정산율여부")),
                    "B2C_정산율": text(rights_meta.get("B2C_정산율")),
                    "B2BC_정산율": text(rights_meta.get("B2BC_정산율")),
                    "B2B_정산율": text(rights_meta.get("B2B_정산율")),
                    "선인세_원문": text(rights_meta.get("선인세_원문")),
                }
            )

        if reason == "확정":
            row_dict["감리결과"] = "더미계약서_명확후보"
            confirmed_rows.append(row_dict)
        else:
            row_dict["감리단계"] = "저작권매핑"
            row_dict["제외사유"] = reason
            mapping_excluded_rows.append(row_dict)

    confirmed = pd.DataFrame(confirmed_rows)
    excluded = pd.concat(
        [pre_excluded, pd.DataFrame(mapping_excluded_rows)],
        ignore_index=True,
        sort=False,
    ).fillna("")

    base_name = "20260518_dummy_contract_진짜명확"
    confirmed_path = config.output_dir / f"{base_name}.csv"
    excluded_path = config.output_dir / f"{base_name}__제외사유.csv"
    summary_path = config.output_dir / f"{base_name}__summary.csv"

    preferred_columns = [
        "감리결과",
        "콘텐츠ID",
        "IPS_콘텐츠명",
        "IPS_작가필명",
        "IPS_담당부서",
        "IPS_담당자명",
        "IPS_출판사",
        "admin_출판사목록",
        "상품번호_후보",
        "후보상품수",
        "매핑된_후보상품번호",
        "account_저작권코드",
        "account_저작권명",
        "작가코드_전체",
        "저작권자_전체",
        "예금주_전체",
        "은행명_전체",
        "계좌번호_전체",
        "정산명_전체",
        "B2C_정산율",
        "B2BC_정산율",
        "B2B_정산율",
        "매핑_제목",
        "매핑_시리즈명",
        "매핑_저자",
        "매핑_출판사",
        "매핑_판매여부",
        "계약연결상태",
        "매핑검증_근거",
        "저작권정보_상이여부",
    ]
    if confirmed.empty:
        confirmed = pd.DataFrame(columns=preferred_columns)
    else:
        remaining = [col for col in confirmed.columns if col not in preferred_columns]
        confirmed = confirmed[[col for col in preferred_columns if col in confirmed.columns] + remaining]

    exclude_columns = [
        "감리단계",
        "제외사유",
        "콘텐츠ID",
        "IPS_콘텐츠명",
        "IPS_작가필명",
        "IPS_출판사",
        "admin_출판사목록",
        "상품번호_후보",
        "후보상품수",
        "매핑된_후보상품번호",
        "미매핑_후보상품번호",
        "account_저작권코드",
        "account_저작권명",
        "작가코드_전체",
        "거래처코드수",
        "저작권자_전체",
        "저작권자수",
        "예금주_전체",
        "은행명_전체",
        "계좌번호_전체",
        "계약연결상태",
        "정산제외표시",
        "정산명_전체",
        "저작권정보_상이여부",
    ]
    if excluded.empty:
        excluded = pd.DataFrame(columns=exclude_columns)
    else:
        remaining = [col for col in excluded.columns if col not in exclude_columns]
        excluded = excluded[[col for col in exclude_columns if col in excluded.columns] + remaining]

    confirmed.to_csv(confirmed_path, index=False, encoding="utf-8-sig")
    excluded.to_csv(excluded_path, index=False, encoding="utf-8-sig")

    summary_rows = [
        {"항목": "입력행", "값": len(df)},
        {"항목": "1차_명확후보", "값": len(candidates)},
        {"항목": "조회_거래처코드", "값": len(cp_codes)},
        {"항목": "조회_저작권코드", "값": len(rights_codes)},
        {"항목": "저작권코드조회실패_거래처", "값": len(cp_failures)},
        {"항목": "매핑도서조회실패_저작권코드", "값": len(rights_failures)},
        {"항목": "최종_더미계약서_명확후보", "값": len(confirmed)},
        {"항목": "최종_제외", "값": len(excluded)},
        {"항목": "최종_명확후보_고유거래처", "값": confirmed["작가코드_전체"].nunique() if len(confirmed) else 0},
        {"항목": "최종_명확후보_고유저작권코드", "값": confirmed["account_저작권코드"].nunique() if len(confirmed) else 0},
    ]
    for reason, count in excluded["제외사유"].value_counts().items() if len(excluded) else []:
        summary_rows.append({"항목": f"제외사유::{reason}", "값": int(count)})
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("")
    print("=== 엄격 명확 후보 감리 완료 ===")
    print(f"confirmed : {len(confirmed)} -> {confirmed_path}")
    print(f"excluded  : {len(excluded)} -> {excluded_path}")
    print(f"summary   : {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
