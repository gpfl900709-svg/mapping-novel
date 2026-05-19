# ops 흡수 적대적 감리

기준일: 2026-05-19

## 결론

조건부 통과.

`ops/`는 이제 SSOT/SIAANE 운영 코드를 포크 인수인계용으로 담고 있고, 기계적 import 누락/문법 오류/대표 진입점 help 실패는 해소했다.

다만 live 시스템을 실제로 쓰는 코드는 여전히 운영자 검토가 필요하다. 새 PC에서는 credential과 raw/stage/canonical/export 입력 데이터를 별도로 준비한 뒤 read-only probe부터 시작한다.

## 3회 감리 구성

1. 포크/경로/secret 감리
   - 개인 PC 절대경로, 원본 repo 경로, credential literal, ignore 정책을 확인했다.

2. 실행 진입점/무인 실행 사고 감리
   - `__main__` 진입점, `--help`, live mutation 패턴, dry-run/write guard를 확인했다.

3. 운영 데이터 재생성/누락 체인 감리
   - 새 PC에서 필요한 local input, generated output, account/crosswalk 선행 산출물 체인을 확인했다.

## 감리에서 잡아 고친 것

1. `match_account_cp_bank_info.py`가 `account_login.py`를 요구했지만 누락되어 있었다.
   - 조치: `ops/SIAAN Project/account_login.py` 흡수.

2. account 관측 파이프라인의 선행 산출물 `manager_author_ssot.csv`를 만드는 스크립트가 누락되어 있었다.
   - 조치: `ops/SIAANE_v2/build_manager_author_ssot.py` 흡수.
   - 추가 조치: `--help`, `--manager` CLI를 붙여 새 PC에서 바로 실행되어 파일 누락으로 터지는 UX를 줄였다.

3. `create_natoya_missing_cids_api.py`가 실행 즉시 live POST/더미계약 생성으로 들어가는 옛 recipe였다.
   - 조치: 기본 실행은 preview JSON만 쓰게 변경.
   - live 실행은 `--write`가 있을 때만 가능.

4. 흡수 문서에 원본 PC 절대 링크가 일부 남아 있었다.
   - 조치: `ops/SIAANE_v2/README.md` 링크를 상대 경로로 수정.
   - 조치: `ops/SIAANE_v2/docs/current_context.md`에 참고용 판단 로그라는 경고를 추가하고 개인 PC 절대경로 한 줄을 상대 설명으로 치환.

5. `.env.example`이 ignore될 위험이 있었다.
   - 조치: `ops/.gitignore`에 `.env.example` 예외 추가.
   - 확인: 실제 `.env`는 ignored, `.env.example`은 git status에 표시됨.

6. 2회차 감리에서 `ips_sales_channel_adder.py`가 단독 실행 시 입력 파일만 있으면 live 판매채널 추가로 들어가는 것을 확인했다.
   - 조치: 기본 실행은 dry-run으로 변경.
   - live 추가는 `--write`가 있을 때만 가능.
   - `ips_sales_channel_pipeline.py`는 실제 실행 분기에서 내부 호출에 `write=True`를 넘기도록 보정.

7. 3회차 감리에서 새 PC 재생성에 필요한 입력 manifest가 부족한 것을 확인했다.
   - 조치: `ops/INPUTS.md` 추가.
   - 조치: `ops/.gitignore`에 local config, `data/catalog`, `담당작가_ssot`, 작업별 증거 폴더를 추가 ignore.

8. 1회차 감리에서 handoff 문서에 개인 PC 절대경로가 남은 것을 확인했다.
   - 조치: `operator_handoff_capability_map.md`의 실행 예시와 원본 위치를 placeholder/상대경로로 치환.

## 검증 결과

- `ops` 전체 Python 문법 컴파일: 통과.
- AST 기준 로컬 import 누락: 0건.
- 주요 진입점 `--help` smoke: 통과.
- `create_natoya_missing_cids_api.py` 기본 실행: live write 없이 preview만 생성 확인.
- `ips_sales_channel_adder.py` 기본 실행: live write 없이 `addition_status=dry_run` 산출 확인.
- 기존 배치 리포트 테스트: `tests/test_batch_reports.py` 2건 통과.
- credential scan: 실제 password/token literal은 발견하지 못했고, env key 이름만 확인됨.
- 개인 PC 절대경로/원본 repo 경로 scan: 코드/운영 문서 기준 잔여 없음.

대표 help smoke 대상:

```text
ops/SIAANE_v2/ips_live_lookup.py
ops/SIAANE_v2/build_manager_author_ssot.py
ops/SIAANE_v2/audit_ips_admin_publisher.py
ops/SIAANE_v2/crawl_admin_copyright_info.py
ops/SIAANE_v2/match_account_cp_bank_info.py
ops/scripts/ips_sales_channel_pipeline.py
ops/scripts/ips_sales_channel_harness.py
ops/scripts/ips_sales_channel_adder.py
ops/scripts/create_kipm_content_contract.py
ops/scripts/create_kipm_dummy_contract.py
ops/SIAAN Project/admin_login.py
ops/SIAAN Project/account_login.py
```

## 의도적으로 안 가져온 것

`SIAANE_v2/0513_temp`의 과거 감리/rename/write 스크립트 묶음은 통째로 흡수하지 않았다.

이유:

- 날짜 고정 recipe와 당시 export/data 파일에 강하게 묶여 있다.
- 일부는 live write 결과물/후속 검증 로그와 짝을 이루는 과거 작업 스크립트다.
- 새 작업자가 포크 후 착각해서 실행하기에는 위험하다.

대신 현재 운영선의 감리 스크립트는 유지한다.

```text
ops/SIAANE_v2/crosswalk/build_ips_adversarial_audit_summary.py
```

필요하면 `0513_temp`는 별도 `legacy/` 아카이브로, 실행 불가/참고 전용 경고를 붙여 가져오는 편이 낫다.

## 남은 리스크

1. `raw/`, `stage/`, `canonical/`, `exports/` 데이터는 흡수하지 않았다.
   - 코드 fork만으로는 모든 보고서를 즉시 재생성할 수 없다.
   - 필요한 입력과 재생성 순서는 `ops/INPUTS.md`를 따른다.

2. `create_kipm_dummy_contract.py`, `create_kipm_content_contract.py`, `rename_ips_content_titles_api.py`, `apply_*_live.py`는 목적상 live 조작 도구다.
   - 인자 없이 바로 사고가 나지는 않지만, `--write` 또는 필수 live 입력을 주면 실제 조작한다.
   - 운영 절차에서 lookup/dry-run 산출물 확인 후 소량 write로 제한해야 한다.

3. `ops/SIAANE_v2/docs/current_context.md`는 판단 로그라 오래된 파일명과 업무 맥락이 섞여 있다.
   - 실행 매뉴얼로 쓰면 안 된다.
   - 실행 매뉴얼은 `ops/README.md`와 이 감리 문서를 우선한다.

4. live 시스템 검증은 수행하지 않았다.
   - 이번 감리는 repo 흡수/포크 안전성 감리다.
   - 실제 IPS/admin/account 접속 검증은 credential 세팅 후 read-only probe로 별도 수행한다.
