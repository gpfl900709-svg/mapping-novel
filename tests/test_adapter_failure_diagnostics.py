from __future__ import annotations

import io
import unittest

import pandas as pd
from openpyxl import Workbook

from adapter_failure_diagnostics import (
    build_adapter_failure_payload,
    payload_json_bytes,
    render_failure_report_markdown,
    render_github_issue_body,
)


class AdapterFailureDiagnosticsTest(unittest.TestCase):
    def workbook_bytes(self) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "2026년 5월 네이버 일반 정산상세"
        sheet.append(["이용권 포함 컨텐츠별 매출 통계"])
        sheet.append([])
        sheet.append(["컨텐츠", "컨텐츠No", "공급자코드", "CP명", "작가명", "합계", "마켓수수료"])
        sheet.append(["테스트 작품", 113935, "87997", "바로북_일반도서", "테스트 작가", 7200, 0])
        payload = io.BytesIO()
        workbook.save(payload)
        return payload.getvalue()

    def test_payload_collects_sheet_snapshot_and_header_score(self) -> None:
        source_bytes = self.workbook_bytes()
        result = {
            "source_name": "2026년 5월 네이버 일반 정산상세.xlsx",
            "platform": "네이버",
            "s2_sales_channel": "네이버_일반",
            "status": "blocked",
            "error": "헤더를 찾지 못한 시트가 있습니다: 정산상세",
            "blocking_messages": ["헤더를 찾지 못한 시트가 있습니다: 정산상세"],
            "warning_messages": [],
            "info_messages": [],
            "adapter_summary": {"parsed_rows": 0, "default_feed_rows": 0},
            "audit_df": pd.DataFrame(
                [
                    {
                        "sheet": "2026년 5월 네이버 일반 정산상세",
                        "status": "header_not_found",
                        "header_row": "",
                        "data_start": "",
                        "parsed_rows": 0,
                        "title_present_rows": 0,
                        "note": "single_table_parser",
                    }
                ]
            ),
        }

        payload = build_adapter_failure_payload(
            result=result,
            source_bytes=source_bytes,
            selected_s2_channel="엑셀 파일명으로 자동감지",
            app_commit_sha="abc1234",
            app_url="https://example.test/app",
        )

        self.assertEqual(payload["failure_category"], "header_not_found")
        self.assertEqual(payload["effective_platform"], "네이버")
        self.assertEqual(payload["source_size"], len(source_bytes))
        self.assertTrue(payload["source_sha256"])
        self.assertIn("2026년 5월 네이버 일반 정산상세", payload["sheet_names"])
        sheet = payload["sheet_diagnostics"][0]  # type: ignore[index]
        self.assertEqual(sheet["best_header_candidate"]["row"], 3)  # type: ignore[index]
        self.assertGreaterEqual(sheet["best_header_candidate"]["score"], 8)  # type: ignore[index]

        report = render_failure_report_markdown(payload)
        self.assertIn("Header Candidates", report)
        self.assertIn("abc1234", report)
        self.assertTrue(payload_json_bytes(payload).startswith(b"{"))

    def test_github_issue_body_is_sanitized(self) -> None:
        payload = build_adapter_failure_payload(
            result={
                "source_name": "민감정산.xlsx",
                "platform": "네이버",
                "s2_sales_channel": "네이버_일반",
                "status": "blocked",
                "error": "어댑터가 데이터 행을 만들지 못했습니다.",
                "blocking_messages": ["어댑터가 데이터 행을 만들지 못했습니다."],
                "adapter_summary": {"parsed_rows": 0, "default_feed_rows": 0},
                "audit_df": pd.DataFrame(),
            },
            source_bytes=self.workbook_bytes(),
            app_commit_sha="abc1234",
        )

        body = render_github_issue_body(payload, notion_task_url="https://notion.so/task-1")

        self.assertIn("https://notion.so/task-1", body)
        self.assertIn("원본 정산서 xlsx는 GitHub에 첨부하지 않는다", body)
        self.assertIn("Notion 카드 첨부", body)
        self.assertNotIn("7200", body)


if __name__ == "__main__":
    unittest.main()
