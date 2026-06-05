# ClickUp 매핑 실행 기록 첨부 감리

작성일: 2026-06-05

확신도: 95%

## 결론

매핑 실행 결과를 ClickUp task에 남기는 기능은 유효하다. 다만 원본 정산서 xlsx에는 계약/정산/거래처성 데이터가 포함될 수 있으므로, 매 실행마다 원본을 자동 첨부하는 방식은 위험하다.

구현 기준은 다음으로 정한다.

1. `adapter-failure` 큐와 분리해 `mapping-run` 태그의 실행 기록 task를 만든다.
2. 기본 첨부는 실행 payload JSON, batch summary CSV, PD 작업지시 CSV, 전체 행별매핑 CSV, 결과 ZIP이다.
3. 원본 xlsx 첨부는 사용자가 `원본 xlsx 첨부`를 켠 경우에만 수행한다.
4. 같은 run signature는 세션에서 중복 생성하지 않는다.
5. 개별 첨부가 40MB를 넘으면 task는 만들되 해당 첨부는 제외하고 UI에 표시한다.

## 조사 결과

- 기존 `clickup_notifications.py`는 S2 최신화 요청과 어댑터 실패 task를 지원한다.
- `upload_task_attachment()`가 이미 ClickUp task attachment API를 감싸고 있다.
- `app.py`는 실패/차단 결과에 한해 `_source_bytes`를 보존하고, 성공 결과에서는 원본 bytes를 제거한다.
- 어댑터 실패 패널은 원본 xlsx를 ClickUp에는 붙일 수 있지만 GitHub에는 붙이지 않는 정책을 이미 따른다.

## 적대적 감리

### A. 모든 원본 xlsx 자동 첨부

위험하다. 정상 매핑 파일까지 계속 ClickUp에 남으면 저장량과 민감정보 노출 범위가 커진다.

대응: 원본 첨부는 기본 off.

### B. 성공 결과에서 `_source_bytes`를 계속 보존

메모리 사용량이 커지고 Streamlit 세션이 불안정해질 수 있다.

대응: 성공 결과의 기존 메모리 최적화는 유지하고, 원본 첨부를 선택했을 때 현재 업로드 위젯의 파일 bytes를 다시 읽는다.

### C. 결과만 남기고 입력 파일명이 빠짐

나중에 어떤 정산서 묶음이었는지 추적하기 어렵다.

대응: task markdown과 payload JSON에 입력 파일 목록, run id, status counts, S2 기준 상태, ZIP SHA-256을 남긴다.

### D. 동일 실행을 버튼 중복 클릭으로 여러 task 생성

ClickUp task가 불필요하게 늘어난다.

대응: run signature 기반 `mapping-run-<sha>`를 만들고 session state에 생성 결과를 기록한다.

## 구현 결과

- `clickup_notifications.py`
  - `build_mapping_run_clickup_config()`
  - `build_mapping_run_task_payload()`
  - `create_mapping_run_task()`
- `app.py`
  - 실행 전 `매핑 실행 후 ClickUp 기록 생성` 옵션 추가
  - 결과 화면에 `ClickUp 실행 기록` 패널 추가
  - 결과 ZIP 기본 첨부
  - 원본 xlsx 선택 첨부
  - run signature 기반 중복 방지
- `.env.example`
  - `CLICKUP_MAPPING_RUN_*` 설정 추가
- 테스트
  - mapping-run config normalization
  - mapping-run payload shape
  - mapping-run task attachment upload
