"""Attach Barobook admin copyright info to the contractless title match CSV.

The source CSV contains semicolon-delimited admin product candidates.  This
script logs in to admin.barobook.com once with the existing Barobook env
credentials, reuses the resulting cookies for direct HTTP requests, and records
copyright info for every candidate product code.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parent
ADMIN_PROJECT_ROOT = PROJECT_ROOT.parent / "SIAAN Project"
if str(ADMIN_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(ADMIN_PROJECT_ROOT))

from admin_login import (  # noqa: E402
    PASSWORD_SELECTORS,
    USERNAME_SELECTORS,
    load_config_from_args,
    looks_like_login_page,
    try_fill_first,
    try_submit,
)


WORK_DIR = PROJECT_ROOT / "담당자없는작품_재정리"
DEFAULT_SOURCE_CSV = (
    WORK_DIR
    / "20260518_admin_ips_contractless_title_95plus__정산정보없음포함_사용안함제외.csv"
)
DEFAULT_EDGE_CSV = (
    WORK_DIR
    / "20260518_admin_ips_contractless_title_95plus__정산정보없음포함_사용안함제외_edges.csv"
)

ADMIN_BASE_URL = "http://admin.barobook.com"
DETAIL_URL = ADMIN_BASE_URL + "/ProdMgr/ViewDetail?key={code}"
ENDPOINTS = {
    "serial": ADMIN_BASE_URL + "/ProdMgr/ViewDetailSerialAdditionalInfo?key={code}",
    "onevolume": ADMIN_BASE_URL + "/ProdMgr/ViewDetailOneVolumeAdditionalInfo?key={code}",
    "package": ADMIN_BASE_URL + "/ProdMgr/ViewDetailPackageAdditionalInfo?key={code}",
}
NO_COPYRIGHT_TEXT = "등록된 저작권 정보가 없습니다."

_THREAD_LOCAL = threading.local()


@dataclass(frozen=True)
class ProductTask:
    code: str
    product_type: str


@dataclass
class ProductResult:
    상품번호: str
    상품유형: str
    조회상태: str
    endpoint_사용: str
    http_status: str
    저작권정보: str
    저작권정보_확인값: str
    저작권자: str
    정산명: str
    자체정산율: str
    제휴정산율: str
    B2B정산율: str
    detail_url: str
    additional_url: str
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", default=str(DEFAULT_SOURCE_CSV))
    parser.add_argument("--edge-csv", default=str(DEFAULT_EDGE_CSV))
    parser.add_argument("--env-file", default="")
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--output-prefix", default="")
    return parser.parse_args()


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def split_codes(value: Any) -> list[str]:
    raw = norm(value)
    if not raw:
        return []
    pieces = re.split(r"\s*(?:;|\|\|?|\n|,)\s*", raw)
    out: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        code = norm(piece)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def unique_join(values: list[str], sep: str = " | ") -> str:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = norm(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return sep.join(out)


def preferred_endpoint_names(product_type: str) -> list[str]:
    kind = norm(product_type)
    if "단권" in kind:
        preferred = ["onevolume", "serial", "package"]
    elif "패키지" in kind or "1+1" in kind:
        preferred = ["package", "serial", "onevolume"]
    else:
        preferred = ["serial", "onevolume", "package"]
    out: list[str] = []
    for name in preferred:
        if name not in out:
            out.append(name)
    return out


def load_product_type_map(edge_csv: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    if not edge_csv.exists():
        return {}, {}
    edge_df = pd.read_csv(edge_csv, dtype=str, encoding="utf-8-sig").fillna("")
    mapping: dict[str, str] = {}
    conflicts: dict[str, list[str]] = {}
    seen_types: dict[str, set[str]] = defaultdict(set)
    for _, row in edge_df.iterrows():
        code = norm(row.get("상품번호"))
        product_type = norm(row.get("상품유형"))
        if not code:
            continue
        if product_type:
            seen_types[code].add(product_type)
        if code not in mapping:
            mapping[code] = product_type
    for code, types in seen_types.items():
        if len(types) > 1:
            conflicts[code] = sorted(types)
    return mapping, conflicts


def get_admin_cookies(env_file: str, timeout_ms: int = 30_000) -> list[dict[str, Any]]:
    login_args = argparse.Namespace(
        env_file=env_file,
        base_url=ADMIN_BASE_URL,
        headless=True,
        timeout_ms=timeout_ms,
        probe_only=False,
    )
    config = load_config_from_args(login_args)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--disable-web-security"],
        )
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1600, "height": 1000},
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        page.set_default_navigation_timeout(timeout_ms)

        page.goto(config.base_url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:  # noqa: BLE001
            pass

        if looks_like_login_page(page.url, page.content()):
            user_selector = try_fill_first(page, USERNAME_SELECTORS, config.username)
            password_selector = try_fill_first(page, PASSWORD_SELECTORS, config.password)
            _ = user_selector
            try_submit(page, password_selector)
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:  # noqa: BLE001
                pass

        html = page.content()
        if looks_like_login_page(page.url, html):
            raise RuntimeError(f"admin 로그인 실패: url={page.url}")

        cookies = context.cookies()
        context.close()
        browser.close()

    return cookies


def _session_from_cookies(cookies: list[dict[str, Any]]) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148 Safari/537.36"
            ),
            "Referer": ADMIN_BASE_URL + "/",
        }
    )
    for cookie in cookies:
        domain = cookie.get("domain") or "admin.barobook.com"
        if "barobook" not in domain:
            continue
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=domain,
            path=cookie.get("path") or "/",
        )
    return session


def thread_session(cookies: list[dict[str, Any]]) -> requests.Session:
    session = getattr(_THREAD_LOCAL, "session", None)
    if session is None:
        session = _session_from_cookies(cookies)
        _THREAD_LOCAL.session = session
    return session


def extract_copyright_row(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.select("tr"):
        cells = [norm(cell.get_text(" ", strip=True)) for cell in tr.select("th,td")]
        if not cells:
            continue
        if cells[0] == "저작권 정보" or cells[0].startswith("저작권 정보"):
            value = norm(cells[1] if len(cells) > 1 else "")
            return value, value
    text = norm(soup.get_text(" ", strip=True))
    return "", text[:300]


def parse_copyright_info(value: str) -> dict[str, str]:
    text = norm(value)
    if not text or NO_COPYRIGHT_TEXT in text:
        return {
            "저작권자": "",
            "정산명": "",
            "자체정산율": "",
            "제휴정산율": "",
            "B2B정산율": "",
        }

    holder = ""
    settlement_name = ""
    # Separator in Barobook is " - ".  Copyright-holder names themselves can
    # contain hyphens, for example "AP북스-안성서(선인세)".
    m = re.match(r"^(?P<holder>.*?)\s+-\s+(?P<name>.*?)\s*:\s*\(", text)
    if m:
        holder = norm(m.group("holder"))
        settlement_name = norm(m.group("name"))
    else:
        m = re.match(r"^(?P<holder>.*?)\s+-\s+(?P<name>.*)$", text)
        if m:
            holder = norm(m.group("holder"))
            settlement_name = norm(m.group("name"))

    def ratio(label: str) -> str:
        match = re.search(rf"{re.escape(label)}\s*:\s*([0-9.]+%)", text, flags=re.I)
        return match.group(1) if match else ""

    return {
        "저작권자": holder,
        "정산명": settlement_name,
        "자체정산율": ratio("자체"),
        "제휴정산율": ratio("제휴"),
        "B2B정산율": ratio("B2B"),
    }


def fetch_url(
    session: requests.Session,
    url: str,
    *,
    timeout: float,
    retries: int = 2,
) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code >= 500 and attempt < retries:
                time.sleep(0.4 * (attempt + 1))
                continue
            return response
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(str(last_exc))


def fetch_product(
    task: ProductTask,
    *,
    cookies: list[dict[str, Any]],
    timeout: float,
) -> ProductResult:
    session = thread_session(cookies)
    endpoint_names = preferred_endpoint_names(task.product_type)
    fallback_result: ProductResult | None = None

    for endpoint_name in endpoint_names:
        url = ENDPOINTS[endpoint_name].format(code=task.code)
        try:
            response = fetch_url(session, url, timeout=timeout)
            html = response.text
            if "auth/Login" in html or "top.location.href" in html:
                result = ProductResult(
                    상품번호=task.code,
                    상품유형=task.product_type,
                    조회상태="로그인필요",
                    endpoint_사용=endpoint_name,
                    http_status=str(response.status_code),
                    저작권정보="",
                    저작권정보_확인값="",
                    저작권자="",
                    정산명="",
                    자체정산율="",
                    제휴정산율="",
                    B2B정산율="",
                    detail_url=DETAIL_URL.format(code=task.code),
                    additional_url=url,
                )
                return result
            if response.status_code != 200:
                if fallback_result is None:
                    fallback_result = ProductResult(
                        상품번호=task.code,
                        상품유형=task.product_type,
                        조회상태="HTTP_ERROR",
                        endpoint_사용=endpoint_name,
                        http_status=str(response.status_code),
                        저작권정보="",
                        저작권정보_확인값="",
                        저작권자="",
                        정산명="",
                        자체정산율="",
                        제휴정산율="",
                        B2B정산율="",
                        detail_url=DETAIL_URL.format(code=task.code),
                        additional_url=url,
                        error=response.reason,
                    )
                continue

            copyright_value, evidence_text = extract_copyright_row(html)
            parsed = parse_copyright_info(copyright_value)
            has_real_info = bool(copyright_value) and NO_COPYRIGHT_TEXT not in copyright_value
            status = "OK" if has_real_info else "저작권정보없음" if copyright_value else "저작권행없음"
            result = ProductResult(
                상품번호=task.code,
                상품유형=task.product_type,
                조회상태=status,
                endpoint_사용=endpoint_name,
                http_status=str(response.status_code),
                저작권정보=copyright_value if has_real_info else "",
                저작권정보_확인값=copyright_value or evidence_text,
                저작권자=parsed["저작권자"],
                정산명=parsed["정산명"],
                자체정산율=parsed["자체정산율"],
                제휴정산율=parsed["제휴정산율"],
                B2B정산율=parsed["B2B정산율"],
                detail_url=DETAIL_URL.format(code=task.code),
                additional_url=url,
            )
            if has_real_info:
                return result
            if fallback_result is None or result.조회상태 == "저작권정보없음":
                fallback_result = result
        except Exception as exc:  # noqa: BLE001
            if fallback_result is None:
                fallback_result = ProductResult(
                    상품번호=task.code,
                    상품유형=task.product_type,
                    조회상태="REQUEST_ERROR",
                    endpoint_사용=endpoint_name,
                    http_status="",
                    저작권정보="",
                    저작권정보_확인값="",
                    저작권자="",
                    정산명="",
                    자체정산율="",
                    제휴정산율="",
                    B2B정산율="",
                    detail_url=DETAIL_URL.format(code=task.code),
                    additional_url=url,
                    error=str(exc),
                )

    return fallback_result or ProductResult(
        상품번호=task.code,
        상품유형=task.product_type,
        조회상태="UNKNOWN",
        endpoint_사용="",
        http_status="",
        저작권정보="",
        저작권정보_확인값="",
        저작권자="",
        정산명="",
        자체정산율="",
        제휴정산율="",
        B2B정산율="",
        detail_url=DETAIL_URL.format(code=task.code),
        additional_url="",
    )


def build_tasks(source_df: pd.DataFrame, type_map: dict[str, str]) -> list[ProductTask]:
    seen: set[str] = set()
    tasks: list[ProductTask] = []
    for _, row in source_df.iterrows():
        for code in split_codes(row.get("상품번호_후보")):
            if code in seen:
                continue
            seen.add(code)
            tasks.append(ProductTask(code=code, product_type=type_map.get(code, "")))
    return tasks


def attach_to_rows(source_df: pd.DataFrame, product_results: dict[str, ProductResult]) -> pd.DataFrame:
    out = source_df.copy()
    additions: dict[str, list[str]] = defaultdict(list)

    for _, row in source_df.iterrows():
        codes = split_codes(row.get("상품번호_후보"))
        results = [product_results[code] for code in codes if code in product_results]
        real_results = [res for res in results if res.저작권정보]
        no_info_results = [res for res in results if res.조회상태 == "저작권정보없음"]
        failed_results = [
            res
            for res in results
            if res.조회상태 not in {"OK", "저작권정보없음"}
        ]

        productwise_parts: list[str] = []
        for res in results:
            shown = res.저작권정보 or res.저작권정보_확인값 or res.조회상태
            productwise_parts.append(f"{res.상품번호}:{shown}")

        additions["저작권정보_상품별"].append(" || ".join(productwise_parts))
        additions["저작권정보_전체"].append(unique_join([res.저작권정보 for res in real_results], " || "))
        additions["저작권자_전체"].append(unique_join([res.저작권자 for res in real_results]))
        additions["정산명_전체"].append(unique_join([res.정산명 for res in real_results]))
        additions["자체정산율_전체"].append(unique_join([res.자체정산율 for res in real_results]))
        additions["제휴정산율_전체"].append(unique_join([res.제휴정산율 for res in real_results]))
        additions["B2B정산율_전체"].append(unique_join([res.B2B정산율 for res in real_results]))
        additions["저작권정보_상품코드수"].append(str(len(codes)))
        additions["저작권정보_실정보상품코드수"].append(str(len(real_results)))
        additions["저작권정보_없음상품코드수"].append(str(len(no_info_results)))
        additions["저작권정보_조회실패상품코드"].append(
            " | ".join(f"{res.상품번호}:{res.조회상태}" for res in failed_results)
        )
        additions["저작권정보_상이여부"].append(
            "Y" if len({res.저작권정보 for res in real_results if res.저작권정보}) > 1 else ""
        )

    for column, values in additions.items():
        out[column] = values
    return out


def main() -> int:
    args = parse_args()
    source_csv = Path(args.source_csv)
    edge_csv = Path(args.edge_csv)
    if not source_csv.exists():
        raise FileNotFoundError(source_csv)

    source_df = pd.read_csv(source_csv, dtype=str, encoding="utf-8-sig").fillna("")
    type_map, type_conflicts = load_product_type_map(edge_csv)
    tasks = build_tasks(source_df, type_map)
    if args.limit:
        tasks = tasks[: args.limit]

    print(f"[copyright] source rows      = {len(source_df)}")
    print(f"[copyright] product tasks    = {len(tasks)}")
    print(f"[copyright] type conflicts   = {len(type_conflicts)}")
    print(f"[copyright] workers          = {args.workers}")
    print("[copyright] logging in to admin.barobook.com ...", flush=True)
    cookies = get_admin_cookies(args.env_file)
    cookie_names = sorted({cookie.get("name", "") for cookie in cookies if "barobook" in cookie.get("domain", "")})
    print(f"[copyright] login OK, cookies = {cookie_names}", flush=True)

    started = time.time()
    results: dict[str, ProductResult] = {}
    status_counter: Counter[str] = Counter()

    with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(fetch_product, task, cookies=cookies, timeout=args.timeout): task
            for task in tasks
        }
        for index, future in enumerate(cf.as_completed(futures), start=1):
            task = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                result = ProductResult(
                    상품번호=task.code,
                    상품유형=task.product_type,
                    조회상태="UNHANDLED_ERROR",
                    endpoint_사용="",
                    http_status="",
                    저작권정보="",
                    저작권정보_확인값="",
                    저작권자="",
                    정산명="",
                    자체정산율="",
                    제휴정산율="",
                    B2B정산율="",
                    detail_url=DETAIL_URL.format(code=task.code),
                    additional_url="",
                    error=str(exc),
                )
            results[result.상품번호] = result
            status_counter[result.조회상태] += 1
            if index % 500 == 0 or index == len(tasks):
                elapsed = time.time() - started
                rate = index / elapsed if elapsed else 0
                print(
                    f"[copyright] {index}/{len(tasks)} done "
                    f"({rate:.1f}/s) status={dict(status_counter)}",
                    flush=True,
                )

    if args.limit:
        # In sample mode, keep rows whose candidate product was fetched and leave
        # other candidate codes blank rather than pretending they were checked.
        sample_codes = set(results)
        sample_df = source_df[
            source_df["상품번호_후보"].apply(lambda value: any(code in sample_codes for code in split_codes(value)))
        ].copy()
        attach_df = attach_to_rows(sample_df, results)
    else:
        attach_df = attach_to_rows(source_df, results)

    product_df = pd.DataFrame([asdict(results[code]) for code in sorted(results, key=lambda x: int(x) if x.isdigit() else x)])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = args.output_prefix.strip() or source_csv.with_suffix("").name
    suffix = "_sample" if args.limit else ""
    row_out = source_csv.with_name(f"{prefix}__저작권정보부착{suffix}.csv")
    product_out = source_csv.with_name(f"{prefix}__저작권정보_상품별{suffix}.csv")
    edge_out = source_csv.with_name(f"{prefix}__edges_저작권정보부착{suffix}.csv")
    summary_out = source_csv.with_name(f"{prefix}__저작권정보부착{suffix}_summary.csv")

    attach_df.to_csv(row_out, index=False, encoding="utf-8-sig")
    product_df.to_csv(product_out, index=False, encoding="utf-8-sig")

    if edge_csv.exists():
        edge_df = pd.read_csv(edge_csv, dtype=str, encoding="utf-8-sig").fillna("")
        merged_edge_df = edge_df.merge(product_df, on=["상품번호", "상품유형"], how="left")
        merged_edge_df.to_csv(edge_out, index=False, encoding="utf-8-sig")
    else:
        edge_out = Path("")

    row_status = Counter()
    for value in attach_df["저작권정보_실정보상품코드수"]:
        row_status["rows_with_real_info" if int(value or 0) > 0 else "rows_without_real_info"] += 1
    row_status["rows_with_different_infos"] = int((attach_df["저작권정보_상이여부"] == "Y").sum())

    summary_rows: list[dict[str, str]] = [
        {"항목": "created_at", "값": datetime.now().isoformat(timespec="seconds")},
        {"항목": "source_csv", "값": str(source_csv)},
        {"항목": "edge_csv", "값": str(edge_csv)},
        {"항목": "row_output_csv", "값": str(row_out)},
        {"항목": "product_output_csv", "값": str(product_out)},
        {"항목": "edge_output_csv", "값": str(edge_out) if str(edge_out) else ""},
        {"항목": "source_rows", "값": str(len(source_df))},
        {"항목": "output_rows", "값": str(len(attach_df))},
        {"항목": "product_tasks", "값": str(len(tasks))},
        {"항목": "elapsed_seconds", "값": str(round(time.time() - started, 2))},
        {"항목": "timestamp", "값": timestamp},
    ]
    summary_rows.extend(
        {"항목": f"product_status_counts.{key}", "값": str(value)}
        for key, value in status_counter.items()
    )
    summary_rows.extend(
        {"항목": f"row_status_counts.{key}", "값": str(value)}
        for key, value in row_status.items()
    )
    summary_rows.append({"항목": "type_conflict_count", "값": str(len(type_conflicts))})
    pd.DataFrame(summary_rows).to_csv(summary_out, index=False, encoding="utf-8-sig")

    print("")
    print("=== 저작권 정보 부착 완료 ===")
    print(f"row output     : {row_out}")
    print(f"product output : {product_out}")
    if str(edge_out):
        print(f"edge output    : {edge_out}")
    print(f"summary        : {summary_out}")
    print(f"product status : {dict(status_counter)}")
    print(f"row status     : {dict(row_status)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
