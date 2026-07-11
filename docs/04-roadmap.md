# 04. 로드맵

원칙: 작고 검증 가능한 것부터. 거버넌스·경제 시스템은 참여자가 생기기 전에 과설계하지 않는다.

## MVP0 — Night Grid 최소 동작 (조정 저장소 + 노드 CLI + 원장 v0)

목표: "밤에 노드가 티켓 하나를 받아 패치를 만들고 Actions가 검증한다"는 한 사이클의 증명.

- GitHub 공개 저장소만 지원, 옵트인 레지스트리 (초기엔 자기 프로젝트 1~2개)
- 노드 CLI: 티켓 클레임 → 로컬 샌드박스에서 Claude Code/Codex CLI 실행 → 패치 PR 제출
- 조정 저장소: 티켓 Issue 템플릿 + 라벨 상태머신
- Proof Engine: Actions 워크플로 (빌드 + 테스트 + 결과 코멘트)
- 원장 v0: 데이터 저장소에 JSONL append (적립만, 차감·감가 없음)
- 허용 작업 3종만: 테스트 생성, CI 복구, 문서 수정
- 자동 병합 없음 — Draft PR까지만
- 거버넌스 없음 — 프로젝트 소유자가 RFC를 수동 큐레이션

## MVP1 — 거버넌스와 호혜

- RFC Issue 템플릿 + 서명 투표 파일 + 집계 Action (5중 게이트 중 A·B·E)
- 호혜 원장 가동: 적립/차감/감가, 호혜 지수 계산
- 두레 쿼터 (개발:검증:재현 비율) + 검증 무작위 지명
- 예치금 (클레임 잠금/몰수)
- Node Steward v1: 정책 파일(YAML) 기반 자동 평가·투표
- 역할별 평판 분리 시작

## MVP2 — 방어와 진화

- 허니팟 검증 (중앙 비공개 로직)
- 동적 현상금
- 자원 약정 게이트 (5중 게이트 C·D)
- 보증인 제도
- Minority Fork
- 경쟁 개발 (동일 티켓 다중 구현 + 블라인드 평가)
- Observer Console (Pages 대시보드)

## 이후 — Autonomous Forge / Evolution Lab

- 역할 에이전트 조직 (Scout/Planner/Architect/Builder/Critic/Security/Integrator/Historian)
- staging 자동 병합 (신뢰 등급 L4~L5)
- 세대 반복 진화 실험

## 성공 지표

- 검증된 패치 수 / Maintainer가 수락한 PR 비율
- 작업당 평균 AI 비용 / 재현 성공률
- 호혜 지수 분포 (무임승차 노드 비율 추이)
- 허니팟 적발률과 오탐률
- **보안 사고·비밀정보 노출 0건**

## 다음 이터레이션 후보

1. 티켓/RFC 스키마 JSON Schema 정의
2. 노드 CLI 프로토타입 (Python 또는 TypeScript)
3. 조정 저장소 템플릿 (Issue 템플릿 + Actions 워크플로) 실물 제작
