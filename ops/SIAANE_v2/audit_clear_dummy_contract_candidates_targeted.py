from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd

import audit_clear_dummy_contract_candidates as base


ROOT = Path(__file__).resolve().parent
WORK_DIR = ROOT / "담당자없는작품_재정리"
DEFAULT_INPUT = (
    WORK_DIR
    / "20260518_admin_ips_contractless_title_95plus__일치9175_account계좌매칭_CID행기준.csv"
)
DEFAULT_DETAIL = (
    WORK_DIR
    / "20260518_admin_ips_contractless_title_95plus__정산정보없음포함_사용안함제외__저작권정보부착.csv"
)
SEARCH_URL = (
    "http://account.barobook.com/Popup/CpCprMappProdList"
    "?page={page}&SearchItem=0&SearchString={term}&SortItem=0&SortMethod=1"
    "&PageSize=500&CpCPrShareRtSQ={rights_code}"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Targeted strict audit using account mapping-book title search.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--detail", default=str(DEFAULT_DETAIL))
    parser.add_argument("--output-dir", default=str(WORK_DIR))
    parser.add_argument("--env-file", default=str(base.DEFAULT_ENV))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit-rows", type=int, default=0)
    return parser.parse_args()


def title_terms(row: pd.Series) -> list[str]:
    raw_values: list[Any] = [
        row.get("IPS_콘텐츠명"),
        row.get("IPS_정제제목"),
    ]
    for col in ["어드민_제목_후보", "어드민_정제제목_후보"]:
        raw_values.extend(base.split_values(row.get(col)))

    terms: list[str] = []
    for raw in raw_values:
        cleaned = base.text(raw)
        if not cleaned:
            continue
        for candidate in [cleaned, base.normalize_series(cleaned)]:
            candidate = base.text(candidate).strip("[]() ")
            if len(base.compact(candidate)) < 2:
                continue
            if candidate not in terms:
                terms.append(candidate)
    return terms[:8]


def search_mapping(session: Any, rights_code: str, term: str) -> list[dict[str, str]]:
    encoded = urllib.parse.quote(term)
    rows: list[dict[str, str]] = []
    page = 1
    while True:
        html = base.get_html(
            session,
            SEARCH_URL.format(rights_code=rights_code, term=encoded, page=page),
        )
        page_rows, last = base.parse_mapping_table(html, rights_code)
        rows.extend(page_rows)
        if page >= max(last, 1) or not page_rows:
            break
        page += 1
    return rows


def dedupe_hits(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for row in rows:
        key = (base.text(row.get("account_저작권코드")), base.text(row.get("매핑_상품번호")))
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def evaluate_row(
    row: pd.Series,
    *,
    rights_codes: list[str],
    search_results: dict[tuple[str, str], list[dict[str, str]]],
    rights_by_code: dict[str, dict[str, str]],
) -> tuple[str, dict[str, str]]:
    product_ids = base.split_product_ids(row.get("상품번호_후보"))
    terms = base.split_values(row.get("__search_terms"))
    product_hits: dict[str, list[dict[str, str]]] = {pid: [] for pid in product_ids}

    for rights_code in rights_codes:
        for term in terms:
            for hit in search_results.get((rights_code, term), []):
                product_id = base.text(hit.get("매핑_상품번호"))
                if product_id in product_hits:
                    product_hits[product_id].append(hit)

    for product_id in list(product_hits):
        product_hits[product_id] = dedupe_hits(product_hits[product_id])

    hit_products = [pid for pid, hits in product_hits.items() if hits]
    all_hits = [hit for hits in product_hits.values() for hit in hits]
    if not all_hits:
        return "후보상품번호_검색매핑없음", {
            "검색어_사용": base.pipe_join(terms),
            "매핑된_후보상품번호": "",
            "미매핑_후보상품번호": base.pipe_join(product_ids),
        }
    if len(hit_products) != len(product_ids):
        return "후보상품번호_일부만검색매핑", {
            "검색어_사용": base.pipe_join(terms),
            "매핑된_후보상품번호": base.pipe_join(hit_products),
            "미매핑_후보상품번호": base.pipe_join([pid for pid in product_ids if pid not in hit_products]),
        }

    found_rights = sorted({base.text(hit.get("account_저작권코드")) for hit in all_hits if base.text(hit.get("account_저작권코드"))})
    if len(found_rights) != 1:
        return "매핑저작권코드_복수", {
            "검색어_사용": base.pipe_join(terms),
            "매핑된_후보상품번호": base.pipe_join(hit_products),
            "account_저작권코드": base.pipe_join(found_rights),
        }

    ips_pub = base.normalize_publisher(row.get("IPS_출판사"))
    admin_pubs = [base.normalize_publisher(value) for value in base.split_values(row.get("admin_출판사목록"))]
    publisher_bad: list[str] = []
    for hit in all_hits:
        mapped_pub = base.normalize_publisher(hit.get("매핑_출판사"))
        if mapped_pub and ips_pub and mapped_pub != ips_pub and mapped_pub not in admin_pubs:
            publisher_bad.append(base.text(hit.get("매핑_출판사")))
    if publisher_bad:
        return "매핑도서_출판사불일치", {
            "검색어_사용": base.pipe_join(terms),
            "매핑된_후보상품번호": base.pipe_join(hit_products),
            "매핑_출판사": base.pipe_join(publisher_bad),
        }

    rights_code = found_rights[0]
    rights_meta = rights_by_code.get(rights_code, {})
    return "확정", {
        "검색어_사용": base.pipe_join(terms),
        "매핑된_후보상품번호": base.pipe_join(hit_products),
        "account_저작권코드": rights_code,
        "account_저작권명": base.text(rights_meta.get("account_저작권명")),
        "기본정산율여부": base.text(rights_meta.get("기본정산율여부")),
        "B2C_정산율": base.text(rights_meta.get("B2C_정산율")),
        "B2BC_정산율": base.text(rights_meta.get("B2BC_정산율")),
        "B2B_정산율": base.text(rights_meta.get("B2B_정산율")),
        "선인세_원문": base.text(rights_meta.get("선인세_원문")),
        "매핑_상품번호": base.pipe_join([hit.get("매핑_상품번호") for hit in all_hits]),
        "매핑_제목": base.pipe_join([hit.get("매핑_제목") for hit in all_hits]),
        "매핑_시리즈명": base.pipe_join([hit.get("매핑_시리즈명") for hit in all_hits]),
        "매핑_저자": base.pipe_join([hit.get("매핑_저자") for hit in all_hits]),
        "매핑_출판사": base.pipe_join([hit.get("매핑_출판사") for hit in all_hits]),
        "매핑_판매여부": base.pipe_join([hit.get("매핑_판매여부") for hit in all_hits]),
        "매핑검증_근거": "제목검색결과에서_후보상품번호전부_동일account저작권코드_정확매핑",
    }


def main() -> None:
    args = parse_args()
    cfg_args = argparse.Namespace(
        input=args.input,
        output_dir=args.output_dir,
        env_file=args.env_file,
        headless=args.headless,
        limit_cp=0,
        limit_rows=args.limit_rows,
        workers=max(1, int(args.workers)),
    )
    config = base.load_config(cfg_args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input, encoding="utf-8-sig", dtype=str).fillna("")
    if args.limit_rows:
        df = df.head(args.limit_rows).copy()
    print(f"[input] rows={len(df)} file={args.input}", flush=True)
    candidates, pre_excluded = base.build_prefilter(df)
    print(f"[filter] strict rows={len(candidates)} pre_excluded={len(pre_excluded)}", flush=True)

    detail = pd.read_csv(args.detail, encoding="utf-8-sig", dtype=str).fillna("")
    detail_cols = [
        "콘텐츠ID",
        "IPS_정제제목",
        "어드민_제목_후보",
        "어드민_정제제목_후보",
        "어드민_저자_후보",
        "어드민_출판사_후보",
    ]
    candidates = candidates.merge(
        detail[[col for col in detail_cols if col in detail.columns]].drop_duplicates("콘텐츠ID"),
        on="콘텐츠ID",
        how="left",
    ).fillna("")
    candidates["__search_terms"] = candidates.apply(lambda row: base.pipe_join(title_terms(row)), axis=1)

    cp_codes = sorted(
        {base.split_values(raw)[0] for raw in candidates["작가코드_전체"].tolist() if base.split_values(raw)},
        key=lambda value: int(value) if value.isdigit() else 10**18,
    )
    print(f"[rights] cp_codes={len(cp_codes)}", flush=True)

    session = base.login_and_make_session(config)
    print("[login] account session ok", flush=True)

    copyright_rows: list[dict[str, str]] = []
    cp_failures: dict[str, str] = {}
    for index, cp_code in enumerate(cp_codes, start=1):
        started = time.time()
        try:
            rows = base.fetch_copyright_rows(session, cp_code)
            copyright_rows.extend(rows)
            status = f"rights={len(rows)}"
        except Exception as exc:  # noqa: BLE001
            cp_failures[cp_code] = str(exc)
            status = f"FAIL {exc}"
        if index % 20 == 0 or index == len(cp_codes):
            print(f"[rights {index}/{len(cp_codes)}] cp={cp_code} {status} {time.time()-started:.1f}s", flush=True)

    rights_by_code = {row["account_저작권코드"]: row for row in copyright_rows}
    rights_by_cp: dict[str, list[str]] = {}
    for row in copyright_rows:
        rights_by_cp.setdefault(base.text(row.get("작가코드")), []).append(base.text(row.get("account_저작권코드")))
    for cp_code in list(rights_by_cp):
        rights_by_cp[cp_code] = sorted(set(rights_by_cp[cp_code]), key=lambda value: int(value) if value.isdigit() else 10**18)
    print(f"[rights] rows={len(copyright_rows)} unique_rights={len(rights_by_code)} failures={len(cp_failures)}", flush=True)

    search_tasks: set[tuple[str, str]] = set()
    for _, row in candidates.iterrows():
        cp_code = base.split_values(row.get("작가코드_전체"))[0]
        for rights_code in rights_by_cp.get(cp_code, []):
            for term in base.split_values(row.get("__search_terms")):
                search_tasks.add((rights_code, term))
    tasks = sorted(search_tasks, key=lambda item: (int(item[0]) if item[0].isdigit() else 10**18, item[1]))
    print(f"[search] tasks={len(tasks)} workers={config.workers}", flush=True)

    search_results: dict[tuple[str, str], list[dict[str, str]]] = {}
    search_failures: dict[tuple[str, str], str] = {}

    def search_job(task: tuple[str, str]) -> tuple[tuple[str, str], list[dict[str, str]], float, str]:
        rights_code, term = task
        started = time.time()
        try:
            rows = search_mapping(base.clone_session(session), rights_code, term)
            return task, rows, time.time() - started, ""
        except Exception as exc:  # noqa: BLE001
            return task, [], time.time() - started, str(exc)

    with ThreadPoolExecutor(max_workers=config.workers) as executor:
        futures = [executor.submit(search_job, task) for task in tasks]
        for index, future in enumerate(as_completed(futures), start=1):
            task, rows, elapsed, error = future.result()
            if error:
                search_failures[task] = error
                status = f"FAIL {error}"
            else:
                search_results[task] = rows
                status = f"rows={len(rows)}"
            if index % 100 == 0 or index == len(tasks):
                print(f"[search {index}/{len(tasks)}] rights={task[0]} term={task[1][:40]} {status} {elapsed:.1f}s", flush=True)

    confirmed_rows: list[dict[str, Any]] = []
    mapping_excluded_rows: list[dict[str, Any]] = []
    for _, row in candidates.iterrows():
        cp_code = base.split_values(row.get("작가코드_전체"))[0]
        row_dict = row.drop(labels=[col for col in ["__search_terms"] if col in row.index]).to_dict()
        row_dict["저작권자수"] = "1"
        row_dict["거래처코드수"] = "1"
        row_dict["후보상품수"] = str(len(base.split_product_ids(row.get("상품번호_후보"))))
        if cp_code in cp_failures:
            reason = "거래처_저작권코드조회실패"
            extra = {"조회실패": cp_failures[cp_code]}
        elif not rights_by_cp.get(cp_code):
            reason = "거래처_저작권코드없음"
            extra = {}
        else:
            reason, extra = evaluate_row(
                row,
                rights_codes=rights_by_cp.get(cp_code, []),
                search_results=search_results,
                rights_by_code=rights_by_code,
            )
        row_dict.update(extra)
        if reason == "확정":
            row_dict["감리결과"] = "더미계약서_명확후보"
            confirmed_rows.append(row_dict)
        else:
            row_dict["감리단계"] = "저작권매핑_제목검색"
            row_dict["제외사유"] = reason
            mapping_excluded_rows.append(row_dict)

    confirmed = pd.DataFrame(confirmed_rows).fillna("")
    excluded = pd.concat(
        [pre_excluded, pd.DataFrame(mapping_excluded_rows)],
        ignore_index=True,
        sort=False,
    ).fillna("")

    base_name = "20260518_dummy_contract_진짜명확"
    confirmed_path = output_dir / f"{base_name}.csv"
    excluded_path = output_dir / f"{base_name}__제외사유.csv"
    summary_path = output_dir / f"{base_name}__summary.csv"

    confirmed_columns = [
        "감리결과",
        "콘텐츠ID",
        "IPS_콘텐츠명",
        "IPS_정제제목",
        "IPS_작가필명",
        "IPS_담당부서",
        "IPS_담당자명",
        "IPS_출판사",
        "admin_출판사목록",
        "상품번호_후보",
        "후보상품수",
        "검색어_사용",
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
        confirmed = pd.DataFrame(columns=confirmed_columns)
    else:
        confirmed = confirmed[[col for col in confirmed_columns if col in confirmed.columns] + [col for col in confirmed.columns if col not in confirmed_columns]]

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
        "검색어_사용",
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
        excluded = excluded[[col for col in exclude_columns if col in excluded.columns] + [col for col in excluded.columns if col not in exclude_columns]]

    confirmed.to_csv(confirmed_path, index=False, encoding="utf-8-sig")
    excluded.to_csv(excluded_path, index=False, encoding="utf-8-sig")

    summary_rows = [
        {"항목": "입력행", "값": len(df)},
        {"항목": "1차_명확후보", "값": len(candidates)},
        {"항목": "조회_거래처코드", "값": len(cp_codes)},
        {"항목": "조회_저작권코드", "값": len(rights_by_code)},
        {"항목": "제목검색_task", "값": len(tasks)},
        {"항목": "제목검색_실패task", "값": len(search_failures)},
        {"항목": "최종_더미계약서_명확후보", "값": len(confirmed)},
        {"항목": "최종_제외", "값": len(excluded)},
        {"항목": "최종_명확후보_고유거래처", "값": confirmed["작가코드_전체"].nunique() if len(confirmed) else 0},
        {"항목": "최종_명확후보_고유저작권코드", "값": confirmed["account_저작권코드"].nunique() if len(confirmed) else 0},
    ]
    for reason, count in excluded["제외사유"].value_counts().items() if len(excluded) else []:
        summary_rows.append({"항목": f"제외사유::{reason}", "값": int(count)})
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("")
    print("=== 제목검색 기반 엄격 명확 후보 감리 완료 ===", flush=True)
    print(f"confirmed : {len(confirmed)} -> {confirmed_path}", flush=True)
    print(f"excluded  : {len(excluded)} -> {excluded_path}", flush=True)
    print(f"summary   : {summary_path}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
