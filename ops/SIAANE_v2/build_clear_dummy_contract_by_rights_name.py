from __future__ import annotations

import argparse
import sys
import time
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build truly clear dummy-contract candidates by unique account copyright name.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(WORK_DIR))
    parser.add_argument("--env-file", default=str(base.DEFAULT_ENV))
    parser.add_argument("--headless", action="store_true")
    return parser.parse_args()


def rights_name_key(value: Any) -> str:
    return base.compact(str(value or "").replace(" ", ""))


def main() -> None:
    args = parse_args()
    cfg_args = argparse.Namespace(
        input=args.input,
        output_dir=args.output_dir,
        env_file=args.env_file,
        headless=args.headless,
        limit_cp=0,
        limit_rows=0,
        workers=1,
    )
    config = base.load_config(cfg_args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input, encoding="utf-8-sig", dtype=str).fillna("")
    print(f"[input] rows={len(df)} file={args.input}", flush=True)
    candidates, pre_excluded = base.build_prefilter(df)
    print(f"[filter] strict rows={len(candidates)} pre_excluded={len(pre_excluded)}", flush=True)

    cp_codes = sorted(
        {base.split_values(raw)[0] for raw in candidates["작가코드_전체"].tolist() if base.split_values(raw)},
        key=lambda value: int(value) if value.isdigit() else 10**18,
    )
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
        if index % 50 == 0 or index == len(cp_codes):
            print(f"[rights {index}/{len(cp_codes)}] cp={cp_code} {status} {time.time()-started:.1f}s", flush=True)

    rights_by_cp_name: dict[tuple[str, str], list[dict[str, str]]] = {}
    rights_by_cp: dict[str, list[dict[str, str]]] = {}
    for row in copyright_rows:
        cp_code = base.text(row.get("작가코드"))
        rights_by_cp.setdefault(cp_code, []).append(row)
        rights_by_cp_name.setdefault((cp_code, rights_name_key(row.get("account_저작권명"))), []).append(row)
    print(f"[rights] rows={len(copyright_rows)} failures={len(cp_failures)}", flush=True)

    confirmed_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    for _, row in candidates.iterrows():
        row_dict = row.to_dict()
        row_dict["저작권자수"] = "1"
        row_dict["거래처코드수"] = "1"
        row_dict["후보상품수"] = str(len(base.split_product_ids(row.get("상품번호_후보"))))
        cp_code = base.split_values(row.get("작가코드_전체"))[0]
        settlement_names = base.split_values(row.get("정산명_전체"))

        if cp_code in cp_failures:
            row_dict["감리단계"] = "account저작권명"
            row_dict["제외사유"] = "거래처_저작권코드조회실패"
            row_dict["조회실패"] = cp_failures[cp_code]
            excluded_rows.append(row_dict)
            continue
        if len(settlement_names) != 1:
            row_dict["감리단계"] = "account저작권명"
            row_dict["제외사유"] = f"정산명수_{len(settlement_names)}"
            excluded_rows.append(row_dict)
            continue

        hits = rights_by_cp_name.get((cp_code, rights_name_key(settlement_names[0])), [])
        if len(hits) != 1:
            row_dict["감리단계"] = "account저작권명"
            row_dict["제외사유"] = f"account저작권명_매칭코드수_{len(hits)}"
            row_dict["account_동명저작권코드"] = base.pipe_join([hit.get("account_저작권코드") for hit in hits])
            row_dict["account_거래처저작권명목록"] = base.pipe_join([hit.get("account_저작권명") for hit in rights_by_cp.get(cp_code, [])])
            excluded_rows.append(row_dict)
            continue

        hit = hits[0]
        row_dict.update(
            {
                "감리결과": "더미계약서_명확후보",
                "account_저작권코드": base.text(hit.get("account_저작권코드")),
                "account_저작권명": base.text(hit.get("account_저작권명")),
                "기본정산율여부": base.text(hit.get("기본정산율여부")),
                "B2C_정산율": base.text(hit.get("B2C_정산율")),
                "B2BC_정산율": base.text(hit.get("B2BC_정산율")),
                "B2B_정산율": base.text(hit.get("B2B_정산율")),
                "선인세_원문": base.text(hit.get("선인세_원문")),
                "매핑검증_근거": "단일저작권자+단일거래처+단일계좌+admin정산명_account저작권명_유일일치",
                "매핑도서전수검색필요": "N",
            }
        )
        confirmed_rows.append(row_dict)

    confirmed = pd.DataFrame(confirmed_rows).fillna("")
    excluded = pd.concat([pre_excluded, pd.DataFrame(excluded_rows)], ignore_index=True, sort=False).fillna("")

    base_name = "20260518_dummy_contract_진짜명확"
    confirmed_path = output_dir / f"{base_name}.csv"
    excluded_path = output_dir / f"{base_name}__제외사유.csv"
    summary_path = output_dir / f"{base_name}__summary.csv"

    confirmed_columns = [
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
        "선인세_원문",
        "계약연결상태",
        "매핑검증_근거",
        "매핑도서전수검색필요",
        "저작권정보_상이여부",
    ]
    if confirmed.empty:
        confirmed = pd.DataFrame(columns=confirmed_columns)
    else:
        confirmed = confirmed[[col for col in confirmed_columns if col in confirmed.columns] + [col for col in confirmed.columns if col not in confirmed_columns]]

    excluded_columns = [
        "감리단계",
        "제외사유",
        "콘텐츠ID",
        "IPS_콘텐츠명",
        "IPS_작가필명",
        "IPS_출판사",
        "admin_출판사목록",
        "상품번호_후보",
        "후보상품수",
        "account_동명저작권코드",
        "account_거래처저작권명목록",
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
        excluded = pd.DataFrame(columns=excluded_columns)
    else:
        excluded = excluded[[col for col in excluded_columns if col in excluded.columns] + [col for col in excluded.columns if col not in excluded_columns]]

    confirmed.to_csv(confirmed_path, index=False, encoding="utf-8-sig")
    excluded.to_csv(excluded_path, index=False, encoding="utf-8-sig")

    summary_rows = [
        {"항목": "입력행", "값": len(df)},
        {"항목": "1차_명확후보", "값": len(candidates)},
        {"항목": "조회_거래처코드", "값": len(cp_codes)},
        {"항목": "조회_저작권코드", "값": len(copyright_rows)},
        {"항목": "저작권코드조회실패_거래처", "값": len(cp_failures)},
        {"항목": "최종_더미계약서_명확후보", "값": len(confirmed)},
        {"항목": "최종_제외", "값": len(excluded)},
        {"항목": "최종_명확후보_고유거래처", "값": confirmed["작가코드_전체"].nunique() if len(confirmed) else 0},
        {"항목": "최종_명확후보_고유저작권코드", "값": confirmed["account_저작권코드"].nunique() if len(confirmed) else 0},
    ]
    for reason, count in excluded["제외사유"].value_counts().items() if len(excluded) else []:
        summary_rows.append({"항목": f"제외사유::{reason}", "값": int(count)})
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("")
    print("=== account 저작권명 1:1 기준 명확 후보 생성 완료 ===", flush=True)
    print(f"confirmed : {len(confirmed)} -> {confirmed_path}", flush=True)
    print(f"excluded  : {len(excluded)} -> {excluded_path}", flush=True)
    print(f"summary   : {summary_path}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
