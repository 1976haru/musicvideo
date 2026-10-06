# MV Director Studio — Architecture Blueprint

## 1. 제품 정의

MV Director Studio는 “프롬프트 생성기”가 아니라 **AI Music Video Pre-production + Generation Orchestrator + Continuity QC**입니다.

### 입력
- 음악 WAV/MP3
- 가사 TXT/SRT/LRC
- 레퍼런스 이미지/영상
- 사용자가 적은 한 줄 아이디어 또는 스토리
- 선택: 캐릭터 마스터 이미지, 장소 마스터 이미지

### 출력
- World Bible
- Character / Location / Prop Bible
- Story Beats
- Shot List
- Provider별 Generation Pack
- 생성 결과 및 버전 비교
- QC 리포트
- 최종 편집용 타임라인/EDL/FFmpeg manifest

---

## 2. 전체 파이프라인

```text
MUSIC INGEST
   ↓
AUDIO MAP
(tempo / beat / onset / lyric / sections)
   ↓
CREATIVE THESIS
   ↓
WORLD BIBLE
   ↓
REFERENCE VAULT
   ↓
STORY ARCHITECT
   ↓
SHOT DIRECTOR
   ↓
CONTINUITY SUPERVISOR
   ↓
PROMPT COMPILER
   ↓
MANUAL GENERATION STUDIO (G4 FIRST)
   ├─ Generic Website Pack
   ├─ Higgsfield Manual Profile
   └─ Future Manual Profiles
   ↓
OPTIONAL PROVIDER ADAPTERS (LATER)
   ├─ Runway
   ├─ Veo
   ├─ Luma
   ├─ Kling via fal
   └─ ComfyUI Local
   ↓
OUTPUT VAULT
   ↓
QC ENGINE
   ↓
REGENERATE / ACCEPT
   ↓
EDITOR
(FFmpeg / PySceneDetect)
```

---

## 3. 핵심 데이터 모델

### Project
- title
- song
- creative_thesis
- world_bible
- characters
- locations
- props
- reference_assets
- story_beats
- shots
- outputs

### WorldBible
반드시 “좋아 보이는 키워드”가 아니라 **변하면 안 되는 규칙**을 저장합니다.

- premise
- emotional_thesis
- reality_rules
- time_period
- visual_language
- palette
- material_language
- weather_rules
- lighting_rules
- camera_rules
- recurring_motifs
- forbidden_elements

### CharacterBible
- identity_anchor
- age_range
- silhouette
- face/hair anchors
- wardrobe locks
- accessories
- motion signature
- emotional range
- forbidden_variations
- master_reference_ids

### LocationBible
- architectural grammar
- spatial anchors
- time/weather rules
- signature objects
- entry/exit logic
- master_reference_ids

### ShotSpec
샷 하나가 생성에 필요한 모든 계약입니다.

- start/end/duration
- narrative_function
- lyric_or_music_cue
- subject
- action
- environment
- composition
- camera
- lighting
- emotional_note
- motif
- continuity_in
- continuity_out
- reference_ids
- generation_mode
- first_frame / last_frame
- negative_constraints

---

## 4. “거장급 세계관”을 만드는 구조

특정 창작자의 표현을 복제하지 않습니다. 대신 아래 **작가주의적 설계 요소**를 구조화합니다.

### A. 세계 법칙
예: “비가 오면 도시의 오래된 기억이 유리창에 비친다.”

### B. 반복 모티프
예: 붉은 우산 / 유리컵의 물결 / 떠나는 전차 / 푸른 리본.

모티프는 최소 3회 등장하되 같은 방식으로 반복하지 않습니다.

- 1차: 발견
- 2차: 의미 변화
- 3차: 회수 / 결말

### C. 공간의 기억
장소를 배경 이미지가 아니라 **서사 상태를 가진 객체**로 관리합니다.

### D. 감정 곡선
곡의 볼륨이 아니라 “인물의 감정적 거리”를 수치화합니다.

예:
`0.15 → 0.25 → 0.62 → 0.40 → 0.90 → 0.55`

### E. 시각적 문법
카메라 규칙을 잠급니다.

예:
- Verse: 정적인 50mm / 미세한 전진
- Pre: 인물과 배경 거리 증가
- Chorus: 35mm / 이동량 확대
- Bridge: 거의 정지 + 상징 클로즈업
- Final: 앞 장면의 시각 motif 회수

---

## 5. 레퍼런스 계층

레퍼런스는 폴더에 사진을 모아 두는 방식이 아니라 역할을 부여합니다.

```text
REFERENCE VAULT
├─ CHARACTER_MASTER
├─ CHARACTER_WARDROBE
├─ LOCATION_MASTER
├─ PROP_MASTER
├─ COLOR_LIGHT
├─ COMPOSITION
├─ CAMERA_MOTION
└─ TEXTURE_MATERIAL
```

각 레퍼런스는 다음 메타데이터를 가집니다.

- reference_id
- role
- file_path
- lock_strength: 0.0~1.0
- applies_to: project / scene / shot
- notes
- embedding(optional)
- provider_asset_id(optional)

### G2 파일 경로 및 원본 보존 정책

- 세션 파일이 저장된 프로젝트 폴더 안의 reference는 POSIX 구분자를 사용한 상대경로로 저장한다.
- 프로젝트 폴더 밖의 reference는 정규화한 절대경로로 저장한다.
- 상대경로는 세션 JSON의 부모 폴더를 기준으로 복원한다.
- 등록/등록 해제는 메타데이터만 변경하며 원본을 이동, 이름 변경, 수정, 삭제하지 않는다.
- 존재하지 않는 파일도 metadata를 유지하고 `missing` 상태로 표시한다.
- thumbnail은 원본과 별도의 사용자 cache에 파생 파일로 저장한다.

---

## 6. Prompt Compiler

하나의 긴 문장을 저장하지 않습니다.

```text
WORLD LOCK
CHARACTER LOCK
LOCATION LOCK
SHOT INTENT
SUBJECT ACTION
CAMERA
TEMPORAL MOTION
LIGHT
MATERIAL / ATMOSPHERE
CONTINUITY
NEGATIVE CONSTRAINTS
TRANSITION INTENT
```

Provider adapter가 이를 재조립합니다.

### Runway Image-to-Video
이미지가 이미 구도·인물·빛을 주므로 **움직임과 카메라 중심으로 짧게** 만듭니다.

### Veo
first/last frame, 연장, 장면 묘사를 활용하는 장면에 우선 배정합니다.

### Luma
keyframe 및 extend 연결이 필요한 연속 장면에 우선 배정합니다.

### Kling/fal
인물 행동과 카메라 움직임을 명확하게 분리해 컴파일합니다.

### ComfyUI
positive / negative / seed / workflow variable / reference paths로 내보냅니다.

---

## 7. Generation Strategy Router

모든 샷을 비싼 최고 모델로 돌리지 않습니다.

| 샷 유형 | 우선 전략 |
|---|---|
| 얼굴 클로즈업/연기 | reference 강한 I2V |
| 공간 establishing | T2V 또는 master image→I2V |
| 앞뒤 연결 장면 | first+last frame / keyframe |
| 반복 motif | 기존 output을 reference로 재사용 |
| 몽환/추상 | T2V |
| 정체성 민감 장면 | reference + 낮은 변화량 |
| 카메라가 복잡한 샷 | 고급 API 모델 + 짧은 길이 |

---

## 8. QC Engine

### 자동 점수
- Prompt alignment
- Reference similarity
- Character consistency
- Palette drift
- Flicker / jitter
- Motion strength
- Cut rhythm
- Shot redundancy

### 감독 점수
- World coherence
- Emotional truth
- Motif usefulness
- Narrative clarity
- Originality
- “다음 샷을 보고 싶은가?”

자동 점수만으로 최종 승인하지 않습니다.

---

## 9. UI 구조

### ① MUSIC
음악 파일, 가사, SRT를 불러오고 파형/비트/가사/섹션을 확인.

### ② WORLD BIBLE
세계관 한 줄 → 규칙 → 색 → 빛 → 소재 → 금지 항목.

### ③ REFERENCE VAULT
드래그앤드롭. 역할 지정. Master/Secondary/Do Not Use.

### ④ STORY ROOM
3막/5막/뮤직비디오형 비선형 구조 선택.
각 Story Beat를 음악 타임라인에 배치.
G3에서 Beat는 `lyric_line_ids`와 `music_cue_ids`를 함께 보존하며, 반복 motif의 setup/development/payoff 상태와 World Bible 규칙 및 Reference ID를 연결한다.

### ⑤ SHOT BOARD
카드형 샷 보드.
썸네일 / 타임코드 / 렌즈 / 카메라 / reference / provider / prompt.
각 Shot은 상위 `beat_id`와 가사·음악 근거 ID를 이어받고, continuity in/out 비교 경고를 제공한다.

### ⑥ GENERATE
G4 초기 기본은 API가 아니라 “사이트 수동 입력 Pack”이다.
Shot별 Main / Motion / Camera / Negative / Reference / First-Last frame / Duration / Aspect 지시를 만들고 복사한다.
Higgsfield 같은 웹사이트에서 사용자가 직접 생성한 뒤 결과를 다시 등록한다.

### ⑦ QC / EDIT
A/B 결과 비교, Reject reason, Re-render, Final lock.
최종 클립을 음악 타임라인에 붙여 출력.

---

## 10. 권장 기술

### Desktop
- Python 3.11+
- PySide6
- SQLite
- Pydantic
- SQLModel(optional)

### Media
- FFmpeg
- PySceneDetect
- OpenCV
- librosa
- faster-whisper
- optional Demucs

### Visual QC
- OpenCLIP
- optional DINO 계열
- OpenCV temporal metrics

### AI Video
- G4 first: Manual Website Pack (Generic / Higgsfield)
- Later optional: Runway API
- Later optional: Google Veo
- Later optional: Luma
- Later optional: Kling via fal
- Later optional: ComfyUI local

### Packaging
- PyInstaller
- GitHub Actions
- Windows first

## 11. Lyrics-to-World Engine (v0.2)

`MUSIC INGEST → LYRICS & MEANING → WORLD LAB → WORLD BIBLE → STORY → SHOT` 순서로 확장한다.

World/Beat/Shot은 가능한 한 `lyric_line_ids`를 보존해 생성 이유를 추적할 수 있어야 한다. 상세 설계는 `docs/LYRICS_TO_WORLD.md` 참고.
