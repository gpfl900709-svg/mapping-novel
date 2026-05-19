from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus

import requests

SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from build_ips_contract_id_map import build_api_url, build_authenticated_session, fetch_contract_rows


PROJECT_ROOT = Path(__file__).resolve().parents[1] / "SIAAN Project"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "exports" / "ips_contract_attachments"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download KIPM 계약 첨부파일 for one or more CID values through "
            "[7021] 콘텐츠상세 > 정산정보 > 계약목록 attachment download."
        ),
    )
    parser.add_argument(
        "--cid",
        action="append",
        required=True,
        help="Target CID. Repeatable.",
    )
    parser.add_argument(
        "--attachment-name-contains",
        action="append",
        default=[],
        help=(
            "Optional attachment or contract-name substring filter. "
            "Repeatable; rows matching any token are kept."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional output directory. Defaults to a timestamped export directory.",
    )
    parser.add_argument(
        "--env-file",
        default="",
        help="Optional env file path for KIPM credentials.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Page size to request from the 계약목록 API.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing file path instead of creating a unique suffix.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect matching attachments without downloading files.",
    )
    return parser.parse_args()


def build_output_dir(args: argparse.Namespace) -> Path | None:
    if args.dry_run:
        return None
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT_ROOT / f"{stamp}__ips_contract_attachments"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def safe_filename(value: str, *, fallback: str = "attachment", max_length: int = 120) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = text or fallback
    if len(text) <= max_length:
        return text

    stem, dot, suffix = text.rpartition(".")
    suffix_text = f"{dot}{suffix}" if dot and len(suffix) <= 15 else ""
    base_text = stem if suffix_text else text
    allowed = max(1, max_length - len(suffix_text))
    shortened = base_text[:allowed].rstrip(" ._")
    return f"{shortened or fallback}{suffix_text}"


def parse_content_disposition_filename(header_value: str) -> str:
    header_text = str(header_value or "").strip()
    if not header_text:
        return ""

    filename_star_match = re.search(
        r"filename\*\s*=\s*(?:UTF-8''|utf-8'')?([^;]+)",
        header_text,
        flags=re.IGNORECASE,
    )
    if filename_star_match:
        return unquote_plus(filename_star_match.group(1).strip().strip('"'))

    filename_match = re.search(
        r"filename\s*=\s*\"([^\"]+)\"|filename\s*=\s*([^;]+)",
        header_text,
        flags=re.IGNORECASE,
    )
    if filename_match:
        raw_value = (filename_match.group(1) or filename_match.group(2) or "").strip().strip('"')
        return unquote_plus(raw_value)
    return ""


def resolve_response_filename(
    response: requests.Response,
    *,
    fallback_name: str,
    cid: str,
    contract_id: str,
    attachment_id: str,
) -> str:
    content_disposition = response.headers.get("Content-Disposition") or response.headers.get("content-disposition") or ""
    response_name = parse_content_disposition_filename(content_disposition)
    if response_name:
        return safe_filename(response_name)

    if fallback_name:
        return safe_filename(fallback_name)

    stem = "__".join(
        value
        for value in (cid.strip(), contract_id.strip(), attachment_id.strip())
        if value
    )
    return safe_filename(f"{stem or 'attachment'}.bin")


def build_saved_filename(
    *,
    cid: str,
    contract_id: str,
    attachment_id: str,
    original_name: str,
) -> str:
    prefix = "__".join(
        value
        for value in (str(cid or "").strip(), str(contract_id or "").strip(), str(attachment_id or "").strip())
        if value
    )
    if not prefix:
        prefix = "attachment"
    return f"{safe_filename(prefix)}__{safe_filename(original_name)}"


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}__{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def contract_matches_filters(contract: dict[str, Any], filters: list[str]) -> bool:
    if not filters:
        return True
    haystack = " ".join(
        str(contract.get(key) or "").lower()
        for key in ("atchfOrgNm", "cntrNm", "cntrPtnNm", "relCntrNm")
    )
    normalized_filters = [str(value or "").strip().lower() for value in filters if str(value or "").strip()]
    if not normalized_filters:
        return True
    return any(token in haystack for token in normalized_filters)


def download_attachment(
    session: requests.Session,
    *,
    api_base_url: str,
    attachment_id: str,
    fallback_name: str,
    output_dir: Path,
    cid: str,
    contract_id: str,
    overwrite: bool,
) -> tuple[Path, str]:
    response = session.get(
        build_api_url(api_base_url, f"media/cntr/download-file/{attachment_id}"),
        stream=True,
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"첨부 다운로드 실패: HTTP {response.status_code} {response.text[:300]}")

    original_name = resolve_response_filename(
        response,
        fallback_name=fallback_name,
        cid=cid,
        contract_id=contract_id,
        attachment_id=attachment_id,
    )
    target_path = output_dir / build_saved_filename(
        cid=cid,
        contract_id=contract_id,
        attachment_id=attachment_id,
        original_name=original_name,
    )
    if not overwrite:
        target_path = ensure_unique_path(target_path)

    with target_path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if chunk:
                handle.write(chunk)
    return target_path, original_name


def build_manifest_row(
    *,
    cid: str,
    contract: dict[str, Any] | None,
    contract_count: int,
    status: str,
    filter_tokens: list[str],
    saved_path: str = "",
    original_name: str = "",
    error: str = "",
) -> dict[str, Any]:
    contract = contract or {}
    attachment_id = str(contract.get("atchfId") or "").strip()
    contract_id = str(contract.get("cntrId") or "").strip()
    return {
        "cid": cid,
        "contract_count": contract_count,
        "status": status,
        "filter_tokens": " | ".join(str(token).strip() for token in filter_tokens if str(token).strip()),
        "visible_contract_id": contract_id,
        "unity_contract_id": str(contract.get("unityCntrId") or "").strip(),
        "attachment_id": attachment_id,
        "attachment_name": str(contract.get("atchfOrgNm") or "").strip(),
        "resolved_file_name": original_name,
        "contract_name": str(contract.get("cntrNm") or "").strip(),
        "contract_kind": str(contract.get("cntrKndNm") or "").strip(),
        "contract_kind_code": str(contract.get("cntrKndCd") or "").strip(),
        "counterparty_name": str(contract.get("cntrPtnNm") or "").strip(),
        "related_contract_name": str(contract.get("relCntrNm") or "").strip(),
        "contract_date": str(contract.get("cntrCclsDt") or "").strip(),
        "contract_status": str(contract.get("cntrStsNm") or "").strip(),
        "is_primary_contract": str(contract.get("ocntrYn") or "").strip(),
        "saved_path": saved_path,
        "download_url": build_api_url("https://kipm-api.kld.kr", f"media/cntr/download-file/{attachment_id}") if attachment_id else "",
        "error": error,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key in seen:
                continue
            seen.add(key)
            fieldnames.append(key)

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    output_dir = build_output_dir(args)
    filters = [str(value or "").strip() for value in args.attachment_name_contains if str(value or "").strip()]

    site, session = build_authenticated_session(args.env_file)

    manifest_rows: list[dict[str, Any]] = []
    downloaded = 0
    matched = 0
    no_contract = 0
    no_match = 0
    no_attachment = 0
    errors = 0

    for raw_cid in args.cid:
        cid = str(raw_cid or "").strip()
        if not cid:
            continue
        print(f"[contracts] cid={cid}")
        try:
            contracts, total = fetch_contract_rows(
                session,
                api_base_url=site.api_base_url,
                cid=cid,
                page_size=args.page_size,
            )
        except Exception as exc:  # noqa: BLE001
            errors += 1
            manifest_rows.append(
                build_manifest_row(
                    cid=cid,
                    contract=None,
                    contract_count=0,
                    status="error",
                    filter_tokens=filters,
                    error=str(exc),
                ),
            )
            continue

        if not contracts:
            no_contract += 1
            manifest_rows.append(
                build_manifest_row(
                    cid=cid,
                    contract=None,
                    contract_count=total,
                    status="no_contract",
                    filter_tokens=filters,
                ),
            )
            continue

        matching_contracts = [contract for contract in contracts if contract_matches_filters(contract, filters)]
        if not matching_contracts:
            no_match += 1
            manifest_rows.append(
                build_manifest_row(
                    cid=cid,
                    contract=None,
                    contract_count=total,
                    status="no_matching_attachment",
                    filter_tokens=filters,
                ),
            )
            continue

        matched += len(matching_contracts)
        for contract in matching_contracts:
            attachment_id = str(contract.get("atchfId") or "").strip()
            attachment_name = str(contract.get("atchfOrgNm") or "").strip()
            contract_id = str(contract.get("cntrId") or "").strip()

            if not attachment_id:
                no_attachment += 1
                manifest_rows.append(
                    build_manifest_row(
                        cid=cid,
                        contract=contract,
                        contract_count=total,
                        status="missing_attachment_id",
                        filter_tokens=filters,
                    ),
                )
                continue

            if args.dry_run:
                manifest_rows.append(
                    build_manifest_row(
                        cid=cid,
                        contract=contract,
                        contract_count=total,
                        status="matched",
                        filter_tokens=filters,
                    ),
                )
                continue

            assert output_dir is not None
            try:
                saved_path, resolved_name = download_attachment(
                    session,
                    api_base_url=site.api_base_url,
                    attachment_id=attachment_id,
                    fallback_name=attachment_name,
                    output_dir=output_dir,
                    cid=cid,
                    contract_id=contract_id,
                    overwrite=args.overwrite,
                )
                downloaded += 1
                manifest_rows.append(
                    build_manifest_row(
                        cid=cid,
                        contract=contract,
                        contract_count=total,
                        status="downloaded",
                        filter_tokens=filters,
                        saved_path=str(saved_path),
                        original_name=resolved_name,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                errors += 1
                manifest_rows.append(
                    build_manifest_row(
                        cid=cid,
                        contract=contract,
                        contract_count=total,
                        status="download_error",
                        filter_tokens=filters,
                        error=str(exc),
                    ),
                )

    csv_path = ""
    json_path = ""
    if not args.dry_run and output_dir is not None:
        csv_output = output_dir / "manifest.csv"
        json_output = output_dir / "manifest.json"
        write_csv(csv_output, manifest_rows)
        json_output.write_text(json.dumps({"rows": manifest_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        csv_path = str(csv_output)
        json_path = str(json_output)

    summary = {
        "cid_count": len([str(value or "").strip() for value in args.cid if str(value or "").strip()]),
        "matched_contract_rows": matched,
        "downloaded": downloaded,
        "no_contract": no_contract,
        "no_matching_attachment": no_match,
        "missing_attachment_id": no_attachment,
        "errors": errors,
        "output_dir": str(output_dir) if output_dir is not None else "",
        "csv_output": csv_path,
        "json_output": json_path,
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
