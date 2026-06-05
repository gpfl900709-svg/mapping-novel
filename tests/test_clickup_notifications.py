from __future__ import annotations

import unittest
from datetime import datetime, timezone

from clickup_notifications import (
    ClickUpAttachment,
    build_adapter_failure_clickup_config,
    build_adapter_failure_task_payload,
    build_clickup_config,
    build_mapping_run_clickup_config,
    build_mapping_run_task_payload,
    build_s2_refresh_task_payload,
    create_adapter_failure_task_with_attachments,
    create_mapping_run_task,
    create_s2_refresh_request_task,
    normalize_clickup_secret_values,
)


class ClickUpNotificationsTest(unittest.TestCase):
    def test_section_secrets_are_normalized(self) -> None:
        values = normalize_clickup_secret_values(
            {
                "clickup": {
                    "api_token": "token-123",
                    "list_id": "901817301594",
                    "assignee_ids": "306885786",
                    "s2_request_due_date_minutes": "3",
                    "app_url": "https://example.test/app",
                }
            }
        )

        config = build_clickup_config(values)

        self.assertTrue(config.is_configured)
        self.assertEqual(config.token, "token-123")
        self.assertEqual(config.list_id, "901817301594")
        self.assertEqual(config.assignee_ids, (306885786,))
        self.assertEqual(config.due_date_minutes, 3)
        self.assertEqual(config.app_url, "https://example.test/app")

    def test_payload_contains_current_s2_state(self) -> None:
        config = build_clickup_config(
            {
                "CLICKUP_API_TOKEN": "token-123",
                "CLICKUP_LIST_ID": "901817301594",
                "CLICKUP_APP_URL": "https://example.test/app",
            }
        )

        payload = build_s2_refresh_task_payload(
            config=config,
            updated_at="2026-05-12 13:14",
            usage_label="확인 필요",
            s2_rows=124755,
            s2_id_rows=124755,
            missing_guard_rows=2327,
            billing_guard_rows=869,
            service_content_rows=96298,
            requested_at=datetime(2026, 5, 13, 1, 30, tzinfo=timezone.utc),
            assignee_ids=(306885786,),
        )

        self.assertEqual(payload["name"], "S2 최신화 요청 - 2026-05-13 10:30")
        self.assertEqual(payload["assignees"], [306885786])
        self.assertTrue(payload["notify_all"])
        self.assertTrue(payload["due_date_time"])
        self.assertEqual(payload["due_date"], 1778635920000)
        self.assertIn("현재 S2 기준 행: 124,755", payload["markdown_content"])
        self.assertIn("계약연결 S2 ID: 124,755", payload["markdown_content"])
        self.assertIn("통합계약ID(cntrId) != 0", payload["markdown_content"])
        self.assertIn("누락 guard: 2,327", payload["markdown_content"])
        self.assertIn("https://example.test/app", payload["markdown_content"])

    def test_create_task_auto_assigns_token_owner(self) -> None:
        config = build_clickup_config({"CLICKUP_API_TOKEN": "token-123", "CLICKUP_LIST_ID": "901817301594"})
        session = FakeSession()

        result = create_s2_refresh_request_task(
            config,
            updated_at="2026-05-12 13:14",
            usage_label="확인 필요",
            s2_rows=124755,
            s2_id_rows=124755,
            missing_guard_rows=2327,
            billing_guard_rows=869,
            service_content_rows=96298,
            requested_at=datetime(2026, 5, 13, 1, 30, tzinfo=timezone.utc),
            session=session,  # type: ignore[arg-type]
        )

        self.assertEqual(result.task_id, "task-1")
        self.assertEqual(result.url, "https://app.clickup.com/t/task-1")
        self.assertEqual(session.post_payloads[0]["assignees"], [306885786])
        self.assertTrue(session.post_payloads[0]["notify_all"])
        self.assertEqual(session.comment_payloads[0]["assignee"], 306885786)
        self.assertTrue(session.comment_payloads[0]["notify_all"])
        self.assertIn("모바일 알림", session.comment_payloads[0]["comment_text"])

    def test_adapter_failure_section_secrets_are_normalized(self) -> None:
        values = normalize_clickup_secret_values(
            {
                "clickup": {
                    "api_token": "token-123",
                    "adapter_failure_list_id": "901818576269",
                    "adapter_failure_assignee_ids": "306885786",
                    "adapter_failure_attach_original": "true",
                    "adapter_failure_tags": "adapter-failure,mapping-novel,네이버",
                }
            }
        )

        config = build_adapter_failure_clickup_config(values)

        self.assertTrue(config.is_configured)
        self.assertEqual(config.list_id, "901818576269")
        self.assertEqual(config.assignee_ids, (306885786,))
        self.assertTrue(config.attach_original)
        self.assertIn("adapter-failure", config.tags)
        self.assertEqual(config.due_date_minutes, 2)

    def test_mapping_run_section_secrets_are_normalized(self) -> None:
        values = normalize_clickup_secret_values(
            {
                "clickup": {
                    "api_token": "token-123",
                    "mapping_run_list_id": "901818576269",
                    "mapping_run_assignee_ids": "306885786",
                    "mapping_run_tags": "mapping-run,mapping-novel,audit",
                }
            }
        )

        config = build_mapping_run_clickup_config(values)

        self.assertTrue(config.is_configured)
        self.assertEqual(config.list_id, "901818576269")
        self.assertEqual(config.assignee_ids, (306885786,))
        self.assertIn("mapping-run", config.tags)
        self.assertEqual(config.priority, 3)

    def test_mapping_run_payload_summarizes_issues_and_sources(self) -> None:
        config = build_mapping_run_clickup_config(
            {
                "CLICKUP_API_TOKEN": "token-123",
                "CLICKUP_MAPPING_RUN_LIST_ID": "901818576269",
                "CLICKUP_APP_URL": "https://example.test/app",
            }
        )

        payload = build_mapping_run_task_payload(
            config=config,
            run_payload={
                "run_id": "run-abc",
                "file_count": 2,
                "status_counts": {"success": 1, "blocked": 1, "failed": 0},
                "review_required_count": 3,
                "s2_source_label": "관리자 배포 S2 기준",
                "s2_rows": 125499,
                "s2_id_rows": 125499,
                "source_names": ["네이버.xlsx", "무툰.xlsx"],
                "zip_sha256": "abc123",
            },
            requested_at=datetime(2026, 6, 5, 1, 30, tzinfo=timezone.utc),
            assignee_ids=(306885786,),
        )

        self.assertEqual(payload["name"], "[매핑 실행 기록] 2026-06-05 10:30 · 2개 · 이슈 4")
        self.assertIn("mapping-issue", payload["tags"])
        self.assertIn("검토필요 행: 3", payload["markdown_content"])
        self.assertIn("`네이버.xlsx`", payload["markdown_content"])
        self.assertIn("https://example.test/app", payload["markdown_content"])

    def test_adapter_failure_defaults_to_phone_alert_assignee_and_due_date(self) -> None:
        config = build_adapter_failure_clickup_config(
            {
                "CLICKUP_API_TOKEN": "token-123",
                "CLICKUP_ADAPTER_FAILURE_LIST_ID": "901818576269",
            }
        )

        payload = build_adapter_failure_task_payload(
            config=config,
            failure_payload={
                "source_name": "네이버.xlsx",
                "effective_platform": "네이버",
                "detected_s2_channel": "네이버_일반",
                "failure_category": "header_not_found",
                "failure_reason": "헤더를 찾지 못했습니다.",
            },
            requested_at=datetime(2026, 6, 5, 1, 30, tzinfo=timezone.utc),
            assignee_ids=config.assignee_ids,
        )

        self.assertEqual(config.assignee_ids, (306885786,))
        self.assertEqual(payload["status"], "to do")
        self.assertEqual(payload["assignees"], [306885786])
        self.assertTrue(payload["due_date_time"])
        self.assertEqual(payload["due_date"], 1780623120000)

    def test_adapter_failure_payload_uses_dedicated_list_shape(self) -> None:
        config = build_adapter_failure_clickup_config(
            {
                "CLICKUP_API_TOKEN": "token-123",
                "CLICKUP_ADAPTER_FAILURE_LIST_ID": "901818576269",
                "CLICKUP_ADAPTER_FAILURE_ASSIGNEE_IDS": "306885786",
                "CLICKUP_APP_URL": "https://example.test/app",
            }
        )

        payload = build_adapter_failure_task_payload(
            config=config,
            failure_payload={
                "source_name": "네이버.xlsx",
                "effective_platform": "네이버",
                "detected_s2_channel": "네이버_일반",
                "failure_category": "header_not_found",
                "failure_reason": "헤더를 찾지 못했습니다.",
                "source_sha256": "abc",
                "app_commit_sha": "def",
            },
            requested_at=datetime(2026, 6, 5, 1, 30, tzinfo=timezone.utc),
            assignee_ids=(306885786,),
        )

        self.assertEqual(payload["name"], "[긴급][정산서 어댑터 실패] 네이버_일반 / 네이버.xlsx")
        self.assertEqual(payload["priority"], 1)
        self.assertEqual(payload["assignees"], [306885786])
        self.assertIn("adapter-failure", payload["tags"])
        self.assertIn("네이버_일반", payload["tags"])
        self.assertIn("header_not_found", payload["markdown_content"])

    def test_create_adapter_failure_task_uploads_attachments(self) -> None:
        config = build_adapter_failure_clickup_config(
            {
                "CLICKUP_API_TOKEN": "token-123",
                "CLICKUP_ADAPTER_FAILURE_LIST_ID": "901818576269",
                "CLICKUP_ADAPTER_FAILURE_ASSIGNEE_IDS": "306885786",
            }
        )
        session = FakeSession()

        result = create_adapter_failure_task_with_attachments(
            config,
            failure_payload={
                "source_name": "네이버.xlsx",
                "effective_platform": "네이버",
                "detected_s2_channel": "네이버_일반",
                "failure_category": "header_not_found",
                "failure_reason": "헤더를 찾지 못했습니다.",
            },
            attachments=(
                ClickUpAttachment("failure_report.md", b"# report", "text/markdown"),
                ClickUpAttachment("failure_payload.json", b"{}", "application/json"),
            ),
            session=session,  # type: ignore[arg-type]
        )

        self.assertEqual(result.task_id, "task-1")
        self.assertEqual(session.comment_payloads[0]["assignee"], 306885786)
        self.assertIn("모바일 알림", session.comment_payloads[0]["comment_text"])
        self.assertEqual(len(session.attachment_payloads), 2)
        self.assertEqual(session.attachment_payloads[0]["attachment"][0], "failure_report.md")

    def test_create_mapping_run_task_uploads_attachments(self) -> None:
        config = build_mapping_run_clickup_config(
            {
                "CLICKUP_API_TOKEN": "token-123",
                "CLICKUP_MAPPING_RUN_LIST_ID": "901818576269",
                "CLICKUP_MAPPING_RUN_ASSIGNEE_IDS": "306885786",
            }
        )
        session = FakeSession()

        result = create_mapping_run_task(
            config,
            run_payload={
                "run_id": "run-abc",
                "file_count": 1,
                "status_counts": {"success": 1},
                "review_required_count": 0,
                "source_names": ["네이버.xlsx"],
            },
            attachments=(
                ClickUpAttachment("batch_summary.csv", b"csv", "text/csv"),
                ClickUpAttachment("mapping_results.zip", b"zip", "application/zip"),
            ),
            requested_at=datetime(2026, 6, 5, 1, 30, tzinfo=timezone.utc),
            session=session,  # type: ignore[arg-type]
        )

        self.assertEqual(result.task_id, "task-1")
        self.assertEqual(session.post_payloads[0]["name"], "[매핑 실행 기록] 2026-06-05 10:30 · 1개 · 이슈 0")
        self.assertEqual(len(session.attachment_payloads), 2)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = ""
        self.reason = ""

    def json(self) -> dict[str, object]:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.post_payloads: list[dict[str, object]] = []
        self.comment_payloads: list[dict[str, object]] = []
        self.attachment_payloads: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        if method == "GET" and url.endswith("/user"):
            return FakeResponse(200, {"user": {"id": 306885786}})
        if method == "POST" and ("/list/901817301594/task" in url or "/list/901818576269/task" in url):
            payload = kwargs["json"]
            assert isinstance(payload, dict)
            self.post_payloads.append(payload)
            return FakeResponse(200, {"id": "task-1", "url": "https://app.clickup.com/t/task-1"})
        if method == "POST" and "/task/task-1/comment" in url:
            payload = kwargs["json"]
            assert isinstance(payload, dict)
            self.comment_payloads.append(payload)
            return FakeResponse(200, {"id": f"comment-{len(self.comment_payloads)}"})
        if method == "POST" and "/task/task-1/attachment" in url:
            files = kwargs["files"]
            assert isinstance(files, dict)
            self.attachment_payloads.append(files)
            return FakeResponse(200, {"ok": True})
        return FakeResponse(404, {"err": "not found"})


if __name__ == "__main__":
    unittest.main()
