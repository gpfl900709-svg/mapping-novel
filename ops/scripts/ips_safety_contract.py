from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


class NextAction:
    PASTE_SALES_CHANNEL_CONTENT_ID = "paste_sales_channel_content_id"
    ADD_PLATFORM_IN_IPS = "add_platform_in_ips"
    CHECK_SOURCE_CONTRACT_ID = "check_source_contract_id"
    CONNECT_CONTRACT_BEFORE_SHEET = "connect_contract_before_sheet"
    MANUAL_REVIEW = "manual_review"


class SafetyStatus:
    PASSED = "passed"
    BLOCKED_INVALID_ID = "blocked_invalid_id"
    BLOCKED_PAYMENT_SETUP_ONLY = "blocked_payment_setup_only"
    BLOCKED_MISSING_CONTRACT_ID = "blocked_missing_contract_id"
    BLOCKED_MISSING_VERIFICATION = "blocked_missing_verification"
    BLOCKED_WRONG_ACTION = "blocked_wrong_action"


class EvidenceStatus:
    DETAIL_PLATFORM_LIST = "detail_platform_list"
    SETTLEMENT_TEMPLATE = "settlement_template"
    S2_CONTRACT_NONZERO = "contract_nonzero"
    S2_PASSED = "passed"


CONTRACT_ID_COLUMNS = (
    "settlement_verified_contract_id",
    "settlement_source_contract_id",
    "source_contract_id",
    "s2_통합계약ID",
    "통합계약ID",
    "통합 계약 ID",
    "cntrId",
    "unityCntrId",
    "srcCntrId",
)
PAYMENT_SETUP_ONLY_STATUSES = {"payment_setup_linked"}
SETTLEMENT_VERIFICATION_PASSED = {
    EvidenceStatus.DETAIL_PLATFORM_LIST,
    EvidenceStatus.SETTLEMENT_TEMPLATE,
}
S2_VERIFICATION_PASSED = {
    EvidenceStatus.S2_CONTRACT_NONZERO,
    EvidenceStatus.S2_PASSED,
}


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    status: str
    reason: str
    contract_id: str = ""


@dataclass(frozen=True)
class WriteRunManifest:
    run_id: str
    script: str
    mode: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    live_write: bool = False
    operator_note: str = ""
    source_input_path: str = ""
    source_input_sha256: str = ""
    s2_lookup_path: str = ""
    s2_lookup_sha256: str = ""
    preflight_status: str = ""
    postwrite_verification_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def text(value: Any) -> str:
    return str(value or "").strip()


def id_text(value: Any) -> str:
    raw = text(value).replace(",", "")
    if raw.endswith(".0"):
        raw = raw[:-2]
    return raw


def is_positive_numeric_id(value: Any) -> bool:
    raw = id_text(value)
    if not raw.isdigit():
        return False
    return int(raw) > 0


def is_nonzero_contract_id(value: Any) -> bool:
    return is_positive_numeric_id(value)


def first_nonzero_contract_id(row: dict[str, Any], columns: Iterable[str] = CONTRACT_ID_COLUMNS) -> str:
    for column in columns:
        value = id_text(row.get(column))
        if is_nonzero_contract_id(value):
            return value
    return ""


def settlement_verification_passed(row: dict[str, Any]) -> bool:
    status = text(row.get("settlement_verification_status"))
    return status in SETTLEMENT_VERIFICATION_PASSED


def s2_verification_passed(row: dict[str, Any]) -> bool:
    status = text(row.get("s2_payment_contract_status") or row.get("s2_contract_verification_status"))
    return status in S2_VERIFICATION_PASSED


def classify_sheet_uploadable_sales_channel_row(
    row: dict[str, Any],
    *,
    value_column: str = "sales_channel_content_id",
    action_column: str = "next_action",
    required_action: str = NextAction.PASTE_SALES_CHANNEL_CONTENT_ID,
    allow_unverified_id: bool = False,
) -> SafetyDecision:
    action = text(row.get(action_column))
    if action != required_action:
        return SafetyDecision(False, SafetyStatus.BLOCKED_WRONG_ACTION, f"next_action={action or '<blank>'}")

    value = id_text(row.get(value_column))
    if not is_positive_numeric_id(value):
        return SafetyDecision(False, SafetyStatus.BLOCKED_INVALID_ID, f"{value_column} is not a positive numeric ID")

    source_row_status = text(row.get("settlement_source_row_status"))
    if source_row_status in PAYMENT_SETUP_ONLY_STATUSES:
        return SafetyDecision(
            False,
            SafetyStatus.BLOCKED_PAYMENT_SETUP_ONLY,
            "payment setup evidence is not enough for sheet upload; nonzero contract ID is required",
        )

    contract_id = first_nonzero_contract_id(row)
    if not contract_id:
        if allow_unverified_id:
            return SafetyDecision(True, SafetyStatus.PASSED, "operator allowed unverified numeric ID", "")
        return SafetyDecision(
            False,
            SafetyStatus.BLOCKED_MISSING_CONTRACT_ID,
            "nonzero source/verified/S2 contract ID is required",
        )

    if settlement_verification_passed(row) or s2_verification_passed(row):
        return SafetyDecision(True, SafetyStatus.PASSED, "verified contract-linked sales-channel content", contract_id)

    if allow_unverified_id:
        return SafetyDecision(True, SafetyStatus.PASSED, "operator allowed ID without verification status", contract_id)

    return SafetyDecision(
        False,
        SafetyStatus.BLOCKED_MISSING_VERIFICATION,
        "settlement or S2 contract verification status is required",
        contract_id,
    )


def is_sheet_uploadable_sales_channel_row(row: dict[str, Any], **kwargs: Any) -> bool:
    return classify_sheet_uploadable_sales_channel_row(row, **kwargs).allowed


def apply_sheet_upload_gate_fields(row: dict[str, Any], decision: SafetyDecision) -> dict[str, Any]:
    output = dict(row)
    output["sheet_upload_gate_status"] = decision.status
    output["sheet_upload_gate_reason"] = decision.reason
    output["sheet_upload_contract_id"] = decision.contract_id
    return output


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return ""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_run_id(prefix: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", text(prefix)).strip("_") or "run"
    return f"{datetime.now():%Y%m%d_%H%M%S}__{cleaned}"


def write_manifest(path: str | Path, manifest: WriteRunManifest) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target
