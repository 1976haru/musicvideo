# G5B MEGAGATE — Visual/Semantic QC + Director Intelligence + Music Intelligence

## Baseline
- Branch: g5-automated-qc
- Current progress: about 87%
- G5A Technical / Temporal QC: PASS
- Target after this gate: about 92%
- Do NOT start Editor/Render in this gate.
- Do NOT add provider APIs or browser automation.

## Why this gate exists
The product structure is now strong, but two creative-intelligence gaps remain:
1. lyric/world/story intelligence is still mostly heuristic/rule based;
2. music structure is still mainly novelty/energy driven rather than full functional section understanding.

This gate must close those gaps while finishing visual/semantic QC.

---

# PART A — Visual / Semantic QC

## A1. Optional OpenCLIP backend
Create a lazy, optional visual-semantic backend.

Requirements:
- OpenCLIP is optional.
- No app crash if it is not installed.
- No automatic large model download without clear user action.
- Technical QC must continue to work without it.
- Cache loaded model/backend objects.
- CPU must be supported; GPU may be used when available.
- Do not describe this as exact face identity verification.

User-facing wording:
- "프롬프트와 장면 의미가 비슷한 정도"
- "레퍼런스와 시각적으로 비슷한 정도"

Never:
- "동일인 확률"

## A2. Prompt ↔ frame semantic alignment
For a Take:
- sample representative frames;
- locate the linked ManualGenerationPack when available;
- compare frames against main prompt / shot intent;
- aggregate conservatively;
- no pack = N/A, not failure.

## A3. Reference visual similarity
Use only references eligible for the Shot.

Prioritize:
- CHARACTER_MASTER
- CHARACTER_WARDROBE
- LOCATION_MASTER
- PROP_MASTER
- COLOR_LIGHT

Do not compare against scope-ineligible references.

If OpenCLIP is unavailable:
- show "선택 기능을 사용할 수 없습니다";
- do not lower the overall result only because dependency is absent.

## A4. Palette drift
Implement an OpenCV/numpy baseline:
- sampled-frame HSV/Lab distributions;
- internal clip color drift;
- compare with COLOR_LIGHT reference or World Bible palette only when meaningful.

Use cautious wording:
- "색감 변화가 큽니다"
- "World/Reference 색감과 차이가 있을 수 있습니다"

## A5. Adjacent Shot continuity
For accepted Takes in timeline order:
- previous ending representative frame;
- next starting representative frame;
- compare coarse color/composition/embedding where available.

Use context:
- location change;
- beat change;
- continuity_in/out;
- explicit narrative transition.

Do not treat intentional hard changes as errors.

## A6. Shot redundancy
Compare adjacent accepted Takes.

Warn when shots are extremely visually similar while their narrative/camera intent differs.

Warning only. Never auto-reject.

---

# PART B — Director Intelligence

## B1. Keep current heuristic analysis
Do NOT remove current lyrics_engine.py analysis.

It remains:
- instant;
- offline;
- deterministic;
- fallback.

## B2. Add structured Director Intelligence exchange
No API is required.

Workflow:
1. 프로그램이 "AI 감독 분석 프롬프트" 생성
2. 사용자가 ChatGPT / Claude 등에 붙여넣기
3. 외부 AI가 structured JSON 생성
4. 사용자가 JSON 파일 또는 텍스트를 프로그램에 가져오기
5. 프로그램이 schema/evidence를 검증
6. 사용자가 비교 후 명시적으로 적용

No automatic overwrite.

Recommended model:
DirectorIntelligenceResult
- result_id
- created_at
- source_label
- language
- synopsis
- pov
- central_conflict
- emotional_arc
- narrative_thesis
- recurring_motifs[]
- motif_progression[]
- section_interpretations[]
- world_concepts[]
- story_beat_suggestions[]
- ending_image
- lyric_evidence_map
- warnings[]
- schema_version

Every major creative claim should cite lyric_line_ids where possible.

## B3. Strict JSON validation
Detect/block/warn:
- unknown lyric line IDs;
- duplicate suggested Beat IDs;
- impossible time ranges;
- missing evidence for major motifs/world claims;
- invalid top-level structure;
- invalid enums.

Never silently replace:
- selected World Bible;
- existing Story Beats;
- existing Shots.

Imported Director Intelligence is a proposal snapshot.

## B4. Beginner UI
Main wording:
"더 깊은 AI 감독 분석이 필요하신가요?"

Buttons:
- 감독 분석 프롬프트 복사
- AI 결과 JSON 불러오기
- 현재 분석과 비교
- 선택한 제안 반영

Show clearly:
"API 없이도 사용할 수 있습니다."

Internal IDs and schema details belong under expert details.

## B5. Apply policy
Allow explicit selective apply:
- interpretation only;
- world concept candidates;
- story beat suggestions.

Do NOT auto-regenerate all existing Shots in this gate.
Locked data must not be silently destroyed.

---

# PART C — Music Intelligence

## C1. Librosa compatibility
Current project blocks librosa 1.x.

Add compatibility with modern librosa 1.x after regression validation.

Preferred dependency intent:
- librosa >=1.0,<2

If compatibility issues exist, fix code where reasonable rather than immediately pinning back.

## C2. Beat backend interface
Create a music-analysis backend interface.

Default:
- existing librosa beat/onset engine.

Optional enhanced backend:
- Beat This when installed.

Requirements:
- lazy import;
- no crash if absent;
- CPU fallback;
- no mandatory GPU;
- no automatic large downloads without user-visible consent;
- provenance recorded.

## C3. Functional music structure optional backend
Add an optional adapter for a modern All-In-One-compatible inference package when installed.

Desired output:
- tempo;
- beats;
- downbeats;
- functional section boundaries;
- functional labels such as intro / verse / chorus / bridge / outro.

Requirements:
- optional only;
- Windows install complexity must not break default install;
- if unavailable, current AudioMap fallback remains;
- do not infer semantic Verse/Chorus labels from librosa novelty alone.

## C4. Music structure model
Recommended:

MusicStructureSegment
- segment_id
- label
- start_sec
- end_sec
- confidence
- source_backend

EnhancedMusicStructure
- backend
- tempo_bpm
- beats[]
- downbeats[]
- segments[]
- warnings[]

Persist with provenance.

## C5. Timeline fusion
When enhanced structure exists:
- fuse Chorus/Bridge/Verse boundaries with lyric returns and existing Audio transitions;
- increase director cue confidence when multiple sources agree;
- do NOT cut on every beat/downbeat;
- preserve artistic pacing.

Repeated chorus visual logic remains:
setup → transformation → payoff.

## C6. Beginner UI
Do not expose backend complexity first.

Show:
"음악 구조를 더 정확하게 분석할까요?"

Buttons:
- 기본 분석
- 고급 음악 구조 분석 (only when available)

Readable output:
Intro → Verse → Chorus → Bridge → Outro

Advanced details can show backend/confidence.

---

# PART D — Unified Beginner QC UI

Keep the primary question:
"이 영상은 사용해도 될까요?"

Show at most these groups:
1. 파일/길이
2. 화면 안정성
3. 프롬프트/레퍼런스
4. 색감/연속성
5. 다른 Shot과 중복

Status:
- ✅ 사용 가능
- ⚠ 확인 필요
- ❌ 다시 생성 권장
- ⛔ 파일 문제 해결 필요

Then one clear recommended action.

Expert metrics remain collapsed.

Main buttons >=44px.
Long Korean/Japanese text wraps.
1100×720 must remain usable.

---

# PART E — Optional dependency strategy

Heavy AI packages must not be part of the minimal install.

Recommended extras:
- music-basic
- music-intelligence
- visual-qc

Optional component availability states:
- AVAILABLE
- NOT_INSTALLED
- LOAD_FAILED

App startup must continue when optional components are missing.

---

# PART F — Session / cache

Recommended schema: 0.9

Persist:
- Director Intelligence proposal snapshots;
- enhanced music structure metadata;
- semantic QC summary/reports;
- backend/model versions;
- source fingerprints.

Do NOT store:
- model tensors;
- huge per-frame embeddings;
- binary evidence images inside session JSON.

Derived evidence belongs in cache.

---

# PART G — Tests

Minimum new coverage:
1. OpenCLIP optional-unavailable does not crash
2. semantic QC N/A when no pack
3. reference scope eligibility respected
4. palette drift deterministic synthetic test
5. adjacent continuity uses accepted Takes only
6. redundancy warning does not auto-reject
7. Director Intelligence prompt generation
8. Director JSON valid import
9. unknown lyric ID warning/block
10. duplicate suggested Beat ID warning
11. imported proposal does not overwrite current World/Story/Shot
12. selective apply interpretation
13. selective apply world concept candidates
14. selective apply story beat suggestions
15. librosa 1.x compatibility regression
16. basic backend still works without enhanced modules
17. Beat backend unavailable gracefully
18. functional structure backend unavailable gracefully
19. enhanced music structure roundtrip
20. timeline fusion increases confidence only with evidence
21. no beat-cut explosion
22. beginner UI hides technical model details by default
23. schema 0.9 roundtrip
24. 0.8 backward compatibility
25. Korean/Japanese/space paths
26. full G0-G5A regression
27. PySide6 offscreen
28. compileall
29. git diff --check

---

# Completion report

[전체 진행률]
약 92%

[G5B MEGAGATE 상태]
PASS / FAIL

[Visual / Semantic QC]

[Director Intelligence]

[Music Intelligence]

[Beginner UI]

[Optional Dependencies]

[세션 / Cache]

[전체 테스트]
xx passed / xx failed

[수동 확인 필요]

[남은 위험]

[다음 단계]
Editor / Render는 시작하지 말고 WAITING FOR REVIEW

Stop there.
