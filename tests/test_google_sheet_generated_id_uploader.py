from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_SCRIPTS = REPO_ROOT / "ops" / "scripts"
if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

from google_sheet_generated_id_uploader import build_upload_rows, is_safe_sales_channel_content_id


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


if __name__ == "__main__":
    unittest.main()
