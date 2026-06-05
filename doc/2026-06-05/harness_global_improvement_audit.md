# 하네스 전역 감리 및 개선안

작성일: 2026-06-05

확신도: 95%

## 결론

전역 하네스는 2026-06-04 감리 이후 핵심 쓰기 경로가 많이 안전해졌지만, 아직 공통 safety contract가 없다. 그래서 같은 의미의 `계약 ID`, `지급정산 존재`, `시트 입력 가능`, `검증 완료`가 스크립트마다 다르게 해석될 수 있다.

가장 큰 개선점은 세 가지다.

1. 계약서 생성 함수 내부에서 account RS 근거 검증을 강제해야 한다.
2. 판매채널콘텐츠ID를 시트에 입력하기 전, `통합계약ID != 0` 근거를 공통 게이트로 통과시켜야 한다.
3. output/debug 산출물은 기본적으로 커밋 대상에서 차단하고, 필요한 결과만 redaction 후 doc/output receipt로 승격해야 한다.

이번 감리는 코드/문서/테스트를 정적 조사했다. 라이브 IPS/S2 쓰기는 실행하지 않았다.

## 구현 결과

2026-06-05 구현 완료.

- 계약서 생성 guard:
  - `create_dummy_contract()` 함수 내부에서 account RS guard를 강제한다.
  - `create_kipm_content_contract.py`도 account 저작권코드/정산명/account RS율을 받아 dummy contract 단계로 전달한다.
- 판매채널/시트 입력 guard:
  - `ops/scripts/ips_safety_contract.py`로 `next_action`, 계약 ID, 지급정산 검증 상태, S2 검증 상태를 공통 판정한다.
  - Sheet uploader는 이제 숫자 ID만으로 통과하지 않는다. `통합계약ID != 0` 근거와 검증 상태가 없으면 blocked row로 남긴다.
  - `payment_setup_id`만 있는 evidence는 sheet upload에서 차단된다.
  - API 판매채널 추가도 기본적으로 `cntrId=0`이면 중단한다. 예외는 `--allow-payment-setup-only`와 사유가 있을 때만 가능하다.
  - 검증 없는 숫자 ID의 시트 입력 예외도 `--allow-unverified-id`와 사유가 같이 있어야만 열린다.
- S2 검증:
  - `ops/scripts/s2_sales_channel_id_verifier.py`를 추가했다.
  - S2 지급정산 lookup에서 `통합계약ID != 0`인 판매채널콘텐츠ID만 `contract_nonzero`로 인정한다.
  - pipeline은 upload 직전에 S2 verifier 결과 파일을 만들고, 최종 uploader에는 검증 후 CSV를 넘긴다.
- 산출물/보안:
  - runtime output/cookies/debug 산출물을 `.gitignore`에 추가했다.
  - browser/admin/account/debug JSON 산출물에 redaction을 적용했다.
  - `ops/scripts/secret_redaction.py`와 `scripts/check_sensitive_artifacts.py`를 추가했다.
- SIAANE local mutator:
  - account/crosswalk apply 계열을 `--dry-run` 기본, `--write` 명시 쓰기로 바꿨다.
  - live write 시 backup과 receipt를 남긴다.
- S2 최신화:
  - `scripts/refresh_s2_all.py`를 추가해 payment settlement, sales channel contents, reference guards를 같은 epoch manifest로 묶는다.

검증 결과:

- `python -m pytest -q`: 194 passed, 17 skipped, 41 subtests passed.
- 변경 파일 `py_compile`: 33 files compiled.
- `python scripts/check_sensitive_artifacts.py`: `sensitive_artifact_scan=ok`.
- 라이브 IPS/S2/Google Sheet 쓰기는 실행하지 않았다.

## 조사 범위

- `ops/scripts/ips/core/*`: Playwright/auth/browser 공통 하네스
- `ops/scripts/ips_sales_channel_harness.py`: IPS detail/판매채널 lookup
- `ops/scripts/ips_sales_channel_adder.py`: IPS 판매채널 추가
- `ops/scripts/ips_sales_channel_pipeline.py`: lookup -> add -> Google Sheet upload orchestration
- `ops/scripts/google_sheet_generated_id_uploader.py`: Google Sheet E열 입력
- `ops/scripts/create_kipm_dummy_contract.py`: KIPM 계약서 생성
- `ops/scripts/create_kipm_content_contract.py`: KIPM 콘텐츠 생성 + 계약서 연결
- `ops/scripts/rename_ips_content_titles_api.py`, `probe_ips_content_detail.py`, `collect_ips_contract_links.py`
- `scripts/triage_generated_id_gaps.py`, `scripts/audit_sales_channel_settlement_gap.py`
- `kiss_payment_settlement.py`, `s2_reference_guards.py`, `scripts/refresh_*`
- `ops/SIAAN Project/account_login.py`, `ops/SIAAN Project/admin_login.py`
- `ops/SIAANE_v2/account/*`, `ops/SIAANE_v2/crosswalk/*`
- 관련 테스트: `tests/test_*`
- 선행 감리 문서: `doc/2026-06-04/harness_global_safety_audit.md`

## 이미 괜찮아진 부분

- S2 지급정산 기준은 상당수 경로에서 `통합계약ID != 0`으로 필터링된다.
  - `kiss_payment_settlement.py`는 `CONTRACT_ID_COLUMN = "통합계약ID"`를 표준화하고, `to_s2_lookup()`에서 nonzero contract ID만 남긴다.
  - `triage_generated_id_gaps.py`는 payment lookup 로드 시 계약 ID 0 행을 제거한다.
  - `audit_sales_channel_settlement_gap.py`도 S2 settlement lookup에서 계약 ID nonzero 행만 기준으로 삼는다.
  - 테스트도 `test_generated_id_gap_triage.py`, `test_kiss_payment_settlement.py`, `test_settlement_status_gate.py`에서 이 방향을 확인한다.
- 판매채널 추가 하네스는 이전 사고 지점이었던 동명이채널 문제를 많이 막았다.
  - `ips_sales_channel_adder.py`는 `cprCd` 맥락으로 채널을 고르고, 같은 이름의 채널이 복수인데 회사 코드가 없으면 자동 선택을 중단한다.
  - 저장 후 `schnId`, `cntrId` 기준으로 재조회 검증을 한다.
- Google Sheet uploader는 숫자가 아닌 검토 메모가 E열에 들어가는 사고를 막는다.
  - `google_sheet_generated_id_uploader.py`의 `is_safe_sales_channel_content_id()`는 양의 정수만 허용한다.
  - 위험한 UI 쓰기 경로는 기본 차단이고, `--allow-dangerous-ui-write` 없이는 live write가 실패한다.
- S2 지급정산 본체 refresh는 전체 교체, lock, history 기록이 있다.

## 주요 발견

### P0. 계약서 생성 account RS guard가 함수 내부에서 강제되지 않는다

근거:

- `create_kipm_dummy_contract.py:1494`에 `validate_account_rs_guard()`가 있다.
- 하지만 `create_dummy_contract()` 시작부(`create_kipm_dummy_contract.py:1561`)에는 이 검증 호출이 없다.
- 검증은 CLI `main()`에서만 호출된다(`create_kipm_dummy_contract.py:1799`).
- `create_kipm_content_contract.py`는 `create_dummy_contract()`를 함수로 직접 호출한다(`create_kipm_content_contract.py:795`).
- `ContentContractSpec`에는 `rs_rate`만 있고 account 저작권코드/정산명/account RS율 필드가 없다(`create_kipm_content_contract.py:76-93`).

위험:

- 사용자가 콘텐츠 생성 + 계약 연결 래퍼를 쓰면, account에서 확인한 저작권코드/RS 근거 없이 계약서가 들어갈 수 있다.
- 현재 테스트는 `validate_account_rs_guard()` 자체만 검증한다. "모든 계약 생성 경로에서 guard가 반드시 실행되는가"는 테스트하지 않는다.

개선안:

- `create_dummy_contract()` 첫 줄에서 `validate_account_rs_guard(spec)`를 호출한다.
- 정말 예외가 필요하면 `unsafe_skip_account_rs_guard` 같은 내부 전용 플래그를 두되, CLI에는 노출하지 않는다. 사용할 때는 reason과 run manifest 기록을 필수로 한다.
- `create_kipm_content_contract.py`에 다음 인자를 추가한다.
  - `--account-rights-code`
  - `--account-rights-name`
  - `--account-rs-rate`
  - `--allow-zero-rs`
- `ContentContractSpec`와 report payload에도 account evidence를 남긴다.
- 테스트 추가:
  - `create_dummy_contract()`가 guard 없이 호출되면 실패
  - `create_kipm_content_contract.build_spec()`가 account evidence를 전달
  - write mode에서 account evidence 누락 시 계약 단계 진입 전 실패

### P1. `payment_setup_id`만 있는 경로가 시트 입력 가능 상태로 승격될 수 있다

근거:

- `ips_sales_channel_adder.py`는 `source_payment_setup_id` 또는 `source_platform`을 명시하면 계약 ID 0 정산 템플릿도 선택할 수 있다.
- `add_platform_via_api()`는 이 경우 `settlement_source_row_status = "payment_setup_linked"`를 반환한다.
- 이후 `process_rows()`는 판매채널콘텐츠ID가 나오면 `next_action = "paste_sales_channel_content_id"`로 바꾼다.

위험:

- 이번 기준은 "지급정산 유무 = 통합 계약 ID가 0이 아닌 것"이다.
- 그러면 `payment_setup_id`만 있는 상태는 "판매채널 추가 참고 정보"일 수는 있어도, E열 입력 승인 근거가 되면 안 된다.

개선안:

- `source_contract_id <= 0`인 addition 결과는 기본적으로 `next_action = "connect_contract_before_sheet"` 또는 `check_source_contract_id`로 남긴다.
- `settlement_source_row_status = payment_setup_linked`인 row는 `sales_channel_content_id`가 있어도 uploader가 거부한다.
- `source_payment_setup_id` 경로는 수사/진단용으로 유지하되, live add 자체도 `--allow-payment-setup-only --payment-setup-only-reason <text>` 없이는 차단한다.
- 테스트 추가:
  - `payment_setup_linked` 결과는 paste action으로 승격되지 않는다.
  - uploader가 `settlement_verified_contract_id` 0/blank row를 거부한다.

### P1. Sheet uploader의 최종 게이트가 너무 얇다

근거:

- `google_sheet_generated_id_uploader.py:115`의 `build_upload_rows()`는 `next_action`, row id, positive numeric ID만 본다.
- `settlement_verification_status`, `settlement_verified_contract_id`, S2 lookup verification status를 요구하지 않는다.

위험:

- 앞 단계 CSV가 오래됐거나 수동 편집됐거나 다른 스크립트에서 나온 경우, 숫자 ID와 `paste_sales_channel_content_id`만 맞추면 E열 입력 후보가 된다.
- "IPS에 판매채널콘텐츠가 있음"과 "S2 지급정산 기준이 있음"이 섞일 수 있다.

개선안:

- `ops/scripts/ips_safety_contract.py`를 만들고 uploader가 다음 공통 조건을 통과한 row만 받게 한다.
  - `sales_channel_content_id`: positive numeric
  - `next_action`: `paste_sales_channel_content_id`
  - `settlement_verified_contract_id` 또는 `source_contract_id`: positive numeric
  - `settlement_verification_status`: `detail_platform_list` 또는 `settlement_template`
  - 새 S2 verifier를 통과한 경우 `s2_payment_contract_status = contract_nonzero`
- 위 조건을 만족하지 않는 row는 `blocked_before_sheet_upload`로 별도 report에 남긴다.
- 정말 예외 입력이 필요하면 `--allow-unverified-id --unverified-id-reason <text>`처럼 reason 필수 flag로 분리한다.

### P1. 공통 status/action enum과 run manifest가 없다

근거:

- `next_action`, `addition_status`, `lookup_status`, `settlement_verification_status`, `contract_gate`가 파일마다 문자열로 흩어져 있다.
- 선행 감리도 `ops/scripts/ips_safety_contract.py` 도입을 권고했다.

위험:

- `paste_sales_channel_content_id`가 어느 단계에서는 "IPS detail에서 기존 플랫폼 발견", 다른 단계에서는 "계약 연결 검증 완료", 또 다른 단계에서는 "그냥 숫자 ID 있음"처럼 해석될 수 있다.
- 사람이 CSV를 합치거나 재사용할 때 단계별 의미가 사라진다.

개선안:

- `ops/scripts/ips_safety_contract.py`
  - `SafeStatus`, `NextAction`, `EvidenceStatus` 상수
  - `is_positive_numeric_id()`
  - `is_nonzero_contract_id()`
  - `is_sheet_uploadable_sales_channel_row(row)`
  - `classify_payment_evidence(row)`
  - `WriteRunManifest`
- 모든 write 계열 output에 다음 필드를 공통으로 넣는다.
  - `run_id`
  - `script`
  - `mode`
  - `source_input_path`
  - `source_input_sha256`
  - `s2_lookup_path`
  - `s2_lookup_sha256`
  - `s2_refresh_history_id` 또는 최신화 timestamp
  - `live_write`
  - `operator_note`
  - `preflight_status`
  - `postwrite_verification_status`

### P1. output/debug 산출물 보안 경계가 약하다

근거:

- `.gitignore`는 `igignore/`, 루트 CSV/XLSX, 일부 data cache만 막는다.
- `output/`, `ops/SIAAN Project/output/`는 전역 ignore가 아니다.
- `admin_login.py`는 성공/실패 artifact에 HTML, screenshot, cookies JSON을 저장한다(`admin_login.py:202`, `admin_login.py:206-208`).
- `probe_ips_content_detail.py`는 `--capture-network`일 때 response body 전체를 JSON으로 남긴다.
- `rename_ips_content_titles_api.py`는 PUT payload 전체를 `ops/SIAAN Project/output/ips_api_debug/put_payload_<cid>.json`에 저장한다.

위험:

- API 응답, cookie, token, 개인정보, 계약/계좌/거래처 정보가 runtime output에 남고, 이후 `git add` 범위에 섞일 수 있다.
- 실제로 최근 output 산출물 커밋 과정에서 push protection이 token 문자열을 잡은 전례가 있다.

개선안:

- `.gitignore`에 runtime output 차단을 추가한다.
  - `/output/`
  - `ops/SIAAN Project/output/`
  - `**/cookies.json`
  - `**/*token*.json`
  - `**/*debug*/`
- 보존해야 하는 감사 결과는 `doc/<date>/` 또는 `reports/<date>/`에 redaction 후 승격한다.
- `ops/scripts/secret_redaction.py` 추가:
  - key 기준 redaction: `token`, `authorization`, `cookie`, `password`, `secret`, `api_key`, `accessToken`
  - 값 기준 redaction: JWT, bearer token, ClickUp/Atlassian/GitHub token pattern
- `scripts/check_sensitive_artifacts.py` 추가 후 pre-commit/pre-push 전에 실행한다.
- browser failure artifact의 `page.html` 저장은 기본 off, `--capture-html` 또는 failure debug mode에서만 켠다.

### P2. Pipeline live upload가 fail-closed인데 UX가 헷갈린다

근거:

- `ips_sales_channel_pipeline.py`는 `--write`가 live add/upload라고 설명한다.
- 하지만 uploader는 `allow_dangerous_ui_write`가 없으면 live write를 차단한다(`google_sheet_generated_id_uploader.py:495`).
- pipeline의 `upload_args`에는 `allow_dangerous_ui_write`가 없다(`ips_sales_channel_pipeline.py:228-249`).

판정:

- 안전 측면에서는 fail-closed라 나쁘지 않다.
- 운영 측면에서는 `--write`만 줬는데 add는 되고 sheet upload는 막히는 식으로 헷갈릴 수 있다.

개선안:

- 단기: pipeline에 `--allow-dangerous-ui-write`를 노출하되 help에 "백업본에서만"을 명시한다.
- 권장: Google Sheets API batch update writer로 교체한다. UI keyboard/CDP writer는 legacy fallback으로 격하한다.

### P2. SIAANE_v2 local-state mutator가 backup 없이 latest CSV를 덮어쓴다

근거:

- `ops/SIAANE_v2/account/apply_*.py`와 `ops/SIAANE_v2/crosswalk/apply_*.py`가 `latest__*.csv`를 직접 읽고 직접 덮어쓴다.
- 예: `apply_account_cid_split_auto_approval.py`, `apply_account_cid_split_bulk_approval.py`, `apply_account_name_review_bulk_approval.py`.

위험:

- 라이브 IPS/S2 쓰기는 아니지만 account/admin 판단 자료가 바뀐다.
- 잘못 실행하면 되돌릴 기준이 없다.

개선안:

- local mutator 공통 helper 추가:
  - 실행 전 `exports/.backup/<timestamp>/...csv` 백업
  - `--dry-run` 기본
  - `--write` 명시 시만 덮어쓰기
  - 변경 row count, before/after hash, touched columns를 JSON receipt로 기록

### P2. S2 보조 lookup refresh가 본체 refresh epoch와 느슨하게 묶여 있다

근거:

- `refresh_kiss_payment_settlement.py`는 lock/history가 있다.
- `refresh_s2_sales_channel_contents.py`, `refresh_s2_reference_guards.py`는 각각 summary를 만들지만 본체 refresh history id와 하나의 manifest로 묶이지 않는다.

위험:

- 지급정산 lookup, 판매채널콘텐츠 lookup, missing/billing guard가 서로 다른 시점 데이터일 수 있다.
- 하네스가 "현재 S2 기준"을 판단할 때 어떤 파일 조합인지 자동으로 알 수 없다.

개선안:

- `scripts/refresh_s2_all.py` 추가:
  - payment settlement
  - sales channel contents
  - reference guards
  - history/manifest 단일화
- 각 lookup CSV 옆에 `.meta.json` 생성:
  - source API
  - started/finished
  - row count
  - sha256
  - refresh_history_id
  - contract ID column availability
- harness/pipeline은 `.meta.json`의 freshness와 같은 epoch 여부를 확인한다.

## 적대적 감리

### 시나리오 A: 계약서 래퍼가 account RS 근거 없이 계약을 만든다

현재 결과: 가능성이 있다.

- CLI dummy contract는 guard가 있지만 함수 내부 guard가 없다.
- content contract wrapper는 account evidence 필드 없이 함수 호출한다.

필요 조치: P0.

### 시나리오 B: 통합계약ID 0인 지급설정만 보고 판매채널콘텐츠ID가 E열로 간다

현재 결과: 가능성이 있다.

- `source_payment_setup_id` 경로가 있고, 최종 uploader는 contract ID nonzero를 요구하지 않는다.

필요 조치: P1.

### 시나리오 C: 동명이채널 `밀리의 서재`처럼 wrong schnId가 들어간다

현재 결과: 핵심 adder 경로에서는 완화됨.

- company code context와 expected channel id 검증이 있다.
- 다만 drift check가 별도 명령으로 중앙화되어 있지 않아, 새 스크립트가 channel name만 쓰면 재발 가능하다.

필요 조치: P1 공통 channel identity helper.

### 시나리오 D: 검토 메모가 E열 ID로 들어간다

현재 결과: 핵심 uploader에서는 차단됨.

- positive numeric ID guard가 있다.

남은 위험: 검증 상태 없는 숫자 ID는 통과한다.

필요 조치: P1 uploadable row contract.

### 시나리오 E: output에 token/cookie가 남고 커밋된다

현재 결과: 가능성이 높다.

- output ignore가 약하고, cookie/body/payload 저장 경로가 있다.
- push protection이 마지막 방어선이 되면 이미 늦다.

필요 조치: P1 artifact quarantine/redaction.

## 구현 순서

### 0단계: 즉시 차단

1. `create_dummy_contract()` 내부에서 `validate_account_rs_guard()` 호출.
2. `create_kipm_content_contract.py`에 account evidence 인자 추가.
3. `payment_setup_linked` addition은 sheet paste action으로 승격 금지.
4. uploader가 `settlement_verified_contract_id > 0` 또는 S2 nonzero contract verification 없으면 차단.
5. `.gitignore`에 runtime output 차단 추가.
6. 민감 산출물 scanner 추가.

### 1단계: 공통 safety contract

1. `ops/scripts/ips_safety_contract.py` 생성.
2. status/action enum과 ID validator 중앙화.
3. sales-channel adder, pipeline, uploader, safe backfill이 같은 helper를 사용하게 변경.
4. 테스트를 helper 기준으로 재배치.

### 2단계: S2 verification gate

1. `ops/scripts/s2_sales_channel_id_verifier.py` 추가.
2. S2 payment lookup의 `통합계약ID != 0`과 현재 판매채널/콘텐츠명 일치를 확인.
3. pipeline이 upload 전에 verifier 결과를 merge.
4. verifier 실패 row는 sheet upload에서 제외하고 review CSV로 분리.

### 3단계: runtime output hygiene

1. artifact redaction 모듈 도입.
2. `probe_ips_content_detail.py`, `rename_ips_content_titles_api.py`, browser failure artifact에 redaction 적용.
3. `doc/<date>/`에 올라가는 산출물만 curated output으로 취급.

### 4단계: local-state mutator 정리

1. SIAANE_v2 `apply_*.py`에 `--dry-run` 기본, `--write` 필수 적용.
2. 덮어쓰기 전 자동 backup.
3. receipt JSON 생성.

## 구현 후 확인해야 할 테스트

- `python -m pytest tests/test_kipm_dummy_contract_channel.py`
- `python -m pytest tests/test_ips_sales_channel_adder.py`
- `python -m pytest tests/test_google_sheet_generated_id_uploader.py`
- `python -m pytest tests/test_ips_sales_channel_pipeline.py`
- 신규:
  - `tests/test_kipm_content_contract_guard.py`
  - `tests/test_ips_safety_contract.py`
  - `tests/test_sensitive_artifact_redaction.py`

## 최종 판정

95% 확신으로, 지금 가장 먼저 고칠 곳은 계약 생성 guard와 Sheet upload gate다.

`S2에 있음`은 더 이상 지급정산 존재가 아니다. 앞으로 자동 입력 가능 조건은 `판매채널콘텐츠ID 양수 + 통합계약ID nonzero + 검증 상태 passed`로 고정해야 한다.
