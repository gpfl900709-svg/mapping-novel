from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for path in (REPO_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from kiss_payment_settlement import CONTRACT_ID_COLUMN  # noqa: E402
from triage_generated_id_gaps import decide, read_payment_lookup  # noqa: E402


class GeneratedIdGapTriageTest(unittest.TestCase):
    def test_payment_lookup_loader_filters_zero_contract_id_rows(self) -> None:
        frame = pd.DataFrame(
            [
                {"콘텐츠명": "계약 0 작품", "판매채널명": "타채널", "판매채널콘텐츠ID": "S-ZERO", CONTRACT_ID_COLUMN: "0"},
                {"콘텐츠명": "계약 연결 작품", "판매채널명": "타채널", "판매채널콘텐츠ID": "S-OK", CONTRACT_ID_COLUMN: "86000"},
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "payment_lookup.csv"
            frame.to_csv(path, index=False, encoding="utf-8-sig")
            loaded = read_payment_lookup(path)

        self.assertEqual(loaded["판매채널콘텐츠ID"].tolist(), ["S-OK"])
        self.assertEqual(loaded[CONTRACT_ID_COLUMN].tolist(), ["86000"])

    def test_other_channel_payment_requires_ips_contract_id_gate(self) -> None:
        other_payment = pd.DataFrame(
            [
                {
                    "판매채널명": "네이버_장르",
                    "판매채널콘텐츠ID": "901218",
                    "콘텐츠명": "몬스터 홀",
                }
            ]
        )

        decision, action = decide(
            payment=pd.DataFrame(),
            sales_channel=pd.DataFrame(),
            missing=pd.DataFrame(),
            billing=pd.DataFrame(),
            other_payment=other_payment,
            other_sales_channel=pd.DataFrame(),
            fuzzy="",
        )

        self.assertEqual(decision, "S2_타채널지급정산_존재")
        self.assertIn("타채널 ID 입력 금지", action)
        self.assertIn("IPS 정산정보 source 통합 계약 ID 확인", action)
        self.assertIn("판매채널 추가 가능/계약·정산 연결 선행 여부 판단", action)
        self.assertNotIn("판매채널/지급정산 추가 대상", action)


if __name__ == "__main__":
    unittest.main()
