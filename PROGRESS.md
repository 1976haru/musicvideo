# MV Director Studio 진행률

## 전체 진행률: 100% (MV Director Studio 1.0.2 LOCAL RELEASE READY)

### 완료

- **G5B MEGAGATE (FINAL PASS)**
  - optional OpenCLIP 의미/레퍼런스 유사도 adapter와 graceful N/A
  - OpenCV palette drift, accepted Take continuity, adjacent Shot redundancy 경고
  - API 없는 Director Intelligence prompt → JSON proposal → 검증 → 선택 반영
  - LIBROSA_BASIC + optional BEAT_THIS / FUNCTIONAL_STRUCTURE backend 계층
  - concrete Beat This / All-In-One adapter, registry, CPU 기본, graceful fallback
  - 기능 구간 + audio transition + lyric return Director timeline fusion
  - schema 0.9 proposal / structure / semantic QC 저장·복원

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

### G6 핵심 목표

- Accepted Take 기반 자동 Rough Cut
- Shot 타임라인과 원곡 오디오 정렬
- FFmpeg 기반 preview/final render
- OpenTimelineIO .otio 선택형 export
- 초보자용 "자동 편집 만들기 → 미리보기 → 최종 영상 내보내기" 흐름
- 원본 미디어 read-only / 최종 출력 atomic

### G7 최종 목표

- Windows 패키징 및 packaged smoke test
- FFmpeg/ffprobe 탐지와 첫 실행 환경 진단
- 세션 백업·crash recovery·로그·진단 보고서
- 안전한 cache 정리와 프로젝트 무결성 검사
- 전체 초보자 workflow 최종 마감
- synthetic end-to-end release smoke
- GitHub Actions Windows build artifact
- MV Director Studio 1.0 release 문서 및 manifest
- 패키징 검증 실패 시 100%를 선언하지 않고 99% RELEASE BLOCKED로 보고

### 남은 단계

- G4A Manual Generation Studio: **78% / FINAL PASS**
- G4B Result / Take Manager: **83% / FINAL PASS**
- G5A Technical / Temporal QC + Beginner UI: **약 87% / 1차 구현 완료**
- G5B MEGAGATE · Visual/Semantic QC + Director Intelligence + Music Intelligence: **92% / FINAL PASS**
- G6 Editor/Render MEGAGATE: **98% / FINAL PASS**
- G7 Packaging/Recovery/Release FINAL: **100% / FINAL RELEASE READY**

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
# G6 Editor / Render MEGAGATE — FINAL PASS (98%)

- accepted Take만 사용하는 비파괴 Rough Cut
- short clip / gap 명시적 해결과 overlap blocker
- FFmpeg segment normalize → concat → 원곡 mux → atomic final output
- cover / contain, preview, 실제 progress, cancel, segment cache
- MV Director Edit Plan JSON 및 optional OpenTimelineIO export
- 세션 schema 1.0, 기존 0.9 이하 하위호환, 편집 결정 autosave
- 초보자용 `10 EDIT / RENDER` 화면과 44px 주요 행동 버튼
- 음악·Take·Reference 원본은 계속 read-only

# MV Director Studio 1.0.1 — LOCAL RELEASE HOTFIX

- Windows ONEDIR build: PASS (`release/dist/MV_Director_Studio`)
- Packaged UI/runtime smoke: PASS (`--smoke-test`, no developer PYTHONPATH)
- Packaged FFmpeg render smoke: PASS (`--render-smoke-test`, app-local FFmpeg, source bytes unchanged)
- Full tests: 98 passed / 0 failed
- Backup rotation / crash marker / recovery validation: PASS
- Session schema: 1.0
- Release gate: Packaging / Recovery / Doctor / E2E / CI

G7을 완료했습니다. G8 범위는 이 릴리스에 포함하지 않습니다.


# 1.0.1 HOTFIX

- Windows packaged music analysis SciPy compatibility packaging fixed
- Single root executable workflow: `D:\\03 musicvideo\\MV Director Studio.exe`
- Packaged + root smoke/music/render/stress gates
- Rollback protection and staging cleanup
- Session schema remains 1.0


## 1.0.1 HOTFIX RELEASE GATE
- SciPy/librosa packaged music analysis fix
- single root executable: D:\\03 musicvideo\\MV Director Studio.exe
- staging packaged smoke / music / render / stress
- root smoke / music / render / stress / GUI Music action
- rollback protection and temporary build cleanup
- session schema remains 1.0


## 1.0.2 WORLD BIBLE SAVE/UI HOTFIX
- World Bible save now persists directly to the Session JSON
- first save prompts for project JSON path; cancel never claims disk save
- World Bible form uses dark background with visible field labels
- sidebar release label uses APP_VERSION dynamically
- single root executable / staging / stress / rollback gates remain unchanged
