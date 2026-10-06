# MV Director Studio v0.4 — MUSIC + LYRICS DIRECTOR TIMELINE

AI 영상 생성 사이트를 호출하기 전에 **음악과 가사를 실제로 읽고 감독용 타임라인을 만드는 단계**까지 구현한 버전입니다.

## 현재 전체 진행률: 78% (G4A FINAL PASS)

```text
MUSIC FILE
  ↓
Beat / Onset / Energy / Spectral Change
  ↓
Audio Change Candidates
  +
LYRICS
  ↓
POV / Conflict / Emotion / Repetition / Visual Anchors
  ↓
MV DIRECTOR TIMELINE
  ↓
WORLD LAB
  ↓
WORLD BIBLE + REFERENCE VAULT
  ↓
STORY ROOM + SHOT BOARD (1차 구현 중)
```

## v0.4 핵심 기능

- WAV / MP3 / FLAC / OGG 중심 음악 읽기
- Tempo BPM
- Beat time
- Onset
- RMS Energy
- Spectral centroid / bandwidth 변화
- 음악 변화점 후보
- Audio section 후보
- 4 / 8 / 16 beats 컷 cadence 참고값
- 가사 Line ID와 음악 변화 결합
- 반복 가사의 setup → transformation → payoff cue
- MV Director Timeline
- MUSIC 데스크톱 UI 탭
- Music/Lyrics/World 세션 JSON 저장 및 다시 열기
- 명시적으로 저장하거나 기존 세션을 연 뒤 1초 debounce autosave

## 가장 중요한 원칙

프로그램은 음악만 보고 Verse/Chorus를 확정하지 않습니다.
오디오 분석은 `section_candidate`를 만들고, 향후 가사 반복/LLM/사용자 확인으로 의미적 Section을 확정합니다.

또한 Beat가 있다고 매번 화면을 자르지 않습니다.
Timeline의 Priority는 **연출을 바꿀 만한 우선순위**이지 자동 컷 명령이 아닙니다.

## Windows 실행

`RUN_WINDOWS.bat` 더블클릭.

최초 실행 시 `.venv`를 만들고 `PySide6 + librosa + soundfile`을 설치합니다.

## CLI

```bash
mvstudio music-pack song.wav
mvstudio timeline-pack song.wav --lyrics lyrics.srt
mvstudio lyrics-pack lyrics.txt --duration 180
```

## G2 완료

- 선택한 세계관을 실제 World Bible로 잠금
- Character Master
- Wardrobe
- Location Master
- Prop Master
- Color / Light
- Composition
- Camera Motion
- Texture / Material
- drag & drop reference management
- reference lock strength
- Project scope Reference 등록
- G2 project scope는 UI에서 사용할 수 있습니다. Scene/Shot scope는 모델 준비가 완료됐으며 G3 UI에서 실제 ID에 연결됩니다.
- 세션 열기와 기존 파일 대상 autosave

G3 Story Room + Shot Board FINAL hardening을 완료했습니다. Provider API 작업은 시작하지 않았습니다.

## G4A 완료

- Manual Generation Studio
- Generic / Higgsfield manual site profile
- Shot 기반 Main / Motion / Camera / Negative prompt pack
- Reference / First-Last Frame / Duration / Aspect / Resolution 지침
- Readiness 검사, 복사, TXT/JSON export
- Pack snapshot 세션 저장·복원·autosave

G4A는 수동 웹사이트 입력 workflow만 지원하며 API, SDK, HTTP generation, 브라우저 자동화를 포함하지 않습니다.

## Codex / Claude 전환

**v0.4 / 45%가 첫 Codex 병행 시점입니다.**

`docs/G2_CODEX_HANDOFF.md`의 지시문을 그대로 사용하세요.
Claude Code는 Reference Vault가 완성되는 58%부터 적극 병행을 권장합니다.
