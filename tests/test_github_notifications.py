from __future__ import annotations

import unittest

from github_notifications import (
    build_adapter_failure_issue_payload,
    build_github_issue_config,
    create_adapter_failure_issue,
    normalize_github_secret_values,
)


class GitHubNotificationsTest(unittest.TestCase):
    def test_section_secrets_are_normalized(self) -> None:
        values = normalize_github_secret_values(
            {
                "github": {
                    "token": "gh-token",
                    "repository": "macximin/mapping-novel",
                    "adapter_failure_labels": "adapter-failure,urgent",
                    "adapter_failure_assignees": "wjjo",
                    "adapter_failure_mentions": "wjjo",
                }
            }
        )

        config = build_github_issue_config(values)

        self.assertTrue(config.is_configured)
        self.assertEqual(config.repository, "macximin/mapping-novel")
        self.assertEqual(config.labels, ("adapter-failure", "urgent"))
        self.assertEqual(config.assignees, ("wjjo",))
        self.assertEqual(config.mentions, ("wjjo",))

    def test_issue_payload_is_sanitized_and_links_notion(self) -> None:
        config = build_github_issue_config(
            {
                "GITHUB_ADAPTER_FAILURE_TOKEN": "gh-token",
                "GITHUB_ADAPTER_FAILURE_REPO": "macximin/mapping-novel",
                "GITHUB_ADAPTER_FAILURE_ASSIGNEES": "wjjo",
            }
        )

        payload = build_adapter_failure_issue_payload(
            config=config,
            notion_task_url="https://notion.so/task-1",
            failure_payload={
                "source_name": "네이버.xlsx",
                "source_sha256": "abc",
                "effective_platform": "네이버",
                "detected_s2_channel": "네이버_일반",
                "status": "blocked",
                "failure_category": "header_not_found",
                "failure_reason": "헤더를 찾지 못했습니다.",
                "app_commit_sha": "def",
                "sheet_audits": [],
                "sheet_diagnostics": [
                    {
                        "sheet": "정산",
                        "best_header_candidate": {
                            "row": 3,
                            "score": 15,
                            "cells": ["컨텐츠", "7200", "작가명"],
                        },
                    }
                ],
            },
        )

        self.assertEqual(payload["title"], "[adapter-failure] 네이버_일반 header_not_found: 네이버.xlsx")
        self.assertEqual(payload["assignees"], ["wjjo"])
        self.assertIn("https://notion.so/task-1", payload["body"])
        self.assertIn("notion_task", payload["body"])
        self.assertIn("<number>", payload["body"])
        self.assertNotIn("7200", payload["body"])

    def test_create_issue_posts_to_repository(self) -> None:
        config = build_github_issue_config(
            {
                "GITHUB_ADAPTER_FAILURE_TOKEN": "gh-token",
                "GITHUB_ADAPTER_FAILURE_REPO": "macximin/mapping-novel",
            }
        )
        session = FakeSession()

        result = create_adapter_failure_issue(
            config,
            notion_task_url="https://notion.so/task-1",
            failure_payload={
                "source_name": "네이버.xlsx",
                "effective_platform": "네이버",
                "detected_s2_channel": "네이버_일반",
                "failure_category": "header_not_found",
                "failure_reason": "헤더를 찾지 못했습니다.",
                "sheet_audits": [],
                "sheet_diagnostics": [],
            },
            session=session,  # type: ignore[arg-type]
        )

        self.assertEqual(result.issue_number, 7)
        self.assertEqual(result.url, "https://github.com/macximin/mapping-novel/issues/7")
        self.assertEqual(session.post_urls[0], "https://api.github.com/repos/macximin/mapping-novel/issues")


class FakeResponse:
    status_code = 201
    text = ""
    reason = ""

    def json(self) -> dict[str, object]:
        return {"number": 7, "html_url": "https://github.com/macximin/mapping-novel/issues/7"}


class FakeSession:
    def __init__(self) -> None:
        self.post_urls: list[str] = []
        self.post_payloads: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        self.post_urls.append(url)
        payload = kwargs["json"]
        assert method == "POST"
        assert isinstance(payload, dict)
        self.post_payloads.append(payload)
        return FakeResponse()


if __name__ == "__main__":
    unittest.main()
