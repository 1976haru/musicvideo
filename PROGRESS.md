# MV Director Studio 진행률

## 전체 진행률: 약 87% (G5A Technical / Temporal QC + Beginner UI)

### 완료

- **G5A Technical / Temporal QC + Beginner UI**
  - read-only 영상 읽기·duration·resolution·fps 검사
  - near-black / freeze / flicker / coarse motion / instability heuristic
  - deterministic PASS / REVIEW / REGENERATE / BLOCKED 추천
  - source fingerprint 기반 QC cache와 schema 0.8 roundtrip
  - 결론 → 쉬운 이유 → 추천 행동 → 접힌 전문가 정보 UI

- **G4B Result / Take Manager (FINAL PASS)**
  - metadata-only result registration and portable paths
  - Shot → Pack → Take lineage
  - candidate / accepted / rejected state transitions
  - Take A/B/C compare list and one FINAL TAKE per Shot
  - schema 0.7 session roundtrip / autosave
  - duplicate ID / multiple accepted 비파괴 audit와 mutation 차단
  - stale counter reconciliation, metadata-only missing-file relink
  - refresh 후 stable selection과 partial-success multi-file drop

- **G4A Manual Generation Studio (FINAL PASS)**
  - GENERIC_MANUAL / HIGGSFIELD data-driven profiles
  - LyricsWorldSession + ShotSpec manual pack compiler
  - Main / Motion / Camera / Negative / Reference instructions
  - Readiness, camera preset recommendation, TXT/JSON export
  - Pack snapshot session save/open/autosave

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
- **G2 World Bible + Reference Vault**
  - 선택 WorldConcept → WorldBible draft 승격
  - lyric foundation / source concept 추적
  - 역할·잠금 강도·scope·Master 메타데이터
  - Project scope UI 지원, Scene/Shot scope는 모델만 준비 (G3에서 연결)
  - drag & drop / 파일 선택 Reference UI
  - 원본 보존형 add/remove와 missing-file 상태
  - 상대/절대 경로 세션 roundtrip
  - core/UI 분리 thumbnail cache
  - 기존 JSON 세션 열기 및 화면 복원
  - 사용자가 정한 세션 파일 대상 debounced atomic autosave
  - Project scope는 UI 사용 가능, Scene/Shot scope는 데이터 모델만 준비되어 G3 UI에서 연결 예정
  - 세션 열기 및 자동 저장
- **G3 Story Room + Shot Board (FINAL PASS)**
  - 음악 cue / 가사 Line ID 기반 Story Beat 자동 초안과 편집 UI
  - Beat 시간 구간 gap / overlap 경고
  - Story Beat에서 Shot 생성·시간 분할·복제·삭제
  - Reference ID 연결, World Bible 금지 요소 및 continuity 경고
  - G3 FINAL PASS 확정

### UI 원칙

- G5부터 Beginner UI Standard 적용
- 처음 실행한 사용자도 설명서 없이 주요 흐름을 완료할 수 있어야 함
- 상태 → 이유 → 추천 행동 → 전문가 상세 순서

### 남은 단계

- G4A Manual Generation Studio: **78% / FINAL PASS**
- G4B Result / Take Manager: **83% / FINAL PASS**
- G5A Technical / Temporal QC + Beginner UI: **약 87% / 1차 구현 완료**
- G5B Visual / Semantic QC: **87→91%**
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
로컬 + GitHub를 주 개발환경으로 전환. 초기 G4는 API가 아니라 Higgsfield 같은 웹사이트에 수동 입력하는 Generation Pack 방식으로 진행.
