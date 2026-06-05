# S2 지급정산 통합 계약 ID 게이트 구현안

## 결론

지급정산 유무 판정은 `판매채널콘텐츠ID가 S2 지급정산 목록에 존재하는가`가 아니라 `통합 계약 ID(cntrId)가 0이 아닌 지급정산 행이 존재하는가`로 정의한다.

현재 로컬 S2 원천 캐시에는 `cntrId`가 포함되어 있으나 `kiss_payment_settlement.to_s2_lookup()`이 이 컬럼을 표준화/필터링하지 않아 `cntrId=0` 행도 S2 매핑 후보로 승격된다. 이 때문에 계약/정산 연결이 없는 판매채널이 "지급정산 있음"으로 오판될 수 있다.

## 조사 근거

- `data/kiss_payment_settlement_cache_part_*.csv`에는 API 원천 컬럼 `cntrId`가 존재한다.
- 현재 캐시 기준 전체 141,733행 중 `cntrId != 0` 행은 20,397행뿐이다.
- 현재 `data/kiss_payment_settlement_s2_lookup.csv`는 `통합계약ID` 컬럼이 없고 125,499행을 보유한다.
- `kiss_payment_settlement.py`의 `API_RAW_COLUMN_ALIASES`에는 `cntrId` 매핑이 없고, `to_s2_lookup()`은 계약 ID를 보지 않는다.
- `scripts/audit_sales_channel_settlement_gap.py`는 `판매채널콘텐츠ID in settlement_ids`만으로 `지급정산관리_존재=Y`를 만든다.
- `settlement_status_gate.py`는 `지급정산관리_존재=Y`를 그대로 OK로 해석하고, 동일 콘텐츠 mixed risk도 이 값 기준으로 계산한다.
- `s2_reference_guards.py`의 타채널 지급정산 근거 인덱스도 S2 lookup 전체를 믿는다.

## 변경 원칙

1. `cntrId`, `unityCntrId`, `통합 계약 ID`, `통합계약ID`를 표준 컬럼 `통합계약ID`로 정규화한다.
2. S2 지급정산 lookup은 `통합계약ID`가 0이 아닌 행만 남긴다.
3. 최신 S2 원천에 계약 ID 컬럼이 없으면 조용히 통과시키지 않고 명시 오류로 막는다.
4. `지급정산관리_존재`는 계약 ID 필터를 지난 행 기준으로만 Y가 되게 한다.
5. 타채널 지급정산 증거도 계약 ID 0 행은 증거에서 제외한다.
6. 결과 summary와 lookup에는 `통합계약ID`를 남겨 이후 감리에서 근거를 바로 볼 수 있게 한다.

## 구현 순서

1. `kiss_payment_settlement.py`
   - 표준 계약 ID 컬럼 상수 추가
   - raw API alias에 `cntrId` 추가
   - 계약 ID 정규화/비0 판정 helper 추가
   - `to_s2_lookup()`에서 계약 ID 필수 검증 및 `cntrId != 0` 필터 적용
   - summary에 계약 ID 컬럼 존재 여부, nonzero/zero_or_blank 건수, nonzero unique ID 수 추가

2. `scripts/audit_sales_channel_settlement_gap.py`
   - `load_settlement_lookup()`에서 계약 ID 컬럼을 읽고 0이 아닌 행만 settlement 기준으로 사용
   - `지급정산관리_통합계약ID`를 판정표에 남김

3. `settlement_status_gate.py`
   - `지급정산관리_존재` 판정을 통합 계약 ID 기준으로 보정
   - 동일 콘텐츠 mixed risk도 계약 ID가 0이 아닌 행만 정상 지급정산으로 계산
   - 상태 사유 문구를 "통합 계약 ID 0/공란" 기준으로 갱신

4. `s2_reference_guards.py`
   - 타채널 지급정산 인덱스에서 계약 ID 0 행 제외
   - 근거 컬럼에 `통합계약ID` 포함

5. 테스트
   - S2 lookup이 `cntrId=0`/공란을 제외하는지 검증
   - 계약 ID 컬럼 없는 원천은 명시 오류인지 검증
   - 상태표가 `지급정산관리_존재=Y`라도 계약 ID 0이면 HOLD로 내리는지 검증
   - 타채널 지급정산 근거에서 계약 ID 0 행이 제외되는지 검증

## 적대적 감리 체크

- 같은 판매채널콘텐츠ID에 `cntrId=0` 최신행과 nonzero 구행이 섞인 경우: nonzero 행만 남기고 그 안에서 최신 dedupe한다.
- `cntrId=0`, `pymtSetlSetmId` 있음: 지급정산 있음으로 보지 않는다.
- 수동 업로드 S2 원천에 계약 ID 컬럼 없음: 최신 원천 재다운로드를 요구한다.
- 관리자 배포 lookup이 구버전이라 `통합계약ID`가 없음: 앱은 최신화 요청/재생성을 요구해야 한다.
- 타채널 지급정산 증거는 계약 ID 0만 있으면 "존재"로 주석 달지 않는다.

## 구현 후 로컬 데이터 감리

- 현재 로컬 S2 원천 캐시 행: 141,733
- `통합계약ID != 0` 원천 행: 20,397
- 전체 판매채널콘텐츠ID 고유값: 124,755
- 계약 연결 판매채널콘텐츠ID 고유값: 19,249
- 기존 관리자 lookup 행: 125,499
- 새 기준 재생성 lookup 행: 19,249
- 새 lookup 내 `통합계약ID` 0/공란 행: 0

현재 로컬 캐시는 실운영 최신 상태가 아니다. 직전 작업에서 새로 만든 `마왕이 나노머신을 숨김`, `용사 노릇이 지겨워서...` 계열 신규 지급정산/판매채널 ID는 로컬 캐시 재생성 결과에 아직 없다. 배포 환경은 S2 전체 최신화가 필요하다.

## Cloud Streamlit 최신화 요청 문구

배포 환경에서는 변경 반영 후 S2 지급정산 원천을 다시 전체 교체로 최신화해야 한다. 요청에는 다음을 포함한다.

- 지급정산 기준 변경: `통합계약ID(cntrId) != 0`만 S2 기준으로 사용
- S2 지급정산 lookup 재생성 필요
- S2 정산정보누락 guard, 청구 guard, 판매채널콘텐츠 lookup도 최신화 필요
- 재생성 후 `통합계약ID` 컬럼이 lookup에 포함되는지 확인 필요

로컬 `.env` 기준 ClickUp S2 요청 큐 설정은 없어 direct API 태스크 생성은 하지 못했다. 대신 Cloud Streamlit 앱의 `관리자에게 S2 최신화 요청` 버튼을 눌러 실제 요청 성공 메시지를 확인했다.

- Cloud 앱: `https://mapping-novel-ascmdzm897irzyvzwn9kqo.streamlit.app/`
- 확인 화면: `output/cloud_streamlit_after_request.png`
- 앱 표시 메시지: `S2 최신화 요청을 보냈습니다.`

배포 환경 secrets가 설정된 Cloud Streamlit 앱에서는 `관리자에게 S2 최신화 요청` 버튼 payload에 다음 문구가 포함되도록 수정했다.

> 지급정산 기준은 `통합계약ID(cntrId) != 0` 행만 사용합니다.

수동 요청이 필요하면 다음 문구로 보낸다.

```text
S2 최신화 요청

- 기준 변경: 지급정산 있음 판정은 통합계약ID(cntrId) != 0 행만 인정
- S2 지급정산 lookup 전체 재생성 필요
- S2 정산정보누락 guard / 청구 guard / 판매채널콘텐츠 lookup 최신화 필요
- 재생성 후 lookup에 통합계약ID 컬럼이 포함되고, 통합계약ID 0/공란 행이 0건인지 확인 필요
- 현재 로컬 재생성 기준: S2 지급정산 lookup 19,249행, 0계약 행 0건
```
