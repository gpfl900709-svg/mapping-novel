# crosswalk

여기서는 플랫폼 내부 canonical을 바로 섞지 않고, 플랫폼 간 연결 seed만 만든다.

현재 우선순위
- `account → ips` 작품 단위 CID seed
- `account → ips` rename/create 후보 action queue

현재 합의
- `account_decision_queue`는 `저작권코드 1행` 기준 검토 큐로만 쓴다.
- `IPS`에서 필요한 `작품별 CID`는 `crosswalk/`에서 따로 만든다.
- 복수 작품이 한 `account_저작권코드`에 묶인 경우, `account_decision_queue`에서는 이름을 억지로 1개로 닫지 않는다.
- 이런 행은 `CID분해필요`로 표시하고, `crosswalk` seed에서 작품별로 분해한다.

추천 산출물
- `exports/latest__account_ips_cid_seed_<manager>.xlsx`
- `exports/latest__account_ips_cid_seed_<manager>.csv`
- `exports/latest__account_cid_split_review_queue_<manager>.xlsx`
- `exports/latest__account_ips_action_queue_<manager>.xlsx`
- `exports/latest__account_ips_match_candidates_<manager>.csv`

`account_ips_cid_seed` grain
- `작품명 + 대표작가명 + 연결_선인세코드 + 특수 + account_저작권코드 + 정산자`

주요 컬럼
- `작품명`
- `대표작가명`
- `정산자`
- `연결_선인세코드`
- `특수`
- `account_저작권코드`
- `정산대표Y/N`
- `CID_seed_id`

정산자 규칙
- 우선순위는 `account_예금주 → account_real_name → account_pen_name`

주의
- 이 seed는 바로 `IPS rename/create`를 실행하는 큐가 아니다.
- 먼저 `account` 판단 결과를 반영할 수 있는 중간 seed다.
- `CID분해필요` 검토는 `latest__account_cid_split_review_queue_<manager>.xlsx`에서 권리행/작품행을 함께 본다.
- `account_ips_action_queue`도 실행 전 검토 큐다. 특히 `IPS_분해/중복검토`, `IPS_사용안함검토`, `IPS_매칭검토`는 자동 실행하지 않는다.
