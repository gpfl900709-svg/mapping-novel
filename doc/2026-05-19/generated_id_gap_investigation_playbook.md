# 생성 ID 빈 행 조사 플레이북

대상 시트:

```text
https://docs.google.com/spreadsheets/d/1jG0Q6LKzJ_q2VqdqtoDHSEwl8hfOEUrxRuxXq7KSazY/edit?gid=1569459807#gid=1569459807
```

대상 헤더:

```text
S2 판매채널
정제_상품명
정산서_대표콘텐츠명
S2_미매핑상세사유
S2_판매채널콘텐츠ID
담당자(없을 시 공란)
비고
```

## 목적

`S2_판매채널콘텐츠ID`가 빈 행을 아래 둘로 나눈다.

1. 실제로 S2/IPS에 없어서 생성 또는 계약 보강이 필요한 행
2. 제목 정제, 판매채널 필터, 특수 규칙 때문에 놓친 행

## 1차 자동 판정

```powershell
python scripts\triage_generated_id_gaps.py
```

공개 CSV export가 막히면 구글시트를 CSV로 내려받아 실행한다.

```powershell
python scripts\triage_generated_id_gaps.py --input <downloaded-sheet.csv>
```

산출물:

```text
doc/YYYY-MM-DD/generated_id_gap_triage.csv
doc/YYYY-MM-DD/generated_id_gap_triage.json
```

판정 기준:

- `S2_지급정산_존재`: S2 지급정산 기준에 이미 있다. 정제/채널 필터나 시트 반영 누락을 확인한다.
- `S2_정산정보누락`: S2 누락 guard에 있다. 더미계약보다 S2 정산정보 보강이 먼저다.
- `S2_청구정산후보`: 청구정산 guard에 있다. 지급정산 전송용 ID로 바로 쓰면 안 된다.
- `S2_판매채널콘텐츠만_존재`: 판매채널콘텐츠는 있으나 지급정산 기준에는 없다. 정산 설정/IPS 판매채널 상태를 확인한다.
- `S2_타채널지급정산_존재`: 같은 정제 제목의 지급정산 ID가 다른 채널에만 있다. 현재 채널 ID로 입력하지 않고 IPS 정산정보의 source 통합 계약 ID를 확인한다.
- `S2_타채널판매채널콘텐츠만_존재`: 같은 정제 제목의 판매채널콘텐츠가 다른 채널에만 있다. 정산정보 없음 보조 증거로만 본다.
- `정제규칙_검토필요`: fuzzy 후보가 있다. alias 또는 특수 제목 규칙 추가 여부를 본다.
- `S2_부재_가능성`: S2 쪽 증거가 약하다. IPS/admin/account 조사로 넘어간다.

## 질문 1: 진짜 S2에 없나?

확인 순서:

1. `generated_id_gap_triage.csv`에서 `판정`을 본다.
2. `S2_지급정산_존재`면 생성하지 않는다.
3. `정제규칙_검토필요`면 `S2_fuzzy_top`의 제목과 ID를 사람 눈으로 확인한다.
4. 같은 패턴이 반복되면 `cleaning_rules.py`의 alias 또는 정제 규칙으로 반영한다.
5. `S2_판매채널콘텐츠만_존재`면 S2 상세에는 있지만 지급정산 기준이 없는 상태이므로, 정산 설정/계약 연결 확인으로 넘긴다.
6. `S2_타채널지급정산_존재`면 타채널 ID를 복사하지 않고 IPS 콘텐츠 상세의 정산정보에서 source 통합 계약 ID를 확인한다.
7. source 통합 계약 ID가 0이 아닌 단일 값이면 해당 계약 ID 기준으로 판매채널 추가를 진행할 수 있다.
8. 정산정보가 전부 0이면 판매채널 추가가 아니라 계약/정산 연결 보강이 먼저다.
9. 0이 아닌 계약 ID가 여러 개면 계약서를 사람이 선택한 뒤 진행한다.

## 질문 2: 더미 계약서가 필요하면 상대를 찾을 수 있나?

S2에서 지급정산 근거가 없고 IPS 생성/계약 보강이 필요한 행만 대상으로 한다.

확인 순서:

1. IPS live lookup

```powershell
python ops\SIAANE_v2\ips_live_lookup.py --env-file "ops\SIAAN Project\.env" --query "<정산서_대표콘텐츠명>" --page-size 20 --fetch-all --headless
```

2. IPS에 기존 콘텐츠가 있으면 CID/담당자/출판사/상태를 확인한다.

3. admin 저작권/출판사 근거 확인

```powershell
python ops\SIAANE_v2\crawl_admin_copyright_info.py --env-file "ops\SIAAN Project\.env" --source-csv <candidate.csv> --headless
python ops\SIAANE_v2\audit_ips_admin_publisher.py --env-file "ops\SIAAN Project\.env" --ssot-csv <copyright-attached.csv> --headless
```

4. account 거래처/계좌 근거 확인

```powershell
python ops\SIAANE_v2\match_account_cp_bank_info.py --env-file "ops\SIAAN Project\.env" --headless
```

5. 거래처 후보가 복수면 아래를 비교한다.

- 저작권자명
- 예금주명
- 필명
- 거래처코드
- admin 저작권정보
- IPS 출판사/담당자

## 더미 계약 생성으로 넘어가는 조건

아래가 모두 충족될 때만 더미 계약 생성 후보로 둔다.

- S2 지급정산 exact match 없음
- S2 누락/청구 guard로 설명되지 않음
- 제목 정제/fuzzy 후보 검토 후 기존 S2 후보 없음
- IPS에 기존 콘텐츠가 없거나, 기존 CID로 해결할 수 없음
- admin/account에서 거래처 또는 저작권자 근거 확보
- 담당자/운영자가 생성 대상이라고 승인

실행은 반드시 dry-run/preview부터 한다.

```powershell
python ops\scripts\create_kipm_content_contract.py --help
python ops\scripts\create_kipm_dummy_contract.py --help
```

live write는 소량으로만 실행한다.
