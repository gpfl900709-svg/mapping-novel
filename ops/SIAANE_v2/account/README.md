# account canonical

여기서는 `account`를 먼저 플랫폼 내부 기준으로 정리합니다.

우선순위
- `작가코드`
- `저작권코드`
- `저작권명`
- `선인세코드`
- `선인세명`
- `정산기준`
- `정산자`
- `정산대표 Y/N`
- `특수`

가정
- 선인세는 반드시 `저작권코드`에 연결된다.
- 현재 account 관측 단계의 특수는 `일반`, `카카오MG`, `네이버MG`, `원작`만 사용한다.
- `카카오MG` / `네이버MG` / `원작`은 연결된 선인세명 기준으로 판정한다.

추천 산출물
- `raw/account_copyright_codes.xlsx`
- `raw/account_advance_balances.xlsx`
- `raw/account_author_exception_share_rates.xlsx`
- `stage/account_rights_base.csv`
- `stage/account_advance_link_candidates.csv`
- `canonical/account_rights_special.csv`
- `canonical/account_advance_registry.csv`
- `exports/latest__account_observation_<manager>.xlsx`
- `exports/latest__account_decision_queue_<manager>.xlsx`

목표
- `account_rights_special`
  - grain: `작가코드 + 저작권코드 + 특수`
- `account_advance_registry`
  - grain: `선인세코드`
- `account_decision_queue`
  - grain: `저작권코드 1행`
  - 역할: `현재 저작권명` / `canonical 제안명` / `action 제안` / `작가특수RS`를 한 번에 검토하는 작업 큐

주의
- 아직 `IPS rename` 포맷으로 바로 가지 않는다.
- 먼저 `account` 안에서 특수와 저작권/선인세 연결을 고정한다.
- `관측_작품수 > 1`인 권리행은 `account_decision_queue`에서 이름을 1개로 닫지 않는다.
- 이런 행은 `CID분해필요`로 표시하고, 작품 단위 `IPS` seed는 `crosswalk/`에서 만든다.
