# Claude Code / Codex Handoff Plan

## 원칙
한 번에 “전체 프로그램 완성”을 시키지 않습니다.
Gate 단위로 작업하고 각 Gate가 PASS일 때만 다음 단계로 갑니다.

## G0.5 Lyrics-to-World 고도화 지시
`docs/LYRICS_TO_WORLD.md`를 기준으로 구현을 확장한다.
- TXT/SRT/LRC parser를 유지한다.
- 한국어/일본어/영어 가사에서 line ID를 절대 잃지 않는다.
- LLM adapter가 추가되어도 core parser/anchor extraction과 분리한다.
- WorldConcept 핵심 설정은 lyric evidence IDs를 요구한다.
- Chorus 반복 구절은 setup→transformation→payoff 여부를 검사한다.
- “가사 명사 그대로 영상화” 비율이 과도하면 warning 한다.
- 실제 사용자 가사 원문은 테스트 fixture에 커밋하지 않는다.
- 완료 시 lyric relevance regression test를 추가한다.

## G1 지시
`docs/ARCHITECTURE.md`와 현재 Pydantic 모델을 기준으로 Music Ingest 모듈을 구현한다.
- WAV/MP3 메타데이터 읽기
- librosa beat/onset
- SRT/LRC import
- 결과는 AudioMap JSON
- 원본 파일은 수정하지 않음
- unit test 추가
- Windows 경로/한글 경로 테스트
- 기존 schema 깨지지 않게 migration 고려
- 완료 시 변경 파일, 테스트, 미해결 위험을 보고

## G2 지시
PySide6로 World Bible + Reference Vault UI를 구현한다.
- reference drag/drop
- role 지정
- lock strength
- master reference
- 썸네일 cache
- project autosave
- UI와 core domain 분리
- API key 저장 기능은 아직 구현하지 않음

## G3 지시
Story Beat와 Shot Board를 구현한다.
- 음악 타임라인과 연결
- shot duration 검증
- motif recurrence
- continuity_in/out
- ShotSpec card
- provider 미선택 상태도 허용

## G4 지시
provider adapter interface를 기준으로 Manual/Runway/Veo/Luma/fal/ComfyUI를 독립 모듈로 구현한다.
- core가 vendor SDK에 직접 의존하지 않게 함
- 각 adapter는 capabilities를 반환
- 실제 API 호출은 명시적 버튼에서만
- API key는 환경변수/로컬 vault
- log에 key 출력 금지

## G5 지시
QC engine 구현.
- 자동 점수는 advisory
- 결과 삭제 금지
- reject 이유 저장
- A/B 결과 보존
- threshold는 설정 파일화


## v0.3 HANDOFF RULE
G1 Music Ingest가 테스트까지 PASS해 전체 45%가 되면 GitHub에 올리고 Codex/Claude Code 병행을 시작한다. Codex는 테스트/리팩터링/CLI, Claude Code는 PySide6 timeline/drag-drop UX, ChatGPT는 World Bible/Reference Vault schema와 Gate 리뷰를 맡는다.


## CURRENT HANDOFF — v0.4 / 45%

이제 Codex 1차 병행 시점이다. G2는 `docs/G2_CODEX_HANDOFF.md`를 기준으로 진행한다.
