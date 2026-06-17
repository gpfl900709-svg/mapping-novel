from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from typing import Any

import requests

from notion_tasks import (
    SINGLE_PART_LIMIT_BYTES,
    NotionAttachment,
    NotionTaskConfig,
    NotionTaskError,
    append_text_blocks,
    build_page_request,
    build_s2_refresh_task_payload,
    create_notion_task,
    file_block,
    normalize_notion_secret_values,
    notion_blocks,
    upload_attachment,
)


class NotionTasksTest(unittest.TestCase):
    def config(self, **overrides: object) -> NotionTaskConfig:
        values = {
            "token": "notion-token",
            "data_source_id": "ds-123",
            "api_base_url": "https://api.notion.test/v1",
            "app_url": "https://mapping.test/app",
        }
        values.update(overrides)
        return NotionTaskConfig(**values)

    def test_section_secrets_are_normalized(self) -> None:
        values = normalize_notion_secret_values(
            {
                "notion": {
                    "token": "ntn-token",
                    "task_data_source_id": "ds-456",
                    "api_version": "2026-03-11",
                    "app_url": "https://mapping.test/app",
                    "attach_files": True,
                    "attach_original_xlsx": False,
                    "max_attachment_bytes": 123,
                }
            }
        )

        self.assertEqual(values["NOTION_TOKEN"], "ntn-token")
        self.assertEqual(values["NOTION_TASK_DATA_SOURCE_ID"], "ds-456")
        self.assertEqual(values["NOTION_API_VERSION"], "2026-03-11")
        self.assertEqual(values["NOTION_ATTACH_ORIGINAL_XLSX"], False)

    def test_s2_refresh_page_uses_data_source_parent(self) -> None:
        config = self.config()
        payload = build_s2_refresh_task_payload(
            config,
            updated_at="2026-06-17 12:00",
            usage_label="사용 가능",
            usage_tone="ok",
            s2_rows=10,
            s2_id_rows=9,
            missing_guard_rows=1,
            billing_guard_rows=2,
            service_content_rows=3,
            requested_at=datetime(2026, 6, 17, 12, 5, tzinfo=timezone.utc),
        )
        request = build_page_request(payload, config)

        self.assertEqual(request["parent"], {"type": "data_source_id", "data_source_id": "ds-123"})
        self.assertEqual(request["properties"]["상태"]["select"]["name"], "인박스")
        self.assertEqual(request["properties"]["영역"]["select"]["name"], "매핑")
        self.assertEqual(request["properties"]["우선순위"]["select"]["name"], "보통")
        self.assertEqual(request["properties"]["링크"]["url"], "https://mapping.test/app")

    def test_s2_refresh_warning_uses_high_priority(self) -> None:
        payload = build_s2_refresh_task_payload(
            self.config(),
            updated_at="",
            usage_label="확인 필요",
            usage_tone="warn",
            s2_rows=0,
            s2_id_rows=0,
            missing_guard_rows=0,
            billing_guard_rows=0,
            service_content_rows=0,
        )

        self.assertEqual(payload["properties"]["우선순위"], "높음")

    def test_file_block_matches_notion_file_upload_shape(self) -> None:
        block = file_block("upload-1", "source.xlsx")

        self.assertEqual(
            block,
            {
                "object": "block",
                "type": "file",
                "file": {"type": "file_upload", "file_upload": {"id": "upload-1"}},
            },
        )

    def test_body_chunks_stay_under_notion_text_limit(self) -> None:
        blocks = notion_blocks(["가" * 5000])

        self.assertGreater(len(blocks), 1)
        for block in blocks:
            content = block["paragraph"]["rich_text"][0]["text"]["content"]
            self.assertLessEqual(len(content), 1800)

    def test_create_task_uploads_small_file_after_page_create(self) -> None:
        session = FakeSession()
        result = create_notion_task(
            self.config(),
            {
                "properties": {
                    "업무명": "작업 카드",
                    "상태": "인박스",
                    "영역": "매핑",
                    "우선순위": "보통",
                },
                "body": ["본문"],
            },
            attachments=[NotionAttachment("failure_payload.json", b"secret-bytes", "application/json")],
            session=session,  # type: ignore[arg-type]
        )

        self.assertEqual(result.url, "https://notion.test/page-1")
        self.assertEqual(result.uploaded_attachments, ("failure_payload.json",))
        page_request = session.requests[0]
        self.assertTrue(page_request["url"].endswith("/pages"))
        self.assertNotIn("secret-bytes", json.dumps(page_request["json"], ensure_ascii=False))
        self.assertTrue(any(request["url"].endswith("/file_uploads") for request in session.requests))
        self.assertTrue(any("/blocks/page-1/children" in request["url"] for request in session.requests))

    def test_large_file_uses_multipart_upload(self) -> None:
        session = FakeSession()
        upload_id = upload_attachment(
            self.config(),
            NotionAttachment("large.zip", b"x" * (SINGLE_PART_LIMIT_BYTES + 1), "application/zip"),
            session=session,  # type: ignore[arg-type]
        )

        create_request = next(request for request in session.requests if request["url"].endswith("/file_uploads"))
        send_requests = [request for request in session.requests if request["url"].endswith("/send")]
        complete_requests = [request for request in session.requests if request["url"].endswith("/complete")]

        self.assertEqual(upload_id, "upload-1")
        self.assertEqual(create_request["json"]["mode"], "multi_part")
        self.assertEqual(create_request["json"]["number_of_parts"], 3)
        self.assertEqual([request["data"]["part_number"] for request in send_requests], ["1", "2", "3"])
        self.assertEqual(len(complete_requests), 1)

    def test_append_text_blocks_batches_large_warning_lists(self) -> None:
        session = FakeSession()

        append_text_blocks(self.config(), "page-1", [f"line-{index}" for index in range(205)], session=session)  # type: ignore[arg-type]

        append_requests = [request for request in session.requests if "/blocks/page-1/children" in request["url"]]
        self.assertEqual(len(append_requests), 3)
        self.assertEqual([len(request["json"]["children"]) for request in append_requests], [100, 100, 5])

    def test_size_limit_skips_attachment_but_keeps_page(self) -> None:
        session = FakeSession()
        result = create_notion_task(
            self.config(max_attachment_bytes=3),
            {"properties": {"업무명": "작업 카드", "상태": "인박스", "영역": "매핑", "우선순위": "보통"}},
            attachments=[NotionAttachment("too_big.xlsx", b"1234", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")],
            session=session,  # type: ignore[arg-type]
        )

        self.assertEqual(result.url, "https://notion.test/page-1")
        self.assertIn("too_big.xlsx", result.skipped_attachments[0])
        self.assertFalse(any(request["url"].endswith("/file_uploads") for request in session.requests))
        self.assertTrue(any("/blocks/page-1/children" in request["url"] for request in session.requests))

    def test_upload_network_failure_skips_attachment_but_keeps_page(self) -> None:
        session = FakeSession(fail_send=True)

        result = create_notion_task(
            self.config(),
            {"properties": {"업무명": "작업 카드", "상태": "인박스", "영역": "매핑", "우선순위": "보통"}},
            attachments=[NotionAttachment("failure_payload.json", b"{}", "application/json")],
            session=session,  # type: ignore[arg-type]
        )

        self.assertEqual(result.url, "https://notion.test/page-1")
        self.assertEqual(result.uploaded_attachments, ())
        self.assertIn("failure_payload.json", result.skipped_attachments[0])
        self.assertIn("Notion API 요청 실패", result.skipped_attachments[0])

    def test_api_error_raises_task_error(self) -> None:
        session = FakeSession(fail_pages=True)

        with self.assertRaises(NotionTaskError):
            create_notion_task(
                self.config(),
                {"properties": {"업무명": "작업 카드", "상태": "인박스", "영역": "매핑", "우선순위": "보통"}},
                session=session,  # type: ignore[arg-type]
            )


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any], text: str = "") -> None:
        self.status_code = status_code
        self.payload = payload
        self.text = text
        self.reason = "fake"

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeSession:
    def __init__(self, *, fail_pages: bool = False, fail_send: bool = False) -> None:
        self.fail_pages = fail_pages
        self.fail_send = fail_send
        self.requests: list[dict[str, Any]] = []
        self.upload_counter = 0

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        record = {
            "method": method,
            "url": url,
            "json": kwargs.get("json"),
            "data": kwargs.get("data"),
            "files": kwargs.get("files"),
            "headers": kwargs.get("headers"),
        }
        self.requests.append(record)
        if url.endswith("/pages") and method == "POST":
            if self.fail_pages:
                return FakeResponse(400, {"message": "bad request"}, "bad request")
            return FakeResponse(200, {"id": "page-1", "url": "https://notion.test/page-1"})
        if url.endswith("/users/me"):
            return FakeResponse(200, {"bot": {"workspace_limits": {"max_file_upload_size_in_bytes": 999999999}}})
        if url.endswith("/file_uploads") and method == "POST":
            self.upload_counter += 1
            return FakeResponse(200, {"id": f"upload-{self.upload_counter}"})
        if url.endswith("/send"):
            if self.fail_send:
                raise requests.Timeout("send timed out")
            upload_id = url.rstrip("/").split("/")[-2]
            return FakeResponse(200, {"id": upload_id})
        if url.endswith("/complete"):
            upload_id = url.rstrip("/").split("/")[-2]
            return FakeResponse(200, {"id": upload_id})
        if "/blocks/page-1/children" in url:
            return FakeResponse(200, {"results": []})
        if "/pages/page-1" in url:
            return FakeResponse(200, {"id": "page-1"})
        return FakeResponse(404, {"message": "not found"}, "not found")

    def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
