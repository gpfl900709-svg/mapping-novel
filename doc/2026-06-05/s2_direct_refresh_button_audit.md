# S2 직접 최신화 버튼 원복 감리

## 결론

Cloud 앱 사이드바 버튼은 `관리자에게 S2 최신화 요청`으로 원복한다. 이 버튼은 S2 API를 직접 호출하지 않고 ClickUp S2 최신화 요청 task만 생성한다.

## 원복 사유

- Streamlit Cloud 서버에서 `kiss-api.kld.kr`로 직접 접속하면 사내망/IP 허용 목록 제한으로 타임아웃될 수 있다.
- Cloud에 S2 ID/PW를 넣어도 네트워크가 막히면 최신화가 되지 않는다.
- 사용자에게 직접 최신화가 되는 것처럼 보이면 운영 판단이 흔들린다.

## 현재 기준

- Cloud 앱: repo에 배포된 S2 lookup을 읽고, 버튼은 ClickUp 요청만 생성한다.
- S2 실제 최신화: 사내망/회사컴/관리자 로컬 runner에서 실행한다.
- 최신화 결과는 repo `data/`와 `doc/YYYY-MM-DD/*summary*`에 반영한 뒤 커밋/푸시한다.

## 남은 구현 후보

Cloud 버튼이 로컬 CLI를 직접 여는 방식은 불가하다. 자동화를 붙이려면 Cloud 버튼은 ClickUp task를 만들고, 회사컴 watcher가 그 task를 감지해 로컬 최신화 스크립트를 실행하는 구조로 간다.
