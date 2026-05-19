from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "SIAAN Project"
CATALOG_DIR = PROJECT_ROOT / "data" / "catalog"
EXPORT_DIR = PROJECT_ROOT / "data" / "exports" / "ips"

from ips.core.auth import resolve_env_path
from ips.core.browser import BrowserSettings
from ips.core.harness import IPSHarness
from ips.sites import get_site

DETAIL_PATH = "/cntsd/cntschg/ctns-chg-list/detail/{cid}"

AXIOS_GET = """
async (path) => {
    const app = document.querySelector('#app');
    const axios = app && app.__vue_app__._context.provides['$axios'];
    if (!axios) return { ok: false, error: 'axios-not-found' };
    try {
        const r = await axios.get(path);
        return { ok: true, status: r.status, data: r.data };
    } catch (e) {
        return { ok: false, error: String(e.message || e), status: e.response && e.response.status };
    }
}
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Probe IPS for chgerNm/chgerTeam per CID.")
    p.add_argument("--source", choices=["picked", "universe", "cids"], default="universe",
                   help="picked = manual_overrides picks only; universe = all s2_work_cid_map entries; cids = --cid flags")
    p.add_argument("--cid", action="append", default=[])
    p.add_argument("--expected-manager", default="조원재")
    p.add_argument("--env-file", default="")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--output-json", default=str(CATALOG_DIR / "ips_manager_probe.json"))
    p.add_argument("--output-csv", default=str(EXPORT_DIR / "ips_manager_probe.csv"))
    return p.parse_args()


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def pick_cids(args: argparse.Namespace) -> list[str]:
    if args.source == "cids":
        return [str(c).strip() for c in args.cid if str(c).strip()]
    if args.source == "picked":
        mo = load_json(PROJECT_ROOT / "config" / "manual_overrides.local.json") or {}
        cids = {str(i.get("work_cid") or "").strip() for i in mo.get("ips_cid_overrides", []) if i.get("work_cid")}
        return sorted(c for c in cids if c)
    # universe: s2 map
    smap = load_json(CATALOG_DIR / "s2_work_cid_map_조원재.json") or []
    # pull from manual_overrides picks (because s2 map has empty work_cid mostly)
    mo = load_json(PROJECT_ROOT / "config" / "manual_overrides.local.json") or {}
    picked = {str(i.get("work_cid") or "").strip() for i in mo.get("ips_cid_overrides", []) if i.get("work_cid")}
    # also include any CIDs listed in review queue
    rq = load_json(CATALOG_DIR / "ips_override_review_queue.json") or {}
    for row in rq.get("rows", []):
        cid = str(row.get("work_cid") or "").strip()
        if cid:
            picked.add(cid)
    return sorted(c for c in picked if c)


def main() -> None:
    args = parse_args()
    cids = pick_cids(args)
    print(f"probing {len(cids)} CIDs (source={args.source})")

    settings = BrowserSettings(
        headless=args.headless,
        slow_mo_ms=0,
        timeout_ms=20_000,
        artifacts_root=PROJECT_ROOT / "output" / "ips_harness",
    )
    env_path = resolve_env_path(args.env_file)
    site = get_site("kipm")

    rows: list[dict[str, Any]] = []
    with IPSHarness(site, settings=settings, env_path=env_path) as harness:
        harness.ensure_logged_in(path="/ip/cntsd/cntschg/ctns-chg-list?pageNum=1&pageSize=10")
        harness.page.wait_for_timeout(1_500)
        for idx, cid in enumerate(cids, start=1):
            resp = harness.page.evaluate(AXIOS_GET, DETAIL_PATH.format(cid=cid))
            vo = {}
            if resp.get("ok") and isinstance(resp.get("data"), dict):
                vo = resp["data"].get("ctnsDetailVO") or {}
            ctns_nm = str(vo.get("ctnsNm") or "").strip()
            chger_nm = str(vo.get("chgerNm") or "").strip()
            chger_team = str(vo.get("chgerTeam") or "").strip()
            chger_id = str(vo.get("chgerId") or "").strip()
            service_ty = str(vo.get("svcTyNm") or "").strip()
            mismatch = bool(chger_nm) and (chger_nm != args.expected_manager)
            rows.append({
                "work_cid": cid,
                "current_title": ctns_nm,
                "chger_nm": chger_nm,
                "chger_team": chger_team,
                "chger_id": chger_id,
                "service_type": service_ty,
                "mismatch": mismatch,
                "ok": bool(resp.get("ok")),
                "http_status": resp.get("status"),
                "error": resp.get("error") or "",
            })
            if idx % 10 == 0 or mismatch:
                marker = " !!" if mismatch else ""
                print(f"[{idx}/{len(cids)}] {cid}  chger={chger_nm or '-'}  team={chger_team or '-'}  title={ctns_nm[:40]}{marker}")

    mismatches = [r for r in rows if r["mismatch"]]
    summary = {
        "generated_at": datetime.now().isoformat(),
        "expected_manager": args.expected_manager,
        "total": len(rows),
        "mismatch_count": len(mismatches),
        "mismatch_cids": [r["work_cid"] for r in mismatches],
        "rows": rows,
    }
    out_json = Path(args.output_json)
    out_csv = Path(args.output_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with out_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\ntotal={len(rows)}  mismatch={len(mismatches)}")
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
