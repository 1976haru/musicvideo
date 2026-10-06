# v0.2 변경 요약 — LYRICS → WORLD

## 추가
- `src/mvstudio/lyrics_engine.py`
- TXT/SRT/LRC parser
- ko/ja/en 언어 힌트
- POV / 중심 갈등 / 감정 Arc
- 반복 가사 탐지
- 장소·날씨·사물·시간·행동·감각·관계·빛·자연 앵커
- World Concept 3안
- LyricVisualBridge
- LLM Director Prompt Pack
- Shot별 `lyric_line_ids`, `lyric_intent`, `lyric_visual_strategy`
- WorldBible `lyric_foundation`
- QC `lyric_grounding` 20점
- `mvstudio lyrics-pack` CLI
- `docs/LYRICS_TO_WORLD.md`
- 일본어 오리지널 예제 가사와 생성 결과

## 핵심 설계 변경
이제 세계관은 임의로 생성되는 것이 아니라 가사의 Line ID에 근거를 남긴다. 후렴 반복은 같은 영상을 재사용하는 것이 아니라 setup → transformation → payoff로 발전시키는 것을 기본 규칙으로 한다.
