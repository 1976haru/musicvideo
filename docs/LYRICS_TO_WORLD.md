# LYRICS → WORLD ENGINE v0.2

## 목적
가사를 “영상에 넣을 문장”으로 취급하지 않고, **뮤직비디오의 세계관과 장면을 정당화하는 원천 데이터**로 사용한다.

```text
LYRICS
  ↓
LINE / TIME SEGMENTATION
  ↓
MEANING MAP
  ├─ POV
  ├─ central conflict
  ├─ emotional arc
  ├─ repeated phrases / chorus
  ├─ place / weather / object / motion / sensory anchors
  └─ visual risks
  ↓
WORLD LAB
  ├─ grounded literal concept
  ├─ restrained magical-realism concept
  └─ hybrid concept (recommended)
  ↓
LYRIC ↔ VISUAL BRIDGE
  ↓
STORY BEAT
  ↓
SHOT
  ↓
PROVIDER PROMPT
```

## 1. 가사 입력
지원: TXT / SRT / LRC. SRT/LRC는 타임코드를 유지하고, TXT는 곡 길이를 알면 1차 시간 배치를 한다. 이후 Music Ingest에서 실제 음악 구조와 다시 맞춘다.

## 2. 가사를 그대로 그림으로 만들지 않는다
나쁜 방식: “비가 내리고 너를 기다렸어” → 비 맞으며 누군가를 기다리는 사람만 생성.

좋은 방식: 먼저 그 문장의 기능을 `사건 / 감정 / 기억 / 반복 후렴 / 시간 변화 / 상징 / 감각 / 공간`으로 판정하고 다음 시각 전략을 선택한다.

- `literal`: 실제 사건/행동으로 옮김
- `metaphor`: 빛, 공간, 거리, 물성 변화로 옮김
- `motif`: 후렴/반복 구절을 반복 상징으로 발전
- `counterpoint`: 가사와 반대되는 평온한 장면 등으로 긴장 형성
- `performance`: 보컬/연주 중심
- `silence`: 일부러 비워 감정을 남김

## 3. 가사 근거 추적
모든 핵심 장면은 `lyric_line_ids`, `lyric_intent`, `lyric_visual_strategy`를 가진다.

```json
{
  "shot_id": "S018",
  "lyric_line_ids": ["L027", "L028"],
  "lyric_intent": "떠난 사람을 원망하기보다 아직 습관처럼 기다리는 상태",
  "lyric_visual_strategy": "motif"
}
```

따라서 “왜 이 장면이 들어갔지?”라는 질문에 프로그램이 가사 근거를 설명할 수 있다.

## 4. World Lab
가사 분석 후 최소 3개 세계관 후보를 만든다.

### A. Grounded / Literal
가사 속 실제 장소·사건 중심. 연결감은 강하지만 뻔한 재연이 될 위험이 있다.

### B. Metaphoric
감정을 하나의 물리 법칙으로 만든다. 불가능한 규칙은 되도록 하나만 둔다.

예: 기억이 강해질수록 창문의 빗물이 과거를 반사한다.

### C. Hybrid — 기본 추천
현실 80% + 시적 비현실 20%. 현실의 인물·공간이 중심이고 반복 가사/감정 문턱에서만 하나의 비현실적 현상이 나타난다.

## 5. Chorus Rule
같은 후렴이 3번 나와도 같은 이미지를 3번 만들지 않는다.

예: “다시 네가 돌아오면”

- 1차 후렴 — SETUP: 빈 의자를 본다.
- 2차 후렴 — TRANSFORMATION: 빈 의자에 과거의 그림자가 잠깐 앉는다.
- 3차 후렴 — PAYOFF: 추억의 물건을 의자에 남기고 떠난다.

**같은 가사 → 다른 서사 상태**가 되어야 한다.

## 6. Lyric Relevance Score
권장 배점:
- 25: 핵심 갈등이 가사에서 왔는가
- 20: 주요 motif가 가사 앵커에서 왔는가
- 20: 감정 곡선이 가사 순서와 연결되는가
- 15: 후렴이 발전형 motif로 설계되었는가
- 10: 장면에 lyric line ID가 남아 있는가
- 10: 결말이 초반 가사/상징을 회수하는가

85점 미만이면 World/Story 단계로 되돌리는 것을 권장한다.

## 7. UI 추가
기존: MUSIC → WORLD BIBLE → REFERENCE → STORY → SHOT → GENERATE → QC

v0.2: **MUSIC → LYRICS & MEANING → WORLD LAB → WORLD BIBLE → REFERENCE → STORY → SHOT → GENERATE → QC**

### LYRICS & MEANING
왼쪽: 가사/타임코드/Verse-Chorus 태그

가운데: POV/중심 갈등/감정곡선/반복구절/장소·사물·날씨·감각 앵커

오른쪽: literal/metaphor/motif/counterpoint 추천과 이유

### WORLD LAB
후보 3개 카드에 다음을 표시한다.
- 한 줄 세계관
- 현실 법칙
- 가사 근거 Line ID
- 반복 motif
- 결말 이미지
- Lyric relevance score
- 세계관 선택 버튼

## 8. LLM 연결 원칙
로컬 규칙 기반 분석은 **가사 앵커와 Line ID를 안정적으로 유지**하는 역할을 하고, 고차원적인 문학적 해석과 세계관 확장은 연결된 LLM이 맡는다.

LLM에게 원문만 던지지 않고 프로그램이 먼저 POV, 반복구절, 감정곡선, concrete anchor, conflict를 구조화해 전달한다. `lyrics-pack`이 생성하는 `05_director_llm_prompt.txt`가 그 입력 계약의 초안이다.
