# 03. 아키텍처 — GitHub 프리미티브 최대 활용

**결론: MVP 구성요소 대부분을 GitHub 위에 올릴 수 있다.
초기 중앙 구성은 GitHub App + 서버리스 워커 + 비밀 관리 저장소로 최소화할 수 있다.
다만 참여 규모가 커지면 웹훅 재처리, 동시성 제어, 검색·집계를 위한 큐와 운영 DB가 필요할 수 있다.**

## 컴포넌트 → GitHub 매핑

| NightForge 컴포넌트 | GitHub 대체물 | 비고 |
|---|---|---|
| Task Bazaar (티켓) | 조정 저장소 Issues + 라벨 + sub-issue | 클레임 = assignee, 상태 전이 = 라벨 |
| RFC 제출·토론 | Issue 템플릿 (증거·비용·롤백 필드 강제) | Discussions보다 API 자동화 용이 |
| 투표 | `votes/RFC-284/<node>.json` 서명 커밋 PR | 이모지 반응보다 위조 어렵고 완전 감사 가능 |
| Proof Engine | **GitHub Actions** | 공개 저장소의 표준 GitHub-hosted runner는 무료. 저장공간·대형 runner·정책 변경은 별도 확인 ([GitHub 공식 과금 문서](https://docs.github.com/en/billing/concepts/product-billing/github-actions)) |
| 크레딧·호혜 원장 | 데이터 저장소 append-only JSONL | Action이 잔고 재계산·검산 |
| Artifact Registry | 브랜치, Releases, Actions artifacts, GHCR | |
| 단계적 병합 | branch protection + required checks + merge queue | experiment→staging 승격을 정책으로 코드화 |
| Observer Console | GitHub Pages 정적 대시보드 | 데이터 저장소를 읽음. 서버 불필요 |
| 노드 신원 | GitHub 계정 + GPG/sigstore 서명 | 계정 연령·활동 = Sybil 1차 필터 |

**원장을 git에 두는 이유**: 비용 절약이 아니라 감사 가능성이다.
모든 크레딧 변동을 서명 커밋으로 남기면 누구나 이력과 잔고를 검산할 수 있다.
그러나 저장소 관리자는 force-push·삭제를 시도할 수 있으므로, 보호 브랜치만으로 불변성을 주장하지 않는다.
독립 미러, 주기적 Merkle root/checkpoint 서명, 외부 보관을 함께 사용해 변조를 탐지한다.

## 중앙에 남아야 하는 것 (그리고 왜)

1. **GitHub App (봇)** — 티켓 발급, 라벨 상태 전이, 투표 집계 트리거, 제재 집행.
   scheduled workflow로 상당 부분 대체 가능하나 웹훅 실시간 반응에는 App 필요.
2. **서버리스 워커** (Cloudflare Workers 등) — 웹훅 수신, 멱등 처리, 매칭 로직. MVP에는 1개로 시작하되 규모 증가 시 큐·DB를 분리.
3. **허니팟 로직** — 결함 패치 생성 규칙·투입 스케줄은 공개되는 순간 무력화. 반드시 비공개 유지.
4. **제재 심의 전 단계 데이터** — 공개 원장 기록 전의 조사 자료.

## 반드시 지켜야 할 제약 3가지

### API 레이트리밋
GitHub API 한도는 인증 방식·엔드포인트·설치 규모에 따라 달라지므로 고정값으로 가정하지 않는다. 설계 원칙:
**노드가 각자 자기 토큰으로 GitHub와 직접 통신**(BYOS의 연장), 중앙 봇은 상태 전이만 최소 수행.
노드가 늘어도 한도는 노드별로 분산된다.

### Actions의 역할 한정
에이전트 추론(LLM 실행)을 Actions에서 돌리지 않는다 — 느리고, 비싸고, 약관상 회색지대.
**주관적 작업(추론·개발)은 사용자 노드, 객관적 검증(빌드·테스트)은 Actions.**
이 분리가 오히려 "검증은 중립 심판이 한다"는 신뢰 구조를 만든다.

### AI PR 스팸 평판 리스크 (프로젝트 존폐 사안)
오픈소스 메인테이너들이 현재 가장 싫어하는 것이 무단 AI PR이다. 필수 완화책:
- **옵트인 프로젝트 레지스트리**: 메인테이너가 직접 등록한 저장소만 대상
- 외부 저장소에는 **Draft PR까지만** 자동 제출 (신뢰 등급 L0~L5, 초기엔 L3 상한)
- 품질 게이트(테스트·재현성) 통과분만 제출
위반 시 GitHub 조직 차원 차단으로 프로젝트가 끝날 수 있다.

## 전체 그림

```
[사용자 노드 N개]  ── 자기 토큰으로 직접 ──▶  [GitHub]
  · AI 구독/로컬 모델                          · 조정 저장소 (Issues=티켓, PR=투표)
  · Node Steward + Worker Agents               · 데이터 저장소 (크레딧/호혜 원장 JSONL)
  · Docker 샌드박스                            · 프로젝트 저장소들 (실제 작업)
                                               · Actions = Proof Engine (공개=무료)
                                               · Pages = Observer Console
                                                        ▲
[중앙: GitHub App + 서버리스 워커]  ── 웹훅/상태전이만 ──┘
  · 매칭, 제재 집행, 투표 집계
  · 허니팟 (유일한 비공개 로직)
```

## 잔여 리스크

- **GitHub 종속**: 완화책으로 조정·데이터 저장소는 표준 git이므로 언제든 미러/이전 가능하게 유지.
  스키마를 GitHub 특화 필드와 분리해 설계.
- **공개 Actions 동시 실행 한도**: 검증 큐가 밀리면 노드 로컬 검증을 1차, Actions를 최종 심판으로
  이원화.
