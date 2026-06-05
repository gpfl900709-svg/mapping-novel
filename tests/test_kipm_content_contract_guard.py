from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_SCRIPTS = REPO_ROOT / "ops" / "scripts"
if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

from create_kipm_content_contract import build_spec  # noqa: E402


class KipmContentContractGuardTest(unittest.TestCase):
    def test_build_spec_carries_account_rs_evidence_to_dummy_contract_step(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
            args = argparse.Namespace(
                folder_path="",
                pdf_path=handle.name,
                title="마왕이 나노머신을 숨김",
                author="갈드",
                copyright_code="1005302",
                special_kind="선인세없음",
                holder_name="김관표",
                release_date="2026-06-05",
                book_price="100",
                rental_price="100",
                isbn="9790000000000",
                contract_name="마왕이 나노머신을 숨김_갈드_1005302_선인세없음_확정",
                counterparty_type="개인",
                counterparty_code="",
                pen_name="갈드",
                existing_cid="109843",
                account_rights_code="1005302",
                account_rights_name="기본정산율",
                account_rs_rate=80,
                rs_rate=80,
                allow_zero_rs=False,
            )

            spec = build_spec(args, registry_match=None)

        self.assertEqual(spec.account_rights_code, "1005302")
        self.assertEqual(spec.account_rights_name, "기본정산율")
        self.assertEqual(spec.account_rs_rate, 80)
        self.assertEqual(spec.rs_rate, 80)


if __name__ == "__main__":
    unittest.main()
