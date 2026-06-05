# 매핑 실패 LLM/Codex 연계 아이디어 조사

작성일: 2026-06-05 KST
확신도: 95%

## 결론

도입할 만한 1순위는 `LLM 실패 진단 패널`이다.

현재 앱은 이미 매핑 실패 시 `failure_payload.json`, `failure_report.md`, 원본 xlsx ClickUp 첨부, GitHub Issue 생성을 갖고 있다. 따라서 LLM을 새 파이프라인의 중심에 두기보다, 기존 실패 진단 패키지를 입력으로 받아 다음 JSON을 생성하게 하는 보조 레이어가 가장 안전하다.

```text
매핑 실패
-> 기존 failure_payload.json 생성
-> LLM이 구조화 JSON으로 원인/수정 후보/필요 테스트/운영 조치 제안
-> ClickUp task comment 또는 앱 화면에 표시
-> 사람이 확인
-> 필요 시 GitHub Issue label로 Codex draft PR 생성
```

바로 “LLM이 원본 정산서를 보고 코드 수정 후 배포”는 비추천이다. 정산/계약/지급 자료는 민감하고, 어댑터 수정은 회귀 위험이 커서 반드시 테스트와 사람 확인이 필요하다.

## 현재 내부 구조

이미 있는 것:

- `adapter_failure_diagnostics.py`
  - 원본 workbook에서 시트명, 상위 행, 헤더 후보, best header score를 수집한다.
  - 실패 분류: `channel_detection_failed`, `header_not_found`, `sheet_name_mismatch`, `zero_parsed_rows`, `s2_filter_empty` 등.
  - `failure_payload.json`, `failure_report.md`, sanitized GitHub Issue body를 생성한다.
- `app.py`
  - 매핑 결과 중 `blocked`/`failed`만 `어댑터 실패 요청` 패널에 올린다.
  - ClickUp task, 첨부, GitHub Issue 생성 흐름이 있다.
- `clickup_notifications.py`
  - 실패 task 생성 및 attachment 업로드가 있다.
- `github_notifications.py`
  - sanitized GitHub Issue 생성 경로가 있다.

즉 LLM 연계는 “실패 정보를 새로 수집”하는 문제가 아니라 “이미 수집한 진단 패키지를 더 잘 읽고 다음 행동을 제안”하는 문제다.

## 외부 조사

### OpenAI 공식 문서

- Responses API는 구조화 JSON 출력을 지원한다. `json_schema`를 사용하면 모델 출력이 지정 schema를 따르도록 만들 수 있다.
  - https://developers.openai.com/api/reference/resources/responses/methods/create
- Codex는 IDE, CLI, 웹/모바일, SDK, CI/CD 파이프라인에서 사용할 수 있는 코딩 에이전트로 설명된다.
  - https://developers.openai.com/api/docs/guides/code-generation
- 장기 작업은 Responses `background=true`로 비동기 실행하고 polling할 수 있다.
  - https://developers.openai.com/api/docs/guides/background
- local shell/shell 계열 도구는 위험하므로 sandbox 또는 allow/deny-list가 필요하다고 문서가 명시한다.
  - https://developers.openai.com/api/docs/guides/tools-local-shell
- Agents SDK는 guardrails, human-in-the-loop, tracing, sandbox agent 개념을 제공한다.
  - https://github.com/openai/openai-agents-python
- `openai/codex-action`은 GitHub Actions에서 Codex CLI를 실행하고, sandbox/safety strategy와 권한 제어를 제공한다.
  - https://github.com/openai/codex-action

### GitHub 검색 결과

조사한 공개 사례:

- Excel/Streamlit/LLM 채팅형 분석 앱
  - https://github.com/frank-flin/excelchat-streamlit
  - https://github.com/zenklinov/Streamlit-CSV-excel-xlsx-Llama3-Ollama-PandasAI
- Codex GitHub Action
  - https://github.com/openai/codex-action
- 자동 PR 생성 action
  - https://github.com/marketplace/actions/create-pull-request

평가:

- 공개 Excel+LLM 예시는 “업로드한 엑셀에 자연어 질의”가 중심이다. 우리처럼 정산 어댑터 실패를 코드 수정 루프로 연결하는 사례와는 결이 다르다.
- GitHub/Codex Action 계열은 “이슈/PR 입력 -> repo 분석 -> 코멘트/PR 생성” 경로가 맞다.
- 따라서 현 시점 도입 후보는 PandasAI식 자유 채팅보다 “정형 실패 진단 -> 정형 제안 -> 검증된 Codex 작업” 쪽이다.

## 도입 후보 순위

### 1. LLM 실패 진단 패널

추천도: 높음
확신도: 95%

동작:

```text
failure_payload.json
-> LLM
-> adapter_failure_llm_analysis.v1 JSON
-> 앱 화면/ClickUp comment에 표시
```

출력 schema 예:

```json
{
  "schema_version": "adapter_failure_llm_analysis.v1",
  "confidence": "high|medium|low",
  "likely_root_cause": "",
  "adapter_surface": "",
  "suggested_fix_summary": "",
  "required_tests": [],
  "fixture_strategy": "",
  "unsafe_to_autofix_reasons": [],
  "human_checklist": []
}
```

장점:

- 기존 실패 패키지만 사용하면 구현 범위가 작다.
- 구조화 출력으로 UI/ClickUp/GitHub에 안정적으로 붙일 수 있다.
- 코드 변경을 자동으로 하지 않으므로 위험이 낮다.

감리:

- 원본 xlsx 전체를 LLM에 보내지 않는다.
- 금액/계좌/개인정보가 들어갈 수 있는 row snapshot은 더 강하게 sanitize한다.
- LLM 출력은 “판단 보조”이며 S2 ID/계약/정산 결정의 근거가 될 수 없다.

### 2. 실패 fixture 생성 제안

추천도: 높음
확신도: 90%

동작:

```text
failure_payload.json
-> LLM
-> 최소 재현 workbook fixture 설계
-> 테스트 코드 후보 제안
```

용도:

- 어댑터 실패를 바로 코드 수정으로 넘기기 전에, 작은 재현 fixture를 만든다.
- `header_not_found`, `sheet_name_mismatch`, `zero_parsed_rows`에 특히 유효하다.

감리:

- LLM이 만든 fixture는 실제 정산 데이터가 아니라 synthetic workbook이어야 한다.
- 테스트 통과 전에는 어댑터 수정 PR을 만들지 않는다.

### 3. GitHub Issue label 기반 Codex draft PR

추천도: 중간
확신도: 80%

동작:

```text
GitHub Issue 생성
-> 사람이 `codex:auto-draft` label 추가
-> GitHub Action에서 Codex 실행
-> 수정안 또는 draft PR 생성
```

후보 구현:

- `openai/codex-action`으로 repo 안에서 Codex 실행
- Codex prompt에는 sanitized issue body, failure category, adapter file map, 테스트 명령만 전달
- PR 생성은 `peter-evans/create-pull-request` 같은 action을 사용하거나 Codex output을 사람이 적용한다.

감리:

- GitHub Action에서 ClickUp 원본 첨부를 자동 다운로드하는 것은 1차 도입에서 제외한다.
- Codex는 read-only 또는 workspace-write sandbox에서만 돌린다.
- draft PR만 만들고 자동 merge는 금지한다.
- 테스트 실패 시 PR 생성보다 분석 comment만 남기는 쪽이 안전하다.

### 4. ClickUp 댓글 자동 요약

추천도: 중간
확신도: 85%

동작:

```text
ClickUp 실패 task 생성
-> LLM 분석 결과를 task comment로 추가
-> 담당자는 ClickUp만 보고 1차 판단
```

장점:

- 기존 운영 큐와 잘 맞는다.
- GitHub를 열지 않아도 “뭘 고쳐야 하는지”가 보인다.

감리:

- LLM comment에는 “자동 판단, 검증 필요” 문구를 붙인다.
- LLM이 계좌/금액/정산 판단을 요약하지 못하게 필드 제한한다.

### 5. 어댑터 회귀 eval 세트

추천도: 중간
확신도: 85%

동작:

```text
과거 failure_payload 모음
-> LLM 분석 prompt 변경마다 replay
-> JSON schema valid / 추천 adapter surface / unsafe reason 누락 여부 검사
```

용도:

- LLM prompt가 시간이 지나며 헛소리하는지 감시한다.
- 새 플랫폼 실패가 들어올 때 회귀 corpus가 된다.

### 6. 예비 회사컴 운영 감시자

추천도: 높음
확신도: 95% (회사컴이 업무시간에 켜져 있고 사내망/IPS/S2/ClickUp/GitHub 접근이 가능하다는 전제)

동작:

```text
예비 회사컴 작업 스케줄러
-> ClickUp 큐 polling
-> 새/미처리 카드 분류
-> 안전한 처리 루틴 실행 또는 사용자 확인 요청
```

이건 로컬 Codex thread heartbeat가 아니다. 사내망과 운영 권한이 붙은 예비 회사컴을 운영 러너로 보고, repo에 있는 스크립트나 별도 운영 스크립트가 ClickUp을 주기적으로 확인하는 구조다.

권장 체크 시각:

- 평일 09:00~18:00 정각
- 추가 체크: 10:30, 13:30, 14:30, 15:30, 16:30

카드 분류:

- `s2-refresh`: S2 최신화 실행 가능 여부 확인 후 최신화 또는 관리자 확인 요청
- `adapter-failure`: ClickUp 첨부의 `failure_payload.json`/`failure_report.md` 기준으로 진단
- `mapping-run`: 실행 기록/이슈 수 변화 확인
- `llm-codex`: LLM 진단 또는 Codex draft PR 후보

장점:

- Streamlit Cloud 앱 자체가 장기 background worker 역할을 하지 않아도 된다.
- 로컬 Windows Codex thread에 자동화를 걸지 않아도 된다.
- 회사컴이 사내망/S2 접근권을 유지하므로 S2 최신화나 내부 하네스 실행 쪽에 맞다.

감리:

- ClickUp은 운영 mirror이고 repo/test 결과가 최종 근거다.
- 회사컴은 시스템 잠자기 방지, 네트워크 복구 후 재시도, 실행 로그 보관을 먼저 설정한다.
- 화면 잠금/보호 모드는 괜찮지만, 예약 작업이 잠금 상태에서도 실행되는지 확인한다.
- 회사컴 runner는 토큰을 로그에 출력하지 않는다.
- 카드 중복 처리를 막기 위해 task id + 상태 + 마지막 처리 시각을 local state로 남긴다.
- 자동 merge, 자동 배포, 원본 xlsx의 GitHub 업로드는 금지한다.
- S2 최신화, LLM 진단, Codex draft PR은 각각 별도 explicit mode로 나눈다.

## 비추천 아이디어

### 원본 xlsx 전체를 LLM에 보내기

비추천.

이유:

- 정산 금액, 사업자/작가/계좌성 정보가 섞일 수 있다.
- 지금도 ClickUp에는 원본을 붙이지만 GitHub에는 sanitized 정보만 보낸다. LLM도 같은 원칙을 따라야 한다.

### 앱에서 바로 코드 수정/배포

비추천.

이유:

- Streamlit Cloud 앱 서버는 repo 영구 상태와 다르다.
- 어댑터 수정은 테스트, 코드리뷰, PR이 필요하다.
- 실패 원인이 S2 기준/파일명/수동 선택 문제일 수도 있는데 코드부터 바꾸면 회귀가 난다.

### PandasAI식 자유 채팅

비추천.

이유:

- 공개 사례는 일반 데이터 분석에는 맞지만, 이 repo의 핵심은 S2 계약/정산 기준과 어댑터 회귀 제어다.
- 자유 채팅은 재현성, schema adherence, 감사 가능성이 약하다.

## 권장 구현 순서

### 1단계: 문서/설계만 반영

- 이 문서 유지.
- 사이드바 `업데이트 예정`에 `매핑 실패 시 LLM 진단/Codex 연결` 항목 추가.

### 2단계: LLM 분석 모듈

추가 파일 후보:

- `adapter_failure_llm.py`
- `tests/test_adapter_failure_llm.py`

기능:

- secrets/env에서 `OPENAI_API_KEY` 읽기
- `failure_payload`를 sanitize
- Responses API 호출
- `adapter_failure_llm_analysis.v1` JSON schema 강제
- 실패 시 앱은 죽지 않고 “LLM 분석 실패”만 표시

### 3단계: UI/ClickUp 연결

앱:

- 실패 expander 안에 `LLM 진단 생성` 버튼 추가
- 결과 JSON을 사람이 읽는 요약으로 표시
- `ClickUp에 LLM 진단 댓글 추가` 옵션 추가

ClickUp:

- 기존 실패 task 생성 후 LLM comment를 후속으로 붙인다.
- comment에는 `자동 진단 / 사람 검증 필요`를 명시한다.

### 4단계: Codex draft PR

GitHub:

- label: `codex:auto-draft`
- action: `openai/codex-action`
- sandbox: 우선 `read-only` 분석 comment, 이후 `workspace-write` draft PR
- PR 생성: 별도 action 또는 Codex output 적용 후 create-pull-request

수용 기준:

- 자동 merge 없음
- tests 통과 없으면 PR 생성 없음 또는 draft만 생성
- 원본 xlsx는 GitHub runner로 가져오지 않음
- sanitized issue와 synthetic fixture만 사용

### 5단계: 회사컴 ClickUp 감시자

예비 회사컴:

- Windows 작업 스케줄러로 평일 업무시간 polling 실행
- `.env` 또는 OS keychain에서 ClickUp/OpenAI/GitHub 토큰 읽기
- 처리 상태 저장: `data/clickup_watch_state.sqlite` 또는 local JSON
- 새 카드가 없으면 조용히 종료
- 새 카드가 있으면 분류 후 안전한 next action만 수행

초기 구현 범위:

- 읽기 전용 ClickUp polling
- 새 task 요약 출력 또는 ClickUp comment만 남기기
- 자동 코드수정/자동 PR은 1차에서 제외

확장 구현:

- `adapter-failure` 카드에 LLM 진단 comment 추가
- `codex:auto-draft` label/card field가 있을 때만 Codex draft PR job 트리거
- S2 refresh 요청 카드가 있으면 회사컴에서 S2 최신화 스크립트 실행 후 결과 comment

## 최종 판단

도입할 만하다. 단, `LLM -> Codex -> PR`을 한 번에 붙이면 위험하다.

가장 좋은 첫 구현은 다음이다.

```text
매핑 실패 시 LLM 진단 생성
-> 구조화 JSON
-> 앱/ClickUp에 표시
-> 사람이 확인
-> 필요할 때만 Codex draft PR
```

이 방식이면 지금의 ClickUp/GitHub 실패 큐를 살리면서, 운영자가 매번 `failure_payload.json`을 직접 읽는 시간을 줄일 수 있다.

감시 주체는 로컬 Codex thread heartbeat가 아니라 사내망 접근 가능한 예비 회사컴 runner가 맞다. 이 repo에는 그 runner가 실행할 polling/분류/처리 스크립트를 넣고, 회사컴의 Windows 작업 스케줄러가 정해진 시각에 호출하는 구조로 간다.
