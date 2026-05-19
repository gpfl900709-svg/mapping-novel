from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1] / "SIAAN Project"
DEFAULT_WORK_CID_REGISTRY_PATH = PROJECT_ROOT / "config" / "work_cid_registry.local.csv"

WORK_CID_REGISTRY_FIELDS = [
    "work_cid",
    "legacy_work_id",
    "folder_path",
    "readj_path",
    "source_group",
    "manager",
    "source_system",
    "department_name",
    "service_type",
    "title_final",
    "author_final",
    "sales_channel_cids",
    "sales_channel_names",
    "contract_ids",
    "remark",
    "ips_name",
    "match_status",
    "match_reason",
    "matched_s2_title",
    "matched_s2_author",
    "matched_ips_title",
    "matched_ips_author",
    "related_content_ids",
    "related_service_types",
    "created_at",
    "note",
]


def split_pipe_list(raw_value: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in (raw_value or "").split("|"):
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        values.append(cleaned)
        seen.add(cleaned)
    return values


def join_pipe_list(values: list[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = (value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        ordered.append(cleaned)
        seen.add(cleaned)
    return "|".join(ordered)


def load_work_cid_registry(path: Path = DEFAULT_WORK_CID_REGISTRY_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    by_folder_path: dict[str, dict[str, str]] = {}
    for row in rows:
        folder_path = (row.get("folder_path") or "").strip()
        work_cid = (row.get("work_cid") or "").strip()
        if not folder_path or not work_cid:
            continue
        by_folder_path[folder_path] = row
    return by_folder_path


def write_work_cid_registry(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=WORK_CID_REGISTRY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
