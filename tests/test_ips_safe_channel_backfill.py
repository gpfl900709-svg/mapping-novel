from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for path in (REPO_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ips_safe_channel_backfill import CONTRACT_CHECK_ACTION, build_candidates  # noqa: E402


class IpsSafeChannelBackfillTest(unittest.TestCase):
    def test_build_candidates_requires_contract_check_before_add_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "report.csv"
            ips_path = root / "ips.xlsx"
            output_path = root / "safe.csv"
            excluded_path = root / "excluded.csv"
            summary_path = root / "summary.json"

            pd.DataFrame(
                [
                    {
                        "S2_미매핑상세사유": "해당채널 지급정산 없음 / 타채널 지급정산 존재",
                        "S2 판매채널": "에피루스 이북클럽(B2C)",
                        "S2_미매핑근거": "콘텐츠ID=295590",
                        "S2_판매채널콘텐츠_후보수": "0",
                        "S2_정산정보누락_후보수": "0",
                        "청구정산_후보수": "0",
                        "정제_상품명": "몬스터홀",
                        "정산서_대표콘텐츠명": "몬스터 홀 100화",
                    }
                ]
            ).to_csv(report_path, index=False, encoding="utf-8-sig")
            pd.DataFrame([{"콘텐츠ID": "295590"}]).to_excel(ips_path, index=False)

            build_candidates(
                SimpleNamespace(
                    report=str(report_path),
                    ips=str(ips_path),
                    output=str(output_path),
                    excluded_output=str(excluded_path),
                    summary=str(summary_path),
                )
            )

            safe_rows = pd.read_csv(output_path, dtype=str).fillna("")

        self.assertEqual(len(safe_rows), 1)
        self.assertEqual(safe_rows.loc[0, "next_action"], CONTRACT_CHECK_ACTION)
        self.assertEqual(safe_rows.loc[0, "contract_gate"], "source_contract_id_required")


if __name__ == "__main__":
    unittest.main()
