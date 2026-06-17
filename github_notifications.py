from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import requests

from adapter_failure_diagnostics import render_github_issue_body


GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_DEFAULT_LABELS = ("adapter-failure", "urgent")


class GitHubNotificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubIssueConfig:
    token: str = ""
    repository: str = ""
    api_base_url: str = GITHUB_API_BASE_URL
    labels: tuple[str, ...] = GITHUB_DEFAULT_LABELS
    assignees: tuple[str, ...] = ()
    mentions: tuple[str, ...] = ()
    timeout_seconds: int = 15

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.repository and "/" in self.repository)


@dataclass(frozen=True)
class GitHubIssueResult:
    issue_number: int
    url: str


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    try:
        return dict(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return {}


def _first_value(values: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        raw = values.get(key)
        if _text(raw):
            return _text(raw)
    return ""


def _parse_text_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        parts = [_text(item) for item in value]
    else:
        parts = [part.strip() for part in _text(value).replace(";", ",").split(",")]
    return tuple(part for part in parts if part)


def normalize_github_secret_values(raw_secrets: object) -> dict[str, Any]:
    secrets = _as_mapping(raw_secrets)
    section = _as_mapping(secrets.get("github") or secrets.get("GITHUB"))
    values: dict[str, Any] = {}

    for source in (secrets, section):
        token = _first_value(
            source,
            (
                "GITHUB_ADAPTER_FAILURE_TOKEN",
                "GITHUB_TOKEN",
                "adapter_failure_token",
                "token",
            ),
        )
        if token:
            values["GITHUB_ADAPTER_FAILURE_TOKEN"] = token

        repository = _first_value(
            source,
            (
                "GITHUB_ADAPTER_FAILURE_REPO",
                "GITHUB_REPOSITORY",
                "adapter_failure_repo",
                "repository",
            ),
        )
        if repository:
            values["GITHUB_ADAPTER_FAILURE_REPO"] = repository

        api_base_url = _first_value(source, ("GITHUB_API_BASE_URL", "api_base_url"))
        if api_base_url:
            values["GITHUB_API_BASE_URL"] = api_base_url

        labels = source.get("GITHUB_ADAPTER_FAILURE_LABELS")
        if labels is None:
            labels = source.get("adapter_failure_labels")
        if labels:
            values["GITHUB_ADAPTER_FAILURE_LABELS"] = labels

        assignees = source.get("GITHUB_ADAPTER_FAILURE_ASSIGNEES")
        if assignees is None:
            assignees = source.get("adapter_failure_assignees")
        if assignees:
            values["GITHUB_ADAPTER_FAILURE_ASSIGNEES"] = assignees

        mentions = source.get("GITHUB_ADAPTER_FAILURE_MENTIONS")
        if mentions is None:
            mentions = source.get("adapter_failure_mentions")
        if mentions:
            values["GITHUB_ADAPTER_FAILURE_MENTIONS"] = mentions

    return values


def build_github_issue_config(values: Mapping[str, Any]) -> GitHubIssueConfig:
    labels = _parse_text_tuple(values.get("GITHUB_ADAPTER_FAILURE_LABELS")) or GITHUB_DEFAULT_LABELS
    return GitHubIssueConfig(
        token=_first_value(values, ("GITHUB_ADAPTER_FAILURE_TOKEN", "GITHUB_TOKEN")),
        repository=_first_value(values, ("GITHUB_ADAPTER_FAILURE_REPO", "GITHUB_REPOSITORY")),
        api_base_url=(_first_value(values, ("GITHUB_API_BASE_URL",)) or GITHUB_API_BASE_URL).rstrip("/"),
        labels=labels,
        assignees=_parse_text_tuple(values.get("GITHUB_ADAPTER_FAILURE_ASSIGNEES")),
        mentions=_parse_text_tuple(values.get("GITHUB_ADAPTER_FAILURE_MENTIONS")),
    )


def build_adapter_failure_issue_payload(
    *,
    config: GitHubIssueConfig,
    failure_payload: Mapping[str, Any],
    notion_task_url: str,
) -> dict[str, Any]:
    channel = _text(failure_payload.get("detected_s2_channel")) or _text(failure_payload.get("selected_s2_channel"))
    channel = channel or "판매채널 확인 필요"
    category = _text(failure_payload.get("failure_category")) or "unexpected_exception"
    source_name = _text(failure_payload.get("source_name")) or "uploaded.xlsx"
    body = render_github_issue_body(failure_payload, notion_task_url=notion_task_url)
    if config.mentions:
        body += "\n" + " ".join(f"@{mention.lstrip('@')}" for mention in config.mentions) + "\n"

    payload: dict[str, Any] = {
        "title": f"[adapter-failure] {channel} {category}: {source_name}",
        "body": body,
        "labels": list(config.labels),
    }
    if config.assignees:
        payload["assignees"] = list(config.assignees)
    return payload


def create_adapter_failure_issue(
    config: GitHubIssueConfig,
    *,
    failure_payload: Mapping[str, Any],
    notion_task_url: str,
    session: requests.Session | None = None,
) -> GitHubIssueResult:
    if not config.is_configured:
        raise GitHubNotificationError("GitHub Issue 설정이 없습니다.")

    owner_repo = config.repository.strip("/")
    url = f"{config.api_base_url}/repos/{owner_repo}/issues"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {config.token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = build_adapter_failure_issue_payload(
        config=config,
        failure_payload=failure_payload,
        notion_task_url=notion_task_url,
    )

    owns_session = session is None
    session = session or requests.Session()
    try:
        response = session.request("POST", url, headers=headers, json=payload, timeout=config.timeout_seconds)
        if response.status_code >= 400:
            detail = response.text[:500] if response.text else response.reason
            raise GitHubNotificationError(f"GitHub API 오류 {response.status_code}: {detail}")
        body = response.json()
        return GitHubIssueResult(issue_number=int(body.get("number") or 0), url=_text(body.get("html_url")))
    finally:
        if owns_session:
            session.close()
