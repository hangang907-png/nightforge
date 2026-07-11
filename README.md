# NightForge

> NightForge는 사용자의 유휴 AI 구독과 로컬 컴퓨팅을 계정 공유 없이 연결해,
> 오픈소스 소프트웨어를 밤마다 자율적으로 유지·실험·개선하는 검증 중심 분산 개발망이다.

사람은 관리자가 아니라 **헌법 제정자이자 최종 관찰자**다.
에이전트는 사람이 정한 경계 안에서 자유롭게 탐색하고,
결과는 승인이 아니라 **테스트·재현성·감사 로그**로 평가된다.

## 문서

| 문서 | 내용 |
|---|---|
| [00-vision.md](docs/00-vision.md) | 한 문장 정의, 핵심 원칙, 5개 계층 구조 |
| [01-governance.md](docs/01-governance.md) | RFC → 재현 → 투표+자원약정 → 티켓 → 경쟁개발 → 단계적 병합 |
| [02-reciprocity.md](docs/02-reciprocity.md) | 품앗이 호혜 시스템 — 체리피커·무임승차 제재 설계 |
| [03-architecture-github.md](docs/03-architecture-github.md) | GitHub 프리미티브 최대 활용 아키텍처, 최소 중앙 구성 |
| [04-roadmap.md](docs/04-roadmap.md) | MVP0 → MVP1 → MVP2 로드맵과 성공 지표 |
| [05-design-review.md](docs/05-design-review.md) | 기술 가정 검토, 확정·수정 사항, 다음 게이트 |
| [06-aws-webhook.md](docs/06-aws-webhook.md) | Lambda + API Gateway + DynamoDB 운영 배포 |
| [07-cloudflare-webhook.md](docs/07-cloudflare-webhook.md) | Worker + D1 + Queue 무서버 운영 배포 |

## MVP0 CLI

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/nightforge validate examples/ticket.json schemas/ticket.schema.json
.venv/bin/nightforge claim examples/ticket.json --node node-a
.venv/bin/nightforge submit DEV-1 change.patch --node node-a --verify "pytest -q"
.venv/bin/nightforge webhook delivery-123 issues payload.json
.venv/bin/nightforge transition state:claimed state:submitted
.venv/bin/nightforge github-list hangang907-png/nightforge
.venv/bin/nightforge github-claim hangang907-png/nightforge 123 --node hangang907-png
.venv/bin/nightforge github-draft hangang907-png/nightforge nightforge/ticket-123 \
  --title "fix: repair CI" --body "Closes #123"
.venv/bin/nightforge publish .nightforge/submissions/DEV-1.node-a.json \
  --github-repo hangang907-png/nightforge --issue 123
.venv/bin/nightforge webhook-state hangang907-png/nightforge check-suite.json
NIGHTFORGE_WEBHOOK_SECRET='replace-me' \
  .venv/bin/nightforge webhook-serve hangang907-png/nightforge --port 8787
```

## 상태

설계 검증 및 MVP0 구현 단계. 현재 이터레이션:
- RFC·티켓·원장 이벤트 JSON Schema
- 노드 CLI 최소 수직 흐름 (검증 → 클레임 → 결과 manifest 제출)
- 웹훅 delivery ID 멱등 기록 (중복 이벤트 무시)
- RFC·개발 티켓 GitHub Issue Forms
- 티켓 라벨 상태머신 (`open → claimed → submitted → verifying → accepted/rejected`)
- GitHub API 티켓 조회 및 단일 PATCH 클레임(assignee + 상태 라벨)
- 유지관리자 옵트인 저장소 레지스트리
- GitHub API가 `draft: true`를 강제하는 Draft PR 제출
- `nightforge publish`: manifest hash 검증 → 격리 worktree → patch 적용 → 검증 → 브랜치 push → Draft PR
- Draft PR 생성 성공 시 티켓 `claimed → submitted`
- `check_suite` 시작/완료 이벤트를 `verifying → accepted/rejected`로 변환
- `X-Hub-Signature-256` HMAC-SHA256 상수시간 검증
- delivery ID 원자적 멱등 처리, 1 MiB payload 제한, `check_suite`/`ping` 허용목록
- 의존성 없는 WSGI 웹훅 수신기 (`nightforge webhook-serve`)
- AWS SAM 배포 어댑터: Lambda + API Gateway + DynamoDB 영구 delivery receipt
- Lambda는 `NIGHTFORGE_GITHUB_TOKEN`으로 GitHub REST API를 호출하며 `gh` CLI 의존성이 없음
- Cloudflare Worker 어댑터: Workers + D1 영구 receipt + Queue 비동기 GitHub 상태 전이
