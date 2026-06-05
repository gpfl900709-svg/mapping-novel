from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_SCRIPTS = REPO_ROOT / "ops" / "scripts"
if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

from google_sheet_generated_id_uploader import build_upload_plan, build_upload_rows, is_safe_sales_channel_content_id


class GoogleSheetGeneratedIdUploaderTest(unittest.TestCase):
    def test_sales_channel_content_id_must_be_positive_numeric(self) -> None:
        self.assertTrue(is_safe_sales_channel_content_id("906884"))
        self.assertFalse(is_safe_sales_channel_content_id(""))
        self.assertFalse(is_safe_sales_channel_content_id("0"))
        self.assertFalse(is_safe_sales_channel_content_id("인간 판단 필요 : 통합 계약 ID 복수"))

    def test_build_upload_rows_skips_review_notes_for_id_column(self) -> None:
        uploads = build_upload_rows(
            [
                {
                    "__row_id": "7",
                    "next_action": "paste_sales_channel_content_id",
                    "sales_channel_content_id": "인간 판단 필요 : 통합 계약 ID 복수",
                }
            ],
            value_column="sales_channel_content_id",
            action_column="next_action",
            required_action="paste_sales_channel_content_id",
            row_id_columns=["__row_id"],
            column_letter="E",
            limit=0,
        )

        self.assertEqual(uploads, [])

    def test_build_upload_rows_accepts_numeric_id(self) -> None:
        uploads = build_upload_rows(
            [
                {
                    "__row_id": "7",
                    "next_action": "paste_sales_channel_content_id",
                    "sales_channel_content_id": "906884",
                    "settlement_verified_contract_id": "86248",
                    "settlement_verification_status": "detail_platform_list",
                    "input_title": "골 때리는 엄마들",
                    "input_platform": "밀리의 서재",
                }
            ],
            value_column="sales_channel_content_id",
            action_column="next_action",
            required_action="paste_sales_channel_content_id",
            row_id_columns=["__row_id"],
            column_letter="E",
            limit=0,
        )

        self.assertEqual(len(uploads), 1)
        self.assertEqual(uploads[0].cell_ref, "E7")
        self.assertEqual(uploads[0].value, "906884")

    def test_build_upload_rows_blocks_numeric_id_without_contract_evidence(self) -> None:
        plan = build_upload_plan(
            [
                {
                    "__row_id": "7",
                    "next_action": "paste_sales_channel_content_id",
                    "sales_channel_content_id": "906884",
                }
            ],
            value_column="sales_channel_content_id",
            action_column="next_action",
            required_action="paste_sales_channel_content_id",
            row_id_columns=["__row_id"],
            column_letter="E",
            limit=0,
        )

        self.assertEqual(plan.uploads, [])
        self.assertEqual(plan.blocked_rows[0]["sheet_upload_gate_status"], "blocked_missing_contract_id")

    def test_build_upload_rows_blocks_payment_setup_only_evidence(self) -> None:
        plan = build_upload_plan(
            [
                {
                    "__row_id": "7",
                    "next_action": "paste_sales_channel_content_id",
                    "sales_channel_content_id": "906884",
                    "settlement_source_row_status": "payment_setup_linked",
                    "settlement_source_payment_setup_id": "1071696",
                }
            ],
            value_column="sales_channel_content_id",
            action_column="next_action",
            required_action="paste_sales_channel_content_id",
            row_id_columns=["__row_id"],
            column_letter="E",
            limit=0,
        )

        self.assertEqual(plan.uploads, [])
        self.assertEqual(plan.blocked_rows[0]["sheet_upload_gate_status"], "blocked_payment_setup_only")

    def test_unverified_id_override_requires_reason(self) -> None:
        rows = [
            {
                "__row_id": "7",
                "next_action": "paste_sales_channel_content_id",
                "sales_channel_content_id": "906884",
            }
        ]

        blocked_plan = build_upload_plan(
            rows,
            value_column="sales_channel_content_id",
            action_column="next_action",
            required_action="paste_sales_channel_content_id",
            row_id_columns=["__row_id"],
            column_letter="E",
            limit=0,
            allow_unverified_id=True,
        )
        allowed_plan = build_upload_plan(
            rows,
            value_column="sales_channel_content_id",
            action_column="next_action",
            required_action="paste_sales_channel_content_id",
            row_id_columns=["__row_id"],
            column_letter="E",
            limit=0,
            allow_unverified_id=True,
            unverified_id_reason="operator-reviewed disposable sheet backfill",
        )

        self.assertEqual(blocked_plan.uploads, [])
        self.assertEqual(blocked_plan.blocked_rows[0]["sheet_upload_gate_status"], "blocked_missing_contract_id")
        self.assertEqual(len(allowed_plan.uploads), 1)


if __name__ == "__main__":
    unittest.main()
