# mapping-novel 운영/조작 capability map

기준일: 2026-05-19

## 결론

`mapping-novel`만 포크해서 넘기면 현재는 **S2/IPS 조회형 최신화, 정산 매핑 운영, 그리고 SSOT에서 흡수한 운영 스크립트 코드**까지 같이 넘길 수 있다.

2026-05-19에 아래 조작 레이어를 `ops/` 아래로 흡수했다.

- IPS live write: 콘텐츠명 수정, 사용안함 승격/rename, 판매채널 추가, 신규 콘텐츠 생성
- KIPM 더미 계약 생성
- admin 저작권/출판사 정보 크롤링
- account canonical/decision queue 생성
- account ↔ IPS crosswalk 작업 큐 생성

단, 이것은 **코드 흡수**다. 실제 credential, 과거 raw/stage/canonical/export 데이터, live write 검증 결과는 repo에 넣지 않았다.

## 흡수 완료 위치

```text
ops/
  scripts/
    ips/
    build_work_index.py
    ips_title_rules.py
    work_cid_utils.py
    ips_sales_channel_harness.py
    ips_sales_channel_adder.py
    ips_sales_channel_pipeline.py
    google_sheet_generated_id_uploader.py
    chrome_debug_session.py
    rename_ips_content_titles.py
    rename_ips_content_titles_api.py
    create_kipm_content_contract.py
    create_kipm_dummy_contract.py
  SIAAN Project/
    .env.example
    admin_login.py
    account_login.py
  SIAANE_v2/
    build_manager_author_ssot.py
    account/
    crosswalk/
    ips_live_lookup.py
    crawl_admin_copyright_info.py
    audit_ips_admin_publisher.py
    create_natoya_missing_cids_api.py
  더미+계약서.pdf
  requirements-ops.txt
```

운영자는 `ops\SIAAN Project\.env.example`을 복사해 `.env`를 만들고, `ops\README.md`의 순서대로 read-only probe부터 확인한다.

## 현재 mapping-novel 단독 가능

### S2

가능:
- S2 지급정산 기준 최신화
- S2 정산정보누락/청구정산 guard 최신화
- S2 판매채널콘텐츠 lookup 최신화
- Streamlit 앱에서 정산서 매핑
- PD 작업지시/행별 종합 리포트 생성

진입점:

```powershell
python scripts\refresh_kiss_payment_settlement.py --env-file .env --mode full-replace --lookup-only --page-size 1000000 --content-style-code 102
python scripts\refresh_s2_reference_guards.py --env-file .env --page-size 1000000 --content-style-code 102
python scripts\refresh_s2_sales_channel_contents.py --env-file .env --content-style-code 102
```

배치:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_daily_s2_refresh.ps1 -RepoRoot <mapping-novel 경로> -Python <python.exe 경로>
```

### IPS 조회/보조자료 최신화

가능:
- KIPM 콘텐츠 목록 API 조회
- `data/all_contents.xlsx`
- `data/kidari_contents.xlsx`
- `data/kidari_webtoon.xlsx`

진입점:

```powershell
python scripts\refresh_ips_auxiliary_data.py --env-file .env
```

확인된 최신 수치:
- 전체 유지 콘텐츠: 62,867
- 소설: 29,827
- 웹툰: 32,636

### IPS live 작업

가능 코드:
- `ops\scripts\ips_sales_channel_harness.py`
- `ops\scripts\ips_sales_channel_adder.py`
- `ops\scripts\ips_sales_channel_pipeline.py`
- `ops\scripts\rename_ips_content_titles_api.py`
- `ops\scripts\create_kipm_content_contract.py`
- `ops\scripts\create_kipm_dummy_contract.py`
- `ops\SIAANE_v2\ips_live_lookup.py`
- `ops\SIAANE_v2\apply_*_live.py`

주의:
- live write는 반드시 dry-run/lookup 후 소량 실행한다.
- `ops\SIAANE_v2\create_natoya_missing_cids_api.py`는 흡수 후 보정해서 기본 preview만 수행하고, `--write`를 줘야 live POST/계약 생성으로 들어간다.

## 흡수 전 원본 위치

아래는 흡수 전 원본 repo 안의 상대 위치다. 추후 diff나 원본 확인이 필요할 때만 참조한다.

### IPS live write 본체 원본

SSOT 쪽 주요 진입점:

```text
scripts\ips\*
scripts\ips_sales_channel_harness.py
scripts\ips_sales_channel_adder.py
scripts\rename_ips_content_titles_api.py
scripts\create_kipm_content_contract.py
scripts\create_kipm_dummy_contract.py
```

SIAANE_v2 쪽 사용 예:

```text
SIAANE_v2\ips_live_lookup.py
SIAANE_v2\apply_cid_redirect_disabled_rename_live.py
SIAANE_v2\apply_bukholic_ips_rename_live.py
SIAANE_v2\create_natoya_missing_cids_api.py
```

대표 흐름:

1. `IPSHarness(get_site("kipm"))`로 KIPM 로그인
2. `axios_call(page, method, path, payload)`로 KIPM API 호출
3. dry-run 산출물 생성
4. write 실행
5. verify 실행

### admin 원본

SSOT 쪽 진입점:

```text
SIAANE_v2\crawl_admin_copyright_info.py
SIAANE_v2\audit_ips_admin_publisher.py
```

현재 mapping-novel에는 `ops\SIAANE_v2\crawl_admin_copyright_info.py`, `ops\SIAANE_v2\audit_ips_admin_publisher.py`, `ops\SIAAN Project\admin_login.py`가 흡수되어 있다.

### account 원본

SSOT 쪽 진입점:

```text
SIAANE_v2\account\build_account_rights_canonical.py
SIAANE_v2\account\build_account_observation_bundle.py
SIAANE_v2\account\build_account_name_review_queue.py
SIAANE_v2\account\build_account_decision_queue.py
SIAANE_v2\account\build_account_work_gap_queue.py
```

account README 핵심:
- 먼저 account 내부 canonical을 만든다.
- 그 다음 account ↔ IPS crosswalk를 만든다.
- IPS rename/create로 바로 가지 않는다.

### account ↔ IPS crosswalk 원본

SSOT 쪽 진입점:

```text
SIAANE_v2\crosswalk\build_account_ips_cid_seed.py
SIAANE_v2\crosswalk\build_account_ips_action_queue.py
SIAANE_v2\crosswalk\build_ips_create_request.py
SIAANE_v2\crosswalk\build_ips_apply_work_order.py
SIAANE_v2\crosswalk\build_ips_rename_apply_pack.py
```

## 구글시트 땜방 운영

대상:

```text
https://docs.google.com/spreadsheets/d/1jG0Q6LKzJ_q2VqdqtoDHSEwl8hfOEUrxRuxXq7KSazY/edit?gid=1569459807#gid=1569459807
```

확정 헤더:

```text
S2 판매채널
정제_상품명
정산서_대표콘텐츠명
S2_미매핑상세사유
생성 ID
담당자(없을 시 공란)
비고
```

이 시트는 당분간 append/수기 입력용 땜방으로 둔다.
자동 쓰기를 붙일 때도 기존 행 수정 금지, append-only, 중복 skip 규칙이 필요하다.

## 포크 인수인계 체크리스트

남이 `mapping-novel`만 fork해서 조작까지 하려면 아래는 이미 repo 안에 들어와 있다.

1. 공용 KIPM/IPS 하네스
   - `ops\scripts\ips\`
   - `ips_sales_channel_harness.py`
   - `ips_sales_channel_adder.py`
   - `rename_ips_content_titles_api.py`

2. KIPM create/contract
   - `create_kipm_content_contract.py`
   - `create_kipm_dummy_contract.py`
   - `더미+계약서.pdf`

3. SIAANE_v2 조작 레시피
   - `ips_live_lookup.py`
   - `create_natoya_missing_cids_api.py`
   - `apply_cid_redirect_disabled_rename_live.py`
   - `audit_ips_admin_publisher.py`
   - `crawl_admin_copyright_info.py`
   - `account\*.py`
   - `crosswalk\build_*ips*.py`

4. 의존성
   - `python-dotenv`
   - `playwright`
   - `selenium`
   - `pywin32` on Windows

추가로 새 PC에서 1회 실행:

```powershell
pip install -r requirements.txt -r ops\requirements-ops.txt
python -m playwright install chromium
```

## 운영 판단

이제 코드만 놓고 보면 다른 repo를 빌릴 필요는 없다.

다만 장기적으로 남에게 넘길 거면 `ops`를 아래처럼 재정리하는 편이 낫다.

```text
ops/
  kipm/
    auth.py
    ips_content.py
    ips_sales_channel.py
    ips_create.py
    dummy_contract.py
  admin/
  account/
  google_sheet_queue.py
```

이렇게 나누면 `SIAANE_v2` 없이도 fork 단독 운영이 가능해진다.
