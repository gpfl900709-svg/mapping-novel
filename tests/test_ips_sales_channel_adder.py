from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_SCRIPTS = REPO_ROOT / "ops" / "scripts"
if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

from ips_sales_channel_adder import (
    build_requests,
    channel_from_existing_platform_row,
    classify_unresolved_generated_id,
    choose_settlement_source_row_index,
    choose_settlement_template_row,
    extract_unified_contract_id,
    find_platform_row_for_contract,
    get_row_contract_id,
    row_has_approved_status,
    row_has_unified_contract_id,
)


class IpsSalesChannelAdderTest(unittest.TestCase):
    def test_approval_status_does_not_treat_unapproved_as_approved(self) -> None:
        self.assertFalse(row_has_approved_status("미승인"))
        self.assertTrue(row_has_approved_status("승인"))
        self.assertTrue(row_has_approved_status("6\n교보문고(소설)\n승인\n83016"))

    def test_prefers_bottommost_approved_row(self) -> None:
        rows = [
            "1\n원스토어(소설)\n미승인\n83016",
            "2\n리디북스(소설)\n승인\n83016",
            "3\n교보문고(소설)\n승인\n83016",
        ]

        self.assertEqual(choose_settlement_source_row_index(rows), 2)

    def test_extracts_unified_contract_id_after_status_cell(self) -> None:
        self.assertEqual(extract_unified_contract_id("10\n교보문고(소설)\n미승인\n85999\n박준호"), 85999)
        self.assertEqual(extract_unified_contract_id("1\n미스터블루(소설)\n승인\n0\n지급"), 0)
        self.assertFalse(row_has_unified_contract_id("1\n미스터블루(소설)\n승인\n0\n지급"))

    def test_prefers_bottommost_nonzero_contract_row_before_approval_when_single_contract(self) -> None:
        rows = [
            "1\n미스터블루(소설)\n승인\n0",
            "2\n교보문고(소설)\n미승인\n85999",
            "3\n교보문고(소설)\n미승인\n85999",
        ]

        self.assertEqual(choose_settlement_source_row_index(rows), 2)

    def test_multiple_nonzero_contract_rows_require_explicit_choice(self) -> None:
        rows = [
            "1\n미스터블루(소설)\n승인\n0",
            "2\n교보문고(소설)\n미승인\n86000",
            "3\n교보문고(소설)\n미승인\n85999",
        ]

        with self.assertRaisesRegex(RuntimeError, "source_contract_id"):
            choose_settlement_source_row_index(rows)
        self.assertEqual(choose_settlement_source_row_index(rows, preferred_contract_id=85999), 2)

    def test_falls_back_to_bottom_row_when_none_are_approved(self) -> None:
        rows = [
            "1\n원스토어(소설)\n미승인\n83016",
            "2\n리디북스(소설)\n미승인\n83016",
        ]

        self.assertEqual(choose_settlement_source_row_index(rows), 1)

    def test_empty_rows_return_no_selection(self) -> None:
        self.assertEqual(choose_settlement_source_row_index(["", "  "]), -1)

    def test_template_source_requires_nonzero_contract_id(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "통합 계약 ID"):
            choose_settlement_template_row([{"pymtStd": "지급", "cntrId": 0}])

    def test_template_source_requires_explicit_choice_for_multiple_contract_ids(self) -> None:
        rows = [
            {"pymtStd": "지급", "cntrId": 0},
            {"pymtStd": "지급", "cntrId": 85999},
            {"pymtStd": "지급", "cntrId": 86000},
            {"pymtStd": "원천", "cntrId": 90000},
        ]

        with self.assertRaisesRegex(RuntimeError, "source_contract_id"):
            choose_settlement_template_row(rows)

        row = choose_settlement_template_row(rows, preferred_contract_id=85999)

        self.assertEqual(get_row_contract_id(row), 85999)

    def test_template_source_uses_single_nonzero_payment_contract_id(self) -> None:
        row = choose_settlement_template_row(
            [
                {"pymtStd": "지급", "cntrId": 0},
                {"pymtStd": "지급", "cntrId": 85999},
                {"pymtStd": "지급", "cntrId": 85999},
            ]
        )

        self.assertEqual(get_row_contract_id(row), 85999)

    def test_build_requests_accepts_source_contract_and_force_add_columns(self) -> None:
        requests = build_requests(
            [
                {
                    "next_action": "add_platform_in_ips",
                    "work_cid": "160492",
                    "input_platform": "원스토어(소설)",
                    "source_contract_id": "86011",
                    "force_add_existing_platform": "ㅇㅇ",
                }
            ],
            cid_column="work_cid",
            platform_column="input_platform",
            action_column="next_action",
            required_action="add_platform_in_ips",
            source_contract_id=0,
            source_contract_id_column="source_contract_id",
            force_add_existing_platform=False,
            force_add_existing_platform_column="force_add_existing_platform",
            limit=0,
        )

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].source_contract_id, 86011)
        self.assertTrue(requests[0].force_add_existing_platform)

    def test_find_platform_row_prefers_matching_contract_id(self) -> None:
        detail = {
            "schnCtnsInfoList": [
                {"lwerSchnNm": "원스토어(소설)", "schnCtnsId": "old", "cntrId": 0},
                {"lwerSchnNm": "원스토어(소설)", "schnCtnsId": "new", "cntrId": 86011},
            ]
        }

        matched = find_platform_row_for_contract(detail, "원스토어(소설)", 86011)

        self.assertIsNotNone(matched)
        self.assertEqual(matched["schnCtnsId"], "new")

    def test_existing_platform_row_can_supply_channel_code_for_forced_settlement(self) -> None:
        channel = channel_from_existing_platform_row(
            {"lwerSchnCd": "92", "lwerSchnNm": "원스토어(소설)", "schnCtnsId": "488201"}
        )

        self.assertEqual(channel, {"schnId": "92", "schnNm": "원스토어(소설)"})

    def test_classifies_missing_contract_as_sheet_status_value(self) -> None:
        status, value = classify_unresolved_generated_id(
            "판매채널 추가에는 통합 계약 ID가 있는 정산 기준행이 필요합니다. 계약변경등록에서 보강하세요."
        )

        self.assertEqual(status, "needs_contract")
        self.assertEqual(value, "판매채널 추가 보류 : source 통합 계약 ID 확인 필요")

    def test_classifies_multiple_contracts_as_human_judgment_value(self) -> None:
        status, value = classify_unresolved_generated_id(
            "통합 계약 ID가 여러 개라 자동 선택을 중단합니다. source_contract_id를 명시하세요."
        )

        self.assertEqual(status, "needs_explicit_contract")
        self.assertEqual(value, "인간 판단 필요 : 통합 계약 ID 복수")


if __name__ == "__main__":
    unittest.main()
