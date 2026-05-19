from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts"
SIAAN_PROJECT_ROOT = REPO_ROOT / "SIAAN Project"

sys.path.insert(0, str(SCRIPTS_ROOT))

from create_kipm_content_contract import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    extract_content_id_from_payload,
    lookup_content_id_by_name,
)
from create_kipm_dummy_contract import DummyContractSpec, create_dummy_contract  # noqa: E402
from ips.core.auth import resolve_env_path  # noqa: E402
from ips.core.browser import BrowserSettings  # noqa: E402
from ips.core.harness import IPSHarness  # noqa: E402
from ips.sites import get_site  # noqa: E402
from rename_ips_content_titles_api import axios_call  # noqa: E402


CREATE_PATH = "/cntsd/cntsreg/ctns-reg/add-ctns-main"
DEFAULT_ENV_FILE = SIAAN_PROJECT_ROOT / ".env"
DEFAULT_PDF_PATH = REPO_ROOT / "더미+계약서.pdf"
DEFAULT_OUTPUT_PATH = (
    DEFAULT_OUTPUT_DIR / "20260506__natoya_missing_cids_api_create_report.json"
)


ITEMS = [
    {
        "title": "이세계 영주 생활",
        "content_name": "이세계 영주 생활_나토야_1005697_선인세없음_확정",
        "dryrun_json": DEFAULT_OUTPUT_DIR
        / "20260506__dryrun5_create_이세계_영주_생활_나토야.json",
    },
    {
        "title": "하이퍼 서퍼 벤젠스",
        "content_name": "하이퍼 서퍼 벤젠스_나토야_1005697_선인세없음_확정",
        "dryrun_json": DEFAULT_OUTPUT_DIR
        / "20260506__dryrun5_create_하이퍼_서퍼_벤젠스_나토야.json",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Legacy NaToya CID creation recipe. Default is preview only; "
            "pass --write to POST live KIPM content rows and create dummy contracts."
        ),
    )
    parser.add_argument("--write", action="store_true", help="Actually execute the live POST/contract creation recipe.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    payload = report["content"]["request_payload"]
    if not isinstance(payload, dict):
        raise RuntimeError(f"dry-run payload is missing: {path}")
    payload = dict(payload)
    payload["pblcDt"] = "2026-05-06"
    return payload


def write_preview(args: argparse.Namespace) -> None:
    rows = [
        {
            "title": item["title"],
            "content_name": item["content_name"],
            "dryrun_json": str(item["dryrun_json"]),
            "dryrun_json_exists": item["dryrun_json"].exists(),
            "would_create_content": True,
            "would_create_dummy_contract_holder": "신경역",
            "status": "preview_only",
        }
        for item in ITEMS
    ]
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "preview",
        "status": "no_live_write",
        "write_required": "--write",
        "rows": rows,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    if not args.write:
        write_preview(args)
        return

    settings = BrowserSettings(
        headless=True,
        timeout_ms=30_000,
        artifacts_root=DEFAULT_OUTPUT_DIR,
    )
    env_path = resolve_env_path(args.env_file)
    site = get_site("kipm")
    rows: list[dict[str, Any]] = []

    with IPSHarness(site, settings=settings, env_path=env_path) as harness:
        harness.ensure_logged_in(path="/ip/cntsd/cntsreg/ctns-reg")
        harness.page.wait_for_timeout(1_500)

        for item in ITEMS:
            payload = load_payload(item["dryrun_json"])
            create_resp = axios_call(harness.page, "post", CREATE_PATH, payload)
            if not create_resp.get("ok"):
                rows.append(
                    {
                        "title": item["title"],
                        "content_name": item["content_name"],
                        "status": "create_failed",
                        "create_response": create_resp,
                    }
                )
                continue

            content_id = extract_content_id_from_payload(create_resp.get("data"))
            if not content_id:
                harness.page.wait_for_timeout(1_500)
                content_id = lookup_content_id_by_name(
                    harness.page,
                    content_name=item["content_name"],
                )

            harness.page.wait_for_timeout(1_500)
            contract = create_dummy_contract(
                harness.page,
                DummyContractSpec(
                    cid=content_id,
                    holder_name="신경역",
                    pdf_path=DEFAULT_PDF_PATH,
                ),
            )
            rows.append(
                {
                    "title": item["title"],
                    "content_name": item["content_name"],
                    "content_id": content_id,
                    "status": "created",
                    "create_status": create_resp.get("status"),
                    "create_data": create_resp.get("data"),
                    "contract": asdict(contract),
                }
            )

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "write",
        "rows": rows,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
