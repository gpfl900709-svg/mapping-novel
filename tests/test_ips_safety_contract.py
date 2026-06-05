from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_SCRIPTS = REPO_ROOT / "ops" / "scripts"
if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

from ips_safety_contract import (  # noqa: E402
    SafetyStatus,
    classify_sheet_uploadable_sales_channel_row,
    first_nonzero_contract_id,
    is_positive_numeric_id,
)


class IpsSafetyContractTest(unittest.TestCase):
    def test_positive_numeric_id_normalizes_float_string(self) -> None:
        self.assertTrue(is_positive_numeric_id("906884.0"))
        self.assertFalse(is_positive_numeric_id("0"))
        self.assertFalse(is_positive_numeric_id("인간 판단 필요"))

    def test_first_nonzero_contract_id_uses_known_columns(self) -> None:
        self.assertEqual(
            first_nonzero_contract_id({"settlement_verified_contract_id": "0", "source_contract_id": "86248"}),
            "86248",
        )

    def test_sheet_upload_requires_contract_and_verification(self) -> None:
        decision = classify_sheet_uploadable_sales_channel_row(
            {
                "next_action": "paste_sales_channel_content_id",
                "sales_channel_content_id": "906884",
                "settlement_verified_contract_id": "86248",
                "settlement_verification_status": "detail_platform_list",
            }
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.contract_id, "86248")

    def test_sheet_upload_blocks_payment_setup_only(self) -> None:
        decision = classify_sheet_uploadable_sales_channel_row(
            {
                "next_action": "paste_sales_channel_content_id",
                "sales_channel_content_id": "906884",
                "settlement_source_row_status": "payment_setup_linked",
                "settlement_source_payment_setup_id": "1071696",
            }
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.status, SafetyStatus.BLOCKED_PAYMENT_SETUP_ONLY)

    def test_sheet_upload_blocks_contract_without_verification_status(self) -> None:
        decision = classify_sheet_uploadable_sales_channel_row(
            {
                "next_action": "paste_sales_channel_content_id",
                "sales_channel_content_id": "906884",
                "settlement_verified_contract_id": "86248",
            }
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.status, SafetyStatus.BLOCKED_MISSING_VERIFICATION)

    def test_sheet_upload_accepts_s2_nonzero_contract_verification(self) -> None:
        decision = classify_sheet_uploadable_sales_channel_row(
            {
                "next_action": "paste_sales_channel_content_id",
                "sales_channel_content_id": "906884",
                "s2_payment_contract_status": "contract_nonzero",
                "s2_통합계약ID": "86248",
            }
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.contract_id, "86248")


if __name__ == "__main__":
    unittest.main()
