from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_SCRIPTS = REPO_ROOT / "ops" / "scripts"
for path in (REPO_ROOT, OPS_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from kiss_payment_settlement import CONTRACT_ID_COLUMN  # noqa: E402
from s2_sales_channel_id_verifier import verify_rows  # noqa: E402


class S2SalesChannelIdVerifierTest(unittest.TestCase):
    def test_contract_nonzero_keeps_paste_action(self) -> None:
        rows = [
            {
                "next_action": "paste_sales_channel_content_id",
                "sales_channel_content_id": "906884",
            }
        ]
        s2 = pd.DataFrame(
            [
                {
                    "판매채널콘텐츠ID": "906884",
                    "판매채널명": "무툰(소설 서비스)",
                    "콘텐츠명": "마왕이 나노머신을 숨김",
                    CONTRACT_ID_COLUMN: "86248",
                }
            ]
        )

        verified = verify_rows(rows, s2, id_column="sales_channel_content_id", platform_column="input_platform", title_column="input_title")

        self.assertEqual(verified[0]["s2_payment_contract_status"], "contract_nonzero")
        self.assertEqual(verified[0]["s2_통합계약ID"], "86248")
        self.assertEqual(verified[0]["next_action"], "paste_sales_channel_content_id")
        self.assertEqual(verified[0]["sheet_upload_gate_status"], "passed")
        self.assertEqual(verified[0]["sheet_upload_contract_id"], "86248")

    def test_missing_or_zero_contract_blocks_paste_action(self) -> None:
        rows = [
            {
                "next_action": "paste_sales_channel_content_id",
                "sales_channel_content_id": "906884",
            }
        ]
        s2 = pd.DataFrame(columns=["판매채널콘텐츠ID", "판매채널명", "콘텐츠명", CONTRACT_ID_COLUMN])

        verified = verify_rows(rows, s2, id_column="sales_channel_content_id", platform_column="input_platform", title_column="input_title")

        self.assertEqual(verified[0]["s2_payment_contract_status"], "missing_or_contract_zero")
        self.assertEqual(verified[0]["next_action"], "check_source_contract_id")
        self.assertEqual(verified[0]["sheet_upload_gate_status"], "blocked_missing_contract_id")


if __name__ == "__main__":
    unittest.main()
