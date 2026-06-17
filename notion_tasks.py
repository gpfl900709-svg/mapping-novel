from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

import requests


NOTION_API_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"
NOTION_TASK_DATA_SOURCE_ID = "465360d4-1b25-49cf-a859-f33dd5da4209"
SINGLE_PART_LIMIT_BYTES = 20 * 1024 * 1024
MULTIPART_PART_SIZE_BYTES = 10 * 1024 * 1024
TEXT_BLOCK_LIMIT = 1800
MAX_BLOCK_CHILDREN_PER_REQUEST = 100
KST = timezone(timedelta(hours=9))


class NotionTaskError(RuntimeError):
    pass


@dataclass(frozen=True)
class NotionTaskConfig:
    token: str = ""
    data_source_id: str = NOTION_TASK_DATA_SOURCE_ID
    api_base_url: str = NOTION_API_BASE_URL
    notion_version: str = NOTION_VERSION
    app_url: str = ""
    attach_files: bool = True
    attach_original: bool = True
    max_attachment_bytes: int = 0
    timeout_seconds: int = 30

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.data_source_id)


@dataclass(frozen=True)
class NotionTaskResult:
    page_id: str
    url: str
    uploaded_attachments: tuple[str, ...] = ()
    skipped_attachments: tuple[str, ...] = ()


@dataclass(frozen=True)
class NotionAttachment:
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


def _first_value(values: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        raw = values.get(key)
        if _text(raw):
            return _text(raw)
    return ""


def _parse_bool(value: object, *, default: bool = False) -> bool:
    raw = _text(value).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _parse_int(value: object, *, default: int = 0) -> int:
    try:
        return int(_text(value).replace(",", ""))
    except ValueError:
        return default


def _safe_int(value: object) -> int:
    return _parse_int(value, default=0)


def normalize_notion_secret_values(raw_secrets: object) -> dict[str, Any]:
    secrets = _as_mapping(raw_secrets)
    section = _as_mapping(secrets.get("notion") or secrets.get("NOTION"))
    values: dict[str, Any] = {}

    for source in (secrets, section):
        token = _first_value(source, ("NOTION_TOKEN", "NOTION_API_KEY", "token", "api_key"))
        if token:
            values["NOTION_TOKEN"] = token

        data_source_id = _first_value(
            source,
            (
                "NOTION_TASK_DATA_SOURCE_ID",
                "NOTION_DATA_SOURCE_ID",
                "task_data_source_id",
                "data_source_id",
            ),
        )
        if data_source_id:
            values["NOTION_TASK_DATA_SOURCE_ID"] = data_source_id

        api_base_url = _first_value(source, ("NOTION_API_BASE_URL", "api_base_url"))
        if api_base_url:
            values["NOTION_API_BASE_URL"] = api_base_url

        api_version = _first_value(source, ("NOTION_API_VERSION", "NOTION_VERSION", "api_version", "notion_version"))
        if api_version:
            values["NOTION_API_VERSION"] = api_version

        app_url = _first_value(source, ("NOTION_APP_URL", "app_url"))
        if app_url:
            values["NOTION_APP_URL"] = app_url

        attach_files = source.get("NOTION_ATTACH_FILES")
        if attach_files is None:
            attach_files = source.get("attach_files")
        if attach_files is not None:
            values["NOTION_ATTACH_FILES"] = attach_files

        attach_original = source.get("NOTION_ATTACH_ORIGINAL_XLSX")
        if attach_original is None:
            attach_original = source.get("attach_original_xlsx")
        if attach_original is not None:
            values["NOTION_ATTACH_ORIGINAL_XLSX"] = attach_original

        max_attachment_bytes = source.get("NOTION_MAX_ATTACHMENT_BYTES")
        if max_attachment_bytes is None:
            max_attachment_bytes = source.get("max_attachment_bytes")
        if max_attachment_bytes is not None:
            values["NOTION_MAX_ATTACHMENT_BYTES"] = max_attachment_bytes

    return values


def build_notion_task_config(values: Mapping[str, Any]) -> NotionTaskConfig:
    return NotionTaskConfig(
        token=_first_value(values, ("NOTION_TOKEN", "NOTION_API_KEY")),
        data_source_id=_first_value(values, ("NOTION_TASK_DATA_SOURCE_ID", "NOTION_DATA_SOURCE_ID"))
        or NOTION_TASK_DATA_SOURCE_ID,
        api_base_url=(_first_value(values, ("NOTION_API_BASE_URL",)) or NOTION_API_BASE_URL).rstrip("/"),
        notion_version=_first_value(values, ("NOTION_API_VERSION", "NOTION_VERSION")) or NOTION_VERSION,
        app_url=_first_value(values, ("NOTION_APP_URL",)),
        attach_files=_parse_bool(values.get("NOTION_ATTACH_FILES"), default=True),
        attach_original=_parse_bool(values.get("NOTION_ATTACH_ORIGINAL_XLSX"), default=True),
        max_attachment_bytes=_parse_int(values.get("NOTION_MAX_ATTACHMENT_BYTES"), default=0),
    )


def chunk_text(value: object, *, limit: int = TEXT_BLOCK_LIMIT) -> list[str]:
    raw = _text(value)
    if not raw:
        return [""]
    chunks: list[str] = []
    rest = raw
    while rest:
        chunks.append(rest[:limit])
        rest = rest[limit:]
    return chunks


def rich_text(content: object) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": _text(content)}}] if _text(content) else []


def notion_blocks(lines: Sequence[object]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for line in lines:
        for chunk in chunk_text(line):
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": rich_text(chunk)},
                }
            )
    return blocks


def _select_property(name: str) -> dict[str, Any]:
    return {"select": {"name": name}}


def _title_property(title: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": title[:2000]}}]}


def _date_property(value: str) -> dict[str, Any]:
    return {"date": {"start": value}}


def _url_property(value: str) -> dict[str, Any]:
    return {"url": value}


def build_page_request(task_payload: Mapping[str, Any], config: NotionTaskConfig) -> dict[str, Any]:
    source_properties = _as_mapping(task_payload.get("properties"))
    title = _text(source_properties.get("업무명")) or _text(task_payload.get("title")) or "mapping-novel task"
    properties: dict[str, Any] = {"업무명": _title_property(title)}

    for key in ("상태", "영역", "우선순위", "반복"):
        value = _text(source_properties.get(key))
        if value:
            properties[key] = _select_property(value)

    due_date = _text(source_properties.get("마감일"))
    if due_date:
        properties["마감일"] = _date_property(due_date)

    link = _text(source_properties.get("링크"))
    if link:
        properties["링크"] = _url_property(link)

    return {
        "parent": {"type": "data_source_id", "data_source_id": config.data_source_id},
        "properties": properties,
        "children": notion_blocks(task_payload.get("body") or []),
    }


def _headers(config: NotionTaskConfig, *, json_content: bool = True) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {config.token}",
        "Notion-Version": config.notion_version,
        "Accept": "application/json",
    }
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def _api_error(response: requests.Response) -> NotionTaskError:
    detail = response.text[:500] if response.text else getattr(response, "reason", "")
    return NotionTaskError(f"Notion API 오류 {response.status_code}: {detail}")


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    config: NotionTaskConfig,
    *,
    json_payload: Mapping[str, Any] | None = None,
    data: Mapping[str, Any] | None = None,
    files: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        response = session.request(
            method,
            url,
            headers=_headers(config, json_content=files is None),
            json=json_payload,
            data=data,
            files=files,
            timeout=config.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise NotionTaskError(f"Notion API 요청 실패: {exc}") from exc
    if response.status_code >= 400:
        raise _api_error(response)
    try:
        body = response.json()
    except ValueError as exc:
        raise NotionTaskError("Notion API 응답 JSON을 읽지 못했습니다.") from exc
    return body if isinstance(body, dict) else {}


def _with_session(session: requests.Session | None) -> tuple[requests.Session, bool]:
    if session is not None:
        return session, False
    return requests.Session(), True


def _safe_filename(filename: str) -> str:
    value = _text(filename) or "attachment.bin"
    value = "".join("_" if char in r'\/:*?"<>|' else char for char in value).strip() or "attachment.bin"
    while len(value.encode("utf-8")) > 850:
        stem, dot, suffix = value.rpartition(".")
        if not dot or len(stem) <= 1:
            value = value[: max(1, len(value) - 10)]
        else:
            value = f"{stem[:-10]}.{suffix}"
    return value


def create_file_upload(
    config: NotionTaskConfig,
    attachment: NotionAttachment,
    *,
    mode: str,
    number_of_parts: int | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    if not config.is_configured:
        raise NotionTaskError("Notion task 설정이 없습니다.")
    session_obj, owns_session = _with_session(session)
    try:
        payload: dict[str, Any] = {
            "mode": mode,
            "filename": _safe_filename(attachment.filename),
            "content_type": _text(attachment.content_type) or "application/octet-stream",
        }
        if number_of_parts is not None:
            payload["number_of_parts"] = number_of_parts
        return _request_json(
            session_obj,
            "POST",
            f"{config.api_base_url}/file_uploads",
            config,
            json_payload=payload,
        )
    finally:
        if owns_session:
            session_obj.close()


def send_file_upload_part(
    config: NotionTaskConfig,
    *,
    upload: Mapping[str, Any],
    attachment: NotionAttachment,
    content: bytes,
    part_number: int | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    upload_id = _text(upload.get("id"))
    if not upload_id:
        raise NotionTaskError("Notion file upload id가 없습니다.")
    session_obj, owns_session = _with_session(session)
    try:
        url = _text(upload.get("upload_url")) or f"{config.api_base_url}/file_uploads/{upload_id}/send"
        data = {"part_number": str(part_number)} if part_number is not None else None
        files = {"file": (_safe_filename(attachment.filename), content, attachment.content_type)}
        return _request_json(session_obj, "POST", url, config, data=data, files=files)
    finally:
        if owns_session:
            session_obj.close()


def complete_file_upload(
    config: NotionTaskConfig,
    *,
    upload: Mapping[str, Any],
    session: requests.Session | None = None,
) -> dict[str, Any]:
    upload_id = _text(upload.get("id"))
    if not upload_id:
        raise NotionTaskError("Notion file upload id가 없습니다.")
    session_obj, owns_session = _with_session(session)
    try:
        url = _text(upload.get("complete_url")) or f"{config.api_base_url}/file_uploads/{upload_id}/complete"
        return _request_json(session_obj, "POST", url, config, json_payload={})
    finally:
        if owns_session:
            session_obj.close()


def upload_attachment(
    config: NotionTaskConfig,
    attachment: NotionAttachment,
    *,
    session: requests.Session | None = None,
) -> str:
    content = attachment.content or b""
    if len(content) <= SINGLE_PART_LIMIT_BYTES:
        upload = create_file_upload(config, attachment, mode="single_part", session=session)
        sent = send_file_upload_part(config, upload=upload, attachment=attachment, content=content, session=session)
        return _text(sent.get("id")) or _text(upload.get("id"))

    number_of_parts = max(1, math.ceil(len(content) / MULTIPART_PART_SIZE_BYTES))
    upload = create_file_upload(
        config,
        attachment,
        mode="multi_part",
        number_of_parts=number_of_parts,
        session=session,
    )
    for part_number in range(1, number_of_parts + 1):
        start = (part_number - 1) * MULTIPART_PART_SIZE_BYTES
        end = min(start + MULTIPART_PART_SIZE_BYTES, len(content))
        send_file_upload_part(
            config,
            upload=upload,
            attachment=attachment,
            content=content[start:end],
            part_number=part_number,
            session=session,
        )
    completed = complete_file_upload(config, upload=upload, session=session)
    return _text(completed.get("id")) or _text(upload.get("id"))


def file_block(file_upload_id: str, filename: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "file",
        "file": {
            "type": "file_upload",
            "file_upload": {"id": file_upload_id},
        },
    }


def append_blocks(
    config: NotionTaskConfig,
    page_id: str,
    children: Sequence[Mapping[str, Any]],
    *,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    session_obj, owns_session = _with_session(session)
    last_response: dict[str, Any] = {}
    try:
        for start in range(0, len(children), MAX_BLOCK_CHILDREN_PER_REQUEST):
            chunk = list(children[start : start + MAX_BLOCK_CHILDREN_PER_REQUEST])
            if not chunk:
                continue
            last_response = _request_json(
                session_obj,
                "PATCH",
                f"{config.api_base_url}/blocks/{page_id}/children",
                config,
                json_payload={"children": chunk},
            )
        return last_response
    finally:
        if owns_session:
            session_obj.close()


def append_text_blocks(
    config: NotionTaskConfig,
    page_id: str,
    lines: Sequence[object],
    *,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    return append_blocks(config, page_id, notion_blocks(lines), session=session)


def update_task_link(
    config: NotionTaskConfig,
    page_id: str,
    link: str,
    *,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    if not _text(link):
        return {}
    session_obj, owns_session = _with_session(session)
    try:
        return _request_json(
            session_obj,
            "PATCH",
            f"{config.api_base_url}/pages/{page_id}",
            config,
            json_payload={"properties": {"링크": _url_property(link)}},
        )
    finally:
        if owns_session:
            session_obj.close()


def workspace_file_limit_bytes(config: NotionTaskConfig, *, session: requests.Session | None = None) -> int:
    if config.max_attachment_bytes > 0:
        return config.max_attachment_bytes
    session_obj, owns_session = _with_session(session)
    try:
        body = _request_json(session_obj, "GET", f"{config.api_base_url}/users/me", config)
    except NotionTaskError:
        return 0
    finally:
        if owns_session:
            session_obj.close()
    bot = _as_mapping(body.get("bot"))
    limits = _as_mapping(bot.get("workspace_limits"))
    return _parse_int(limits.get("max_file_upload_size_in_bytes"), default=0)


def append_attachments(
    config: NotionTaskConfig,
    page_id: str,
    attachments: Sequence[NotionAttachment],
    *,
    session: requests.Session | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    session_obj, owns_session = _with_session(session)
    uploaded: list[str] = []
    skipped: list[str] = []
    try:
        if attachments and not config.attach_files:
            skipped.extend(f"{attachment.filename}: NOTION_ATTACH_FILES=false" for attachment in attachments)
        limit_bytes = workspace_file_limit_bytes(config, session=session_obj) if attachments and config.attach_files else 0
        for attachment in attachments:
            if not config.attach_files:
                continue
            if limit_bytes and len(attachment.content) > limit_bytes:
                skipped.append(f"{attachment.filename}: Notion 업로드 한도 초과 ({len(attachment.content):,} B > {limit_bytes:,} B)")
                continue
            try:
                upload_id = upload_attachment(config, attachment, session=session_obj)
                append_blocks(config, page_id, [file_block(upload_id, attachment.filename)], session=session_obj)
                uploaded.append(attachment.filename)
            except NotionTaskError as exc:
                skipped.append(f"{attachment.filename}: {exc}")

        if skipped and page_id:
            try:
                append_text_blocks(
                    config,
                    page_id,
                    ["첨부 처리 경고", *[f"- {item}" for item in skipped]],
                    session=session_obj,
                )
            except NotionTaskError as exc:
                skipped.append(f"첨부 경고 본문 기록 실패: {exc}")
        return tuple(uploaded), tuple(skipped)
    finally:
        if owns_session:
            session_obj.close()


def create_notion_task(
    config: NotionTaskConfig,
    task_payload: Mapping[str, Any],
    *,
    attachments: Sequence[NotionAttachment] = (),
    session: requests.Session | None = None,
) -> NotionTaskResult:
    if not config.is_configured:
        raise NotionTaskError("Notion task 설정이 없습니다.")

    session_obj, owns_session = _with_session(session)
    try:
        page = _request_json(
            session_obj,
            "POST",
            f"{config.api_base_url}/pages",
            config,
            json_payload=build_page_request(task_payload, config),
        )
        page_id = _text(page.get("id"))
        page_url = _text(page.get("url"))

        uploaded, skipped = append_attachments(config, page_id, attachments, session=session_obj)

        return NotionTaskResult(
            page_id=page_id,
            url=page_url,
            uploaded_attachments=tuple(uploaded),
            skipped_attachments=tuple(skipped),
        )
    finally:
        if owns_session:
            session_obj.close()


def _created_at(value: datetime | None = None) -> datetime:
    return value or datetime.now(KST)


def build_s2_refresh_task_payload(
    config: NotionTaskConfig,
    *,
    updated_at: str,
    usage_label: str,
    usage_tone: str = "",
    s2_rows: int,
    s2_id_rows: int,
    missing_guard_rows: int,
    billing_guard_rows: int,
    service_content_rows: int,
    requested_at: datetime | None = None,
) -> dict[str, Any]:
    created = _created_at(requested_at)
    if usage_tone:
        priority = "높음" if usage_tone != "ok" else "보통"
    else:
        priority = "높음" if usage_label and usage_label not in {"사용 가능", "정상", "ok", "OK"} else "보통"
    title = f"S2 최신화 요청 - {created.strftime('%Y-%m-%d %H:%M')}"
    return {
        "properties": {
            "업무명": title,
            "상태": "인박스",
            "영역": "매핑",
            "우선순위": priority,
            "링크": config.app_url,
        },
        "body": [
            "mapping-novel S2 최신화 요청",
            f"- 요청시각(KST): {created.isoformat(timespec='minutes')}",
            f"- 현재 기준 업데이트: {updated_at or '확인 필요'}",
            f"- 상태: {usage_label or '확인 필요'}",
            f"- S2 rows: {s2_rows:,}",
            f"- 통합 계약 ID 연결 rows: {s2_id_rows:,}",
            f"- 미지급 guard rows: {missing_guard_rows:,}",
            f"- 청구 guard rows: {billing_guard_rows:,}",
            f"- 판매채널콘텐츠 guard rows: {service_content_rows:,}",
            f"- 앱: {config.app_url}",
        ],
    }


def build_adapter_failure_task_payload(
    config: NotionTaskConfig,
    *,
    failure_payload: Mapping[str, Any],
    github_issue_url: str = "",
    requested_at: datetime | None = None,
) -> dict[str, Any]:
    created = _created_at(requested_at)
    channel = _text(failure_payload.get("detected_s2_channel")) or _text(failure_payload.get("selected_s2_channel"))
    channel = channel or "판매채널 확인 필요"
    source_name = _text(failure_payload.get("source_name")) or "uploaded.xlsx"
    title = f"[긴급][정산서 어댑터 실패] {channel} / {source_name}"
    link = _text(github_issue_url) or _text(failure_payload.get("streamlit_app_url")) or config.app_url
    body = [
        "정산서 어댑터 실패 요청",
        f"- 생성시각(KST): {created.isoformat(timespec='minutes')}",
        f"- failure_category: {_text(failure_payload.get('failure_category')) or '확인 필요'}",
        f"- status: {_text(failure_payload.get('status')) or '확인 필요'}",
        f"- failure_reason: {_text(failure_payload.get('failure_reason')) or '확인 필요'}",
        f"- source_name: {source_name}",
        f"- source_sha256: {_text(failure_payload.get('source_sha256'))}",
        f"- source_size: {_safe_int(failure_payload.get('source_size')):,} B",
        f"- platform: {_text(failure_payload.get('effective_platform')) or '확인 필요'}",
        f"- s2_sales_channel: {channel}",
        f"- app_commit_sha: {_text(failure_payload.get('app_commit_sha')) or 'unknown'}",
    ]
    if github_issue_url:
        body.append(f"- GitHub Issue: {github_issue_url}")
    sheet_audits = failure_payload.get("sheet_audits") or []
    if isinstance(sheet_audits, Sequence) and not isinstance(sheet_audits, (str, bytes)):
        body.extend(["", "Sheet audits"])
        for row in list(sheet_audits)[:10]:
            if not isinstance(row, Mapping):
                continue
            body.append(
                "- "
                + " / ".join(
                    part
                    for part in (
                        _text(row.get("sheet")),
                        _text(row.get("status")),
                        f"parsed={_text(row.get('parsed_rows'))}",
                        _text(row.get("note")),
                    )
                    if part
                )
            )
    body.extend(["", "첨부 기준", "- 원본 xlsx와 상세 payload는 Notion 카드 첨부에서 확인한다."])
    return {
        "properties": {
            "업무명": title,
            "상태": "인박스",
            "영역": "매핑",
            "우선순위": "높음",
            "링크": link,
        },
        "body": body,
    }


def build_mapping_run_task_payload(
    config: NotionTaskConfig,
    *,
    run_payload: Mapping[str, Any],
    requested_at: datetime | None = None,
) -> dict[str, Any]:
    created = _created_at(requested_at)
    review_count = _safe_int(run_payload.get("review_required_count"))
    missing_count = _safe_int(run_payload.get("missing_candidate_count"))
    billing_count = _safe_int(run_payload.get("billing_candidate_count"))
    status_counts = _as_mapping(run_payload.get("status_counts"))
    blocked_count = _safe_int(status_counts.get("blocked")) + _safe_int(status_counts.get("failed"))
    issue_count = review_count + missing_count + billing_count + blocked_count
    file_count = _safe_int(run_payload.get("file_count"))
    title = f"[매핑 실행 기록] {created.strftime('%Y-%m-%d %H:%M')} · {file_count:,}개 · 이슈 {issue_count:,}"
    source_names = run_payload.get("source_names") or []
    body = [
        "mapping-novel 매핑 실행 기록",
        f"- run_id: {_text(run_payload.get('run_id'))}",
        f"- signature_sha256: {_text(run_payload.get('signature_sha256'))}",
        f"- 생성시각(KST): {created.isoformat(timespec='minutes')}",
        f"- 입력 파일 수: {file_count:,}",
        f"- 상태 카운트: {dict(status_counts)}",
        f"- 검토필요: {review_count:,}",
        f"- 누락 후보: {missing_count:,}",
        f"- 청구 후보: {billing_count:,}",
        f"- S2 기준: {_text(run_payload.get('s2_source_label'))}",
        f"- S2 rows: {_safe_int(run_payload.get('s2_rows')):,}",
        f"- 통합 계약 ID rows: {_safe_int(run_payload.get('s2_id_rows')):,}",
        f"- ZIP: {_text(run_payload.get('zip_name'))} ({_safe_int(run_payload.get('zip_size')):,} B)",
        f"- ZIP sha256: {_text(run_payload.get('zip_sha256'))}",
        f"- app_commit_sha: {_text(run_payload.get('app_commit_sha')) or 'unknown'}",
        f"- 앱: {config.app_url or _text(run_payload.get('app_url'))}",
        "",
        "입력 파일",
    ]
    if isinstance(source_names, Sequence) and not isinstance(source_names, (str, bytes)):
        for name in list(source_names)[:20]:
            body.append(f"- {_text(name)}")
        if len(source_names) > 20:
            body.append(f"- ... 외 {len(source_names) - 20:,}개")
    return {
        "properties": {
            "업무명": title,
            "상태": "인박스",
            "영역": "매핑",
            "우선순위": "높음" if issue_count else "낮음",
            "링크": config.app_url or _text(run_payload.get("app_url")),
        },
        "body": body,
    }


def create_s2_refresh_request_task(
    config: NotionTaskConfig,
    *,
    updated_at: str,
    usage_label: str,
    usage_tone: str = "",
    s2_rows: int,
    s2_id_rows: int,
    missing_guard_rows: int,
    billing_guard_rows: int,
    service_content_rows: int,
    requested_at: datetime | None = None,
    session: requests.Session | None = None,
) -> NotionTaskResult:
    payload = build_s2_refresh_task_payload(
        config,
        updated_at=updated_at,
        usage_label=usage_label,
        usage_tone=usage_tone,
        s2_rows=s2_rows,
        s2_id_rows=s2_id_rows,
        missing_guard_rows=missing_guard_rows,
        billing_guard_rows=billing_guard_rows,
        service_content_rows=service_content_rows,
        requested_at=requested_at,
    )
    return create_notion_task(config, payload, session=session)


def create_adapter_failure_task(
    config: NotionTaskConfig,
    *,
    failure_payload: Mapping[str, Any],
    attachments: Sequence[NotionAttachment] = (),
    github_issue_url: str = "",
    session: requests.Session | None = None,
) -> NotionTaskResult:
    payload = build_adapter_failure_task_payload(config, failure_payload=failure_payload, github_issue_url=github_issue_url)
    return create_notion_task(config, payload, attachments=attachments, session=session)


def create_mapping_run_task(
    config: NotionTaskConfig,
    *,
    run_payload: Mapping[str, Any],
    attachments: Sequence[NotionAttachment] = (),
    session: requests.Session | None = None,
) -> NotionTaskResult:
    payload = build_mapping_run_task_payload(config, run_payload=run_payload)
    return create_notion_task(config, payload, attachments=attachments, session=session)
