import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops" / "scripts"))

import create_kipm_dummy_contract as dummy_contract


class _VisibleLabels:
    def filter(self, **kwargs):
        return self

    def count(self):
        return 1


class _Page:
    def locator(self, selector):
        return _VisibleLabels()


class DummyContractChannelTest(unittest.TestCase):
    def test_contract_base_channel_is_kyobo_only(self):
        self.assertEqual(
            dummy_contract.CONTRACT_BASE_CHANNEL_SELECTIONS,
            (
                ("서비스가능판매채널", "외부유통"),
                ("상위판매채널", "서드유통-일반(국내)"),
                ("하위판매채널", "교보문고(소설)"),
            ),
        )

    def test_already_selected_base_channel_is_not_reopened(self):
        values = {
            "서비스가능판매채널": "외부유통",
            "상위판매채널": "서드유통-일반(국내)",
            "하위판매채널": "교보문고(소설)",
        }
        with (
            patch.object(dummy_contract, "read_select_value", side_effect=lambda page, label: values[label]),
            patch.object(dummy_contract, "choose_select_with_retry") as choose,
        ):
            dummy_contract.ensure_contract_base_channel_fields(_Page())

        choose.assert_not_called()

    def test_empty_base_channel_is_forced_to_kyobo_defaults(self):
        values = {
            "서비스가능판매채널": "외부유통",
            "상위판매채널": "서드유통-일반(국내)",
            "하위판매채널": "",
        }
        with (
            patch.object(dummy_contract, "read_select_value", side_effect=lambda page, label: values[label]),
            patch.object(dummy_contract, "choose_select_with_retry") as choose,
        ):
            page = _Page()
            dummy_contract.ensure_contract_base_channel_fields(page)

        choose.assert_called_once_with(page, page, "하위판매채널", "교보문고(소설)")

    def test_known_content_name_skips_step1_content_name_read(self):
        spec = dummy_contract.DummyContractSpec(
            cid="328118",
            holder_name="AP 북스",
            pdf_path=Path("dummy.pdf"),
            grade="성인",
            content_name="성인용품점 온 새댁을_정나미_1000114_일반",
        )

        with patch.object(dummy_contract, "read_field_value") as read_field:
            content_name, grade_name = dummy_contract.resolve_contract_content_metadata(_Page(), spec)

        self.assertEqual(content_name, "성인용품점 온 새댁을_정나미_1000114_일반")
        self.assertEqual(grade_name, "성인")
        read_field.assert_not_called()

    def test_explicit_rs_rate_overrides_grade_default(self):
        self.assertEqual(dummy_contract.resolve_rs_rate("비성인", 50), 50)
        self.assertEqual(dummy_contract.resolve_rs_rate("비성인", 0, allow_zero_rs=True), 0)

    def test_rs_rate_without_account_explicit_value_is_not_defaulted(self):
        with self.assertRaisesRegex(dummy_contract.DummyContractError, "등급 기본값"):
            dummy_contract.resolve_rs_rate("비성인", 0)

    def test_account_rs_guard_requires_account_evidence(self):
        spec = dummy_contract.DummyContractSpec(
            cid="328118",
            holder_name="AP 북스",
            pdf_path=Path("dummy.pdf"),
            rs_rate=50,
        )

        with self.assertRaisesRegex(dummy_contract.DummyContractError, "account"):
            dummy_contract.validate_account_rs_guard(spec)

    def test_account_rs_guard_accepts_matching_account_rate(self):
        spec = dummy_contract.DummyContractSpec(
            cid="328118",
            holder_name="AP 북스",
            pdf_path=Path("dummy.pdf"),
            account_rights_code="1000114",
            account_rights_name="기본정산율",
            account_rs_rate=50,
            rs_rate=50,
        )

        dummy_contract.validate_account_rs_guard(spec)

    def test_account_rs_guard_accepts_explicit_zero_rate_override(self):
        spec = dummy_contract.DummyContractSpec(
            cid="160166",
            holder_name="소설사업부(미정산)",
            pdf_path=Path("dummy.pdf"),
            account_rights_code="IPS_ONLY_UNSETTLED",
            account_rights_name="소설사업부(미정산)",
            account_rs_rate=0,
            rs_rate=0,
            allow_zero_rs=True,
        )

        dummy_contract.validate_account_rs_guard(spec)

    def test_account_rs_guard_rejects_mismatched_rate(self):
        spec = dummy_contract.DummyContractSpec(
            cid="109694",
            holder_name="EpyruS",
            pdf_path=Path("dummy.pdf"),
            account_rights_code="1000000",
            account_rights_name="기본정산율",
            account_rs_rate=35,
            rs_rate=70,
        )

        with self.assertRaisesRegex(dummy_contract.DummyContractError, "account 확인값과 다릅니다"):
            dummy_contract.validate_account_rs_guard(spec)

    def test_create_dummy_contract_enforces_account_rs_guard_before_page_work(self):
        spec = dummy_contract.DummyContractSpec(
            cid="328118",
            holder_name="AP 북스",
            pdf_path=Path("dummy.pdf"),
            rs_rate=50,
        )

        with self.assertRaisesRegex(dummy_contract.DummyContractError, "account"):
            dummy_contract.create_dummy_contract(_Page(), spec)

    def test_counterparty_search_aliases_cover_vendor_names(self):
        self.assertEqual(dummy_contract.resolve_counterparty_search_name("APBOOKS"), "AP 북스")
        self.assertEqual(dummy_contract.resolve_counterparty_search_name("AP북스"), "AP 북스")
        self.assertEqual(dummy_contract.resolve_counterparty_search_name("ebook21"), "조은커뮤니티")
        self.assertEqual(dummy_contract.resolve_counterparty_search_name("이북21"), "조은커뮤니티")
        self.assertEqual(dummy_contract.resolve_counterparty_search_name("박준호"), "박준호")


if __name__ == "__main__":
    unittest.main()
