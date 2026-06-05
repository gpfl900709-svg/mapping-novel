from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import requests


CLICKUP_API_BASE_URL = "https://api.clickup.com/api/v2"
CLICKUP_DEFAULT_PRIORITY = 2
CLICKUP_DEFAULT_TAGS = ("s2-refresh", "mapping-novel")
CLICKUP_ADAPTER_FAILURE_DEFAULT_LIST_ID = "901818576269"
CLICKUP_ADAPTER_FAILURE_DEFAULT_PRIORITY = 1
CLICKUP_ADAPTER_FAILURE_DEFAULT_TAGS = ("adapter-failure", "mapping-novel")
KST = timezone(timedelta(hours=9))


class ClickUpNotificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClickUpNotificationConfig:
    token: str = ""
    list_id: str = ""
    api_base_url: str = CLICKUP_API_BASE_URL
    assignee_ids: tuple[int, ...] = ()
    auto_assign_self: bool = True
    status: str = ""
    priority: int | None = CLICKUP_DEFAULT_PRIORITY
    app_url: str = ""
    tags: tuple[str, ...] = CLICKUP_DEFAULT_TAGS
    attach_original: bool = False
    timeout_seconds: int = 15

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.list_id)


@dataclass(frozen=True)
class ClickUpTaskResult:
    task_id: str
    url: str


@dataclass(frozen=True)
class ClickUpAttachment:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


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


def _parse_bool(value: object, default: bool) -> bool:
    raw = _text(value).casefold()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _parse_int(value: object) -> int | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_int_tuple(value: object) -> tuple[int, ...]:
    if isinstance(value, (list, tuple, set)):
        parsed = [_parse_int(item) for item in value]
    else:
        parsed = [_parse_int(part) for part in _text(value).replace(";", ",").split(",")]
    return tuple(item for item in parsed if item is not None)


def _parse_text_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        parts = [text for text in (_text(item) for item in value) if text]
    else:
        parts = [part.strip() for part in _text(value).replace(";", ",").split(",") if part.strip()]
    return tuple(parts)


def normalize_clickup_secret_values(raw_secrets: object) -> dict[str, Any]:
    secrets = _as_mapping(raw_secrets)
    section = _as_mapping(secrets.get("clickup") or secrets.get("CLICKUP"))
    values: dict[str, Any] = {}

    for source in (secrets, section):
        token = _first_value(
            source,
            (
                "CLICKUP_S2_REQUEST_TOKEN",
                "CLICKUP_API_TOKEN",
                "CLICKUP_TOKEN",
                "s2_request_token",
                "api_token",
                "token",
            ),
        )
        if token:
            values["CLICKUP_API_TOKEN"] = token

        list_id = _first_value(
            source,
            (
                "CLICKUP_S2_REQUEST_LIST_ID",
                "CLICKUP_LIST_ID",
                "s2_request_list_id",
                "list_id",
            ),
        )
        if list_id:
            values["CLICKUP_LIST_ID"] = list_id

        api_base_url = _first_value(source, ("CLICKUP_API_BASE_URL", "api_base_url"))
        if api_base_url:
            values["CLICKUP_API_BASE_URL"] = api_base_url

        assignee_ids = source.get("CLICKUP_S2_REQUEST_ASSIGNEE_IDS")
        if assignee_ids is None:
            assignee_ids = source.get("CLICKUP_ASSIGNEE_IDS")
        if assignee_ids is None:
            assignee_ids = source.get("s2_request_assignee_ids")
        if assignee_ids is None:
            assignee_ids = source.get("assignee_ids")
        if assignee_ids:
            values["CLICKUP_ASSIGNEE_IDS"] = assignee_ids

        status = _first_value(source, ("CLICKUP_S2_REQUEST_STATUS", "CLICKUP_STATUS", "s2_request_status", "status"))
        if status:
            values["CLICKUP_STATUS"] = status

        priority = _first_value(
            source,
            ("CLICKUP_S2_REQUEST_PRIORITY", "CLICKUP_PRIORITY", "s2_request_priority", "priority"),
        )
        if priority:
            values["CLICKUP_PRIORITY"] = priority

        app_url = _first_value(source, ("CLICKUP_S2_REQUEST_APP_URL", "CLICKUP_APP_URL", "app_url"))
        if app_url:
            values["CLICKUP_APP_URL"] = app_url

        adapter_failure_list_id = _first_value(
            source,
            (
                "CLICKUP_ADAPTER_FAILURE_LIST_ID",
                "adapter_failure_list_id",
            ),
        )
        if adapter_failure_list_id:
            values["CLICKUP_ADAPTER_FAILURE_LIST_ID"] = adapter_failure_list_id

        adapter_failure_assignee_ids = source.get("CLICKUP_ADAPTER_FAILURE_ASSIGNEE_IDS")
        if adapter_failure_assignee_ids is None:
            adapter_failure_assignee_ids = source.get("adapter_failure_assignee_ids")
        if adapter_failure_assignee_ids:
            values["CLICKUP_ADAPTER_FAILURE_ASSIGNEE_IDS"] = adapter_failure_assignee_ids

        adapter_failure_status = _first_value(
            source,
            ("CLICKUP_ADAPTER_FAILURE_STATUS", "adapter_failure_status"),
        )
        if adapter_failure_status:
            values["CLICKUP_ADAPTER_FAILURE_STATUS"] = adapter_failure_status

        adapter_failure_priority = _first_value(
            source,
            ("CLICKUP_ADAPTER_FAILURE_PRIORITY", "adapter_failure_priority"),
        )
        if adapter_failure_priority:
            values["CLICKUP_ADAPTER_FAILURE_PRIORITY"] = adapter_failure_priority

        adapter_failure_attach_original = source.get("CLICKUP_ADAPTER_FAILURE_ATTACH_ORIGINAL")
        if adapter_failure_attach_original is None:
            adapter_failure_attach_original = source.get("adapter_failure_attach_original")
        if adapter_failure_attach_original is not None:
            values["CLICKUP_ADAPTER_FAILURE_ATTACH_ORIGINAL"] = adapter_failure_attach_original

        adapter_failure_tags = source.get("CLICKUP_ADAPTER_FAILURE_TAGS")
        if adapter_failure_tags is None:
            adapter_failure_tags = source.get("adapter_failure_tags")
        if adapter_failure_tags:
            values["CLICKUP_ADAPTER_FAILURE_TAGS"] = adapter_failure_tags

        auto_assign_self = source.get("CLICKUP_AUTO_ASSIGN_SELF")
        if auto_assign_self is None:
            auto_assign_self = source.get("auto_assign_self")
        if auto_assign_self is not None:
            values["CLICKUP_AUTO_ASSIGN_SELF"] = auto_assign_self

    return values


def build_clickup_config(values: Mapping[str, Any]) -> ClickUpNotificationConfig:
    token = _first_value(values, ("CLICKUP_S2_REQUEST_TOKEN", "CLICKUP_API_TOKEN", "CLICKUP_TOKEN"))
    list_id = _first_value(values, ("CLICKUP_S2_REQUEST_LIST_ID", "CLICKUP_LIST_ID"))
    api_base_url = _first_value(values, ("CLICKUP_API_BASE_URL",)) or CLICKUP_API_BASE_URL
    priority = _parse_int(_first_value(values, ("CLICKUP_S2_REQUEST_PRIORITY", "CLICKUP_PRIORITY")))
    if priority is None:
        priority = CLICKUP_DEFAULT_PRIORITY
    if priority not in {1, 2, 3, 4}:
        priority = None

    return ClickUpNotificationConfig(
        token=token,
        list_id=list_id,
        api_base_url=api_base_url.rstrip("/"),
        assignee_ids=_parse_int_tuple(
            values.get("CLICKUP_S2_REQUEST_ASSIGNEE_IDS") or values.get("CLICKUP_ASSIGNEE_IDS")
        ),
        auto_assign_self=_parse_bool(values.get("CLICKUP_AUTO_ASSIGN_SELF"), default=True),
        status=_first_value(values, ("CLICKUP_S2_REQUEST_STATUS", "CLICKUP_STATUS")),
        priority=priority,
        app_url=_first_value(values, ("CLICKUP_S2_REQUEST_APP_URL", "CLICKUP_APP_URL")),
    )


def build_adapter_failure_clickup_config(values: Mapping[str, Any]) -> ClickUpNotificationConfig:
    token = _first_value(
        values,
        ("CLICKUP_ADAPTER_FAILURE_TOKEN", "CLICKUP_API_TOKEN", "CLICKUP_TOKEN"),
    )
    list_id = _first_value(
        values,
        ("CLICKUP_ADAPTER_FAILURE_LIST_ID", "CLICKUP_LIST_ID"),
    ) or CLICKUP_ADAPTER_FAILURE_DEFAULT_LIST_ID
    api_base_url = _first_value(values, ("CLICKUP_API_BASE_URL",)) or CLICKUP_API_BASE_URL
    priority = _parse_int(_first_value(values, ("CLICKUP_ADAPTER_FAILURE_PRIORITY", "CLICKUP_PRIORITY")))
    if priority is None:
        priority = CLICKUP_ADAPTER_FAILURE_DEFAULT_PRIORITY
    if priority not in {1, 2, 3, 4}:
        priority = None
    tags = _parse_text_tuple(values.get("CLICKUP_ADAPTER_FAILURE_TAGS")) or CLICKUP_ADAPTER_FAILURE_DEFAULT_TAGS

    return ClickUpNotificationConfig(
        token=token,
        list_id=list_id,
        api_base_url=api_base_url.rstrip("/"),
        assignee_ids=_parse_int_tuple(
            values.get("CLICKUP_ADAPTER_FAILURE_ASSIGNEE_IDS") or values.get("CLICKUP_ASSIGNEE_IDS")
        ),
        auto_assign_self=_parse_bool(values.get("CLICKUP_AUTO_ASSIGN_SELF"), default=True),
        status=_first_value(values, ("CLICKUP_ADAPTER_FAILURE_STATUS", "CLICKUP_STATUS")),
        priority=priority,
        app_url=_first_value(values, ("CLICKUP_ADAPTER_FAILURE_APP_URL", "CLICKUP_APP_URL")),
        tags=tags,
        attach_original=_parse_bool(values.get("CLICKUP_ADAPTER_FAILURE_ATTACH_ORIGINAL"), default=False),
    )


def build_s2_refresh_task_payload(
    *,
    config: ClickUpNotificationConfig,
    updated_at: str,
    usage_label: str,
    s2_rows: int,
    s2_id_rows: int,
    missing_guard_rows: int,
    billing_guard_rows: int,
    service_content_rows: int,
    requested_at: datetime | None = None,
    assignee_ids: tuple[int, ...] = (),
) -> dict[str, Any]:
    requested_at = requested_at or datetime.now(KST)
    requested_label = requested_at.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")
    title_time = requested_at.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    app_url_line = f"\n- 앱: {config.app_url}" if config.app_url else ""

    markdown_content = (
        "## S2 최신화 요청\n\n"
        f"- 요청 시각: {requested_label}\n"
        f"- S2 기준 업데이트: {updated_at or '확인 필요'}\n"
        f"- 상태: {usage_label or '확인 필요'}\n"
        f"- 현재 S2 기준 행: {s2_rows:,}\n"
        f"- S2 ID: {s2_id_rows:,}\n"
        f"- 누락 guard: {missing_guard_rows:,}\n"
        f"- 청구 guard: {billing_guard_rows:,}\n"
        f"- 콘텐츠 lookup: {service_content_rows:,}"
        f"{app_url_line}\n\n"
        "사용자가 Streamlit 앱에서 `관리자에게 S2 최신화 요청` 버튼을 눌러 생성된 요청입니다."
    )

    payload: dict[str, Any] = {
        "name": f"S2 최신화 요청 - {title_time}",
        "markdown_content": markdown_content,
        "notify_all": True,
        "tags": list(CLICKUP_DEFAULT_TAGS),
    }
    if config.status:
        payload["status"] = config.status
    if config.priority is not None:
        payload["priority"] = config.priority
    if assignee_ids:
        payload["assignees"] = list(assignee_ids)
    return payload


def build_adapter_failure_task_payload(
    *,
    config: ClickUpNotificationConfig,
    failure_payload: Mapping[str, Any],
    requested_at: datetime | None = None,
    assignee_ids: tuple[int, ...] = (),
    github_issue_url: str = "",
) -> dict[str, Any]:
    requested_at = requested_at or datetime.now(KST)
    requested_label = requested_at.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")
    platform = _text(failure_payload.get("effective_platform")) or "플랫폼 확인 필요"
    channel = _text(failure_payload.get("detected_s2_channel")) or _text(failure_payload.get("selected_s2_channel"))
    channel = channel or "판매채널 확인 필요"
    source_name = _text(failure_payload.get("source_name")) or "uploaded.xlsx"
    failure_category = _text(failure_payload.get("failure_category")) or "unexpected_exception"
    app_url_line = f"\n- 앱: {config.app_url}" if config.app_url else ""
    github_line = f"\n- GitHub Issue: {github_issue_url}" if github_issue_url else ""

    markdown_content = (
        "## 정산서 어댑터 실패\n\n"
        f"- 요청 시각: {requested_label}\n"
        f"- 실패 분류: `{failure_category}`\n"
        f"- 실패 사유: {_text(failure_payload.get('failure_reason')) or '확인 필요'}\n"
        f"- 파일명: `{source_name}`\n"
        f"- 판매채널: {channel}\n"
        f"- 플랫폼: {platform}\n"
        f"- 파일 SHA-256: `{_text(failure_payload.get('source_sha256'))}`\n"
        f"- 앱 커밋: `{_text(failure_payload.get('app_commit_sha')) or 'unknown'}`"
        f"{app_url_line}"
        f"{github_line}\n\n"
        "첨부된 `failure_report.md`, `failure_payload.json`, 원본 정산서 xlsx를 기준으로 어댑터를 수정합니다."
    )

    payload: dict[str, Any] = {
        "name": f"[긴급][정산서 어댑터 실패] {channel} / {source_name}",
        "markdown_content": markdown_content,
        "notify_all": True,
        "tags": list(config.tags or CLICKUP_ADAPTER_FAILURE_DEFAULT_TAGS),
    }
    platform_tag = platform.strip()
    if platform_tag and platform_tag not in payload["tags"]:
        payload["tags"].append(platform_tag)
    if channel and channel not in payload["tags"]:
        payload["tags"].append(channel)
    if config.status:
        payload["status"] = config.status
    if config.priority is not None:
        payload["priority"] = config.priority
    if assignee_ids:
        payload["assignees"] = list(assignee_ids)
    return payload


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    config: ClickUpNotificationConfig,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"Authorization": config.token, "Accept": "application/json"}
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    response = session.request(method, url, headers=headers, json=json_body, timeout=config.timeout_seconds)
    if response.status_code >= 400:
        detail = response.text[:500] if response.text else response.reason
        raise ClickUpNotificationError(f"ClickUp API 오류 {response.status_code}: {detail}")
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _request_multipart_json(
    session: requests.Session,
    url: str,
    *,
    config: ClickUpNotificationConfig,
    attachment: ClickUpAttachment,
) -> dict[str, Any]:
    headers = {"Authorization": config.token, "Accept": "application/json"}
    files = {
        "attachment": (
            attachment.filename,
            attachment.content,
            attachment.content_type,
        )
    }
    response = session.request("POST", url, headers=headers, files=files, timeout=config.timeout_seconds)
    if response.status_code >= 400:
        detail = response.text[:500] if response.text else response.reason
        raise ClickUpNotificationError(f"ClickUp API 오류 {response.status_code}: {detail}")
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def get_authorized_user_id(session: requests.Session, config: ClickUpNotificationConfig) -> int | None:
    payload = _request_json(session, "GET", f"{config.api_base_url}/user", config=config)
    user_id = _parse_int((_as_mapping(payload.get("user"))).get("id"))
    return user_id


def create_s2_refresh_request_task(
    config: ClickUpNotificationConfig,
    *,
    updated_at: str,
    usage_label: str,
    s2_rows: int,
    s2_id_rows: int,
    missing_guard_rows: int,
    billing_guard_rows: int,
    service_content_rows: int,
    requested_at: datetime | None = None,
    session: requests.Session | None = None,
) -> ClickUpTaskResult:
    if not config.is_configured:
        raise ClickUpNotificationError("ClickUp 알림 설정이 없습니다.")

    owns_session = session is None
    session = session or requests.Session()
    try:
        assignee_ids = config.assignee_ids
        if not assignee_ids and config.auto_assign_self:
            try:
                user_id = get_authorized_user_id(session, config)
                assignee_ids = (user_id,) if user_id is not None else ()
            except ClickUpNotificationError:
                assignee_ids = ()

        payload = build_s2_refresh_task_payload(
            config=config,
            updated_at=updated_at,
            usage_label=usage_label,
            s2_rows=s2_rows,
            s2_id_rows=s2_id_rows,
            missing_guard_rows=missing_guard_rows,
            billing_guard_rows=billing_guard_rows,
            service_content_rows=service_content_rows,
            requested_at=requested_at,
            assignee_ids=assignee_ids,
        )
        try:
            task = _request_json(
                session,
                "POST",
                f"{config.api_base_url}/list/{config.list_id}/task",
                config=config,
                json_body=payload,
            )
        except ClickUpNotificationError:
            if "assignees" not in payload:
                raise
            payload.pop("assignees", None)
            task = _request_json(
                session,
                "POST",
                f"{config.api_base_url}/list/{config.list_id}/task",
                config=config,
                json_body=payload,
            )
        return ClickUpTaskResult(task_id=_text(task.get("id")), url=_text(task.get("url")))
    finally:
        if owns_session:
            session.close()


def create_adapter_failure_task(
    config: ClickUpNotificationConfig,
    *,
    failure_payload: Mapping[str, Any],
    requested_at: datetime | None = None,
    github_issue_url: str = "",
    session: requests.Session | None = None,
) -> ClickUpTaskResult:
    if not config.is_configured:
        raise ClickUpNotificationError("ClickUp 어댑터 실패 큐 설정이 없습니다.")

    owns_session = session is None
    session = session or requests.Session()
    try:
        assignee_ids = config.assignee_ids
        if not assignee_ids and config.auto_assign_self:
            try:
                user_id = get_authorized_user_id(session, config)
                assignee_ids = (user_id,) if user_id is not None else ()
            except ClickUpNotificationError:
                assignee_ids = ()

        payload = build_adapter_failure_task_payload(
            config=config,
            failure_payload=failure_payload,
            requested_at=requested_at,
            assignee_ids=assignee_ids,
            github_issue_url=github_issue_url,
        )
        try:
            task = _request_json(
                session,
                "POST",
                f"{config.api_base_url}/list/{config.list_id}/task",
                config=config,
                json_body=payload,
            )
        except ClickUpNotificationError:
            if "assignees" not in payload:
                raise
            payload.pop("assignees", None)
            task = _request_json(
                session,
                "POST",
                f"{config.api_base_url}/list/{config.list_id}/task",
                config=config,
                json_body=payload,
            )
        return ClickUpTaskResult(task_id=_text(task.get("id")), url=_text(task.get("url")))
    finally:
        if owns_session:
            session.close()


def upload_task_attachment(
    config: ClickUpNotificationConfig,
    *,
    task_id: str,
    attachment: ClickUpAttachment,
    session: requests.Session | None = None,
) -> None:
    if not config.is_configured:
        raise ClickUpNotificationError("ClickUp 어댑터 실패 큐 설정이 없습니다.")
    if not task_id:
        raise ClickUpNotificationError("ClickUp task id가 없어 첨부할 수 없습니다.")

    owns_session = session is None
    session = session or requests.Session()
    try:
        _request_multipart_json(
            session,
            f"{config.api_base_url}/task/{task_id}/attachment",
            config=config,
            attachment=attachment,
        )
    finally:
        if owns_session:
            session.close()


def create_adapter_failure_task_with_attachments(
    config: ClickUpNotificationConfig,
    *,
    failure_payload: Mapping[str, Any],
    attachments: tuple[ClickUpAttachment, ...],
    requested_at: datetime | None = None,
    github_issue_url: str = "",
    session: requests.Session | None = None,
) -> ClickUpTaskResult:
    owns_session = session is None
    session = session or requests.Session()
    try:
        result = create_adapter_failure_task(
            config,
            failure_payload=failure_payload,
            requested_at=requested_at,
            github_issue_url=github_issue_url,
            session=session,
        )
        for attachment in attachments:
            upload_task_attachment(config, task_id=result.task_id, attachment=attachment, session=session)
        return result
    finally:
        if owns_session:
            session.close()
