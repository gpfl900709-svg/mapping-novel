from __future__ import annotations

import unittest

import pandas as pd

from scripts.refresh_s2_sales_channel_contents import build_targets, fetch_service_contents


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.headers = {"X-KISS-API-BASE-URL": "https://kiss-api.example"}
        self.calls: list[dict] = []

    def get(self, url: str, *, params: dict, timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse({"data": [{"schnCtnsId": "SVC-1", "ctnsId": "CID-1", "ctnsNm": "작품"}]})


class RefreshS2SalesChannelContentsTest(unittest.TestCase):
    def test_build_targets_records_missing_catalog_channels_without_failing(self) -> None:
        catalog = pd.DataFrame(
            [
                {
                    "schnId": "S-1",
                    "schnNm": "원스토어(소설)",
                    "bcncCd": "B-1",
                    "bcncNm": "거래처",
                    "ctnsStleCdNm": "소설",
                }
            ]
        )

        targets, audit = build_targets(catalog)

        self.assertTrue(any(target["schn_nm"] == "원스토어(소설)" for target in targets))
        self.assertTrue(any(row["상태"] == "missing_channel_catalog" for row in audit))

    def test_build_targets_keeps_base_and_special_channels_for_same_platform(self) -> None:
        catalog = pd.DataFrame(
            [
                {
                    "schnId": "R-NOVEL",
                    "schnNm": "리디북스(소설)",
                    "bcncCd": "RIDIBOOKS",
                    "bcncNm": "리디",
                    "ctnsStleCdNm": "소설",
                },
                {
                    "schnId": "R-EVENT",
                    "schnNm": "리디북스(이벤트)",
                    "bcncCd": "RIDIBOOKS",
                    "bcncNm": "리디",
                    "ctnsStleCdNm": "소설",
                },
            ]
        )

        targets, audit = build_targets(catalog)

        channels = {target["schn_nm"] for target in targets}
        targeted = {row["판매채널명"] for row in audit if row["상태"] == "targeted"}
        self.assertIn("리디북스(소설)", channels)
        self.assertIn("리디북스(이벤트)", channels)
        self.assertIn("리디북스(소설)", targeted)
        self.assertIn("리디북스(이벤트)", targeted)

    def test_fetch_service_contents_sends_content_style_filter(self) -> None:
        session = FakeSession()
        target = {"bcnc_cd": "B-1", "schn_id": "S-1"}

        rows = fetch_service_contents(session, target, content_style_code="102")

        self.assertEqual(rows[0]["schnCtnsId"], "SVC-1")
        self.assertEqual(session.calls[0]["url"], "https://kiss-api.example/sale/ext/ext-salm/schn-ctns")
        self.assertEqual(session.calls[0]["params"]["bcncCd"], "B-1")
        self.assertEqual(session.calls[0]["params"]["schnIds"], "S-1")
        self.assertEqual(session.calls[0]["params"]["ctnsStleCd"], "102")


if __name__ == "__main__":
    unittest.main()
