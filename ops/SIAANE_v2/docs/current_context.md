# Current Context

기준일: `2026-04-24`

흡수 메모: 이 파일은 SSOT/SIAANE_v2 작업 당시의 판단 로그다. 새 PC에서 바로 실행할 입력 데이터가 아니라, 누락/보류 판단을 추적하기 위한 참고 문서로만 사용한다.

## 목적

현재 `SIAAN Project`의 혼합형 wide SSOT를 바로 키우지 않고, `SIAANE_v2`에서 플랫폼별 canonical을 먼저 세운 뒤 마지막에만 연결한다.

현재 우선순위는 아래 순서다.

1. `담당작가 범위`를 고정한다.
2. `account` 현실을 관측한다.
3. `account` 안에서 `저작권코드` 기준으로 canonical과 decision queue를 만든다.
4. 그 다음에만 `IPS`를 건드린다.

## 핵심 원칙

- `mega SSOT`로 바로 가지 않는다.
- `IPS rename/create`는 아직 실행하지 않는다.
- `account`가 먼저다.
- `선인세`는 반드시 `저작권코드`에 연결된다고 본다.
- `최신판 1개` 정책을 유지한다.
- `담당작가 SSOT`와 `account decision queue`는 항상 최신 파일 1개만 남긴다.

## 현재 확정된 운영 규칙

### 담당작가 기준

- 현재 `조원재` 담당작가 범위는 `58명`
- `review_rows = 0`
- 기준 산출물:
  - `담당작가 SSOT`: `SIAANE_v2/담당작가_ssot/조원재_담당작가_ssot.xlsx`
  - 기초 CSV: `SIAANE_v2/담당작가_ssot/manager_author_ssot.csv`

### 수동 동치 규칙

현재 수동으로 묶은 대표 그룹:

- `서호 = 갈드`
- `김유관 = 김조선`
- `서오 = 유동우 = 알렌 = 류화수 = 엔트로`
- `민영모 = 민작가`
- `유승표 = 쓰고또쓰고 = 파워레인젖`
- `이루이 = 지미신 = 김예린`
- `이원규 = 북홀릭 = 이권배`
- `정현우 = 만선`
- `말리브해적 = 말리브의해적 = 말리브 해적 = 말리브의 해적`
- `아즐란 = 낙필`

제외 처리:

- `므찌`
- `가온하루`
- `김태평`
- `대형딱풀`

강제 확정:

- `서호`

원본 설정 파일:

- `SIAANE_v2/manager_author_manual_groups.json`

### account 특수 규칙

현재 account 관측 단계에서는 특수를 아래 4개만 쓴다.

- `일반`
- `카카오MG`
- `네이버MG`
- `원작`

판정 규칙:

- 연결된 선인세명이 없으면 `일반`
- 연결된 선인세명에 `네이버`가 들어가면 `네이버MG`
- 연결된 선인세명에 `카카오`, `선투자`, `콘텐츠 특별 공급`이 들어가면 `카카오MG`
- 연결된 선인세명에 `웹툰`이 들어가면 `원작`

주의:

- 예전의 `네이버 광고수익`, `카카오 창작지원금`은 현재 account 관측의 주특수 체계가 아니다.
- 플랫폼별 RS 조정은 나중에 `IPS`에서 처리한다는 가정이다.
- raw/연결선인세가 stale한 경우는 `SIAANE_v2/account/notes/manual_special_overrides.json`에서 임시 수동 override를 둔다.
- 작품별 작가 스코프를 수동 고정할 때는 `SIAANE_v2/account/notes/manual_work_scope_overrides.json`을 쓴다.
- 현재 반영된 override:
  - `account_작가코드 = 4476973 (낙필/김기홍)` -> `네이버MG`

## 현재 만들어진 산출물

### 1. 담당작가 SSOT

경로:

- `SIAANE_v2/담당작가_ssot/조원재_담당작가_ssot.xlsx`

요약:

- `index_author_labels = 74`
- `index_authors_canonical = 57`
- `nas_authors = 58`
- `confirmed_authors = 58`
- `review_rows = 0`

역할:

- “누가 진짜 내 담당작가냐”를 먼저 닫아두는 기준표

### 2. account observation

경로:

- `SIAANE_v2/account/exports/latest__account_observation_조원재.xlsx`

구성:

- `요약`
- `account_actual_inventory`
- `special_evidence_inventory`

요약:

- `actual_inventory_rows = 143`
- `special_evidence_rows = 143`
- `distinct_author_codes = 59`
- `distinct_copyright_codes = 143`

역할:

- `account` 현실을 먼저 관측하는 표
- 아직 canonical 최종판이 아니라 “실황표” 성격

### 3. 작가코드별 특수 RS 수집본

경로:

- `SIAAN Project/data/exports/barobook/20260424_103630__작가특수RS_조원재.xlsx`

요약:

- 대상 작가: `59명`
- 수집 행: `42행`
- 실패 로그: 없음

수집 컬럼:

- `작가코드`
- `저작권자명_필명`
- `매칭_키_필명`
- `작가특수RS코드`
- `행번호`
- `관리제목`
- `서비스`
- `정산율(%)`
- `정산기준코드`
- `정산기준`
- `등록일`

설명:

- 이것은 `저작권코드별 RS`와 별개다.
- `작가코드` 단위 예외 RS다.
- 수집 위치는 `CpCprShareMgr?key={작가코드}` 하단의 예외 정산율 표다.

### 4. account decision queue

경로:

- `SIAANE_v2/account/exports/latest__account_decision_queue_조원재.xlsx`

구성:

- `요약`
- `account_decision_queue`
- `author_special_rs_summary`
- `author_special_rs_raw`

요약:

- `decision_rows = 143`
- `rename_review_rows = 44`
- `cid_split_rows = 60`
- `author_review_rows = 1`
- `pending_author_review_rows = 0`
- `work_review_rows = 14`
- `pending_work_review_rows = 0`
- `keep_rows = 24`
- `pending_decision_rows = 0`
- `author_special_rs_rows = 42`

역할:

- `저작권코드 1행` 기준 검토 큐
- `현재 저작권명`
- `canonical 저작권명 제안`
- `action 제안`
- `작가특수RS 요약`
- `수동 확정 칸`
  를 한 번에 모아둔 작업판

추가 해석:

- 이 큐는 `account` 내부 검토용이다.
- `IPS`에서 필요한 `작품별 CID`를 직접 표현하는 큐는 아니다.
- `관측_작품수 > 1` 권리행은 `canonical 저작권명`을 1개로 고정하지 않고 `CID분해필요`로 다룬다.
- 작품 단위 분해는 `crosswalk/account→ips CID seed`에서 처리한다.
- `decision_signature`로 수동 확정값을 보존하되, 관측 작품수/action/근거가 바뀐 stale 자동승인은 다시 미처리로 돌린다.
- `유지` 행은 감리 후 `자동 유지` 메모와 함께 처리완료로 닫는다.

### 5. account→ips CID seed

경로:

- `SIAANE_v2/crosswalk/exports/latest__account_ips_cid_seed_조원재.xlsx`

구성:

- `요약`
- `account_ips_cid_seed`
- `raw_seed`

요약:

- `seed_rows = 256`
- `distinct_works = 209`
- `distinct_rights_codes = 127`
- `multi_work_rows = 188`
- `missing_advance_rows = 119`

역할:

- `IPS`에서 사용할 작품 단위 CID 초안 seed
- `account`의 `저작권코드 1행`을 작품별로 분해한 중간 산출물
- 아직 최종 `IPS rename/create` 실행 큐는 아님
- `작가확인`, `작품확인`처럼 사람이 확정하지 않은 행은 seed에 넣지 않는다.

### 6. CID split review queue

경로:

- `SIAANE_v2/crosswalk/exports/latest__account_cid_split_review_queue_조원재.xlsx`

구성:

- `요약`
- `cid_rights_review`
- `cid_work_seed_review`
- `raw_cid_seed`

요약:

- `cid_rights_rows = 59`
- `cid_seed_rows = 188`
- `pending_cid_rights_rows = 0`

역할:

- `CID분해필요` 권리행만 따로 모은 검토판
- 권리행 기준 질문과 작품별 seed를 한 파일에서 같이 본다
- 이후 dedupe, 대표 Y/N, 병합그룹 메모를 남기는 작업판

### 7. account rights canonical

경로:

- `SIAANE_v2/account/exports/latest__account_rights_canonical_조원재.xlsx`

구성:

- `요약`
- `account_rights_canonical`
- `cid_seed_summary`

요약:

- `canonical_rows = 143`
- `usable_rows = 142`
- `excluded_rows = 1`
- `cid_split_rows = 59`
- `pending_rows = 0`

역할:

- `저작권코드 1행` 기준 최종 account canonical
- `수동_최종저작권명`, `유지`, `CID분해`, `담당제외`, `보류` 상태를 한 곳에 닫은 산출물
- `CID분해` 행은 account 권리행으로 유지하되, `CID_seed_행수`, `CID_작품목록`, `CID_seed_id_목록`으로 작품별 seed와 연결한다
- `1003371` 카니발 로사는 `canonical_status = 담당제외`, `canonical_사용(Y/N) = N`으로 남긴다

### 8. account work gap queue

경로:

- `SIAANE_v2/account/exports/latest__account_work_gap_queue_조원재.xlsx`

요약:

- `gap_rows = 44`
- `unmapped_work_total = 122`
- `normalized_clusters = 75`
- `candidate_rows = 14`
- `same_code_candidate_rows = 3`
- `code_less_candidate_rows = 7`

역할:

- `raw CpCprMappProdList`에는 있는데 registry/NAS 폴더에는 아직 안 잡힌 작품만 모은 리포트
- 판단 큐가 아니라 stale/누락 관측용 작업판
- `관측_작품목록`은 raw 기준, `관측_작품_폴더`는 registry 기준으로 비교한다
- episode/권 단위 제목(`1회`, `10-3권` 등)은 로컬 정규화로 한 번 더 접어서 과대계수를 줄인다
- workbook 안의 `normalized_gap_clusters` 시트는 플랫폼 태그, 세트, 권수 표기를 접은 보조 클러스터 요약이다
- workbook 안의 `candidate_gap_queue` 시트는 같은 작가의 다른 저작권코드에서 이미 폴더 후보가 잡히는 행만 모은 보조 시트다
- `추정_후보유형 = 동일코드포함`이면 현재 저작권코드와도 연결 흔적이 있는 강한 후보다
- `추정_후보유형 = 코드없음후보`이면 폴더 후보는 있지만 mapping summary의 저작권코드 연결 흔적은 비어 있다

### 9. IPS action queue

경로:

- `SIAANE_v2/crosswalk/exports/latest__account_ips_action_queue_조원재.xlsx`

구성:

- `요약`
- `action_summary`
- `ips_action_queue`
- `match_candidates`
- `current_ips_inventory`

요약:

- `seed_rows = 256`
- `ips_inventory_rows = 15256`
- `match_candidate_rows = 569`
- `queue_rows = 256`
- `IPS_분해/중복검토 = 140`
- `IPS_사용안함검토 = 24`
- `IPS_매칭검토 = 6`
- `IPS_신규생성 = 31`
- `IPS_이름수정 = 55`

역할:

- `account_ips_cid_seed`의 `CID_seed_id`를 공식 IPS 후보명으로 보고 현재 IPS 콘텐츠 목록과 대조한 작업 큐다.
- 현재 IPS 입력은 `소설편집팀.xlsx`, `소설유통팀.xlsx`의 `콘텐츠 목록` 시트다.
- 원본 IPS 엑셀은 수정하지 않는다.
- `IPS_이름수정`은 현재 CID 1개와 seed 1개가 비교적 안전하게 매칭된 행이다.
- `IPS_신규생성`은 현재 IPS에서 대응 CID를 찾지 못한 행이다.
- `IPS_분해/중복검토`는 현재 CID 1개가 여러 seed에 매칭되거나, seed별 후보 CID가 복수이거나, 현재 IPS명이 묶음명인 행이다.
- `IPS_사용안함검토`는 현재 후보가 `(사용안함)` 계열이라 직접 rename 전에 확인이 필요한 행이다.
- `IPS_매칭검토`는 제목 단독 매칭처럼 작가/코드 근거가 약한 행이다.
- 사용자가 별도로 수정 중인 팀 엑셀 담당자 변경분은 반영 후 이 큐를 다시 빌드하면 된다.

## 현재 스키마 해석

### account_actual_inventory

grain:

- `작가코드 + 저작권코드`

핵심 컬럼:

- `account_작가코드`
- `account_저작권코드`
- `account_저작권명`
- `account_정산기준`
- `B2C/B2BC/B2B 정산율`
- `연결_선인세코드`
- `연결_선인세명`
- `대표_상품번호`
- `대표_제목`
- `관측_작품목록`
- `관측_작품_폴더수`
- `관측_미매핑_작품수`
- `관측_미매핑_작품목록`

해석 메모:

- `관측_작품목록`과 `관측_작품수`는 `raw CpCprMappProdList -> 저작권_시리즈매핑` 기준이다.
- 따라서 registry/NAS에 아직 없는 작품도 raw popup에서 보이면 관측 목록에 포함된다.
- `관측_작품_폴더`는 registry/NAS에서 실제로 확인된 폴더만 보조로 기록한다.

### account_decision_queue

grain:

- `저작권코드 1행`

핵심 컬럼:

- `현재_저작권명`
- `대표작품`
- `특수`
- `canonical_저작권명_제안`
- `action_제안`
- `판정근거`
- `작가특수RS요약`
- `수동_최종저작권명`
- `수동_action`
- `수동_메모`
- `처리완료(Y/N)`

## 현재 남아 있는 이슈

### 1. 범용 저작권명 다수

기존 `이름수정검토 47행`은 권장안 기준으로 전량 승인했다.
이후 `관측_작품목록`을 raw 시리즈맵 기준으로 재생성하고 작가확인 10행을 반영하면서 생긴 `이름수정검토 미처리 15행`도 권장안 기준으로 전량 승인했다.
현재 `account_name_review_queue` 미처리는 0행이다.

주된 유형:

- `기본정산율`
- `신작 ...`
- `창작지원금`
- `구간`
- `선인세 정산 도서`
- `윌라 정산`

의미:

- 저작권코드는 존재하지만 운영에 바로 쓰기 좋은 이름이 아니다.
- `대표작품` 기준으로 canonical 저작권명을 사람이 확정해야 한다.

단, 예외:

- `저작권코드` 하나에 여러 작품이 관측되는 행은 이름을 1개로 닫지 않는다.
- 이런 행은 `CID분해필요`로 넘기고 작품 단위 seed에서 분해한다.

### 2. 복수 작품 권리행

기존 `CID분해필요 22행`은 기본 CID 분해안 기준으로 전량 승인했다.
다만 raw 시리즈맵 기준 멀티작품 권리행과 제목 정규화 분해를 반영한 현재 상태는 `CID분해필요 60행 / cid_rights_review 미처리 0행`이다.
추가로 `생존게임 -> 박천웅`, `레벨원 -> 박천웅`, `미스터 프레지던트 묶음 -> 박천웅`, `슈퍼스타 -> 구라천재`, `재벌가 차남은 먼치킨 -> 말리브해적`, `푸드트럭으로 요리재벌 -> 아즐란`, `마왕군 전입을 명 받았습니다/마왕으로 산다 -> 하늘곰`, `드래곤 잡으려다 내가 잡힘?!/아포칼립스인데 나 혼자 농사 -> 지미신`, `걷기만 해도 조만장자 -> 하늘곰`, `섹스마스터/정자왕 -> 빨간홍차`, `나만의 마조 선생님 -> 순애의망나니`, `신의 연기 -> 백락`, `어서 와 마왕/재벌가 첫째아들 -> 하늘곰` 수동 override를 반영했다.
또 `사용금지`, `사용x`가 붙은 작품명은 observation과 seed에서 제외하도록 바꿨다.
또 `manual_work_scope_conflict`는 사람이 확정한 혼합 작가 권리행이면 `CID분해필요`로 보내고, seed에서 작품별 수동작가를 적용한다.
또 `작가확인`, `작품확인` 행은 사람이 닫기 전까지 CID seed에서 제외한다.
또 제목 정규화 감리로 `(연재)`, `[연재]`, `카카오창작지원금_`, 공백/구두점 차이, 영어 괄호 병기 변형을 추가로 접었다.
자동 승인 가능한 CID분해 43행은 `apply_account_cid_split_auto_approval.py`로 처리했다.
마지막 4건은 사용자 판단을 반영해 `네임드/네임드 플레이어 별도 CID`, `핵무기도 만들어 드릴까요?/핵무기도 만들어 드림 2개 CID`, `카니발 로사 담당제외`, `생호라비=생활비 오탈자 병합`으로 닫았다.

의미:

- `저작권코드 1개`에 `2개 이상 작품`이 물려 있다.
- `account_decision_queue`에서 이름을 1개로 닫는 대신 `crosswalk seed`에서 작품별로 쪼개야 한다.
- 이후 `IPS`로 넘길 때는 작품 단위로 dedupe와 대표 Y/N를 봐야 한다.

### 3. 대표작품 미관측 행

현재 `작품확인 14행`은 전부 `IPS_CID생성보류`로 처리 완료했다.

의미:

- `관측_작품목록`이 비어 있거나 매우 약하다.
- 원작/창작지원금/윌라 정산류 코드가 일부 여기로 빠진다.
- 미래 용도 CID 후보라 있으면 나중이 편할 수 있지만, 현재 IPS에는 없어도 되는 optional 범위로 본다.
- 따라서 지금은 seed에 넣지 않고, 나중에 실제 필요가 생기면 다시 연다.

### 4. 작가 범위 애매한 클러스터

현재 `작가확인` action은 `1005127` 1행만 남아 있지만, 사용자 판단에 따라 `작가확정보류`로 처리 완료했다.
따라서 실제 미처리 `작가확인`은 0행이다.

주된 배경:

- `scope_assignment_basis = ambiguous_scope`
- 다중 필명 흔적
- 다중 작품/다중 계정 흔적

주의:

- 이 상태의 행은 이름을 바로 확정하면 다시 꼬일 수 있다.

### 5. 서호 raw gap

담당 범위는 `서호 = 4476682`로 확정됐지만,
현재 내려받은 account raw에서는 `4476682 / 1004715` 같은 권리행이 아직 observation에 보이지 않는다.

의미:

- 담당 범위는 닫혔지만, account raw 수집은 아직 완전하지 않다.

## 지금까지의 합의된 흐름

현재 워크플로는 아래 순서로 본다.

1. `담당작가 SSOT`로 내 담당 범위를 고정한다.
2. `account observation`으로 현실을 관측한다.
3. `account decision queue`에서 이름/작품/작가 애매한 행을 수동으로 정리한다.
4. 그 뒤 `account canonical`을 만든다.
5. 복수 작품 권리행은 `crosswalk account→ips CID seed`에서 작품 단위로 분해한다.
6. 마지막에만 `IPS action queue`로 넘긴다.

즉, 아직은 `IPS`를 직접 수정할 단계가 아니라 `IPS action queue`를 기준으로 rename/create 후보를 정리하는 단계다.

## 바로 다음 추천 작업

현재 가장 자연스러운 다음 작업은 `IPS action queue`에서 실행 가능한 것과 수동 판단이 필요한 것을 더 줄이는 것이다.

우선순위:

1. 사용자가 `소설유통팀.xlsx`, `소설편집팀.xlsx`의 담당자명 수정 후 `build_account_ips_action_queue.py`를 재실행
2. `IPS_이름수정 55행`은 실행 전 마지막 감리
3. `IPS_신규생성 31행`은 실제 생성 필요 여부 감리
4. `IPS_분해/중복검토 140행`, `IPS_사용안함검토 24행`, `IPS_매칭검토 6행`은 자동 실행 금지, 별도 판단

권장 작업 방식:

- account canonical은 이미 닫힌 입력으로 본다
- CID seed의 `CID_seed_id`를 IPS CID 후보명으로 삼는다
- 기존 IPS CID와 매칭되면 rename/noop, 없으면 create 후보로 둔다
- 현재 CID 1개가 여러 seed에 매칭되면 바로 실행하지 않고 `IPS_분해/중복검토`로 둔다

그 다음 단계:

- `IPS_이름수정`, `IPS_신규생성` 중 안전한 행부터 실행 큐로 승격
- 실제 IPS rename/create 실행은 별도 단계로 진행

## 2026-05-13 추가: IPS 청소 중심 작업 기준

최신 입력 스냅샷은 아래 폴더를 기준으로 본다.

- `SIAANE_v2/0513_temp/data/IPS.xlsx`
- `SIAANE_v2/0513_temp/data/s2_20260513.xlsx`
- `SIAANE_v2/0513_temp/data/플랫폼 매출정산 처리 현황_신청2026-05-13.xlsx`

이번 라운드의 중심 목표는 `IPS 청소`다.

- `mapping-novel`은 판정/후보/작업대상 컨텍스트로 유지한다.
- 실제 IPS 조작은 `SIAANE_v2`에서 수행한다.
- 지급정산 정보가 없는 콘텐츠ID는 기본적으로 쓰지 않는다.
- 단, 후보가 그 1개뿐이고 작품 동일성이 강하면 버리지 않고 `살릴 후보`로 보낸다.
- `살릴 후보`는 직접 매핑하지 않고, IPS 보정/판매채널 추가/지급정산 보강/신규 생성 여부를 먼저 판단한다.

### IPS 후보 폐기/보존 기준

후보는 바로 실행하지 않고 아래 4개 큐로 나눈다.

- `즉시 사용 가능`: 개별 작품이고, 사용 가능 상태이며, 지급정산 정보가 있고, 담당/작가/작품/채널 맥락이 맞는 행
- `살릴 후보`: 작품은 맞지만 지급정산 정보 없음, 판매채널 없음, 사용금지만 존재, 번들/개별 구조가 꼬인 행
- `버릴 후보`: 번들인데 개별 작품 정산에 쓰려는 행, 사용 가능한 대체 후보가 있는 사용금지 행, 제목만 비슷한 오매칭 행
- `사람 판단`: 동일작품 복수 저작권코드, MG/일반/원작 구분 애매, 담당자 귀속 근거가 충돌하는 행

특히 아래 케이스를 우선 검토한다.

- 작품별로 번들만 있고 개별 작품 CID가 없는 경우
- 사용금지 CID만 있고 사용 가능한 CID가 없는 경우
- 지급정산 정보가 없는 CID가 유일 후보인 경우
- 같은 작품으로 보이는 행이 여러 담당자/여러 팀 파일에 흩어진 경우

### 담당자 귀속 추가 기준

담당자는 단순히 현재 IPS/팀 엑셀의 담당자명이 `조원재`인 행만 보지 않는다.

이번 청소 대상에는 아래도 포함한다.

- 현재 담당자명이 `조원재`인 작품
- 현재 담당자명은 다르지만, 원래 `조원재`였어야 하는 작품
- 다른 담당자 작품 중 제목/작가/저작권코드/CID seed/관측 폴더 근거상 `조원재` 작품으로 보이는 행

기존 참고 산출물:

- `SIAANE_v2/account/exports/latest__team_owner_mismatch_candidates_조원재.xlsx`
- `SIAANE_v2/account/exports/latest__team_owner_mismatch_candidates_조원재.csv`
- `SIAANE_v2/account/exports/latest__team_owner_mismatch_candidates_조원재.json`

이 큐의 의미:

- 비조원재 담당 콘텐츠명과 조원재 account/IPS CID seed/관측명이 정규화 exact match 되는 후보
- `강후보`는 담당자 조원재 변경 후보로 본다.
- `수동확인필요`는 MG/일반/구간/번들 차이를 확인한 뒤 조원재 회수 여부를 결정한다.

주의:

- 담당자명이 다르다는 이유만으로 버리지 않는다.
- 조원재 작품으로 보이는 타 담당자 행은 `owner mismatch` 큐로 먼저 보낸다.
- 담당자 변경/IPS rename/create는 한 번에 실행하지 않고, 담당자 귀속 확인 후 별도 실행 큐로 승격한다.

### 2026-05-13 산출: CID 신뢰 증명표

IPS 조작 전, 후보 CID를 작품별로 믿을 수 있는지 증명하는 표를 먼저 만들었다.

산출물:

- `SIAANE_v2/0513_temp/exports/ips_cid_trust_inventory_조원재_20260513.xlsx`
- `SIAANE_v2/0513_temp/exports/ips_cid_trust_inventory_조원재_20260513.csv`
- `SIAANE_v2/0513_temp/exports/ips_cid_trust_work_summary_조원재_20260513.csv`

검증 기준:

- `즉시사용`은 S2 지급정산이 있고, 사용안함/정산정보없음/번들 표식이 없고, 제목 근거가 있는 후보만 둔다.
- `살릴후보`는 지급정산 없음/사용안함/번들 구조가 있어도 유일 후보이거나 정상 대체 후보가 없어 보정 가능성을 봐야 하는 후보로 둔다.
- `버림`은 같은 작품에 정상 S2 후보가 있어 사용안함/정산정보없음/위험 후보를 폐기할 수 있는 경우로 둔다.
- `사람판단`은 타 담당자 귀속, 후보 없음, S2는 있으나 제목 근거 약함, 복합위험을 둔다.

1차 분포:

- 작품 seed 수: `256`
- 후보 증명 행 수: `493`
- `즉시사용`: `217`
- `버림`: `184`
- `사람판단`: `62`
- `살릴후보`: `30`

### 2026-05-13 적대적 감리 1회: 1작품=1CID

목표:

- `조원재` 담당 또는 담당해야 하는 작품에서 `1개 작품 = 1개 CID`가 깨지는지 확인한다.
- `즉시사용` 큐도 믿지 않고, 같은 작품/같은 CID의 중복 연결을 공격적으로 찾는다.

산출물:

- `SIAANE_v2/0513_temp/exports/ips_cid_trust_adversarial_audit1_조원재_20260513.md`
- `SIAANE_v2/0513_temp/exports/ips_cid_trust_adversarial_audit1_findings_조원재_20260513.csv`

결과:

- CRITICAL: `3`
- HIGH: `67`
- MEDIUM: `5`
- INFO: `3`

CRITICAL 직접 위반:

- `영웅은 쉬고 싶다`: 즉시사용 CID `110833`, `311317` 2개
- `용사무적`: 즉시사용 CID `110079`, `110842` 2개
- `미스터 프레지던트 / 미스터 프레지던트 2부`: CID `311615`가 두 작품에 동시에 즉시사용 후보로 연결

판정:

- `즉시사용` 큐를 그대로 IPS 조작에 넘기면 안 된다.
- 위 3건은 대표 CID 1개를 고르거나, 구간/특수/채널 분리 여부를 먼저 확정해야 한다.
- HIGH의 핵심은 동일 CID가 여러 작품 후보로 걸리는 번들/분해 위험과, 타 담당자지만 조원재 작품으로 보이는 후보들이다.

### 2026-05-13 CRITICAL 해소 및 live 사용안함 처리

사용자 확정/대리 판단:

- `미스터 프레지던트 2부`: CID `311615`로 확정한다. `미스터 프레지던트` 후보에서는 제외한다.
- `영웅은 쉬고 싶다`: 대표 CID는 `311317`로 둔다. CID `110833`은 폐기한다.
- `용사무적`: 대표 CID는 `110079`로 둔다. CID `110842`는 폐기한다.

판단 근거:

- `영웅은 쉬고 싶다`의 `311317`은 제목/작가/계정 근거가 더 직접적이고 S2 지급정산 row/channel 근거가 충분하다. `110833`은 구형/일반형 후보로 보이며 대표 CID 중복을 만들기 때문에 죽인다.
- `용사무적`의 `110079`는 일반 대표 CID로 둔다. `110842`는 카카오 특정 후보 성격이 강해 1작품=1CID 원칙에서는 대표로 쓰지 않는다.
- `미스터 프레지던트 2부`는 사용자가 직접 CID `311615`를 확정했다.

수동 결정표:

- `SIAANE_v2/0513_temp/manual_cid_decisions_20260513.csv`

live rename plan:

- `SIAANE_v2/0513_temp/ips_disable_rename_plan_20260513.csv`

live write 산출물:

- `SIAANE_v2/0513_temp/exports/ips_disable_rename_write_20260513.csv`
- `SIAANE_v2/0513_temp/exports/ips_disable_rename_write_20260513.json`

실제 IPS 반영 결과:

- CID `110833`: `0_영웅은 쉬고 싶다_만선_일반` -> `[사용안함]_0_영웅은 쉬고 싶다_만선_일반`
- CID `110842`: `용사무적_만선_카카오` -> `[사용안함]_용사무적_만선_카카오`
- 두 건 모두 live write 후 재조회 검증 결과 `updated` / `verified_after_reload`

재생성 결과:

- 후보 증명 행 수: `492`
- `즉시사용`: `214`
- `버림`: `184`
- `사람판단`: `64`
- `살릴후보`: `30`

재감리 결과:

- CRITICAL: `0`
- HIGH: `67`
- MEDIUM: `5`
- INFO: `3`

주의:

- `0513_temp/data/IPS.xlsx`는 live rename 전 내려받은 스냅샷이다. 따라서 inventory의 원본 IPS 현재명은 다음 최신 다운로드 전까지 예전 이름으로 보일 수 있다.
- 실제 반영 근거는 live write 산출물과 `manual_cid_decisions_20260513.csv`를 기준으로 본다.

### 2026-05-13 다음 판단 영역: 특수/추후처리 suffix

사용자 판단:

- `(웹툰)골 때리는 엄마들`, `(웹툰)핵무기도 만들어 드릴까요`는 지금 확정 처리하지 않고 후속 검토용 `[특수]` suffix를 붙인다.
- `(웹툰)친구엄마와 친구먹기`, `너무 잘 아는 게임에 소환됐다`는 지급정산 없음 + 유일 후보이므로 더미 계약서/정산자 확인 전까지 후속 처리 표식으로 둔다.
- `(웹툰)친구엄마와 친구먹기`는 자동 rename이 실패했지만, 이후 사용자가 수동으로 `_[특수]` 표식을 붙였다.

live rename plan:

- `SIAANE_v2/0513_temp/ips_suffix_marker_rename_plan_20260513.csv`
- `SIAANE_v2/0513_temp/ips_suffix_marker_rename_plan_107853_short_20260513.csv`

live write 산출물:

- `SIAANE_v2/0513_temp/exports/ips_suffix_marker_rename_write_20260513.csv`
- `SIAANE_v2/0513_temp/exports/ips_suffix_marker_rename_write_20260513.json`
- `SIAANE_v2/0513_temp/exports/ips_suffix_marker_rename_write_107853_short_20260513.csv`
- `SIAANE_v2/0513_temp/exports/ips_suffix_marker_rename_write_107853_short_20260513.json`
- `SIAANE_v2/0513_temp/exports/ips_suffix_marker_rename_107853_manual_verify_20260513.csv`
- `SIAANE_v2/0513_temp/exports/ips_suffix_marker_rename_107853_manual_verify_20260513.json`

실제 IPS 반영 결과:

- CID `107761`: `(사용안함)_골 때리는 엄마들·미도파_중복` -> `(사용안함)_골 때리는 엄마들·미도파_중복_[특수]`
- CID `138176`: `[사용안함]_핵무기도 만들어 드릴까요?_북홀릭` -> `[사용안함]_핵무기도 만들어 드릴까요?_북홀릭_[특수]`
- CID `109764`: `[정산정보없음]_너무 잘 아는 게임에 소환됐다_지피노_1003381_530_확정` -> `[정산정보없음]_너무 잘 아는 게임에 소환됐다_지피노_1003381_530_확정_[추후처리]`
- CID `107853`: `(웹툰)친구엄마와 친구먹기` 자동 rename 실패. `_[추후처리]`, `_[후]` 모두 IPS 서버 변경이력 `AFCH_DATA` 길이 오류로 PUT 실패. 이후 사용자가 수동 수정했고, live verify 기준 현재명은 `(웹툰)친구엄마와 친구먹기_[특수]`.

### 2026-05-13 IPS 후보 없음 판단 큐

산출물:

- `SIAANE_v2/0513_temp/ips_no_candidate_judgment_queue_20260513.csv`
- `SIAANE_v2/docs/20260513_ips_cleanup_next_actions.md`
- GitHub issue: https://github.com/macximin/managing/issues/1

사용자가 조원재 작품으로 확정한 수동흡수 대상:

- `골 떄리는 비제이들`: CID `320888` `골 때리는 여자 비제이들_쉐도우스_1005458_미연결_확정`으로 흡수 확정.
- `타락의 검은실 2부`: CID `107843` `타락의 검은 실_용병애쉬_1004942_874_확정`으로 흡수 확정.
- `하이퍼 서버 벤젠스`: CID `327958` `하이퍼 서퍼 벤젠스_나토야_1005697_선인세없음_확정`으로 흡수 확정.

처리 결과:

- `0513_temp/manual_cid_decisions_20260513.csv`에 `assign` 결정 3건을 추가했다.
- `0513_temp/build_cid_trust_inventory.py`는 수동 assign CID를 후보로 끌어오고, 사용자 확정 흡수 건은 `수동흡수` 큐로 분류한다.
- `0513_temp/adversarial_audit_cid_trust.py`는 `수동흡수`를 즉시사용 직접 위반으로 보지 않고, `work_without_immediate_cid`에서도 제외한다.
- 재감리 결과 `work_without_immediate_cid`는 `37`건에서 `34`건으로 감소했다.

2026-05-14 사용자 확정: 아래 작품들은 조원재 담당이 아니므로 `대상외`/no-action 처리한다.

- `4인 청춘 레포트`
- `나선미로`
- `노출광 여대생`
- `드래곤 스튜던트`
- `라이오스의 불량기사`
- `사립루레인학원 윤리선생 | 사립루레인학원 윤리선생(개정판)`
- `짐승들의 만찬`
- `투 브라더스`
- `투 시스터즈`
- `페르기온의 황제`

처리 결과:

- `0513_temp/manual_cid_decisions_20260513.csv`에 `out_of_scope` 결정 11건을 추가했다. 사립루레인학원은 원작/개정판 2 seed로 분리 기록했다.
- `0513_temp/build_cid_trust_inventory.py`는 `out_of_scope`를 `대상외` 큐로 분류한다.
- `0513_temp/adversarial_audit_cid_trust.py`는 `대상외`를 `work_without_immediate_cid`에서 제외한다.
- 재감리 결과 `work_without_immediate_cid`는 `34`건에서 `24`건으로 감소했다.
- 최신 재감리 분포: CRITICAL `0`, HIGH `54`, MEDIUM `5`, INFO `3`.

### 2026-05-14 S2있지만 제목근거약함 6건 판정 반영

사용자 판정 팁:

- 웹툰은 소설 본작과 따로 관리한다.
- 이유: 소설이 아닌데 소설인 `2차 IP`의 정산 담당 영역이기 때문이다.
- 따라서 웹툰 후보는 오류/폐기가 아니라 `특수보류`로 분리한다.

수동 결정:

- `(웹툰)골 때리는 엄마들`
  - CID `107761`
  - `특수보류`
  - 웹툰/2차 IP 별도관리
- `(웹툰)핵무기도 만들어 드릴까요`
  - CID `138176`
  - `특수보류`
  - 웹툰/2차 IP 별도관리
- `NTR당한 암컷용사는 모자상간으로 복수한다`
  - CID `322574`
  - `NTR당한 암컷용사는 존예왕비가 되었다_파랑깨굴_1005388_1086_확정`으로 수동흡수 확정
- `늙은 경비에게 조교당하는 스튜어디스의 이야기`
  - CID `109326`
  - `[사용안함]_늙은 경비에게 조교당하는 스튜어디스_푸른산붉은꽃`
  - S2 지급정산이 있으므로 사용안함 라벨을 그대로 믿지 않고 `IPS보정필요`로 유지
- `다따먹점혈법`
  - 후보 CID `326352 | 278175`
  - 번들/시리즈 구조 확인 필요
  - `구조확인필요`로 유지
- `보수적이라며 팬티는 왜 벗어`
  - CID `108054`
  - `보수적인데 팬티는 왜 벗어?_미도파_1004945_949_확정`으로 수동흡수 확정

처리 결과:

- `0513_temp/manual_cid_decisions_20260513.csv`에 `special_hold`, `assign`, `revive`, `structure_review` 결정을 추가했다.
- `0513_temp/build_cid_trust_inventory.py`에 `특수보류`, `보정필요`, `구조확인` 큐를 추가했다.
- `0513_temp/adversarial_audit_cid_trust.py`에서 `특수보류`는 `work_without_immediate_cid`에서 제외한다.
- `보정필요`, `구조확인`은 즉시사용으로 숨기지 않고 MEDIUM 수준의 남은 작업으로 유지한다.
- 재감리 결과 `work_without_immediate_cid`는 `24`건에서 `20`건으로 감소했다.
- 최신 재감리 분포: CRITICAL `0`, HIGH `48`, MEDIUM `7`, INFO `5`.

추가 사용자 확정:

- `스킬스`
  - 대표 CID는 `318934` `스킬스_류화수_1005190_1021_확정`
  - CID `320964` `[사용안함]_스킬스_서오`는 정상 대표 CID가 있으므로 살리지 않는다.
  - `manual_cid_decisions_20260513.csv`에 `keep` 결정으로 기록했다.
  - 재생성 후 CID `320964`는 `버림 / 수동대표CID아님`으로 분류된다.
- `S2있지만_제목근거약함` 잔여 건수는 `0`.

### 2026-05-14 타담당자 귀속 검토 일부 확정

사용자 확정:

- 아래 작품은 조원재 작품이 맞다.
- 다만 타담당 CID가 곧 대표 CID라는 뜻은 아니다.
- 이미 조원재 대표 CID가 있는 작품은 타담당 CID를 중복/잔여정산 이관 후보로 본다.
- 번들 후보는 나중에 별도 분해한다. 번들 중 살릴 후보는 원칙적으로 1개뿐이므로 자동 확정하지 않는다.

조원재 작품 확정 목록:

- `SM클럽`
- `SSS급 천재`
- `달인`
- `독식하는 재벌 3세`
- `레지스트 쉴드`
- `망한 세상에서 나 혼자 각성`
- `무림영웅 때려칩니다`
- `사이코패스 살인마는 살고 싶다`
- `이세계 영주 생활`
- `혜정이의 야한 이야기`

처리:

- `0513_temp/manual_cid_decisions_20260513.csv`에 `owner_confirmed` 결정을 추가했다.
- `0513_temp/build_cid_trust_inventory.py`에 `담당확정` 큐를 추가했다.
- `0513_temp/adversarial_audit_cid_trust.py`에서 `담당확정` 후보는 `other_owner_possible_jo_work`에서 제외한다.
- 재감리 결과 `other_owner_possible_jo_work`는 `23`건에서 `13`건으로 감소했다.
- 최신 재감리 분포: CRITICAL `0`, HIGH `35`, MEDIUM `10`, INFO `6`.

### 2026-05-14 표식 완료 항목 판단 대상 제외

사용자 지적:

- `(웹툰)친구엄마와 친구먹기` / CID `107853`
- `너무 잘 아는 게임에 소환됐다` / CID `109764`
- 두 건은 이미 `[특수]` 또는 `[추후처리]` 표식 처리한 항목이므로 현재 판단 대상으로 다시 묻지 않는다.

처리:

- `0513_temp/manual_cid_decisions_20260513.csv`에 `defer_hold` 결정을 추가했다.
- `0513_temp/build_cid_trust_inventory.py`에 `추후보류` 큐를 추가했다.
- `0513_temp/adversarial_audit_cid_trust.py`에서 `추후보류`는 `work_without_immediate_cid`에서 제외한다.
- 재감리 결과 `work_without_immediate_cid`는 `20`건에서 `18`건으로 감소했다.
- 최신 재감리 분포: CRITICAL `0`, HIGH `35`, MEDIUM `8`, INFO `6`.

남은 타담당자 귀속 판단 13건:

- `김석산 파이브`
- `드래곤 엔터테인먼트`
- `사립루레인학원 시리즈`
- `소공자 가출사건`
- `열다섯 번째 생일`
- `이웃집 그 녀석`
- `준장 로사 카니발` CID `108024`, `110456`, `110873`, `115419`
- `최종진화소년`
- `킬리만자로의 마법종합학교`
- `하이퍼 서퍼 벤젠스` CID `313547`

### 2026-05-14 엄격 확정명 기준 적용

사용자 확정 기준:

- 현재 목표는 조원재 담당 소설 기준 `1개 작품 = 1개 CID`다.
- 웹툰/2차 IP, `[특수]`, `[추후처리]`, 번들 분해 후보는 엄격 확정 대상에서 제외한다.
- 대표 CID는 S2 지급정산 정보가 있어야 한다.
- IPS 콘텐츠명이 `{작품}_{작가}_{바로북저작권코드}_{바로북선인세코드}_확정` 형태가 아니면 엄격 확정으로 인정하지 않는다.
- 선인세코드가 없는 경우 현재 명명값은 `선인세없음`을 사용한다.

처리:

- 아래 8개 CID는 라이브 IPS rename을 완료했다.
- dry-run 결과 `ready_api` 8건, write 결과 `updated` 8건, 재검증 dry-run 결과 `already_named` 8건.
- `0513_temp/build_cid_trust_inventory.py`의 `즉시사용` 판정도 엄격 확정명 일치가 필요하도록 변경했다.
- 실행 계획: `0513_temp/ips_strict_confirmed_rename_plan_20260514.csv`
- 결과 로그:
  - `0513_temp/exports/ips_strict_confirmed_rename_dryrun_20260514.csv`
  - `0513_temp/exports/ips_strict_confirmed_rename_write_20260514.csv`
  - `0513_temp/exports/ips_strict_confirmed_rename_verify_20260514.csv`

엄격 확정명으로 변경 완료:

- CID `111922`: `나는 작가다_정현우_1004674_선인세없음_확정`
- CID `323106`: `드래곤 잡으려다 내가 잡힘_지미신_1005414_1057_확정`
- CID `247320`: `아포칼립스인데 나 혼자 농사_지미신_1004918_886_확정`
- CID `324335`: `야한 규칙으로 다 따먹음_쓰고또쓰고_1005688_선인세없음_확정`
- CID `323531`: `야한 연극의 TS 주인공이 되었다_쓰고또쓰고_1005668_선인세없음_확정`
- CID `325672`: `야한 회사에서 대박남_쓰고또쓰고_1005741_선인세없음_확정`
- CID `110079`: `용사무적_정현우_1002935_238_확정`
- CID `325675`: `조금은 야한 우리 회사_쓰고또쓰고_1005747_선인세없음_확정`

### 2026-05-14 live IPS 제목 조회 기준 추가

사용자 지적:

- 엄격 확정은 대표 CID명만 맞는 것이 아니라, 같은 작품명이 다른 CID나 번들명에 숨어 있지 않아야 한다.
- 매번 IPS 엑셀을 수동 다운로드하지 않고, 중간중간 live IPS 조회로 확인한다.
- 단, `[사용안함]`/`(사용안함)`으로 죽여 둔 CID는 살아있는 중복 후보로 세지 않는다.
- 목적은 `1개 작품 = 1개 살아있는 대표 CID`를 확정하는 것이며, 사용안함 CID는 잔여 정산/이력 정리 대상으로만 본다.

처리:

- `ips_live_lookup.py`를 추가했다.
- live 목록 API는 `/cntsd/cntschg/ctns-chg-list`이고, 콘텐츠명 검색 파라미터는 `srcCtnsNm`이다.
- `ips_live_lookup.py` 출력에 `disabled_marker`, `active_candidate` 컬럼을 추가했다.
- 산출물:
  - `0513_temp/exports/ips_live_title_lookup_strict8_20260514.csv`
  - `0513_temp/exports/ips_live_title_lookup_strict8_script_20260514.csv`
  - `0513_temp/exports/ips_live_title_lookup_strict8_active_20260514.csv`

live 제목 조회 결과:

- 살아있는 후보 기준 엄격 확정 8건:
  - `나는 작가다` -> active CID `111922`. disabled CID `109750`은 중복으로 세지 않음.
  - `드래곤 잡으려다 내가 잡힘` -> active CID `323106`.
  - `아포칼립스인데 나 혼자 농사` -> active CID `247320`. disabled CID `110024`는 중복으로 세지 않음.
  - `야한 규칙으로 다 따먹음` -> active CID `324335`.
  - `야한 연극의 TS 주인공이 되었다` -> active CID `323531`.
  - `야한 회사에서 대박남` -> active CID `325672`.
  - `용사무적` -> active CID `110079`. disabled CID `110842`, `114786`은 중복으로 세지 않음.
  - `조금은 야한 우리 회사` -> active CID `325675`.

판정:

- 위 8건은 live IPS 조회 기준으로도 `1개 작품 = 1개 살아있는 대표 CID`가 성립하므로 엄격 확정으로 본다.
- 사용안함 CID가 함께 조회되는 경우는 엄격 확정 탈락 사유가 아니라, 잔여 정산/과거 이력/죽인 후보 확인용 신호로만 둔다.

### 2026-05-14 엄격 확정 전체 live 감사

사용자 질문:

- 방금 처리한 8건뿐 아니라, 현재 `엄격 확정`이라고 부르는 전체가 진짜 엄격 확정인지 확인해야 한다.

감사 기준:

- 대상: `latest__account_ips_cid_seed_조원재.csv`의 seed 중 `out_of_scope`, `special_hold`, `defer_hold` 등 명시 제외를 뺀 242개 seed.
- live IPS 조회: `/cntsd/cntschg/ctns-chg-list?srcCtnsNm=...`
- 통과 조건:
  - live IPS에서 같은 작품 세그먼트의 살아있는 소설 CID가 정확히 1개여야 한다.
  - `[사용안함]`, `[정산정보없음]`, `[특수]`, `[추후처리]`는 살아있는 후보로 세지 않는다.
  - 그 1개 CID명이 `{작품}_{작가}_{저작권코드}_{선인세코드/선인세없음}_확정`과 정확히 일치해야 한다.
  - 해당 CID에 S2 지급정산 행이 있어야 한다.

산출물:

- `0513_temp/audit_strict_confirmed_live.py`
- `0513_temp/exports/ips_strict_confirmed_live_audit_조원재_20260514.csv`
- `0513_temp/exports/ips_strict_confirmed_live_audit_조원재_20260514.json`

초기 결과:

- `strict_confirmed`: 96건
- `strict_name_not_found`: 107건
- `no_active_candidate`: 33건
- `active_collision`: 6건

초기 판정:

- 현재 전체 seed 중 live IPS와 S2까지 함께 증명되는 진짜 엄격 확정은 96건이다.
- 나머지는 엄격 확정으로 부르면 안 된다.
- 가장 큰 탈락 유형은 기존 IPS명이 `_미연결_확정`으로 남아 있거나, seed가 요구하는 저작권/선인세코드와 live IPS명이 다르거나, 아직 번들/구형명/후보없음 상태인 경우다.
- `active_collision` 6건은 살아있는 소설 후보가 2개 이상이라 엄격 확정에서 제외한다:
  - `SM클럽`
  - `SSS급 천재`
  - `네임드`
  - `네임드 플레이어`
  - `달인`
  - `보스 몹이 너무 강함`

### 2026-05-14 번들명 prune 처리

사용자 확정:

- 번들은 통째로 죽이지 않는다.
- 이미 개별 엄격 확정 CID가 살아있는 작품명만 번들명에서 뺀다.
- 아직 분해/보정 전인 작품명은 번들명에 남긴다.

처리:

- CID `319513`
  - 변경 전: `0_네임드·네임드 플레이어·망한 세상에서 나 혼자 각성·보스 몹이 너무 강함·사이코패스 살인마는 살고 싶다_민작가_일반`
  - 변경 후: `0_망한 세상에서 나 혼자 각성·사이코패스 살인마는 살고 싶다_민작가_일반`
- 번들에서 제거한 작품:
  - `네임드`
  - `네임드 플레이어`
  - `보스 몹이 너무 강함`
- 번들에 남긴 작품:
  - `망한 세상에서 나 혼자 각성`
  - `사이코패스 살인마는 살고 싶다`

산출물:

- 실행 계획: `0513_temp/ips_bundle_prune_rename_plan_20260514.csv`
- dry-run: `0513_temp/exports/ips_bundle_prune_rename_dryrun_20260514.csv`
- write: `0513_temp/exports/ips_bundle_prune_rename_write_20260514.csv`
- verify: `0513_temp/exports/ips_bundle_prune_rename_verify_20260514.csv`

검증:

- dry-run 결과: `ready_api` 1건
- write 결과: `updated` 1건
- 재검증 결과: `already_named` 1건

번들 prune 후 전체 live 감사 결과:

- `strict_confirmed`: 99건
- `strict_name_not_found`: 107건
- `no_active_candidate`: 33건
- `active_collision`: 3건

변화:

- 엄격 확정: `96 -> 99`
- 살아있는 후보 충돌: `6 -> 3`
- 이번 처리로 `네임드`, `네임드 플레이어`, `보스 몹이 너무 강함`은 엄격 확정으로 승격됐다.

남은 `active_collision` 3건:

- `SM클럽`: active CID `323103 | 107777`
- `SSS급 천재`: active CID `111189 | 110669`
- `달인`: active CID `327817 | 314718`

### 2026-05-14 자동 엄격명 rename 37건 및 충돌 제거

사용자 지시:

- 자동 rename 37건은 판단 필요 없이 실제 IPS rename 처리한다.
- 남은 충돌 후보는 대표 CID를 살리고 중복 CID에 `[사용안함]` 표식을 붙인다.
- IPS rename 처리가 불가하면 GitHub issue에 메모를 남긴다.

자동 엄격명 rename 37건:

- 조건: 살아있는 CID 1개, S2 지급정산 있음, 저작권코드 같음, 작가 같음, 현재명만 `_미연결_확정`.
- 변경: `{작품}_{작가}_{저작권코드}_미연결_확정` -> `{작품}_{작가}_{저작권코드}_선인세없음_확정`
- 실행 계획: `0513_temp/ips_auto_strict37_rename_plan_20260514.csv`
- dry-run: `0513_temp/exports/ips_auto_strict37_rename_dryrun_20260514.csv`
- write: `0513_temp/exports/ips_auto_strict37_rename_write_20260514.csv`
- verify: `0513_temp/exports/ips_auto_strict37_rename_verify_20260514.csv`
- 결과: dry-run `ready_api` 37건, write `updated` 37건, verify `already_named` 37건.

충돌 제거 3건:

- CID `323103`: `SM클럽` -> `[사용안함]_SM클럽`
- CID `110669`: `[카카오]SSS급 천재` -> `[사용안함]_[카카오]SSS급 천재`
- CID `314718`: `달인` -> `[사용안함]_달인`
- 실행 계획: `0513_temp/ips_active_collision_disable_rename_plan_20260514.csv`
- dry-run: `0513_temp/exports/ips_active_collision_disable_rename_dryrun_20260514.csv`
- write: `0513_temp/exports/ips_active_collision_disable_rename_write_20260514.csv`
- verify: `0513_temp/exports/ips_active_collision_disable_rename_verify_20260514.csv`
- 결과: dry-run `ready_api` 3건, write `updated` 3건, verify `already_named` 3건.
- CID `314718`은 담당자명이 `김성경`으로 조회되어, 사용자 명시 지시에 따라 manager check를 해제하고 처리했다.

최종 live 감사 결과:

- `strict_confirmed`: 139건
- `strict_name_not_found`: 70건
- `no_active_candidate`: 33건
- `active_collision`: 0건

변화:

- 엄격 확정: `99 -> 139`
- 살아있는 후보 충돌: `3 -> 0`
- 이번 rename은 전부 성공했으므로 GitHub issue 메모는 생성하지 않았다.

### 2026-05-14 엄격명 불일치 70건 triage

사용자 지적:

- 남은 엄격명 불일치 70건은 자동 rename 대상이 아니다.
- 필명/동명이인/작가코드/제목/선인세가 섞여 있으므로 먼저 후보를 더 줄여야 한다.
- `미스터 프레지던트 2부`처럼 `하늘곰` vs `박천웅`이 섞인 건 자동 처리 금지다.

처리:

- IPS rename은 추가 실행하지 않았다.
- 남은 `strict_name_not_found` 70건을 사유별로 분류하는 triage 스크립트와 보고서를 만들었다.
- 스크립트: `0513_temp/triage_strict_name_mismatches.py`
- CSV: `0513_temp/exports/ips_strict_name_mismatch_triage_조원재_20260514.csv`
- MD: `0513_temp/exports/ips_strict_name_mismatch_triage_조원재_20260514.md`

분류 요약:

- `복수권리행/권리+선인세불일치`: 24건
- `권리+선인세불일치`: 8건
- `복수권리행/제목불일치`: 8건
- `선인세코드불일치`: 7건
- `번들잔존`: 5건
- `제목불일치`: 4건
- `타담당구형명`: 4건
- `복수권리행/권리코드불일치`: 3건
- `복수권리행/작가불일치`: 2건
- `작가불일치`: 2건
- `복수권리행/기타`: 2건
- `권리코드불일치`: 1건

작가/필명 확인이 필요한 대표 예시:

- `미스터 프레지던트 2부`: 기대 `박천웅`, live CID `311615`은 `하늘곰`.
- `섹스마스터가 되어 다 따먹기`: 기대 `빨간홍차`, live CID `320955`은 `아즐란`.
- `여자들이 집착하는 축구 선수가 되었다`: 기대 `민작가`, live CID `320890`은 `쓰고또쓰고`.

다음 원칙:

- 남은 70건은 사용자가 한 번에 판단할 대상이 아니다.
- 먼저 `복수권리행`을 같은 작품별로 접어서 대표 권리/선인세 구조를 줄인다.
- 그 다음 `작가불일치`만 별도 필명/동명이인 큐로 뽑는다.
- title punctuation 차이만 있는 `제목불일치`도 선별 후 별도 자동 rename 후보로 승격한다.

### 2026-05-14 살아있는 후보 없음 33건 부활 후보 triage

사용자 원칙:

- `no_active_candidate` 33건은 지금 건드리지 않는다.
- rename으로 바로 해결되는 영역이 아니다.
- 후속 단계에서 신규 CID 생성, 사용안함 부활, S2/IPS 보정, no-action 중 하나로 판단한다.
- 사용안함 부활은 S2 지급정산이 있고 가장 멀쩡한 후보를 우선 고려한다.

처리:

- IPS rename/write는 실행하지 않았다.
- `no_active_candidate` 33 seed 행을 trust inventory와 결합해 부활 후보를 따로 분류했다.
- 스크립트: `0513_temp/triage_no_active_revival_candidates.py`
- 요약 CSV: `0513_temp/exports/ips_no_active_revival_triage_조원재_20260514.csv`
- 후보 상세 CSV: `0513_temp/exports/ips_no_active_revival_candidates_조원재_20260514.csv`
- MD: `0513_temp/exports/ips_no_active_revival_triage_조원재_20260514.md`

분류 요약(seed 행 기준):

- `부활불필요_정상후보있음`: 20건
- `부활검토_사용안함_S2_단일`: 7건
- `분해후_부활검토_사용안함_S2_번들`: 5건
- `S2보정검토`: 1건

분류 요약(작품 기준):

- `부활불필요_정상후보있음`: 19작품
- `부활검토_사용안함_S2_단일`: 5작품
- `분해후_부활검토_사용안함_S2_번들`: 3작품
- `S2보정검토`: 1작품

부활/분해 검토 우선 후보:

- 단일 사용안함 부활 검토:
  - `늙은 경비에게 조교당하는 스튜어디스의 이야기`: CID `109326`, S2 8행
  - `독식하는 재벌 3세`: CID `111006`, S2 15행
  - `드래곤 엔터테인먼트`: CID `112663`, S2 23행
  - `미스터 프레지던트`: CID `112350`, S2 7행
  - `사립루레인학원 시리즈`: CID `109514`, S2 4행
- 번들 분해 후 부활 검토:
  - `다따먹PD가 됨`: CID `326352`, S2 8행
  - `시간의 마에스트로`: CID `320961`, S2 132행
  - `연봉 1조 신입사원`: CID `320961`, S2 132행

주의:

- `부활불필요_정상후보있음` 20건은 exact 감사에서는 후보 없음처럼 보였지만, trust inventory에는 S2 있는 정상/수동흡수 후보가 있다. 이쪽은 부활보다 제목/띄어쓰기/오타/개명 정리가 먼저다.
- `미스터 프레지던트`는 추천 CID가 `[사용안함]_미스터 프레지던트 2부_하늘곰`이라, 박천웅/하늘곰 필명 또는 동명이인 확인 전 부활 금지다.

### 2026-05-14 엄격 확정 적대적 감리 2차

사용자 지시:

- `strict_confirmed` 139건을 그대로 믿지 말고 false positive가 있는지 적대적으로 감리한다.
- 엄격 확정으로 진짜 확정할 수 있는 것과, 남은 잔여 작업 목록을 분리한다.

처리:

- IPS rename/write는 실행하지 않았다.
- live 감사 결과의 `strict_confirmed` 139건을 대상으로 아래를 재검증했다.
  - strict CID 중복 여부
  - 같은 작품의 미해결 seed 잔존 여부
  - S2 지급정산 제목에 작품명 근거가 있는지
  - `0513_temp/data/IPS.xlsx`에 오늘 live rename 로그를 overlay한 뒤, local 전체 IPS 기준 숨어 있는 active 중복/근접 후보가 있는지
- 스크립트:
  - `0513_temp/adversarial_audit_strict_confirmed.py`
  - `0513_temp/build_remaining_worklist_after_strict_audit.py`

산출물:

- 적대감리 상세: `0513_temp/exports/ips_strict_confirmed_adversarial_audit2_조원재_20260514.csv`
- 진짜 엄격 확정: `0513_temp/exports/ips_strict_confirmed_final_조원재_20260514.csv`
- 잔여 작업 CSV: `0513_temp/exports/ips_remaining_worklist_after_strict_audit_조원재_20260514.csv`
- 잔여 작업 MD: `0513_temp/exports/ips_remaining_worklist_after_strict_audit_조원재_20260514.md`

결과:

- 입력 `strict_confirmed`: 139건
- 최종 `final_strict_confirmed`: 117건
- `row_strict_but_work_pending`: 21건
- `row_strict_review_variant`: 1건
- 강한 false positive blocker: 0건

해석:

- 117건은 현재 기준으로 “진짜 엄격 확정”으로 고정한다.
- 21건은 CID 자체는 엄격명/S2/active uniqueness를 통과했지만, 같은 작품에 미해결 seed가 남아 있어 작품 단위 최종 확정으로 승격하지 않는다.
- 1건 `무림영웅 때려칩니다`은 local IPS에 `무림영웅 때려칩니다 1권` 근접 후보가 있어 확인 전 최종 확정에서 보류한다.

잔여 작업 목록 총괄:

- `엄격확정_적대감리보류`: 22건
- `엄격명_불일치`: 70건
- `살아있는_후보없음`: 33건
- 총 잔여: 125건

잔여 작업 상위 분류:

- `복수권리행/권리+선인세불일치`: 24건
- `row_strict_but_work_pending`: 21건
- `부활불필요_정상후보있음`: 20건
- `권리+선인세불일치`: 8건
- `복수권리행/제목불일치`: 8건
- `선인세코드불일치`: 7건
- `부활검토_사용안함_S2_단일`: 7건
- `번들잔존`: 5건
- `분해후_부활검토_사용안함_S2_번들`: 5건

다음 작업 원칙:

- `final_strict_confirmed` 117건은 더 이상 판단 대상으로 던지지 않는다.
- 잔여 125건은 위 잔여 작업표 기준으로만 처리한다.
- 가장 먼저 할 일은 `부활불필요_정상후보있음`과 `제목불일치`를 합쳐, 제목/띄어쓰기/오타 rename 후보를 따로 뽑는 것이다.

### 2026-05-14 쉬운 확정 증분 처리 및 적대 감리 3회 최신

사용자 지시:

- 판단 거의 필요 없는 쉬운 건은 먼저 처리한다.
- 쉬운 건이 더 없으면 적대적 감리 3회를 돌려 현재 상태를 고정한다.
- 목표는 계속 `조원재 담당 소설 1작품 = 1 엄격 CID`이다.
- 웹툰/2차 IP, `[특수]`, `[추후처리]`, `[사용안함]` 처리된 죽은 후보는 살아있는 중복으로 세지 않는다.

실제 처리:

- 대표 CID가 이미 있는 미해결 seed 35건을 `covered_by_representative`로 닫았다.
  - 스크립트: `0513_temp/apply_easy_seed_closures.py`
  - 결과: `0513_temp/exports/ips_easy_seed_closures_added_조원재_20260514.csv`
- 사용자 수동 assign 중 이미 최종 엄격 CID와 일치하는 3건을 대표 흡수로 닫았다.
  - `골 떄리는 비제이들` -> `골 때리는 여자 비제이들` CID `320888`
  - `타락의 검은실 2부` -> `타락의 검은 실` CID `107843`
  - `하이퍼 서버 벤젠스` -> `하이퍼 서퍼 벤젠스` CID `327958`
  - 스크립트: `0513_temp/apply_manual_assign_final_closures.py`
  - 결과: `0513_temp/exports/ips_manual_assign_final_closures_added_조원재_20260514.csv`
- 제목/띄어쓰기/미연결 보정 자동 rename 9건을 IPS에 실제 적용했다.
  - plan: `0513_temp/ips_easy_title_rename_plan_20260514.csv`
  - dry-run: `0513_temp/exports/ips_easy_title_rename_dryrun_20260514.csv` (`ready_api` 9)
  - write: `0513_temp/exports/ips_easy_title_rename_write_20260514.csv` (`updated` 9)
  - verify: `0513_temp/exports/ips_easy_title_rename_verify_20260514.csv` (`already_named` 9)
- 사용안함 단일 부활 중 안전한 1건만 IPS에 실제 적용했다.
  - CID `109326`
  - 변경 전: `[사용안함]_늙은 경비에게 조교당하는 스튜어디스_푸른산붉은꽃`
  - 변경 후: `늙은 경비에게 조교당하는 스튜어디스의 이야기_푸른산붉은꽃_1004944_873_확정`
  - plan: `0513_temp/ips_easy_single_revival_plan_20260514.csv`
  - dry-run: `0513_temp/exports/ips_easy_single_revival_dryrun_20260514.csv` (`ready_api` 1)
  - write: `0513_temp/exports/ips_easy_single_revival_write_20260514.csv` (`updated` 1)
  - verify: `0513_temp/exports/ips_easy_single_revival_verify_20260514.csv` (`already_named` 1)

감리 스크립트 보정:

- `0513_temp/adversarial_audit_strict_confirmed.py`
  - title overlay가 `rename` 로그뿐 아니라 `revival` 로그도 읽도록 수정.
  - dry-run의 `ready_api`는 더 이상 적용 증거로 보지 않고, `updated`/`already_named`만 반영.
  - `covered_by_representative`, `special_hold`, `defer_hold`, `out_of_scope`, `not_owner`, `exclude` CID는 살아있는 중복 후보에서 제외.
  - 사용자 수동 `assign`/`keep`/`revive` seed는 S2 파일의 제목이 구명칭이어도 제목 근거 부족 blocker로 보지 않음.

최신 숫자:

- live audit target works: 191
- live `strict_confirmed`: 149 seed
- 적대 감리 통과 `final_strict_confirmed`: 149 작품
- 남은 작품: 42
- 잔여 row: 55
- 적대 감리 보류: 0건

추가 처리:

- `무림영웅 때려칩니다`의 근접 중복 후보 CID `322646`을 죽였다.
  - 변경 전: `무림영웅 때려칩니다 1권`
  - 변경 후: `[사용안함]_무림영웅 때려칩니다 1권`
  - dry-run: `0513_temp/exports/ips_disable_murim_1kwon_dryrun_skipmanager_20260514.csv` (`ready_api` 1)
  - write: `0513_temp/exports/ips_disable_murim_1kwon_write_20260514.csv` (`updated` 1)
  - verify: `0513_temp/exports/ips_disable_murim_1kwon_verify_20260514.csv` (`already_named` 1)
  - 참고: 해당 CID 담당자가 `김부용`으로 잡혀 있어 `--skip-manager-check`를 명시적으로 사용했다.

적대 감리 3회:

- 산출물: `0513_temp/exports/ips_adversarial_audit_3round_summary_조원재_20260514.csv`
- 1/2/3회 모두 동일:
  - `final_strict_confirmed=148`
  - `row_strict_review_variant=1`
  - `remaining_rows=56`
  - final CSV SHA256: `29ACB39DE4439D2621CD8EEB05FF51586B8706C4A60C0520B63BFFE809B774E6`

최신 잔여 버킷(작품 기준):

- `C_제목오타_개명_정리`: 13
- `D_사용안함_단일부활`: 4
- `E_사용안함_번들분해`: 3
- `F_필명_동명이인_확인`: 2
- `G_권리선인세_대표정리`: 10
- `H_번들잔존_분해`: 5
- `I_타담당_구형명`: 4
- `J_S2_IPS보정`: 1

남은 단일 부활 후보 중 자동 처리 금지:

- `독식하는 재벌 3세`: 사용자 담당은 맞지만 같은 CID `111006`에 권리/선인세 seed가 3개라 대표 권리/선인세 판단 필요.
- `드래곤 엔터테인먼트`: 복합 위험/담당 판단 필요.
- `미스터 프레지던트`: 추천 CID가 `[사용안함]_미스터 프레지던트 2부_하늘곰`이라 1부/2부/필명 혼선 정리 전 부활 금지.
- `사립루레인학원 시리즈`: 타담당/시리즈 구조 판단 필요.

현재 기준 다음 작업:

- 다음 쉬운 후보는 `C_제목오타_개명_정리` 13건이지만, 상당수는 개명/외전/원작/권리코드가 섞여 있어 사용자 판단 또는 추가 근거 축소 후 처리한다.
- 그 다음은 `G_권리선인세_대표정리` 10건. 특히 동일 CID가 여러 권리/선인세 seed에 걸리는 경우라, 엄격 확정명을 하나로 고르는 기준이 필요하다.

### 2026-05-14 C_제목오타_개명_정리 13건 처리 완료

사용자 결정:

- NAS/실제 판매 제목이 따로 있는 seed는 실제 판매 제목 쪽 대표 CID로 흡수한다.
- 카카오MG/일반 갈래가 섞인 경우 카카오가 아닌 대표명 하나로 접는다.
- `핵무기도 만들어 드릴까요`는 연재/단행/개편/외전/본편을 구분하지 않고 1개 CID로 통일한다.
- `슈퍼스타, 누구도 막을 수 없어`의 `구라천재`/`말리브해적`은 동일인물로 보고 `구라천재` 대표명으로 통일한다.
- `[원작]아버지가 남긴 USB`는 웹툰/원작 계열 `[특수]` 보류로 넘긴다.
- `다따먹점혈법`은 개별 CID가 없으므로 `<탄마 성인 3질(미정)>` 번들/placeholder CID를 뺏어 대표 CID로 확정한다.
- `소공자 가출사건`은 조원재 담당은 아니지만 IPS 제목은 정상 엄격명으로 복구하고, 조원재 target에서는 제외한다.
- `스킬스 - 현대편`, `어서 와, 마왕은 처음이지`는 카카오가 아닌 쪽 대표명으로 정리한다.

IPS 실제 rename:

- plan: `0513_temp/ips_c_title_user_decisions_rename_plan_20260514.csv`
- dry-run: `0513_temp/exports/ips_c_title_user_decisions_dryrun_20260514.csv`
  - `ready_api`: 8
  - `skipped_unexpected_manager`: 1 (`소공자 가출사건`, 담당자 `김정원`)
- skip-manager dry-run: `0513_temp/exports/ips_c_title_user_decisions_dryrun_skipmanager_20260514.csv` (`ready_api` 9)
- write: `0513_temp/exports/ips_c_title_user_decisions_write_20260514.csv` (`updated` 9)
- verify: `0513_temp/exports/ips_c_title_user_decisions_verify_20260514.csv` (`already_named` 9)

rename 적용 목록:

- `슈퍼스타, 누구도 막을 수 없어!!!!!!_구라천재_1003257_471_확정`
  -> `슈퍼스타, 누구도 막을 수 없어_구라천재_1003257_471_확정`
- `유산 받아 레벨 업!_북홀릭_1002962_289_확정`
  -> `유산 받아 레벨 업_북홀릭_1002962_289_확정`
- `핵무기도 만들어 드릴까요?_북홀릭_1003122_804_확정`
  -> `핵무기도 만들어 드릴까요_북홀릭_1003122_804_확정`
- `스킬스 현대편_서오_1005190_1021_확정`
  -> `스킬스 - 현대편_서오_1005190_1021_확정`
- `어서 와, 마왕은 처음이지?_하늘곰_1004931_867_확정`
  -> `어서 와, 마왕은 처음이지_하늘곰_1004931_867_확정`
- `외도 전설 -마법소녀 조교기-_외도정사_1004943_1010_확정`
  -> `외도 전설 -마법소녀 조교기_외도정사_1004943_선인세없음_확정`
- `패배 용사 - 약골 용사의 에로 대모험!_외도정사_1004943_1010_확정`
  -> `패배 용사 - 약골 용사의 에로 대모험_외도정사_1004943_선인세없음_확정`
- `<탄마 성인 3질(미정)>`
  -> `다따먹점혈법_탄마_1005630_1132_확정`
- `0_소공자가출사건_지미신_일반`
  -> `소공자 가출사건_지미신_1003119_선인세없음_확정`

수동 결정 기록:

- 스크립트: `0513_temp/apply_c_title_user_decisions_20260514.py`
- 추가 CSV: `0513_temp/exports/ips_c_title_user_decisions_manual_added_조원재_20260514.csv`
- 추가 수동 결정: 12건
  - NAS/실판매명 대표 흡수: `NTR당한 암컷용사는 모자상간으로 복수한다`, `보수적이라며 팬티는 왜 벗어`
  - 본편 대표 흡수: `핵무기도 만들어 드릴까요 외전`
  - 원작/웹툰 특수 보류: `[원작]아버지가 남긴 USB`
  - 담당 제외: `소공자 가출사건`
  - 비카카오 대표 흡수: `슈퍼스타`, `유산`, `핵무기`, `스킬스 - 현대편`, `어서 와, 마왕은 처음이지`의 카카오/갈래 seed
- `다따먹점혈법` S2 제목이 `<탄마 성인 3질(미정)>`로 남아 있어 적대감리에서 보수 차단되었고, 사용자 확정에 따라 대표 근거를 추가했다.
  - 스크립트: `0513_temp/apply_datameok_bundle_take_decision.py`
  - 추가 CSV: `0513_temp/exports/ips_datameok_bundle_take_decision_added_조원재_20260514.csv`

최신 숫자:

- live audit target works: 185
- live `strict_confirmed`: 156 seed
- 적대 감리 통과 `final_strict_confirmed`: 156 작품
- 적대 감리 보류: 0건
- 남은 작품: 29
- 잔여 row: 36
- `C_제목오타_개명_정리`: 0건

최신 잔여 버킷(작품 기준):

- `D_사용안함_단일부활`: 4
- `E_사용안함_번들분해`: 3
- `F_필명_동명이인_확인`: 2
- `G_권리선인세_대표정리`: 10
- `H_번들잔존_분해`: 5
- `I_타담당_구형명`: 4
- `J_S2_IPS보정`: 1

## 관련 스크립트

- `SIAANE_v2/build_manager_author_ssot.py`
- `SIAANE_v2/account/build_account_observation_bundle.py`
- `SIAANE_v2/account/build_account_decision_queue.py`
- `SIAANE_v2/account/build_account_rights_canonical.py`
- `SIAANE_v2/account/apply_account_author_review_decisions.py`
- `SIAANE_v2/account/apply_account_name_review_bulk_approval.py`
- `SIAANE_v2/account/apply_account_work_review_defer.py`
- `SIAANE_v2/crosswalk/build_account_ips_cid_seed.py`
- `SIAANE_v2/crosswalk/build_account_cid_split_review_queue.py`
- `SIAANE_v2/crosswalk/build_account_ips_action_queue.py`
- `SIAANE_v2/crosswalk/apply_account_cid_split_bulk_approval.py`
- `SIAANE_v2/crosswalk/apply_account_cid_split_auto_approval.py`
- `SIAANE_v2/crosswalk/apply_account_cid_split_manual_decisions.py`
- `SIAANE_v2/account/notes/manual_special_overrides.json`
- `SIAANE_v2/account/notes/manual_work_scope_overrides.json`
- `SIAANE_v2/account/notes/manual_cid_seed_work_overrides.json`
- `SIAAN Project/download_cp_exception_share_rates.py`

### 2026-05-14 G 외도정사 1010 -> 선인세없음 7건 처리 완료

사용자 확인:

- `1010`은 선인세 금액이 없어서 생긴 대표 선인세 코드가 아니라, 기존 IPS/S2 콘텐츠명에 남아 있던 구형/오염된 엄격명 조각으로 판단한다.
- 원천 seed의 `연결_선인세코드`는 빈 값이고, `account/special_evidence`도 `연결선인세없음`으로 잡힌다.

IPS 실제 rename:

- plan: `0513_temp/ips_g_oedo_advance_rename_plan_20260514.csv`
- dry-run: `0513_temp/exports/ips_g_oedo_advance_rename_dryrun_20260514.csv` (`ready_api` 7)
- write: `0513_temp/exports/ips_g_oedo_advance_rename_write_20260514.csv` (`updated` 7)
- verify: `0513_temp/exports/ips_g_oedo_advance_rename_verify_20260514.csv` (`already_named` 7)

처리 목록:

- `TS 에로 게임 탈출기_외도정사_1004943_1010_확정` -> `TS 에로 게임 탈출기_외도정사_1004943_선인세없음_확정`
- `귀축기담_외도정사_1004943_1010_확정` -> `귀축기담_외도정사_1004943_선인세없음_확정`
- `무능 귀족 여체 하렘_외도정사_1004943_1010_확정` -> `무능 귀족 여체 하렘_외도정사_1004943_선인세없음_확정`
- `무인도 하렘 생활기_외도정사_1004943_1010_확정` -> `무인도 하렘 생활기_외도정사_1004943_선인세없음_확정`
- `서큐버스 하렘_외도정사_1004943_1010_확정` -> `서큐버스 하렘_외도정사_1004943_선인세없음_확정`
- `아버지가 남긴 USB_외도정사_1004943_1010_확정` -> `아버지가 남긴 USB_외도정사_1004943_선인세없음_확정`
- `야설로 보는 그리스 로마 신화_외도정사_1004943_1010_확정` -> `야설로 보는 그리스 로마 신화_외도정사_1004943_선인세없음_확정`

최신 숫자:

- live audit target works: 185
- live `strict_confirmed`: 163 seed
- 적대 감리 통과 `final_strict_confirmed`: 163 작품
- 적대 감리 보류: 0건
- 남은 작품: 22
- 잔여 row: 29

최신 잔여 버킷(작품 기준):

- `D_사용안함_단일부활`: 4
- `E_사용안함_번들분해`: 3
- `F_필명_동명이인_확인`: 2
- `G_권리선인세_대표정리`: 3
- `H_번들잔존_분해`: 5
- `I_타담당_구형명`: 4
- `J_S2_IPS보정`: 1

### 2026-05-14 G alias/code 3건 처리 완료

사용자 결정:

- `류화수`, `서오`, `알렌`은 같은 사람으로 본다.
- `스킬스`, `현자귀환`은 카카오MG 갈래를 대표로 살리지 않고 일반 `1005190_1021` 대표명으로 통일한다.
- `코드네임 사신`의 올바른 저작권코드는 `1003575`이다.

IPS 실제 rename:

- plan: `0513_temp/ips_g_alias_code_rename_plan_20260514.csv`
- dry-run: `0513_temp/exports/ips_g_alias_code_rename_dryrun_20260514.csv` (`ready_api` 3)
- write: `0513_temp/exports/ips_g_alias_code_rename_write_20260514.csv` (`updated` 3)
- verify: `0513_temp/exports/ips_g_alias_code_rename_verify_20260514.csv` (`already_named` 3)

처리 목록:

- `스킬스_류화수_1005190_1021_확정` -> `스킬스_서오_1005190_1021_확정`
- `현자귀환_알렌_1005190_1021_확정` -> `현자귀환_서오_1005190_1021_확정`
- `코드네임 사신_준강_1003576_818_확정` -> `코드네임 사신_준강_1003575_818_확정`

수동 결정 기록:

- 스크립트: `0513_temp/apply_g_alias_code_user_decisions_20260514.py`
- 추가 CSV: `0513_temp/exports/ips_g_alias_code_manual_added_조원재_20260514.csv`
- 추가 수동 결정: 2건
  - `스킬스_서오_869_카카오MG_1004823_유동우_N` -> 일반 대표 CID `318934`로 흡수
  - `현자귀환_서오_869_카카오MG_1004823_유동우_Y` -> 일반 대표 CID `318392`로 흡수

최신 숫자:

- live audit target works: 185
- live `strict_confirmed`: 166 seed
- 적대 감리 통과 `final_strict_confirmed`: 166 작품
- 적대 감리 보류: 0건
- 남은 작품: 19
- 잔여 row: 24
- `G_권리선인세_대표정리`: 0건

최신 잔여 버킷(작품 기준):

- `D_사용안함_단일부활`: 4
- `E_사용안함_번들분해`: 3
- `F_필명_동명이인_확인`: 2
- `H_번들잔존_분해`: 5
- `I_타담당_구형명`: 4
- `J_S2_IPS보정`: 1

### 2026-05-14 quick win revival/dedupe 3건 처리 완료

사용자 결정/확인:

- `다따먹PD가 됨`은 신규 CID 생성 대상이 아니라, 남은 탄마 3작품 번들 껍데기 CID `326352`를 대표 CID로 부활한다.
  - live 확인 기준 `다따먹점혈법`은 CID `278175`, `무림누나 능욕게임`은 CID `327814`로 이미 각각 엄격 확정되어 있다.
- `독식하는 재벌 3세`는 카카오MG/카카오창작지원금 갈래를 대표로 살리지 않고, 비카카오/비웹툰 대표 `1005739_1021`로 확정한다.
  - CID `111006`의 live 담당자는 `이선근`이지만 사용자 확정상 조원재 담당이어야 하는 작품이므로, 담당자 polishing 전이라도 엄격 확정으로 센다.
- `혜정이의 야한 이야기`는 조원재 담당 CID `322540`을 대표로 살리고, 김부용/운영팀 구형 빈 작가 CID `322745`는 중복 사용안함 처리한다.
  - `파워레인젖 = 쓰고또쓰고 = 유승표` 동치 규칙을 적용한다.

IPS 실제 rename:

- plan: `0513_temp/ips_quickwin_revival_rename_plan_20260514.csv`
- dry-run: `0513_temp/exports/ips_quickwin_revival_rename_dryrun_20260514.csv` (`ready_api` 2)
- write: `0513_temp/exports/ips_quickwin_revival_rename_write_20260514.csv` (`updated` 2)
- live verify: `0513_temp/exports/live_lookup_quickwin_revival_verify_20260514.json`
- `혜정이` plan: `0513_temp/ips_hyejeong_dedupe_rename_plan_20260514.csv`
- `혜정이` dry-run: `0513_temp/exports/ips_hyejeong_dedupe_rename_dryrun_20260514.csv` (`ready_api` 2)
- `혜정이` write: `0513_temp/exports/ips_hyejeong_dedupe_rename_write_20260514.csv` (`updated` 2)
- `혜정이` live verify: `0513_temp/exports/live_lookup_hyejeong_dedupe_verify_20260514.json`

처리 목록:

- `326352`: `[사용안함]_다따먹PD가됨_다따먹점혈법_무림누나능욕게임_탄마`
  -> `다따먹PD가 됨_탄마_1005760_1179_확정`
- `111006`: `(사용안함)_독식하는 재벌 3세·서오_중복`
  -> `독식하는 재벌 3세_서오_1005739_1021_확정`
- `322540`: `0_혜정이의 야한 이야기_파워레인젖_일반`
  -> `혜정이의 야한 이야기_쓰고또쓰고_1005488_1130_확정`
- `322745`: `혜정이의 야한 이야기`
  -> `[사용안함]_혜정이의 야한 이야기`

수동 결정 기록:

- `manual_cid_decisions_20260513.csv`에 `다따먹PD가 됨`, `독식하는 재벌 3세` 대표 확정 행을 추가했다.
- `독식하는 재벌 3세_서오_869_카카오MG_1004823_유동우_N`은 대표 CID `111006`으로 흡수 처리했다.
- `독식하는 재벌 3세_서오_선인세없음_일반_1005344_유동우_Y`는 SIAAN Project 근거상 카카오창작지원금 계열로 보고 대표 CID `111006`으로 흡수 처리했다.
- `혜정이의 야한 이야기` 대표 CID `322540` 확정 및 중복 CID `322745` 사용안함 처리 근거를 추가했다.
- `audit_strict_confirmed_live.py`는 `assign/owner_confirmed/revive` 수동 결정 seed에 한해 live 담당자 mismatch를 엄격 확정 차단 사유로 보지 않도록 좁게 보정했다.

최신 숫자:

- target works: 185
- 적대 감리 통과 `final_strict_confirmed`: 169 작품
- 적대 감리 보류: 0건
- 남은 작품: 16
- 잔여 seed row: 19

최신 잔여 버킷(작품 기준):

- `D_사용안함_단일부활`: 3
- `E_사용안함_번들분해`: 2
- `F_필명_동명이인_확인`: 2
- `H_번들잔존_분해`: 5
- `I_타담당_구형명`: 3
- `J_S2_IPS보정`: 1

### 2026-05-14 서오 `320961` 번들 분해 방향 확정

사용자 방향:

- `320961` 번들 자체를 대표 CID로 되살리지 않는다.
- 이미 1작품 1CID로 엄격 확정된 작품은 건드리지 않는다.
- 번들에 남은 작품은 새 CID 생성/정산정보 보정 루트로 분리한다.
- `[사용안함]` 번들은 죽은 역사 CID로 보고, 살아있는 중복으로 세지 않는다.

`320961` 계열에서 이미 대표 확정된 작품:

- `독식하는 재벌 3세` -> CID `111006`, `독식하는 재벌 3세_서오_1005739_1021_확정`
- `마법 배운 재벌집 늦둥이` -> CID `112857`, `마법 배운 재벌집 늦둥이_서오_1005041_선인세없음_확정`
- `미생법사` -> CID `318052`, `미생법사_서오_1005190_1021_확정`
- `순혈의 헌터` -> CID `320966`, `순혈의 헌터_서오_1005190_1021_확정`
- `스킬스` -> CID `318934`, `스킬스_서오_1005190_1021_확정`
- `스킬스 - 현대편` -> CID `318115`, `스킬스 - 현대편_서오_1005190_1021_확정`
- `현자귀환` -> CID `318392`, `현자귀환_서오_1005190_1021_확정`

남은 판단:

- `시간의 마에스트로`
  - 비카카오 대표 근거 있음: `1005190`, 선인세 `1021`, 정산자 `유동우`, 필명 `서오`.
  - 기대 엄격명: `시간의 마에스트로_서오_1005190_1021_확정`.
  - 신규 콘텐츠 생성 하네스 dry-run 통과:
    - spec: `0513_temp/kipm_create_spec_time_maestro_20260514.json`
    - resolve: `0513_temp/exports/kipm_time_maestro_resolve_20260514.json`
    - dry-run: `0513_temp/exports/kipm_time_maestro_dryrun_20260514.json`
  - 단, 실제 write는 아직 하지 않았다. 새 CID만 만들면 S2 지급정산이 즉시 생기지 않으므로 현재 엄격 기준 수는 오르지 않는다. write하려면 `신규 CID 생성 -> 더미 계약 -> 판매채널/지급정산 보정 -> S2 최신화`까지 한 묶음으로 처리해야 한다.
- `연봉 1조 신입사원`
  - 바로 생성 금지.
  - `1005344`는 SIAAN Project 근거상 `[카카오창작지원금]` 계열이라 일반 대표로 쓰면 오염 위험이 있다.
  - 별도 후보 `1005708 / 연봉 1조 신입사원(타플) / 선인세 1021`가 있으나, 관측 작품수 0/seed 미연결 상태라 실제 일반 대표 저작권코드로 확정 전 확인이 필요하다.

### 2026-05-14 `시간의 마에스트로` 신규 CID/계약 생성

처리 결과:

- 신규 CID: `328043`
- 콘텐츠명: `시간의 마에스트로_서오_1005190_1021_확정`
- 계약 ID: `85861`
- 계약명: `20260514_시간의 마에스트로_서오_1005190_1021_확정_유동우`
- 계약상대방: `유동우` 개인, 거래처코드 `P000002181`
- RS: 비성인 기준 `70`
- 계약 대상 하위판매채널: `교보문고(소설)` 1개만 선택
- 판매채널콘텐츠ID: `903498`

산출물:

- spec: `0513_temp/kipm_create_spec_time_maestro_20260514.json`
- 최초 write 실패 로그: `0513_temp/exports/kipm_time_maestro_write_20260514.json`
  - 콘텐츠 생성은 성공했으나 계약상대방 `유동우`가 `유아이(구. 유동우)` 사업자 / `유동우` 개인 2건으로 조회되어 계약 단계에서 중단됨.
- 계약 성공 로그: `0513_temp/exports/dummy_contract_time_maestro_debug/debug_result.json`
- CID live 확인: `0513_temp/exports/live_lookup_time_maestro_328043_after_contract_success_20260514.csv`
- 상세 probe: `0513_temp/exports/probe_time_maestro_328043_after_contract/detail_328043.json`
- 판매채널 확인: `0513_temp/exports/sales_channel_time_maestro_328043_kyobo_20260514.csv`

후속 주의:

- `manual_cid_decisions_20260513.csv`에 일반 seed `assign`, 카카오MG seed `covered_by_representative` 결정을 기록했다.
- 새 CID/계약은 생성됐지만, 현재 엄격 확정 수에는 아직 반영하지 않는다.
- 이유: 현재 엄격 기준은 `S2 지급정산 행 존재`까지 요구한다. `328043`은 다음 S2/지급정산 최신화 이후 strict audit에서 승격 여부를 다시 확인해야 한다.
- 더미계약 자동화의 기본 하위판매채널을 `전체`에서 `교보문고(소설)`로 변경했다.
  - 파일: `scripts/create_kipm_dummy_contract.py`
  - 이유: `전체`를 고르면 RS 개별 행이 과도하게 늘어나 작업 시간이 폭증한다.

### 2026-05-14 S2 최신화 및 엄격 확정 재감사

최신화 결과:

- S2 지급정산 API 최신화 완료: `1900-01-01 ~ 2026-05-14`, 소설 `102`.
- 원본 조회: 145,129행.
- 감사용 캐시: 141,677행.
- S2 lookup: 124,708행.
- 최신 캐시:
  - `0513_temp/data/s2_payment_settlement_cache_part_001.csv`
  - `0513_temp/data/s2_payment_settlement_cache_part_002.csv`
  - `0513_temp/data/s2_lookup_20260514.csv`
  - `0513_temp/exports/s2_refresh_summary_20260514.json`

`시간의 마에스트로` 반영 확인:

- CID `328043`이 최신 S2 캐시에 반영됨.
- S2 지급정산 행: 26행.
- 지급정산 상태: `운영중`.
- 대표 콘텐츠명: `시간의 마에스트로_서오_1005190_1021_확정`.
- 따라서 `시간의 마에스트로`는 strict audit에서 엄격 확정으로 승격됨.

주의:

- 중간에 중단했던 최초 계약 시도도 KIPM/S2에 일부 저장되어 계약 `85860`이 생성됨.
- 이후 의도한 교보문고 1개짜리 계약 `85861`도 생성됨.
- 현재 CID 기준 엄격 확정에는 문제 없지만, 계약 정리는 별도 후속 후보로 본다.

최신 엄격 확정 숫자:

- target seed rows: 187
- target works: 185
- live audit `strict_confirmed`: 170
- 적대 감리 통과 `final_strict_confirmed`: 170
- false positive findings: 0
- 남은 작품: 15
- 잔여 seed row: 17

최신 잔여 버킷(작품 기준):

- `D_사용안함_단일부활`: 3
- `E_사용안함_번들분해`: 1
- `F_필명_동명이인_확인`: 2
- `H_번들잔존_분해`: 5
- `I_타담당_구형명`: 3
- `J_S2_IPS보정`: 1

최신 산출물:

- live audit: `0513_temp/exports/ips_strict_confirmed_live_audit_조원재_20260514.csv`
- 적대 감리: `0513_temp/exports/ips_strict_confirmed_adversarial_audit2_조원재_20260514.csv`
- 최종 엄격 확정: `0513_temp/exports/ips_strict_confirmed_final_조원재_20260514.csv`
- 잔여 작업: `0513_temp/exports/ips_remaining_worklist_after_strict_audit_조원재_20260514.md`
- 증가 계획: `0513_temp/exports/ips_strict_confirm_growth_plan_조원재_20260514.md`

### 2026-05-14 잔여 15개 중 조원재 담당 범위 재확정

사용자 확정:

- 잔여 15개 중 조원재 담당으로 계속 처리할 작품은 5개뿐이다.
- 나머지 10개는 조원재 target에서 제외한다.
- 특히 `미스터 프레지던트`는 타 CP 작품이므로 되살리지 않는다. CID `112350`은 live 확인상 이미 `[사용안함]_미스터 프레지던트 2부_하늘곰` 상태라 추가 rename은 하지 않았다.

조원재 담당으로 남길 작품:

- `연봉 1조 신입사원`
- `미스터 프레지던트 2부`
- `섹스마스터가 되어 다 따먹기`
- `망한 세상에서 나 혼자 각성`
- `사이코패스 살인마는 살고 싶다`

조원재 target에서 제외한 작품:

- `드래곤 엔터테인먼트`
- `미스터 프레지던트`
- `사립루레인학원 시리즈`
- `김석산 파이브`
- `이웃집 그 녀석`
- `최종진화소년`
- `열다섯 번째 생일`
- `준장 로사 카니발`
- `킬리만자로의 마법종합학교`
- `사립루레인학원 윤리선생(개정판)`

처리:

- `0513_temp/manual_cid_decisions_20260513.csv`에 위 10개를 `not_owner`로 기록했다.
- live 확인 산출물: `0513_temp/exports/live_lookup_112350_before_discard_20260514.json`

재감사 결과:

- target seed rows: 177
- target works: 175
- 적대 감리 통과 `final_strict_confirmed`: 170
- false positive findings: 0
- 남은 작품: 5
- 잔여 seed row: 7

최신 잔여 버킷:

- `E_사용안함_번들분해`: 1
- `F_필명_동명이인_확인`: 2
- `H_번들잔존_분해`: 2

### 2026-05-14 최종 5개 사용자 판단 반영

사용자 확정:

- `연봉 1조 신입사원`은 `연봉 1조 신입사원_서오_1004823_869_확정`을 기대 엄격명으로 한다.
  - 일반 `1005344_선인세없음` seed는 대표로 쓰지 않는다.
- `미스터 프레지던트 2부`는 `하늘곰 = 박천웅`이며, 대표는 `1004809_선인세없음`이다.
  - 카카오MG `1004782_840` seed는 일반 대표 CID에 흡수한다.
- `섹스마스터가 되어 다 따먹기`는 `아즐란 = 빨간홍차`다.
- `망한 세상에서 나 혼자 각성`과 `사이코패스 살인마는 살고 싶다`는 같은 CID `319513` 번들에 묶여 있으므로 분리 필요 판단이 맞다.

IPS 실제 rename:

- plan: `0513_temp/ips_final5_user_decisions_rename_plan_20260514.csv`
- dry-run: `0513_temp/exports/ips_final5_user_decisions_rename_dryrun_20260514.csv` (`ready_api` 2)
- write: `0513_temp/exports/ips_final5_user_decisions_rename_write_20260514.csv` (`updated` 2)
- live verify: `0513_temp/exports/live_lookup_final5_renamed_verify_20260514.json`

처리 목록:

- CID `311615`
  - `미스터 프레지던트 2부_하늘곰_1004809_미연결_확정`
  - -> `미스터 프레지던트 2부_박천웅_1004809_선인세없음_확정`
- CID `320955`
  - `섹스마스터가 되어 다 따먹기_아즐란_1005511_선인세없음_확정`
  - -> `섹스마스터가 되어 다 따먹기_빨간홍차_1005511_선인세없음_확정`

재감사 결과:

- target works: 175
- 적대 감리 통과 `final_strict_confirmed`: 172
- false positive findings: 0
- 남은 작품: 3
- 잔여 seed row: 3

최신 잔여:

- `연봉 1조 신입사원`
  - 기대 엄격명: `연봉 1조 신입사원_서오_1004823_869_확정`
  - 현재 살아있는 개별 CID 없음. 신규 CID/계약 생성 루트.
- `망한 세상에서 나 혼자 각성`
  - 기대 엄격명: `망한 세상에서 나 혼자 각성_민작가_1005540_1155_확정`
  - 현재 CID `319513` 번들에 묶임.
- `사이코패스 살인마는 살고 싶다`
  - 기대 엄격명: `사이코패스 살인마는 살고 싶다_민작가_1005540_1155_확정`
  - 현재 CID `319513` 번들에 묶임.

번들 분리 관찰:

- CID `319513`은 최신 S2 캐시에 25행 존재하고, 현재 살아있는 번들명은 `0_망한 세상에서 나 혼자 각성·사이코패스 살인마는 살고 싶다_민작가_일반`이다.
- 사용안함 후보 CID `322738`, `321853`은 최신 S2 행이 0이라 단순 부활만으로 엄격 확정되지는 않는다.

### 2026-05-14 `연봉 1조 신입사원` 번들 CID 부활

사용자 확정:

- 과거 지급정산 오염은 고려하지 않는다.
- CID `320961` 사용안함 번들을 `연봉 1조 신입사원` 대표 CID로 부활/rename한다.
- 기대 엄격명은 `연봉 1조 신입사원_서오_1004823_869_확정`이다.

사전 확인:

- `320961` 번들에 묶였던 주요 작품은 이미 별도 엄격 CID로 살아 있다.
  - `독식하는 재벌 3세` -> CID `111006`
  - `미생법사` -> CID `318052`
  - `순혈의 헌터` -> CID `320966`
  - `스킬스` -> CID `318934`
  - `스킬스 - 현대편` -> CID `318115`
  - `시간의 마에스트로` -> CID `328043`
  - `현자귀환` -> CID `318392`
  - `마법 배운 재벌집 늦둥이` -> CID `112857`

IPS 실제 rename:

- plan: `0513_temp/ips_yeonbong_revive_rename_plan_20260514.csv`
- dry-run: `0513_temp/exports/ips_yeonbong_revive_rename_dryrun_20260514.csv` (`ready_api` 1)
- write: `0513_temp/exports/ips_yeonbong_revive_rename_write_20260514.csv` (`updated` 1)
- live verify: `0513_temp/exports/live_lookup_yeonbong_320961_after_rename_20260514.csv`

처리 목록:

- CID `320961`
  - `[사용안함]_독식하는 재벌 3세_미생법사_순혈의 헌터_스킬스_스킬스 - 현대편_시간의 마에스트로_연봉 1조 신입사원_현자귀환_서오`
  - -> `연봉 1조 신입사원_서오_1004823_869_확정`

S2 최신화:

- `320961` rename 직후 S2 전체 최신화를 다시 수행했다.
- summary: `0513_temp/exports/s2_refresh_summary_20260514_after_yeonbong.json`
- S2 change added: 132
- CID `320961` S2 지급정산 행: 132행
- 지급정산 상태: `운영중`

재감사 결과:

- target works: 175
- 적대 감리 통과 `final_strict_confirmed`: 173
- false positive findings: 0
- 남은 작품: 2
- 잔여 seed row: 2

최신 잔여:

- `망한 세상에서 나 혼자 각성`
  - 기대 엄격명: `망한 세상에서 나 혼자 각성_민작가_1005540_1155_확정`
  - 현재 CID `319513` 번들에 묶임.
- `사이코패스 살인마는 살고 싶다`
  - 기대 엄격명: `사이코패스 살인마는 살고 싶다_민작가_1005540_1155_확정`
  - 현재 CID `319513` 번들에 묶임.

### 2026-05-14 최종 번들 분리 완료

처리 방침:

- CID `319513`은 `망한 세상에서 나 혼자 각성` 대표 CID로 사용한다.
- `사이코패스 살인마는 살고 싶다`는 신규 생성 대신, S2 지급정산이 확인된 사용안함 CID `321853`을 부활시켜 대표 CID로 사용한다.
- 담당자 표기는 후속 polish 대상일 수 있으나, 현재 목표인 `1개 작품 = 1개 엄격 확정 CID + S2 지급정산 존재` 기준은 충족한다.

IPS 실제 rename:

- `319513` plan: `0513_temp/ips_final_bundle_319513_rename_plan_20260514.csv`
- `319513` dry-run: `0513_temp/exports/ips_final_bundle_319513_rename_dryrun_20260514.csv` (`ready_api` 1)
- `319513` write: `0513_temp/exports/ips_final_bundle_319513_rename_write_20260514.csv` (`updated` 1)
- `319513` verify: `0513_temp/exports/live_lookup_final_bundle_after_319513_rename_20260514.csv`
- `321853` plan: `0513_temp/ips_final_bundle_321853_revival_plan_20260514.csv`
- `321853` dry-run: `0513_temp/exports/ips_final_bundle_321853_revival_dryrun_20260514.csv` (`ready_api` 1)
- `321853` write: `0513_temp/exports/ips_final_bundle_321853_revival_write_20260514.csv` (`updated` 1)
- `321853` verify: `0513_temp/exports/live_lookup_final_bundle_after_321853_revival_20260514.csv`

처리 목록:

- CID `319513`
  - `0_망한 세상에서 나 혼자 각성·사이코패스 살인마는 살고 싶다_민작가_일반`
  - -> `망한 세상에서 나 혼자 각성_민작가_1005540_1155_확정`
- CID `321853`
  - `(사용안함)_사이코패스 살인마는 살고 싶다·민작가_중복`
  - -> `사이코패스 살인마는 살고 싶다_민작가_1005540_1155_확정`

S2 최신화:

- summary: `0513_temp/exports/s2_refresh_summary_20260514_after_final_bundle.json`
- fetched rows: 145,129
- S2 cache rows: 141,809 -> 141,812
- S2 lookup rows: 124,843
- S2 change added: 3
- S2 change modified: 24
- S2 change deleted: 0
- CID `321853` S2 지급정산 3행 확인

최종 재감사 결과:

- target works: 175
- live audit `strict_confirmed`: 175
- 적대 감리 통과 `final_strict_confirmed`: 175
- false positive findings: 0
- 남은 작품: 0
- 잔여 작업 rows: 0

최종 산출물:

- live audit: `0513_temp/exports/ips_strict_confirmed_live_audit_조원재_20260514.csv`
- adversarial audit: `0513_temp/exports/ips_strict_confirmed_adversarial_audit2_조원재_20260514.csv`
- final strict confirmed: `0513_temp/exports/ips_strict_confirmed_final_조원재_20260514.csv`
- remaining worklist: `0513_temp/exports/ips_remaining_worklist_after_strict_audit_조원재_20260514.csv`
- growth plan: `0513_temp/exports/ips_strict_confirm_growth_plan_조원재_20260514.csv`

### 2026-05-15 최신 IPS 재검산 및 추가 cleanup

입력:

- 최신 IPS 다운로드본: 당시 `mapping-novel` 작업 폴더의 `ips_20260515.xlsx`

검산 결과:

- 2026-05-14 기준 정산 target 175개는 최신 IPS에서도 전부 엄격 확정 상태.
- 담당자명 `조원재` active 소설 전체로 넓히면 구형/비엄격명이 추가로 보였고, 사용자 판단에 따라 일부 처리했다.

특수 suffix 처리:

- plan: `0513_temp/ips_20260515_special_suffix_plan.csv`
- dry-run: `0513_temp/exports/ips_20260515_special_suffix_dryrun.csv` (`ready_api` 4)
- write: `0513_temp/exports/ips_20260515_special_suffix_write.csv` (`updated` 4)
- verify: `0513_temp/exports/live_lookup_20260515_special_suffix_verify.csv`

처리 목록:

- CID `323123`: `가온하루_신작 1질` -> `가온하루_신작 1질_[특수]`
- CID `322451`: `20250625_카카오_마늘소금 작가 일체_CHUNG MI SOO` -> `20250625_카카오_마늘소금 작가 일체_CHUNG MI SOO_[특수]`
- CID `308904`: `대형딱풀` -> `대형딱풀_[특수]`
- CID `308297`: `마늘소금-보장인세 1권` -> `마늘소금-보장인세 1권_[특수]`
- CID `321190`은 사용자가 직접 죽였다고 확인. 이번 자동 rename 대상에서 제외했다.

바로북 ACCOUNT 근거:

- 사용자 제공 CP key:
  - `4476714`: `박천웅 ( 하늘곰 )`
  - `4476682`: `주식회사 지그(성태민) ( 갈드 )`
- CP 목록 최신 다운로드: `SIAAN Project/data/exports/barobook/20260515_101237__저작권자 목록_full.xlsx`
- 수동 key 입력 파일: `SIAAN Project/data/exports/barobook/20260515_101237__manual_cp_keys_4476714_4476682.xlsx`
- 저작권코드 수집: `SIAAN Project/data/exports/barobook/20260515_101350__저작권코드_manual_4476714_4476682.xlsx`
- 선인세잔액 수집: `SIAAN Project/data/exports/barobook/20260515_101349__선인세잔액_manual_4476714_4476682.xlsx`
- 저작권-시리즈 매핑: `SIAAN Project/data/exports/barobook/20260515_101529__저작권_시리즈매핑_manual_4476714_4476682.xlsx`

확인된 주요 근거:

- `조선 양과자 제과점`: 하늘곰 CP `4476714`, 저작권코드 `1005780`, 선인세 매핑 없음.
- `전직 랭커는 템빨로 레벨 업!` 일반: 갈드 CP `4476682`, 기본정산율 `1004715`, 선인세 `775`.
- `전직 랭커는 템빨로 레벨 업!` 카카오: 저작권코드 `1004861`, 선인세 `839`.
- `전직 랭커는 템빨로 레벨 업!` 윌라: 저작권코드 `1005121`, 선인세 `775`.
- `음공천하` 일반: 갈드 CP `4476682`의 기본정산율 `1004715`, 선인세 `775`; `서호`는 갈드 계정 alias로 처리.
- `고인물 무림에 가다`: 저작권코드 `1005202`, 선인세 `1095`.

엄격명 rename 처리:

- plan: `0513_temp/ips_20260515_legacy_strict_rename_plan.csv`
- dry-run: `0513_temp/exports/ips_20260515_legacy_strict_rename_dryrun.csv` (`ready_api` 6)
- write: `0513_temp/exports/ips_20260515_legacy_strict_rename_write.csv` (`updated` 6)
- verify: `0513_temp/exports/live_lookup_20260515_after_legacy_cleanup.csv`

처리 목록:

- CID `327959`
  - `조선 양과자 제과점_하늘곰_신작예정_신작예정_확정`
  - -> `조선 양과자 제과점_하늘곰_1005780_선인세없음_확정`
- CID `110454`
  - `갈드_일반_전직랭커는템빨로레벨업!`
  - -> `전직 랭커는 템빨로 레벨 업!_갈드_1004715_775_확정`
- CID `110867`
  - `전직 랭커는 템빨로 레벨 업!_갈드_카카오`
  - -> `전직 랭커는 템빨로 레벨 업!_갈드_1004861_839_확정`
- CID `247293`
  - `갈드_윌라_전직 랭커는 템빨로 레벨 업!`
  - -> `전직 랭커는 템빨로 레벨 업!_갈드_1005121_775_확정`
- CID `110854`
  - `0_음공천하_서호_일반`
  - -> `음공천하_서호_1004715_775_확정`
- CID `110487`
  - `고인물 무림에 가다_갈드_창작지원금`
  - -> `고인물 무림에 가다_갈드_1005202_1095_확정`

사용자 재지적 및 기준 보정:

- 사용자가 `엄격 확정은 1작품 1CID`라고 재확정했다.
- `창작지원금`, `카카오`, `윌라`는 작품명이 아니라 판매/정산 채널 성격이다.
- 따라서 한 작품에 일반/카카오/윌라/창작지원금 CID가 여러 개 있어도, 엄격 확정 CID는 대표 1개만 둔다.
- 엄격 확정이 아닌 CID는 기본 `(사용안함)` 처리한다.
- 사용자가 명시적으로 `[특수]` 지정한 CID만 active `[특수]`로 살린다.

잘못 처리한 중간 산출물:

- `0513_temp/ips_20260515_creative_support_strict_rename_plan.csv`
- `0513_temp/exports/ips_20260515_creative_support_strict_rename_write.csv`
- `0513_temp/ips_20260515_channel_title_correction_plan.csv`
- `0513_temp/exports/ips_20260515_channel_title_correction_write.csv`
- `0513_temp/ips_20260515_representative_only_channel_hold_plan.csv`
- `0513_temp/exports/ips_20260515_representative_only_channel_hold_write.csv`

대표 CID만 엄격 확정으로 남기고 채널성 CID를 사용안함 처리한 최종 보정:

- plan: `0513_temp/ips_20260515_channel_cids_disable_plan.csv`
- dry-run: `0513_temp/exports/ips_20260515_channel_cids_disable_dryrun.csv` (`ready_api` 4)
- write: `0513_temp/exports/ips_20260515_channel_cids_disable_write.csv` (`updated` 4)
- verify: `0513_temp/exports/live_lookup_20260515_full_cleanup_verify_final_policy.csv`

처리 목록:

- 대표 엄격 CID:
  - CID `110454`: `전직 랭커는 템빨로 레벨 업!_갈드_1004715_775_확정`
  - CID `110854`: `음공천하_서호_1004715_775_확정`
- 사용자가 명시적으로 살린 `[특수]` CID:
  - CID `323123`: `가온하루_신작 1질_[특수]`
  - CID `322451`: `20250625_카카오_마늘소금 작가 일체_CHUNG MI SOO_[특수]`
  - CID `308904`: `대형딱풀_[특수]`
  - CID `308297`: `마늘소금-보장인세 1권_[특수]`
- 채널성 CID 사용안함:
  - CID `110867`: `(사용안함)_전직 랭커는 템빨로 레벨 업!_갈드_카카오`
  - CID `247293`: `(사용안함)_갈드_윌라_전직 랭커는 템빨로 레벨 업!`
  - CID `110497`: `(사용안함)_전직 랭커는 템빨로 레벨 업!_갈드_창작지원금`
  - CID `110493`: `(사용안함)_음공천하_서호_창작지원금`

되돌린 잘못된 이름:

- CID `110497`
  - `전직 랭커는 템빨로 레벨 업! 창작지원금_갈드_1004715_775_확정`
  - -> `(사용안함)_전직 랭커는 템빨로 레벨 업!_갈드_창작지원금`
- CID `110493`
  - `음공천하 창작지원금_서호_1004715_775_확정`
  - -> `(사용안함)_음공천하_서호_창작지원금`

최종 live 재검증:

- verify: `0513_temp/exports/live_lookup_20260515_full_cleanup_verify_final_policy.csv`
- 2026-05-15 최신 IPS에서 잡힌 조원재 active 소설 비엄격/구형명 13건은 모두 다음 중 하나로 닫았다:
  - 대표 엄격명 처리: 4건
  - 사용자 지정 `[특수]` 유지: 4건
  - `(사용안함)` 처리: 4건
  - 사용자 수동 처리 확인 및 현재 담당자 조원재 아님: CID `321190`

최종 감사:

- live strict audit 재실행: `0513_temp/exports/ips_strict_confirmed_live_audit_조원재_20260514.csv`
- generated_at: `2026-05-15T10:44:13`
- target seed rows: 175
- status: `strict_confirmed` 175건
- 현재 기준으로 정산 target 175개는 모두 `1작품 1대표 CID + S2 지급정산 존재 + 엄격명 일치`를 통과했다.

타 담당 카카오 파생 CID 사용안함:

- 사용자 지시로 조원재 대표 CID가 이미 확정된 작품의 타 담당 카카오 파생 CID 2건을 사용안함 처리했다.
- plan: `0513_temp/ips_20260515_other_manager_kakao_disable_dryrun_plan.csv`
- dry-run: `0513_temp/exports/ips_20260515_other_manager_kakao_disable_dryrun.csv` (`ready_api` 2)
- write: `0513_temp/exports/ips_20260515_other_manager_kakao_disable_write.csv` (`updated` 2)
- verify: `0513_temp/exports/live_lookup_20260515_other_manager_kakao_disable_verify.csv`
- 처리 목록:
  - CID `317605`: `(카카오)전직 랭커는 템빨로 레벨 업!` -> `(사용안함)_(카카오)전직 랭커는 템빨로 레벨 업!`
  - CID `312022`: `[카카오]음공천하 단행본` -> `(사용안함)_[카카오]음공천하 단행본`
