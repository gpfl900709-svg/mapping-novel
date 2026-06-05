from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "SIAAN Project"

from ips.core.auth import resolve_env_path
from ips.core.browser import BrowserSettings
from ips.core.harness import IPSHarness
from ips.sites import get_site
from secret_redaction import write_json_redacted


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "ips_probe"
DETAIL_PATH_TEMPLATE = "/cntsd/cntschg/ctns-chg-list/detail/{cid}"
REQUIRED_FIELD_KEYS = ("svcTyCd", "mnplyCd", "serlPargCyclCd", "ctnsExptQntCd")


FETCH_DETAIL_SCRIPT = """
async (path) => {
    const app = document.querySelector('#app');
    const axios = app && app.__vue_app__._context.provides['$axios'];
    if (!axios) {
        return { ok: false, error: 'axios-not-found' };
    }
    try {
        const response = await axios.get(path);
        return {
            ok: true,
            status: response.status,
            headers: response.headers,
            data: response.data,
        };
    } catch (error) {
        return {
            ok: false,
            error: String(error && error.message || error),
            status: error && error.response && error.response.status,
            data: error && error.response && error.response.data,
        };
    }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe IPS 콘텐츠 edit page: dump $axios detail response + all API calls observed.",
    )
    parser.add_argument("--cid", action="append", required=True)
    parser.add_argument("--env-file", default="")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=20_000)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--slow-mo-ms", type=int, default=0)
    parser.add_argument(
        "--capture-network",
        action="store_true",
        help="Attach request/response listeners and log every API call during edit-page load.",
    )
    return parser.parse_args()


def classify_validation_gap(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"matched": False, "missing": list(REQUIRED_FIELD_KEYS)}

    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    present: dict[str, Any] = {}
    missing: list[str] = []
    for key in REQUIRED_FIELD_KEYS:
        value = payload.get(key, None)
        present[key] = value
        if value in ("", None):
            missing.append(key)
    return {
        "matched": True,
        "present": present,
        "missing": missing,
        "has_validation_gap": bool(missing),
    }


def attach_network_recorder(page: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    def _on_response(response: Any) -> None:
        try:
            url = response.url
            if "kipm-api.kld.kr" not in url and "/api/" not in url:
                return
            event: dict[str, Any] = {
                "phase": "response",
                "method": response.request.method,
                "url": url,
                "status": response.status,
            }
            try:
                event["body"] = response.json()
            except Exception:  # noqa: BLE001
                try:
                    event["body_text"] = response.text()
                except Exception:  # noqa: BLE001
                    pass
            events.append(event)
        except Exception:  # noqa: BLE001
            pass

    page.on("response", _on_response)
    return events


def probe_cid(harness: IPSHarness, cid: str, *, capture_network: bool) -> dict[str, Any]:
    edit_path = f"/ip/cntsd/cntschg/ctns-chg-edit?parCtnsId={cid}"
    network_events: list[dict[str, Any]] = []
    if capture_network:
        network_events = attach_network_recorder(harness.page)

    harness.navigate(edit_path)
    harness.page.wait_for_timeout(2_500)

    detail_path = DETAIL_PATH_TEMPLATE.format(cid=cid)
    response = harness.page.evaluate(FETCH_DETAIL_SCRIPT, detail_path)

    summary = {
        "cid": cid,
        "detail_path": detail_path,
        "ok": bool(response.get("ok")),
        "status": response.get("status"),
        "error": response.get("error"),
        "data_keys": list(response.get("data", {}).keys()) if isinstance(response.get("data"), dict) else None,
        "validation_check": classify_validation_gap(response.get("data")),
    }

    network_summary = []
    for event in network_events:
        entry = {
            "method": event.get("method"),
            "url": event.get("url"),
            "status": event.get("status"),
        }
        if isinstance(event.get("body"), dict):
            entry["body_keys"] = list(event["body"].keys())
        network_summary.append(entry)

    return {
        "summary": summary,
        "response": response,
        "network": network_events,
        "network_summary": network_summary,
    }


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = BrowserSettings(
        headless=args.headless,
        slow_mo_ms=args.slow_mo_ms,
        timeout_ms=args.timeout_ms,
        artifacts_root=PROJECT_ROOT / "output" / "ips_harness",
    )
    env_path = resolve_env_path(args.env_file)
    site = get_site("kipm")

    summaries: list[dict[str, Any]] = []
    with IPSHarness(site, settings=settings, env_path=env_path) as harness:
        harness.ensure_logged_in(path="/ip/cntsd/cntschg/ctns-chg-list?pageNum=1&pageSize=10")
        for cid in args.cid:
            cid_clean = str(cid).strip()
            if not cid_clean:
                continue
            print(f"[probe] {cid_clean}")
            result = probe_cid(harness, cid_clean, capture_network=args.capture_network)
            dump_path = output_dir / f"detail_{cid_clean}.json"
            write_json_redacted(dump_path, result)
            summaries.append({
                "cid": cid_clean,
                **result["summary"],
                "network_calls": result["network_summary"],
            })

    print(json.dumps({"summaries": summaries, "output_dir": str(output_dir)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
