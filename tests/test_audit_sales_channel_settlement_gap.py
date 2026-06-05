from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from kiss_payment_settlement import CONTRACT_ID_COLUMN
from scripts.audit_sales_channel_settlement_gap import load_settlement_lookup


class AuditSalesChannelSettlementGapTest(unittest.TestCase):
    def test_settlement_lookup_loader_keeps_only_contract_linked_rows(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "판매채널콘텐츠ID": "S-ZERO",
                    "판매채널명": "테스트 채널",
                    "콘텐츠ID": "C-ZERO",
                    "콘텐츠명": "계약 0 작품",
                    CONTRACT_ID_COLUMN: "0",
                },
                {
                    "판매채널콘텐츠ID": "S-OK",
                    "판매채널명": "테스트 채널",
                    "콘텐츠ID": "C-OK",
                    "콘텐츠명": "계약 연결 작품",
                    CONTRACT_ID_COLUMN: "86000",
                },
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lookup.csv"
            frame.to_csv(path, index=False, encoding="utf-8-sig")

            loaded = load_settlement_lookup(path)

        self.assertEqual(loaded["판매채널콘텐츠ID"].tolist(), ["S-OK"])
        self.assertEqual(loaded[CONTRACT_ID_COLUMN].tolist(), ["86000"])


if __name__ == "__main__":
    unittest.main()
