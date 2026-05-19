from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from s2_auth import apply_env_file, first_env_value  # noqa: E402


KIPM_API_BASE_URL = "https://kipm-api.kld.kr"
KIPM_COMPANY_CODE = "1000"
DEFAULT_PAGE_SIZE = 50_000
DEFAULT_CONTENT_STATUS_CODE = "001"  # 유지
DEFAULT_REVERSION_COMPANY_CODE = "1000"  # 키다리스튜디오
JWT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
SHEET_NAME = "콘텐츠 목록"

KIPM_USERNAME_KEYS = ("KLD_LOGIN_ID", "KIPM_ID", "IPS_ID", "S2_ID", "KISS_ID")
KIPM_PASSWORD_KEYS = ("KLD_LOGIN_PW", "KIPM_PW", "IPS_PW", "S2_PW", "KISS_PW")
KIPM_ACCESS_TOKEN_KEYS = ("KIPM_ACCESS_TOKEN", "IPS_ACCESS_TOKEN", "S2_ACCESS_TOKEN", "KISS_ACCESS_TOKEN")
KIPM_API_BASE_URL_KEYS = ("KIPM_API_BASE_URL",)

OUTPUT_COLUMNS = [
    "콘텐츠ID",
    "콘텐츠형태",
    "귀속법인",
    "콘텐츠명",
    "서비스유형",
    "작가필명",
    "등급",
    "장르",
    "세부장르",
    "독점구분",
    "자체제작여부",
    "글로벌서비스가능여부",
    "예상연재월",
    "담당부서",
    "담당자명",
]


class IPSRefreshError(RuntimeError):
    pass


@dataclass(frozen=True)
class IPSRefreshResult:
    source_rows: int
    all_rows: int
    novel_rows: int
    webtoon_rows: int
    total_rows: int
    fetched_pages: int
    output_paths: tuple[Path, ...]


def main() -> None:
    args = parse_args()
    apply_env_file(Path(args.env_file), overwrite=False)
    rows, total_rows, fetched_pages = fetch_ips_content_rows(
        page_size=args.page_size,
        limit_pages=max(0, args.limit_pages),
        content_style_code=args.content_style_code,
        content_status_code=args.content_status_code,
        reversion_company_code=args.reversion_company_code,
    )
    result = write_auxiliary_workbooks(rows, data_dir=Path(args.data_dir))
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "as_of": args.today or date.today().isoformat(),
        "api_total_rows": total_rows,
        "fetched_rows": len(rows),
        "fetched_pages": fetched_pages,
        "source_rows": result.source_rows,
        "all_rows": result.all_rows,
        "novel_rows": result.novel_rows,
        "webtoon_rows": result.webtoon_rows,
        "content_style_code": args.content_style_code,
        "content_status_code": args.content_status_code,
        "reversion_company_code": args.reversion_company_code,
        "outputs": [str(path) for path in result.output_paths],
    }
    summary_path = Path(args.summary) if args.summary else ROOT / "doc" / (args.today or date.today().isoformat()) / "ips_auxiliary_refresh_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh repo IPS auxiliary workbooks from the KIPM content list API.")
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--summary", default="")
    parser.add_argument("--today", default="")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--limit-pages", type=int, default=0)
    parser.add_argument("--content-style-code", default="", help="KIPM srcCtnsStle. Blank fetches every content shape.")
    parser.add_argument("--content-status-code", default=DEFAULT_CONTENT_STATUS_CODE, help="KIPM srcCtnsStsCd. 001 means 유지.")
    parser.add_argument("--reversion-company-code", default=DEFAULT_REVERSION_COMPANY_CODE, help="KIPM srcRversCprCd.")
    return parser.parse_args()


def fetch_ips_content_rows(
    *,
    page_size: int,
    limit_pages: int,
    content_style_code: str,
    content_status_code: str,
    reversion_company_code: str,
) -> tuple[list[dict[str, Any]], int, int]:
    session = create_authenticated_session()
    try:
        rows: list[dict[str, Any]] = []
        page_num = 1
        total_rows = 0
        fetched_pages = 0
        while True:
            total_rows, page_rows = fetch_page(
                session,
                page_num=page_num,
                page_size=page_size,
                content_style_code=content_style_code,
                content_status_code=content_status_code,
                reversion_company_code=reversion_company_code,
            )
            rows.extend(page_rows)
            fetched_pages += 1
            print(f"[ips page {page_num}] fetched={len(page_rows)} total_accumulated={len(rows)} / total={total_rows}")
            if not page_rows or len(rows) >= total_rows or (limit_pages and fetched_pages >= limit_pages):
                break
            page_num += 1
        return rows, total_rows, fetched_pages
    finally:
        session.close()


def create_authenticated_session(*, login_timeout: int = 30) -> requests.Session:
    api_base_url = first_env_value(*KIPM_API_BASE_URL_KEYS) or KIPM_API_BASE_URL
    api_base_url = api_base_url.rstrip("/")
    access_token = first_env_value(*KIPM_ACCESS_TOKEN_KEYS)
    if access_token:
        return create_bearer_session(api_base_url, access_token)

    username = first_env_value(*KIPM_USERNAME_KEYS)
    password = first_env_value(*KIPM_PASSWORD_KEYS)
    if not username or not password:
        raise IPSRefreshError("KIPM/IPS ID/PW를 찾지 못했습니다. .env에 KIPM_ID/KIPM_PW 또는 IPS_ID/IPS_PW를 입력하세요.")

    session = requests.Session()
    session.headers.update(default_headers())
    response = session.post(
        f"{api_base_url}/user/login",
        json={"username": username, "password": password, "cprCd": KIPM_COMPANY_CODE},
        timeout=login_timeout,
    )
    if not response.ok:
        raise IPSRefreshError(f"KIPM 로그인 실패: HTTP {response.status_code} {response.text[:300]}")
    token = extract_jwt(response.json())
    if not token:
        raise IPSRefreshError("KIPM 로그인 응답에서 인증 토큰을 찾지 못했습니다.")
    session.headers["Authorization"] = f"Bearer {token}"
    session.headers["X-KIPM-API-BASE-URL"] = api_base_url
    return session


def create_bearer_session(api_base_url: str, access_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(default_headers())
    token = access_token.strip()
    session.headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    session.headers["X-KIPM-API-BASE-URL"] = api_base_url.rstrip("/")
    return session


def default_headers() -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=utf-8",
        "X-Requested-With": "XMLHttpRequest",
    }


def extract_jwt(payload: Any) -> str:
    if isinstance(payload, str) and JWT_PATTERN.match(payload):
        return payload
    if isinstance(payload, dict):
        for value in payload.values():
            token = extract_jwt(value)
            if token:
                return token
    if isinstance(payload, list):
        for value in payload:
            token = extract_jwt(value)
            if token:
                return token
    return ""


def fetch_page(
    session: requests.Session,
    *,
    page_num: int,
    page_size: int,
    content_style_code: str,
    content_status_code: str,
    reversion_company_code: str,
) -> tuple[int, list[dict[str, Any]]]:
    api_base_url = session.headers.get("X-KIPM-API-BASE-URL", KIPM_API_BASE_URL).rstrip("/")
    response = session.get(
        f"{api_base_url}/cntsd/cntslt/ctns-list",
        params=query_params(
            page_num=page_num,
            page_size=page_size,
            content_style_code=content_style_code,
            content_status_code=content_status_code,
            reversion_company_code=reversion_company_code,
        ),
        timeout=60,
    )
    if not response.ok:
        raise IPSRefreshError(f"IPS 콘텐츠 목록 조회 실패: HTTP {response.status_code} {response.text[:300]}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise IPSRefreshError(f"IPS 콘텐츠 목록 응답 형식이 예상과 다릅니다: {type(payload).__name__}")
    code = str(payload.get("code") or "").strip()
    if code and code not in {"REQUEST_SUCCESS", "SUCCESS"}:
        raise IPSRefreshError(f"IPS 콘텐츠 목록 조회 실패: code={code} message={payload.get('message')!r}")
    data = payload.get("data")
    if not isinstance(data, dict):
        return 0, []
    rows = data.get("list") or []
    return int(data.get("total") or len(rows)), [row for row in rows if isinstance(row, dict)]


def query_params(
    *,
    page_num: int,
    page_size: int,
    content_style_code: str,
    content_status_code: str,
    reversion_company_code: str,
) -> dict[str, str | int]:
    return {
        "srcCtnsNm": "",
        "srcPencNm": "",
        "srcmnply": "",
        "srcCtnsStle": content_style_code,
        "srcGrad": "",
        "srcGenr": "",
        "srcRversCprCd": reversion_company_code,
        "srchCmpyCd": "",
        "srcChgerIds": "",
        "srcChgerNms": "",
        "srcChgerDeptCds": "",
        "srcChgerDeptNms": "",
        "srcChgerDept": "",
        "srcCtnsId": "",
        "srcCtnsStsCd": content_status_code,
        "srchCtnsDtlGenrList": "",
        "srchOnslfMnftYn": "",
        "srcExptSerlMtSt": "",
        "srcExptSerlMtEd": "",
        "pageNum": page_num,
        "pageSize": page_size,
    }


def write_auxiliary_workbooks(rows: list[dict[str, Any]], *, data_dir: Path) -> IPSRefreshResult:
    data_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([flatten_content_row(row) for row in rows], columns=OUTPUT_COLUMNS).dropna(how="all").copy()
    kidari = frame[frame["귀속법인"].astype(str).str.strip().eq("키다리스튜디오")].copy()
    novel = kidari[kidari["콘텐츠형태"].astype(str).str.strip().eq("소설")].copy()
    webtoon = kidari[kidari["콘텐츠형태"].astype(str).str.strip().eq("웹툰")].copy()
    outputs = [
        (data_dir / "all_contents.xlsx", kidari),
        (data_dir / "kidari_contents.xlsx", novel),
        (data_dir / "kidari_webtoon.xlsx", webtoon),
    ]
    for path, output in outputs:
        output.to_excel(path, sheet_name=SHEET_NAME, index=False, engine="openpyxl")
        print(f"{path}: {len(output):,} rows")
    return IPSRefreshResult(
        source_rows=len(rows),
        all_rows=len(kidari),
        novel_rows=len(novel),
        webtoon_rows=len(webtoon),
        total_rows=len(rows),
        fetched_pages=0,
        output_paths=tuple(path for path, _ in outputs),
    )


def flatten_content_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "콘텐츠ID": text(row.get("ctnsId")),
        "콘텐츠형태": text(row.get("ctnsStleNm")),
        "귀속법인": text(row.get("rversCprNm")) or "키다리스튜디오",
        "콘텐츠명": text(row.get("ctnsNm")),
        "서비스유형": text(row.get("svcTyNm")),
        "작가필명": text(row.get("pencNm")),
        "등급": text(row.get("gradNm")),
        "장르": text(row.get("genrNm")),
        "세부장르": text(row.get("ctnsDtlGenrNm")),
        "독점구분": text(row.get("ocntrYn")),
        "자체제작여부": text(row.get("onslfMnftYn")),
        "글로벌서비스가능여부": text(row.get("globalYn")),
        "예상연재월": text(row.get("exptSerlMt")),
        "담당부서": text(row.get("chgerTeam")),
        "담당자명": text(row.get("chgerNm")),
    }


def text(value: Any) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    return raw[:-2] if raw.endswith(".0") else raw


if __name__ == "__main__":
    main()
