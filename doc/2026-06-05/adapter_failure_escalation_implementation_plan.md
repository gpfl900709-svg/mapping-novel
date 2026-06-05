# 정산서 어댑터 실패 에스컬레이션 구현안

작성일: 2026-06-05 KST
기준 커밋: `52f3d41 Fix Naver settlement sheet fallback`
확신도: 95%

## 결론

정산서 업로드 실패 플로우는 ClickUp Task를 운영 원장으로 쓰고, GitHub Issue는 repo 변경 추적용 sanitized 티켓으로 쓰는 구조가 맞다.

- 원본 `.xlsx`는 ClickUp Task attachment로만 붙인다.
- GitHub Issue에는 원본 파일을 붙이지 않고, 실패 사유/헤더 후보/ClickUp 링크/커밋 SHA/파일 해시만 올린다.
- ClickUp Docs는 실패 원본 보관 위치로 쓰지 않는다. 누적 운영 문서나 월간 회고용이면 나중에 별도 확장한다.
- 폰 알림은 ClickUp 댓글이 아니라 새 태스크 + assignee `306885786` + due date 현재 시각 + 2분으로 만든다. 댓글 `notify_all=true`는 API 유저 활동이면 모바일 푸시가 씹힐 수 있으므로 보조 수단으로만 본다.
- 운영 ClickUp은 전용 Folder와 전용 List를 만든다. 앱이 실제로 쓰는 값은 Folder ID가 아니라 그 안의 실패 티켓 List ID다.

## 조사 근거

내부 코드 기준:

- `app.py`는 업로드 파일별 처리 결과를 `status=success|blocked|failed`로 정리한다.
- `process_settlement_batch_item()`은 실패/차단 결과에 `source_name`, `platform`, `s2_sales_channel`, `error`, `blocking_messages`, `warning_messages`, `stage_seconds`, `adapter_summary`, `audit_df`, `adapter_result`를 붙인다.
- `settlement_adapters.py`는 `adapter_audit_dataframe()`, `adapter_blocking_messages()`, `adapter_warning_messages()`를 이미 제공한다.
- 어댑터 감사는 시트명, 상태, 헤더 행, 데이터 시작 행, 파싱 행, 제목 행, note를 포함한다.
- 헤더 탐지는 `_find_header_row()`와 `_header_score()`가 담당하며, 현재 점수 기준은 8점 이상이다.
- 병렬 처리에서는 `snapshot_uploaded_file()`로 원본 업로드 bytes를 `NamedBytesIO`에 보존한다.
- 기존 `clickup_notifications.py`는 ClickUp API 토큰/list/담당자/priority/secrets 처리와 태스크 생성 패턴을 이미 갖고 있다.
- `doc/OPERATIONS.md`는 업로드 실패 시 오류 상세와 시트별 감사를 먼저 확인하라고 적고 있다. 이번 구현은 그 수동 확인을 자동 패키징하는 것이다.

공식 API 기준:

- ClickUp 태스크 생성: `POST /api/v2/list/{list_id}/task`, body에 `name`, `assignees`, `tags`, `priority`, `notify_all`, `markdown_content` 사용 가능.
- ClickUp 태스크 첨부: `POST /api/v2/task/{task_id}/attachment`, `multipart/form-data`, `attachment` 파일 업로드. 공식 문서상 최대 파일 크기 1GB, 파일 타입 제한 없음.
- GitHub Issue 생성: `POST /repos/{owner}/{repo}/issues`, fine-grained token은 Issues write 권한 필요.

참조:

- https://developer.clickup.com/reference/createtask
- https://developer.clickup.com/docs/attachments
- https://developer.clickup.com/reference/createtaskattachment
- https://docs.github.com/en/rest/issues/issues#create-an-issue

## 권장 플로우

```text
사용자 정산서 업로드
-> 앱 처리 중 blocked/failed 발생
-> 실패 진단 패키지 생성
-> ClickUp 긴급 태스크 생성
-> ClickUp 태스크에 원본 xlsx + failure_report.md + failure_payload.json 첨부
-> GitHub Issue 생성
-> GitHub Issue 본문에 sanitized 요약 + ClickUp 링크 + 커밋 SHA 기록
-> ClickUp/GitHub 담당자 알림으로 운영자 폰에 도달
```

## 역할 분리

### ClickUp

운영 처리용이다.

- 전용 Folder: 예: `mapping-novel 정산서 어댑터`
- 전용 List: 예: `긴급 실패 티켓`
- 긴급 태스크 생성
- priority 높게 설정
- 담당자 지정: 기본 `306885786`
- due date: 기본 현재 시각 + 2분, `due_date_time=true`
- 태그: `adapter-failure`, `mapping-novel`, `{platform}`, `{s2_sales_channel}`
- 원본 `.xlsx` 첨부
- `failure_report.md` 첨부
- `failure_payload.json` 첨부
- 본문에 실패 사유, 헤더 스냅샷 요약, 앱 커밋, 파일 해시, GitHub Issue 링크 기록

### GitHub Issue

repo 변경 추적용이다.

- 원본 `.xlsx` 첨부 금지
- sanitized 실패 요약만 기록
- ClickUp 태스크 링크 기록
- label: `adapter-failure`, `urgent`
- assignee 또는 mention으로 GitHub 모바일 알림 유도
- adapter 수정 PR이 생기면 Issue와 PR을 연결

## 실패 진단 패키지

패키지는 세 덩어리로 만든다.

### `failure_payload.json`

기계 처리용 원본 진단 데이터다. ClickUp에는 첨부하고, GitHub에는 민감 값 제거 후 일부만 본문에 넣는다.

필드:

- `schema_version`: 예: `adapter_failure.v1`
- `event_id`: 중복 방지용 ID
- `created_at_kst`
- `app_commit_sha`
- `app_version`
- `streamlit_app_url`
- `source_name`
- `source_size`
- `source_sha256`
- `selected_s2_channel`
- `detected_s2_channel`
- `effective_platform`
- `status`: `blocked` 또는 `failed`
- `failure_category`
- `failure_reason`
- `blocking_messages`
- `warning_messages`
- `info_messages`
- `sheet_names`
- `sheet_audits`
- `header_snapshots`
- `header_candidates`
- `adapter_summary`
- `s2_channel_filter`
- `s2_guard_summary`
- `stage_seconds`
- `clickup_task_id`
- `clickup_task_url`
- `github_issue_url`

### `failure_report.md`

운영자가 바로 읽는 문서다.

구성:

- 제목: `[긴급][정산서 어댑터 실패] {판매채널} / {파일명}`
- 1줄 결론: 예: `시트명 규칙 불일치 후 헤더 후보 3행 감지, S2 입력 0행`
- 실패 분류
- 사용자가 선택/감지한 판매채널
- 파일 해시
- 앱 커밋 SHA
- 시트 목록
- 시트별 감사표
- 상위 10행 헤더 스냅샷
- 헤더 감지 점수표
- 재현 방법
- 다음 액션: `settlement_adapters.py`의 해당 `AdapterSpec` 또는 파서 규칙 수정

### 원본 `.xlsx`

ClickUp Task attachment로만 올린다.

원칙:

- GitHub에는 첨부하지 않는다.
- 파일명은 원본을 유지하되, ClickUp 첨부명 앞에 `source_`를 붙여도 된다.
- 첨부 전 SHA-256과 size를 기록한다.
- Streamlit 세션 state에 장기 보존하지 않는다. 실패 요청 버튼을 누를 때 업로드 객체/스냅샷에서 bytes를 읽고 즉시 업로드한다.
- ClickUp 첨부 API는 cloud file URL을 넘기는 방식이 아니다. Streamlit 앱이 가진 업로드 bytes를 `multipart/form-data`로 직접 전송한다.

## 실패 분류

`failure_category`는 문자열 enum으로 둔다.

- `channel_detection_failed`: 파일명/수동 선택 기준으로 S2 판매채널 또는 플랫폼을 결정하지 못함
- `sheet_name_mismatch`: 대상 시트를 하나도 찾지 못함
- `header_not_found`: 대상 시트는 있으나 헤더 점수가 기준 미만
- `required_columns_missing`: 헤더는 찾았지만 표준화에 필요한 필수 컬럼이 없음
- `zero_parsed_rows`: 어댑터 파싱 결과가 0행
- `zero_default_feed_rows`: 파싱은 됐지만 S2 매핑 입력 행이 0행
- `amount_policy_unlocked`: S2 전송자료 금액 정책이 확정되지 않은 플랫폼에서 전송자료 생성이 필요한 상태
- `s2_filter_empty`: S2 판매채널 필터 적용 후 기준 행이 0행
- `s2_reference_stale_or_missing`: S2 기준/guard가 없거나 오래됨
- `unexpected_exception`: 위 분류가 아닌 예외

현재 코드의 기존 메시지와 매핑:

- `not s2_channel or not effective_platform` -> `channel_detection_failed`
- `adapter_blocking_messages()`의 `어댑터가 데이터 행을 만들지 못했습니다.` -> `zero_parsed_rows`
- `파싱은 됐지만 S2 매핑으로 보낼 입력 행이 없습니다.` -> `zero_default_feed_rows`
- `헤더를 찾지 못한 시트가 있습니다` -> `header_not_found`
- `audit_df.status == excluded_sheet`만 있고 parsed가 없음 -> `sheet_name_mismatch`
- `s2_channel_filter.active and after_rows == 0` -> `s2_filter_empty`
- `except Exception` -> `unexpected_exception`

## 헤더 스냅샷 설계

운영자가 “시트명이 바뀜”, “헤더가 3행으로 내려감”, “컬럼명이 바뀜”을 바로 보게 만드는 게 핵심이다.

새 함수:

```python
collect_workbook_diagnostics(source, platform) -> WorkbookDiagnostic
```

수집값:

- `sheet_names`: workbook 전체 시트명
- `top_rows_by_sheet`: 각 시트 상위 10행 값
- `header_scores_by_sheet`: 각 시트 상위 100행에 대한 `_header_score()` 결과
- `best_header_candidate_by_sheet`: 최고 점수 행 번호/점수/셀 값
- `sheet_in_scope`: `_sheet_in_scope()` 결과

주의:

- 원본 행 데이터 전체를 넣지 않는다.
- 상위 10행도 GitHub에는 그대로 올리지 말고, 빈 값 제거/긴 문자열 truncate/금액처럼 보이는 값 마스킹을 적용한다.
- ClickUp 첨부 `failure_payload.json`에는 더 자세한 스냅샷을 넣을 수 있지만, 그래도 전체 매출 행은 넣지 않는다.
- `_header_score()`와 `_sheet_in_scope()`를 외부 모듈에서 직접 가져오는 게 불편하면 `settlement_adapters.py`에 public diagnostic wrapper를 추가한다.

## 구현 단위

### 1단계: 진단 패키지 생성

새 파일 후보:

- `adapter_failure_diagnostics.py`

주요 함수:

```python
build_adapter_failure_payload(
    *,
    result: dict[str, Any],
    source_file: object,
    selected_s2_channel: str,
    app_commit_sha: str,
    app_url: str,
) -> AdapterFailurePayload

render_failure_report_markdown(payload: AdapterFailurePayload) -> str
render_failure_payload_json(payload: AdapterFailurePayload) -> bytes
sanitize_payload_for_github(payload: AdapterFailurePayload) -> dict[str, Any]
```

테스트:

- `tests/test_adapter_failure_diagnostics.py`
- Naver 시트명 변경 fixture
- 헤더 없음 fixture
- 파일명 감지 실패 fixture
- `zero_default_feed_rows` fixture

### 2단계: ClickUp 태스크 + 첨부

기존 `clickup_notifications.py`를 확장한다.

전용 모드 기준:

- ClickUp에서 전용 Folder를 만들고 그 안에 실패 티켓 전용 List를 둔다.
- Streamlit/로컬 설정에는 Folder ID가 아니라 전용 List ID를 넣는다.
- S2 최신화 요청용 `CLICKUP_LIST_ID`와 어댑터 실패용 `CLICKUP_ADAPTER_FAILURE_LIST_ID`를 분리한다.

추가 설정:

- `CLICKUP_ADAPTER_FAILURE_LIST_ID`
- `CLICKUP_ADAPTER_FAILURE_ASSIGNEE_IDS`
- `CLICKUP_ADAPTER_FAILURE_STATUS`
- `CLICKUP_ADAPTER_FAILURE_PRIORITY`
- `CLICKUP_ADAPTER_FAILURE_DUE_DATE_MINUTES`
- `CLICKUP_ADAPTER_FAILURE_ATTACH_ORIGINAL`
- `CLICKUP_ADAPTER_FAILURE_TAGS`

기본값:

- 운영/Cloud에서는 `CLICKUP_ADAPTER_FAILURE_LIST_ID`를 필수로 본다
- 기존 `CLICKUP_LIST_ID` fallback은 로컬 개발 또는 임시 테스트에서만 허용한다
- assignee 기본값은 `306885786`으로 둔다
- status 기본값은 `to do`로 둔다
- priority는 `1` 또는 운영 ClickUp에서 가장 높은 우선순위로 맞춘다
- due date 기본값은 생성 시각 + 2분이다
- 전용 큐가 생성됐으므로 원본 첨부 기본값은 `CLICKUP_ADAPTER_FAILURE_ATTACH_ORIGINAL=true`로 둔다

새 함수:

```python
create_adapter_failure_task(config, payload, *, session=None) -> ClickUpTaskResult
upload_task_attachment(config, task_id, filename, content, content_type, *, session=None) -> None
create_adapter_failure_task_with_attachments(
    config,
    payload,
    *,
    original_file: Attachment | None,
    report_markdown: bytes,
    report_json: bytes,
    session=None,
) -> ClickUpTaskResult
```

첨부 순서:

1. ClickUp 태스크 생성
2. `failure_report.md` 첨부
3. `failure_payload.json` 첨부
4. 원본 `.xlsx` 첨부
5. 첨부 실패가 일부 발생하면 task 본문 또는 comment에 실패 사실을 남김

테스트:

- 태스크 payload에 `notify_all`, `priority`, `assignees`, `due_date`, `due_date_time`, `tags` 포함
- multipart 요청이 `attachment` 필드명으로 전송되는지 확인
- 원본 첨부 flag off면 `.xlsx` 미첨부
- ClickUp 첨부 실패 시 사용자에게 ClickUp task URL과 실패 상세 표시

### 3단계: GitHub Issue 생성

새 파일 후보:

- `github_notifications.py`

설정:

- `GITHUB_ADAPTER_FAILURE_TOKEN`
- `GITHUB_ADAPTER_FAILURE_REPO`, 예: `owner/mapping-novel`
- `GITHUB_ADAPTER_FAILURE_ASSIGNEES`
- `GITHUB_ADAPTER_FAILURE_MENTIONS`
- `GITHUB_ADAPTER_FAILURE_LABELS`
- `GITHUB_API_BASE_URL`, 기본 `https://api.github.com`

새 함수:

```python
create_adapter_failure_issue(config, payload, *, clickup_url: str, session=None) -> GitHubIssueResult
```

Issue 제목:

```text
[adapter-failure] {판매채널} {failure_category}: {파일명}
```

Issue 본문 포함:

- 실패 분류
- 실패 사유
- 플랫폼/S2 판매채널
- 시트 목록
- 헤더 후보 요약
- 앱 커밋 SHA
- 파일 SHA-256
- ClickUp task 링크
- 재현용 fixture 생성 가이드

Issue 본문 제외:

- 원본 `.xlsx`
- 매출/정산 금액 행 데이터
- 개인정보/계약정보
- ClickUp API 토큰, GitHub 토큰

테스트:

- Issue body에 ClickUp 링크 포함
- 원본 파일명과 hash는 포함하지만 raw workbook bytes는 없음
- labels/assignees/mentions 반영
- GitHub 403/422 응답 시 사용자가 다운로드할 수 있는 fallback report 제공

### 4단계: Streamlit UI 연결

결과 화면 `처리 결과` 아래에 실패/차단 항목 전용 expander를 추가한다.

권장 UI:

- 실패/차단 항목만 리스트업
- 각 항목에 `어댑터 수정 요청` 버튼
- 버튼 클릭 시:
  - 진단 패키지 생성
  - ClickUp task 생성
  - 첨부 업로드
  - GitHub Issue 생성
  - 완료 후 ClickUp/GitHub 링크 표시
- 중복 요청 방지:
  - `dedupe_key = sha256(source_sha256 + failure_category + app_commit_sha + effective_platform)`
  - 같은 `dedupe_key`가 세션에 있으면 기존 링크를 보여주고 재전송 버튼은 접는다.

원본 파일 bytes 확보:

- 단일 처리에서는 업로드 객체에서 즉시 `getvalue()` 가능
- 병렬 처리에서는 `snapshot_uploaded_file()`처럼 bytes snapshot을 만들어 result와 함께 최소 정보만 연결
- 권장 구현은 `process_settlement_files()`가 `source_sha256`, `source_size`, `source_bytes_ref` 또는 `source_payload`를 결과에 제한적으로 붙이고, zip/report 생성 후에는 불필요 보존을 피하는 것이다.

### 5단계: 운영큐 연결

repo 내부에는 별도 운영큐 DB가 아니라 ClickUp API 기반 요청 경로와 ops 스크립트/문서가 확인된다. 따라서 이 구현에서 운영큐는 ClickUp list/task를 외부 운영큐로 본다.

전용 모드 기준:

- S2 최신화 요청 태그: `s2-refresh`, `mapping-novel`
- 어댑터 실패 요청 태그: `adapter-failure`, `mapping-novel`
- ClickUp Folder: `mapping-novel 정산서 어댑터`
- ClickUp List: `긴급 실패 티켓`
- 앱 설정: `CLICKUP_ADAPTER_FAILURE_LIST_ID=<긴급 실패 티켓 list id>`
- 앱 설정: `CLICKUP_ADAPTER_FAILURE_ASSIGNEE_IDS=306885786`
- 앱 설정: `CLICKUP_ADAPTER_FAILURE_DUE_DATE_MINUTES=2`
- 기존 관리자 요청 큐와 같은 Folder/List를 쓰지 않는다.
- title prefix와 tags는 보조 분리 장치로만 둔다.

## 예시

ClickUp Task:

```text
[긴급][정산서 어댑터 실패] 네이버_일반 / 2026년 5월 네이버 일반 정산상세.xlsx
```

첨부:

```text
source_2026년 5월 네이버 일반 정산상세.xlsx
failure_report.md
failure_payload.json
```

GitHub Issue:

```text
[adapter-failure] 네이버_일반 sheet_name_mismatch: 2026년 5월 네이버 일반 정산상세.xlsx
```

GitHub Issue 본문 요약:

```markdown
## Adapter Failure

- failure_category: sheet_name_mismatch
- source_name: 2026년 5월 네이버 일반 정산상세.xlsx
- source_sha256: ...
- platform: 네이버
- s2_sales_channel: 네이버_일반
- app_commit_sha: 52f3d41
- clickup: https://app.clickup.com/t/...

## Header Candidates

| sheet | best_row | score | cells |
|---|---:|---:|---|
| 2026년 5월 네이버 일반 정산상세 | 3 | 15 | 컨텐츠 / 컨텐츠No / 공급자코드 / 작가명 / 합계 |
```

## 보안 정책

- GitHub는 민감 파일 보관소가 아니다.
- ClickUp 원본 첨부는 전용 Folder/List 안에서만 허용한다.
- 기본 구현은 `CLICKUP_ADAPTER_FAILURE_ATTACH_ORIGINAL=true`다. 정책상 중단해야 하면 Cloud Secrets에서 false로 내린다.
- 파일 hash는 SHA-256을 사용한다.
- GitHub Issue에는 상위 10행이라도 원본 금액/정산금액/개인정보가 들어갈 수 있으므로 sanitize 후 올린다.
- ClickUp/GitHub 토큰은 `.env`, OS env, Streamlit Cloud Secrets에서만 읽는다.
- 실패 payload에 secrets, access token, cookie, session id를 넣지 않는다.

## 수용 기준

구현 완료 판정:

- 실패/차단 결과 1건에서 `failure_payload.json`과 `failure_report.md`가 생성된다.
- ClickUp task가 생성되고, report 2개가 첨부된다.
- 설정이 허용할 때 원본 `.xlsx`가 ClickUp task에 첨부된다.
- GitHub Issue가 생성되고, ClickUp 링크가 포함된다.
- GitHub Issue에는 원본 파일 bytes와 원본 workbook 첨부가 없다.
- 네이버 시트명 변경/헤더 행 변경 fixture로 실패 분류가 기대대로 나온다.
- ClickUp 또는 GitHub API 실패 시 앱이 죽지 않고 fallback 다운로드를 제공한다.
- 중복 클릭 시 같은 실패를 반복 생성하지 않는다.

## 감리 체크

### 1. 이게 기존 구조와 맞는가

맞다. 현재 앱은 이미 result dict에 실패/차단 상태와 어댑터 감사 자료를 붙인다. 새 구현은 처리 파이프라인을 다시 짜는 게 아니라, 실패 result를 운영 패키지로 포장한다.

### 2. ClickUp Docs를 쓰는 게 더 나은가

아니다. 실패 티켓 원본 보관은 task attachment가 맞다. Docs는 누적 운영 매뉴얼/장애 회고/월간 실패 통계로 확장할 때 쓴다.

### 3. GitHub에 xlsx를 올려도 되는가

비추천이다. 정산서는 민감 자료일 가능성이 높다. GitHub에는 sanitized summary와 ClickUp 링크만 둔다.

### 4. 폰 알림은 확실한가

API 댓글만으로는 100% 보장할 수 없다. 실사용 알림 루트는 ClickUp 새 태스크 + assignee `306885786` + due date 현재 시각 + 2분이다. GitHub assignee/mention은 repo 변경 추적과 보조 알림으로만 본다. 모바일 알림 설정 점검은 운영 준비 체크리스트에 넣어야 한다.

### 5. 95%에서 남은 5%

- 실제 ClickUp list/status/priority 정책
- 원본 정산서 ClickUp 첨부를 계속 default on으로 둘지에 대한 운영 정책
- GitHub token 발급 방식과 repo 권한
- Streamlit Cloud에서 대용량 첨부 시 timeout/메모리 한계
- 운영자가 어떤 ClickUp board/list를 “긴급 큐”로 볼지

## 구현 순서

1. `adapter_failure_diagnostics.py`와 단위 테스트부터 만든다.
2. ClickUp task attachment 함수를 추가하고 fake session 테스트를 만든다.
3. GitHub Issue 생성 함수를 추가하고 fake session 테스트를 만든다.
4. Streamlit 결과 화면에 실패 요청 버튼을 붙인다.
5. 네이버/헤더 없음/파일명 감지 실패 fixture로 dry run한다.

다음 행동은 1단계 진단 패키지 생성 모듈부터 구현하는 것이다.

## 구현 반영 기록

2026-06-05 반영:

- 전용 ClickUp List ID: `901818576269`
- ClickUp List 이름: `긴급 실패 티켓`
- 앱 기본값: `CLICKUP_ADAPTER_FAILURE_LIST_ID=901818576269`
- 앱 기본값: `CLICKUP_ADAPTER_FAILURE_ASSIGNEE_IDS=306885786`
- 앱 기본값: `CLICKUP_ADAPTER_FAILURE_DUE_DATE_MINUTES=2`
- 앱 기본값: `CLICKUP_ADAPTER_FAILURE_ATTACH_ORIGINAL=true`
- 추가 모듈: `adapter_failure_diagnostics.py`
- 추가 모듈: `github_notifications.py`
- 확장 모듈: `clickup_notifications.py`
- UI 연결: Streamlit 처리 결과 아래 `어댑터 실패 요청` 패널
- 테스트: 신규 diagnostics/ClickUp/GitHub 테스트 추가
- 검증: ClickUp List 조회 200, 단위 테스트 전체 171개 통과
