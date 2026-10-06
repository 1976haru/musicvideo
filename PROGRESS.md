# MV Director Studio 진행률

## 전체 진행률: 45%

### 완료

- G0 제품/창작 아키텍처
- G0.5 Lyrics → Meaning → World
- 가사 Line ID / Lyric Visual Bridge
- World Lab 3안 비교/선택
- Prompt Compiler 기반
- 기본 QC
- 데스크톱 Lyrics & Meaning / World Lab UI
- **G1 Music Ingest**
  - Tempo / Beat / Onset
  - Energy / Spectral change
  - Audio change candidates
  - Music + Lyrics MV Director Timeline
  - MUSIC UI
  - 세션 export

### 남은 단계

- G2 World Bible + Reference Vault: **45→58%**
- G3 Story Room + Shot Board: **58→72%**
- G4 Provider adapters: **72→83%**
- G5 Automated QC: **83→91%**
- G6 Editor/Render: **91→97%**
- G7 Packaging/Recovery/Release: **97→100%**

## 지금이 Codex 1차 병행 시점

### 45% 현재
GitHub + Codex를 시작하기 좋은 첫 시점이다.
이유는 Music/Lyrics/World의 핵심 데이터 계약이 만들어졌기 때문이다.

권장 역할:
- ChatGPT: 제품/창작 설계, 데이터 계약, Gate/PASS 정의, 코드 리뷰
- Codex: G2 구현, 테스트, 리팩터링, 파일/경로/상태관리, 반복 코딩
- Claude Code: 아직 보조. 58%부터 큰 UI/다중 파일 변경에 적극 사용

### 58%
Reference Vault가 안정화되면 Claude Code 적극 병행.

### 72%
Provider API 연동부터 로컬 + GitHub를 주 개발환경으로 전환.
