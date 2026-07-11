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
```

## 상태

설계 검증 및 MVP0 구현 단계. 현재 이터레이션:
- RFC·티켓·원장 이벤트 JSON Schema
- 노드 CLI 최소 수직 흐름 (검증 → 클레임 → 결과 manifest 제출)
- 웹훅 delivery ID 멱등 기록 (중복 이벤트 무시)
- RFC·개발 티켓 GitHub Issue Forms
- 티켓 라벨 상태머신 (`open → claimed → submitted → verifying → accepted/rejected`)
- GitHub API 티켓 조회 및 단일 PATCH 클레임(assignee + 상태 라벨)
- 옵트인 저장소/Draft PR 정책 검증 전 단계
