# 05. 설계 검토 결정

## 판단

기존 6개 문서는 가져올 가치가 있다. 비전, 거버넌스, 호혜, GitHub 매핑, 로드맵의 경계가 명확하며 MVP0 구현에 필요한 기준을 제공한다.

## 확정

- BYOS와 로컬 추론
- 옵트인 저장소만 작업
- 외부 저장소 자동화는 Draft PR 상한
- 제안·구현·검증 역할 분리
- 호혜 원장과 역할별 평판 분리
- MVP0은 거버넌스보다 단일 수직 흐름 검증 우선

## 수정한 가정

- 공개 저장소의 표준 GitHub-hosted runner 사용은 무료지만 저장공간, 대형 runner, 정책 변경까지 무비용이라고 가정하지 않는다.
- git 이력은 감사 가능하지만 관리자에 대한 절대 불변성을 제공하지 않는다. 독립 미러와 서명 checkpoint가 필요하다.
- 중앙 서버리스 워커 1개는 MVP 구성이다. 규모 증가 시 큐, 멱등성 저장소, 검색용 운영 DB가 필요할 수 있다.
- 허니팟은 실제 외부 프로젝트가 아니라 합성·격리 저장소에서만 실행한다.

## 이번 이터레이션 산출물

- `schemas/rfc.schema.json`
- `schemas/ticket.schema.json`
- `schemas/ledger-event.schema.json`
- `nightforge validate`
- `nightforge claim`
- `nightforge submit`
- 로컬 테스트와 GitHub Actions Proof Engine

## 다음 게이트

GitHub API 연동 전에 로컬 CLI가 다음 불변식을 보장해야 한다.

1. 유효하지 않은 티켓은 클레임할 수 없다.
2. 클레임은 티켓 원문의 SHA-256에 결박된다.
3. 제출 manifest는 패치 SHA-256과 검증 명령을 포함한다.
4. 파일 기록은 임시 파일 후 원자적 교체로 완료된다.
5. GitHub 연동 시 모든 웹훅은 delivery ID로 멱등 처리한다. ✅ 로컬 receipt 저장 구현

## 후속 게이트

1. GitHub Issue 템플릿과 티켓 라벨 상태머신 ✅
2. GitHub API 기반 티켓 조회·클레임 ✅ (assignee와 상태 라벨을 단일 PATCH로 갱신)
3. 옵트인 저장소 검증과 Draft PR 제출 상한 ✅
4. 패치 브랜치 자동 생성·푸시
5. 웹훅 서명 검증과 서버리스 수신기 연결
