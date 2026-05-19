# SIAANE_v2

`SIAAN Project`의 기존 혼합 SSOT와 분리해서, 플랫폼별 canonical을 먼저 세우기 위한 새 작업 베이스입니다.

원칙
- 플랫폼별로 먼저 정리하고 나중에 합친다.
- `raw`는 원본 그대로 둔다.
- `stage`는 정리 중간 산출물이다.
- `canonical`은 플랫폼 내부 기준표다.
- `exports`는 사람이 보는 결과물이다.
- 플랫폼 간 연결은 각 플랫폼 폴더가 아니라 `crosswalk/`에서 관리한다.
- 최종 통합 뷰는 `views/`에서만 만든다.

현재 플랫폼
- `account/`
- `admin/`
- `ips/`
- `s2/`
- `erp/`

공통 구조
- `raw/`
  - 원본 수집본
- `stage/`
  - 전처리, 이름 정리, 중간 매핑
- `canonical/`
  - 플랫폼 내부에서 확정한 기준 테이블
- `exports/`
  - 실무 확인용 결과물
- `notes/`
  - 예외, 판단 근거, TODO

플랫폼 간 폴더
- `crosswalk/`
  - `account↔ips`, `account↔admin` 같은 연결표
- `views/`
  - 운영용 / 정산용 / 예외용 통합 뷰
- `docs/`
  - 구조 문서, 결정 기록

권장 진행 순서
1. `account/` canonical부터 만든다.
2. `account` 기준으로 `특수`, `저작권코드`, `선인세코드`, `정산자`, `정산대표`를 정리한다.
3. 그다음 `admin`, `ips`를 각각 같은 방식으로 canonical화한다.
4. 마지막에 `crosswalk`와 `views`를 만든다.

첫 작업 포인트
- [account/README.md](account/README.md)

현재 컨텍스트
- [docs/current_context.md](docs/current_context.md)
