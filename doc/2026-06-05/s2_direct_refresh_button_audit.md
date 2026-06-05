# S2 직접 최신화 버튼 구현안 감리

## 결론

95% 확신 기준 구현안은 사이드바의 큰 `S2 최신화` 버튼을 단일 진입점으로 두고, 명시적으로 허용된 관리자 환경에서는 실제 S2 최신화를 실행하게 하는 것이다. 직접 최신화가 꺼진 일반 Cloud 환경에서는 같은 버튼이 기존처럼 ClickUp 요청 태스크만 만든다.

## 조사 결과

- `app.py`에는 이미 `run_s2_refresh()`, `run_s2_guard_refresh()`, `run_s2_service_content_refresh()`, `run_s2_full_replace()`가 있다.
- 기존 사이드바 버튼은 `create_s2_refresh_request_task()`만 호출해서 ClickUp 요청 task를 만들었다.
- 수정 후 사이드바 버튼은 `S2_DIRECT_REFRESH_ENABLED=true`인 관리자 환경에서는 `run_s2_direct_refresh_once()`를 호출하고, 직접 최신화가 꺼진 환경에서만 ClickUp 요청 task를 만든다.
- `run_s2_full_replace()`는 지급정산 S2 lookup, 누락/청구 guard, 판매채널콘텐츠 lookup을 순차 갱신한다.
- 지급정산 갱신 스크립트는 `kiss_refresh_lock.refresh_lock()`을 사용해 동시 실행을 차단한다.
- Streamlit Cloud에서 직접 파일을 갱신하면 현재 실행 서버에는 반영되지만, 재배포 뒤 영구 보존은 repo 또는 외부 저장소 반영이 별도로 필요하다.

## 적대적 감리

- 아무 사용자나 버튼을 누르는 문제: 직접 최신화는 기본 OFF이며 `S2_DIRECT_REFRESH_ENABLED=true`가 있어야 노출된다.
- Cloud secrets에 S2 계정이 있는 문제: 직접 최신화는 기본적으로 별도 `S2_DIRECT_REFRESH_TOKEN` 입력까지 요구한다.
- 토큰 누락 오설정: `S2_DIRECT_REFRESH_REQUIRE_TOKEN=true` 상태에서 토큰이 없으면 버튼이 비활성화된다.
- 인증 실패 오판: 실행 전 `run_s2_auth_check()`를 먼저 호출하고 기존 인증/네트워크 실패 판별 메시지를 사용한다.
- 동시 실행: 지급정산 갱신 스크립트의 refresh lock이 1차 방어선이다.
- 민감정보 노출: UI 실행 로그는 기존 `ui_safe_refresh_log()`를 통과하고 5,000자 tail만 보여준다.
- 기존 사용자 흐름 회귀: 직접 최신화가 꺼진 Cloud 환경에서는 ClickUp 요청 흐름을 유지한다.

## 운영 설정

로컬 `.env` 또는 Streamlit Cloud secrets에 아래 값을 둔다.

```toml
[s2_refresh]
enabled = "true"
require_token = "true"
admin_token = "관리자만 아는 실행 키"
```

S2 인증값은 기존 `S2_ID`/`S2_PW` 또는 `S2_ACCESS_TOKEN`을 사용한다.

직접 최신화 모드에서는 사이드바의 `관리자 직접 S2 최신화` expander에서 관리자 실행 키를 입력한 뒤, 큰 `S2 최신화` 버튼을 누른다.

## 남은 한계

- 이 구현은 앱 서버의 즉시 사용 기준을 갱신한다.
- 재배포 후에도 기준을 유지하려면 GitHub Actions, repo commit, DB/object storage 중 하나로 갱신 산출물을 영구 저장하는 2단계 구조가 필요하다.
