# MV Director Studio v0.4 — MUSIC + LYRICS DIRECTOR TIMELINE

AI 영상 생성 사이트를 호출하기 전에 **음악과 가사를 실제로 읽고 감독용 타임라인을 만드는 단계**까지 구현한 버전입니다.

## 현재 전체 진행률: 92% (G5B FINAL PASS)

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

## G4B FINAL PASS

- 외부 사이트에서 생성한 결과 영상을 Shot에 metadata-only로 등록
- ManualGenerationPack → GenerationTake 추적성
- Take A/B/C, candidate / accepted / rejected, Shot당 FINAL TAKE 1개
- 원본 영상 이동·이름 변경·삭제·변환 없음
- duplicate take_id / multiple accepted 비파괴 audit 및 안전한 mutation 차단
- stale/missing counter reconciliation과 missing 결과 영상 metadata-only relink
- 정렬·refresh 후 선택 안정성, 다중 drag & drop 부분 성공 처리
- G4B metadata-only 파일 안전성 정책을 G5A에서도 유지

## G5A Technical / Temporal QC

- 결과 영상 파일 읽기, 길이, 해상도, FPS 확인
- 검은 화면, 화면 멈춤, 밝기 깜빡임, 움직임과 불안정 징후 검사
- PASS / REVIEW / REGENERATE / BLOCKED 추천만 제공하며 자동 ACCEPT/REJECT 없음
- 파일 경로·크기·수정 시각·분석기 버전·옵션 기반 cache 무효화
- schema 0.8 QC report 저장·복원과 0.7 이하 하위호환
- 초보자 화면은 “이 영상은 사용해도 될까요?”와 쉬운 이유·추천 행동을 먼저 표시
- 기술 수치는 기본 화면에서 숨기고 “전문가 정보 보기”에 표시

## G5B MEGAGATE FINAL PASS

- Prompt Pack과 영상의 의미 비교를 위한 optional OpenCLIP adapter
- Shot scope에 맞는 레퍼런스만 사용하는 시각 유사도 비교
- palette drift, accepted Take 경계 continuity, 인접 Shot redundancy 경고
- API 없이 외부 AI와 교환하는 Director Intelligence JSON proposal workflow
- lyric line ID, Beat ID, 시간 범위, enum과 evidence 검증
- Interpretation / World Concept / Story Beat 제안의 명시적 선택 반영
- LIBROSA_BASIC fallback과 optional Beat/Functional Structure backend 계층
- 반복 Chorus를 setup → transformation → payoff로 발전시키는 timeline fusion
- schema 0.9 및 기존 0.8 이하 하위호환

Provider API, 브라우저 자동화, 자동 ACCEPT/REJECT, Editor / Render는 구현하지 않았습니다.

### 선택형 Music Intelligence 설치

고급 음악 패키지는 Windows/Python/PyTorch 조합에 따라 설치 조건이 달라 기본 extras에 넣지 않았습니다.

- Beat This: `pip install beat-this`
  - 모델 파일을 수동으로 내려받은 뒤 `MVSTUDIO_BEAT_THIS_CHECKPOINT`에 로컬 checkpoint 경로를 지정합니다.
  - 앱은 이름 기반 checkpoint를 요청하거나 자동 다운로드하지 않습니다.
- Functional Structure: PyTorch와 Windows용 NATTEN을 먼저 준비한 뒤 `pip install allin1`
  - 로컬 모델 준비를 확인한 환경에서만 `MVSTUDIO_FUNCTIONAL_STRUCTURE_READY=1`을 지정합니다.

두 backend 모두 CPU를 기본으로 사용하며, 설치·모델 준비·API 호출 중 문제가 발생하면 기본 librosa 분석으로 돌아갑니다.

## Codex / Claude 전환

**v0.4 / 45%가 첫 Codex 병행 시점입니다.**

`docs/G2_CODEX_HANDOFF.md`의 지시문을 그대로 사용하세요.
Claude Code는 Reference Vault가 완성되는 58%부터 적극 병행을 권장합니다.
# G6 Editor / Render

`10 EDIT / RENDER`에서 accepted Take만으로 Rough Cut을 만들고, 문제 Shot을 해결한 뒤 미리보기와 최종 MP4를 내보낼 수 있습니다.

- 긴 Take는 필요한 길이만 비파괴 trim합니다.
- 짧은 Take와 timeline gap은 사용자가 해결 방법을 명시적으로 선택합니다.
- overlap은 Shot Board에서 해결하기 전까지 render를 차단합니다.
- YouTube 1080p/4K, Vertical, Square preset을 제공합니다.
- 원곡은 `session.music_path`에서 시작하며 Take 내부 오디오는 제거합니다.
- FFmpeg가 없어도 앱은 정상 실행되고 내보내기만 사용할 수 없습니다.
- Edit Plan JSON은 항상 지원하고 OTIO는 OpenTimelineIO 설치 시에만 지원합니다.
- 모든 원본 파일은 read-only이며 final은 성공 시에만 atomic 교체됩니다.

세션 schema는 1.0이며 0.9 이하 세션도 edit data 없이 정상 로드됩니다.
