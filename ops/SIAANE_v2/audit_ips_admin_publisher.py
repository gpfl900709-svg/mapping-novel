from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts"
SIAAN_PROJECT_ROOT = REPO_ROOT / "SIAAN Project"
WORK_DIR = PROJECT_ROOT / "담당자없는작품_재정리"

sys.path.insert(0, str(SCRIPTS_ROOT))

from ips.core.auth import resolve_env_path  # noqa: E402
from ips.core.browser import BrowserSettings  # noqa: E402
from ips.core.harness import IPSHarness  # noqa: E402
from ips.sites import get_site  # noqa: E402
from rename_ips_content_titles_api import DETAIL_PATH  # noqa: E402


DEFAULT_SSOT = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__정산정보없음포함_사용안함제외__저작권정보부착.csv"
DEFAULT_ADMIN = WORK_DIR / "admin_진열상품_20260518.xls"
DEFAULT_SNAPSHOT = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__IPS출판사_snapshot.csv"
DEFAULT_AUDIT = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__admin_vs_IPS출판사_감리.csv"
DEFAULT_MISMATCH = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__admin_vs_IPS출판사_불일치.csv"
DEFAULT_SUMMARY = WORK_DIR / "20260518_admin_ips_contractless_title_95plus__admin_vs_IPS출판사_감리요약.csv"


BATCH_DETAIL_SCRIPT = """
async ({ cids, concurrency }) => {
    const app = document.querySelector('#app');
    const axios = app && app.__vue_app__._context.provides['$axios'];
    if (!axios) { return cids.map(cid => ({ ctnsId: cid, ok: false, error: 'axios-not-found' })); }

    const results = new Array(cids.length);
    let cursor = 0;

    async function fetchOne(index) {
        const cid = cids[index];
        try {
            const response = await axios.request({
                method: 'get',
                url: `/cntsd/cntschg/ctns-chg-list/detail/${cid}`,
            });
            const data = response.data || {};
            const vo = data.ctnsDetailVO || data || {};
            results[index] = {
                ctnsId: String(vo.ctnsId || cid || ''),
                ok: true,
                status: response.status || '',
                ctnsNm: vo.ctnsNm || '',
                pencNm: vo.pencNm || '',
                chgerTeam: vo.chgerTeam || '',
                chgerNm: vo.chgerNm || vo.ctnsChgerNm || '',
                ctnsStsNm: vo.ctnsStsNm || '',
                svcTyNm: vo.svcTyNm || '',
                pblcoCd: vo.pblcoCd || '',
                pblcoNm: vo.pblcoNm || '',
                grpCtnsId: vo.grpCtnsId || '',
                grpCtnsNm: vo.grpCtnsNm || '',
                rversCprNm: vo.rversCprNm || '',
            };
        } catch (error) {
            results[index] = {
                ctnsId: String(cid || ''),
                ok: false,
                status: error && error.response && error.response.status || '',
                error: String((error && error.message) || error || ''),
            };
        }
    }

    async function worker() {
        while (cursor < cids.length) {
            const index = cursor++;
            await fetchOne(index);
        }
    }

    const workers = [];
    const workerCount = Math.max(1, Math.min(Number(concurrency || 1), cids.length));
    for (let i = 0; i < workerCount; i++) { workers.push(worker()); }
    await Promise.all(workers);
    return results;
}
"""


def text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    raw = str(value).strip()
    if re.fullmatch(r"\d+\.0", raw):
        return raw[:-2]
    return raw


def id_text(value: Any) -> str:
    raw = text(value)
    if re.fullmatch(r"\d+(?:\.0+)?", raw):
        return str(int(float(raw)))
    return raw


def split_semicolon(value: Any) -> list[str]:
    raw = text(value)
    if not raw:
        return []
    return [part.strip() for part in re.split(r"\s*;\s*", raw) if part.strip()]


def join_unique(values: list[Any]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = text(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return " | ".join(out)


def publisher_key(value: Any) -> str:
    cleaned = unicodedata.normalize("NFKC", text(value)).lower()
    cleaned = cleaned.replace("㈜", "주")
    cleaned = re.sub(r"\(주\)|주식회사|\(유\)|유한회사|도서출판|출판사|출판", "", cleaned)
    return re.sub(r"[^0-9a-z가-힣]+", "", cleaned)


def publisher_text(value: Any) -> str:
    cleaned = text(value)
    if cleaned in {"-", "없음", "nan", "NaN", "NULL", "null"}:
        return ""
    return cleaned


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit admin publisher candidates against live IPS pblcoNm.")
    parser.add_argument("--ssot-csv", default=str(DEFAULT_SSOT))
    parser.add_argument("--admin-xls", default=str(DEFAULT_ADMIN))
    parser.add_argument("--snapshot-csv", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--audit-csv", default=str(DEFAULT_AUDIT))
    parser.add_argument("--mismatch-csv", default=str(DEFAULT_MISMATCH))
    parser.add_argument("--summary-csv", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--env-file", default=str(SIAAN_PROJECT_ROOT / ".env"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--content-id", action="append", default=[])
    parser.add_argument("--skip-fetch", action="store_true")
    return parser.parse_args()


def load_ssot(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")


def load_admin(path: Path) -> dict[str, dict[str, str]]:
    admin = pd.read_html(path, encoding="utf-8")[0].astype(str).replace({"nan": ""})
    admin["상품번호_key"] = admin["상품번호"].map(id_text)
    rows: dict[str, dict[str, str]] = {}
    for _, row in admin.iterrows():
        pid = id_text(row.get("상품번호_key"))
        if not pid or pid in rows:
            continue
        rows[pid] = {
            "상품번호": pid,
            "상품유형": text(row.get("상품유형")),
            "제목": text(row.get("제목")),
            "저자": text(row.get("저자")),
            "출판사": text(row.get("출판사")),
            "판매상태": text(row.get("판매상태")),
            "승인상태": text(row.get("승인상태")),
            "수정일": text(row.get("수정일")),
        }
    return rows


def target_cids(ssot: pd.DataFrame, requested: list[str], limit: int) -> list[str]:
    requested_set = {id_text(value) for value in requested if id_text(value)}
    cids: list[str] = []
    for value in ssot["콘텐츠ID"].tolist():
        cid = id_text(value)
        if not cid:
            continue
        if requested_set and cid not in requested_set:
            continue
        if cid not in cids:
            cids.append(cid)
    if limit > 0:
        cids = cids[:limit]
    return cids


SNAPSHOT_FIELDS = [
    "콘텐츠ID",
    "조회상태",
    "http_status",
    "IPS_콘텐츠명_live",
    "IPS_작가필명_live",
    "IPS_담당부서_live",
    "IPS_담당자명_live",
    "IPS_콘텐츠상태_live",
    "IPS_서비스유형_live",
    "IPS_출판사코드",
    "IPS_출판사",
    "IPS_그룹콘텐츠코드",
    "IPS_그룹콘텐츠명",
    "IPS_귀속법인",
    "error",
]


def load_snapshot(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            cid = id_text(row.get("콘텐츠ID"))
            if cid:
                rows[cid] = {field: text(row.get(field)) for field in SNAPSHOT_FIELDS}
    return rows


def write_snapshot(path: Path, rows: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_FIELDS)
        writer.writeheader()
        for cid in sorted(rows, key=lambda value: int(value) if value.isdigit() else value):
            writer.writerow(rows[cid])


def fetch_live_publishers(args: argparse.Namespace, cids: list[str], snapshot_path: Path) -> dict[str, dict[str, str]]:
    snapshot = load_snapshot(snapshot_path)
    missing = [cid for cid in cids if cid not in snapshot or snapshot[cid].get("조회상태") != "ok"]
    if not missing:
        return snapshot

    settings = BrowserSettings(
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        artifacts_root=SIAAN_PROJECT_ROOT / "output" / "ips_harness",
    )
    env_path = resolve_env_path(args.env_file)

    with IPSHarness(get_site("kipm"), settings=settings, env_path=env_path) as harness:
        harness.ensure_logged_in(path="/ip/cntsd/cntschg/ctns-chg-list?pageNum=1&pageSize=10")
        harness.page.wait_for_timeout(1_200)
        total = len(missing)
        for start in range(0, total, args.batch_size):
            batch = missing[start : start + args.batch_size]
            print(f"fetch {start + 1}-{start + len(batch)} / {total}", flush=True)
            fetched = harness.page.evaluate(
                BATCH_DETAIL_SCRIPT,
                {"cids": batch, "concurrency": max(1, args.concurrency)},
            )
            for item in fetched:
                cid = id_text(item.get("ctnsId"))
                if not cid:
                    continue
                ok = bool(item.get("ok"))
                snapshot[cid] = {
                    "콘텐츠ID": cid,
                    "조회상태": "ok" if ok else "failed",
                    "http_status": text(item.get("status")),
                    "IPS_콘텐츠명_live": text(item.get("ctnsNm")),
                    "IPS_작가필명_live": text(item.get("pencNm")),
                    "IPS_담당부서_live": text(item.get("chgerTeam")),
                    "IPS_담당자명_live": text(item.get("chgerNm")),
                    "IPS_콘텐츠상태_live": text(item.get("ctnsStsNm")),
                    "IPS_서비스유형_live": text(item.get("svcTyNm")),
                    "IPS_출판사코드": text(item.get("pblcoCd")),
                    "IPS_출판사": text(item.get("pblcoNm")),
                    "IPS_그룹콘텐츠코드": id_text(item.get("grpCtnsId")),
                    "IPS_그룹콘텐츠명": text(item.get("grpCtnsNm")),
                    "IPS_귀속법인": text(item.get("rversCprNm")),
                    "error": text(item.get("error")),
                }
            write_snapshot(snapshot_path, snapshot)
    return snapshot


@dataclass
class AdminCandidates:
    product_ids: list[str]
    publishers: list[str]
    products: list[str]


def admin_candidates(row: pd.Series, admin_by_id: dict[str, dict[str, str]]) -> AdminCandidates:
    product_ids = split_semicolon(row.get("상품번호_후보"))
    publishers: list[str] = []
    products: list[str] = []
    for pid in product_ids:
        admin = admin_by_id.get(pid)
        if not admin:
            continue
        publishers.append(admin["출판사"])
        products.append(
            f"{pid}:{admin['상품유형']}:{admin['제목']}:{admin['저자']}:{admin['출판사']}:{admin['판매상태']}:{admin['승인상태']}:{admin['수정일']}"
        )
    return AdminCandidates(product_ids=product_ids, publishers=publishers, products=products)


def compare_publishers(ips_publisher: str, admin_publishers: list[str]) -> tuple[str, str]:
    ips = publisher_text(ips_publisher)
    admins = [publisher_text(value) for value in admin_publishers if publisher_text(value)]
    if not ips:
        return "IPS출판사없음", ""
    if not admins:
        return "admin출판사없음", ""
    if ips in admins:
        return "일치", ips
    ips_key = publisher_key(ips)
    for publisher in admins:
        if ips_key and ips_key == publisher_key(publisher):
            return "정규화일치", publisher
    return "불일치", ""


def build_audit(ssot: pd.DataFrame, admin_by_id: dict[str, dict[str, str]], snapshot: dict[str, dict[str, str]]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, row in ssot.iterrows():
        cid = id_text(row.get("콘텐츠ID"))
        live = snapshot.get(cid, {})
        admins = admin_candidates(row, admin_by_id)
        admin_publishers = [publisher for publisher in admins.publishers if publisher]
        status, matched = compare_publishers(live.get("IPS_출판사", ""), admin_publishers)
        rows.append(
            {
                "출판사비교상태": status,
                "매칭_admin출판사": matched,
                "콘텐츠ID": cid,
                "IPS_콘텐츠명": text(row.get("IPS_콘텐츠명")),
                "IPS_콘텐츠명_live": text(live.get("IPS_콘텐츠명_live")),
                "IPS_작가필명": text(row.get("IPS_작가필명")),
                "IPS_작가필명_live": text(live.get("IPS_작가필명_live")),
                "IPS_담당부서": text(row.get("IPS_담당부서")),
                "IPS_담당부서_live": text(live.get("IPS_담당부서_live")),
                "IPS_담당자명": text(row.get("IPS_담당자명")),
                "IPS_담당자명_live": text(live.get("IPS_담당자명_live")),
                "계약연결상태": text(row.get("계약연결상태")),
                "정산제외표시": text(row.get("정산제외표시")),
                "매칭상태": text(row.get("매칭상태")),
                "매칭근거": text(row.get("매칭근거")),
                "confidence": text(row.get("confidence")),
                "후보_상품수": text(row.get("후보_상품수")),
                "상품번호_후보": join_unique(admins.product_ids),
                "IPS_출판사코드": text(live.get("IPS_출판사코드")),
                "IPS_출판사": text(live.get("IPS_출판사")),
                "admin_출판사목록": join_unique(admin_publishers),
                "admin_상품목록": " || ".join(admins.products),
                "SSOT_어드민_출판사_후보": text(row.get("어드민_출판사_후보")),
                "저작권자_전체": text(row.get("저작권자_전체")),
                "정산명_전체": text(row.get("정산명_전체")),
                "저작권정보_상이여부": text(row.get("저작권정보_상이여부")),
                "조회상태": text(live.get("조회상태")),
                "조회error": text(live.get("error")),
            }
        )
    return pd.DataFrame(rows)


def write_summary(audit: pd.DataFrame, path: Path, snapshot_path: Path, audit_path: Path, mismatch_path: Path) -> None:
    rows: list[dict[str, str]] = []
    rows.append({"항목": "generated_at", "값": datetime.now().isoformat(timespec="seconds")})
    rows.append({"항목": "snapshot_csv", "값": str(snapshot_path)})
    rows.append({"항목": "audit_csv", "값": str(audit_path)})
    rows.append({"항목": "mismatch_csv", "값": str(mismatch_path)})
    rows.append({"항목": "rows", "값": str(len(audit))})
    for key, value in Counter(audit["출판사비교상태"]).items():
        rows.append({"항목": f"출판사비교상태.{key}", "값": str(value)})
    for key, value in Counter(audit["조회상태"]).items():
        rows.append({"항목": f"조회상태.{key}", "값": str(value)})
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    ssot_path = Path(args.ssot_csv)
    admin_path = Path(args.admin_xls)
    snapshot_path = Path(args.snapshot_csv)
    audit_path = Path(args.audit_csv)
    mismatch_path = Path(args.mismatch_csv)
    summary_path = Path(args.summary_csv)

    ssot = load_ssot(ssot_path)
    admin_by_id = load_admin(admin_path)
    cids = target_cids(ssot, args.content_id, args.limit)

    if args.skip_fetch:
        snapshot = load_snapshot(snapshot_path)
    else:
        snapshot = fetch_live_publishers(args, cids, snapshot_path)

    audit = build_audit(ssot[ssot["콘텐츠ID"].map(id_text).isin(set(cids))], admin_by_id, snapshot)
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    mismatch = audit[audit["출판사비교상태"].isin(["불일치", "IPS출판사없음", "admin출판사없음"])]
    mismatch.to_csv(mismatch_path, index=False, encoding="utf-8-sig")
    write_summary(audit, summary_path, snapshot_path, audit_path, mismatch_path)

    print(f"rows={len(audit)}")
    print(f"status={dict(Counter(audit['출판사비교상태']))}")
    print(f"audit_csv={audit_path}")
    print(f"mismatch_csv={mismatch_path}")
    print(f"summary_csv={summary_path}")


if __name__ == "__main__":
    main()
