# G5 Automated QC — Product & Data Contract

## Baseline

- Branch: `g5-automated-qc`
- Baseline: G4B FINAL PASS
- Overall progress: 83%
- G5 target: 91%
- G5A first implementation gate: about 87%
- G5B final hardening gate: 91%
- G6 Editor/Render must NOT start during G5.

## Core principle

G5 does not automatically decide art.

It assists the user by analyzing technical and visual risk, then explains the result in plain language.

No automatic ACCEPT / REJECT.

The user remains the final decision maker.

## UI principle

Read `docs/BEGINNER_UI_STANDARD.md`.

The primary QC screen must answer:

"이 영상은 사용해도 될까요?"

Example top-level result:

- ✅ 사용 가능
- ⚠ 확인 필요
- ❌ 다시 생성 권장
- ⛔ 파일 문제 해결 필요

Then show the next recommended action.

Technical scores belong under expandable details.

---

# 1. G5 phases

## G5A — Technical / Temporal QC (83→87%)

Offline, deterministic, CPU-friendly baseline.

Analyze:
- file readability
- duration / expected Shot duration
- resolution
- fps
- black / near-black frames
- frozen / near-frozen frames
- sudden flicker / brightness jumps
- frame-to-frame instability
- coarse motion amount
- possible severe jitter
- accepted result file missing
- simple first/last frame continuity hints

Use:
- ffprobe / FFmpeg where available
- OpenCV
- numpy

Do not require GPU for G5A.

## G5B — Visual / Semantic QC (87→91%)

Optional/advanced local analysis.

Potential metrics:
- prompt / frame semantic similarity
- reference visual similarity
- palette drift
- adjacent accepted-shot visual redundancy
- visual continuity between previous Take end and next Take start
- requested-vs-observed motion strength heuristic

OpenCLIP may be optional for semantic/reference similarity.

Important:
Do NOT label CLIP similarity as exact face identity verification.
Use wording such as:
"레퍼런스 시각 유사도"

A more specialized identity model can be a future optional module.

---

# 2. QC data model

Recommended:

QCMetric
- metric_id
- category
- label
- raw_value
- normalized_score 0..100 optional
- severity: info / good / warning / bad / blocked
- summary_ko
- technical_detail
- recommendation
- evidence optional

TakeQCReport
- report_id
- take_id
- shot_id
- created_at
- analyzer_version
- status: PASS / REVIEW / REGENERATE / BLOCKED
- overall_score optional
- metrics[]
- beginner_summary
- recommended_action
- sampled_frame_times[]
- warnings[]
- analysis_options

Do not embed huge frame images into session JSON.

Derived thumbnails/evidence frames go into cache, not source folders.

---

# 3. Result states

BLOCKED:
- missing file
- unreadable video
- zero/invalid duration

REGENERATE recommendation:
- severe flicker
- major frozen section
- extreme duration mismatch
- severe corruption

REVIEW:
- moderate flicker
- moderate mismatch
- low reference similarity
- motion differs from intent
- continuity concern

PASS:
- no major technical issue

These are recommendations only.

The user can still choose a Take.

---

# 4. Technical analyzers

## Media probe

Collect:
- duration
- fps
- width/height
- codec if available
- frame count estimate

Compare:
- Take duration vs Shot duration
- generation duration hint where available

Do not mutate video.

## Black frame detection

Sample frames.
Use luminance / brightness thresholds.

Avoid declaring a deliberate fade as a defect automatically.
Use:
- short isolated dark segment → info/warning
- sustained near-black unexpectedly → warning/bad

## Freeze detection

Detect long stretches of nearly unchanged frames.

Do not penalize intentional locked-camera shots solely because the camera is static.
Differentiate:
- static composition with subject motion
- entire frame near-identical for too long

Keep heuristic conservative.

## Flicker detection

Analyze frame luminance/color jumps over time.

Ignore normal scene transitions where possible.

## Motion / jitter

Use frame differences or optical flow.

Estimate:
- low / medium / high motion
- instability spikes

Do not claim exact camera motion recognition in G5A.

---

# 5. Prompt / reference alignment

G5B optional local semantic analysis:

- sample representative frames
- compare frame embedding to ManualGenerationPack main prompt
- compare frames to eligible Reference assets

Output:
- "프롬프트와 장면 의미가 대체로 맞음"
- "레퍼런스와 시각 차이가 큼"

Do not expose embedding cosine values on beginner surface.

Do not use online API.

If OpenCLIP dependency is unavailable:
- technical QC still runs
- semantic metrics show "사용 불가 / 선택 기능"
- no crash

---

# 6. Palette / continuity

For each Take:
- sample frame color distributions
- compare against World Bible palette where meaningful

For adjacent accepted Shots:
- compare previous ending frame vs next starting frame
- flag extreme visual discontinuity as REVIEW

Do not force continuity when the Shot/Beat intentionally changes location or lighting.

Use Shot/Beat context if available.

---

# 7. Redundancy

Compare adjacent accepted Takes.

Warn when several adjacent Shots are visually extremely similar while:
- narrative function differs
- camera intent differs

This is a warning, not an error.

---

# 8. Beginner QC UI

Keep 09 QC / EDIT disabled during G5A if necessary until a stable QC page exists.
When QC UI is activated, it must follow Beginner UI Standard.

Primary header:

"이 영상은 사용해도 될까요?"

Then:
- large status
- 3–5 plain-language findings
- one recommended next action

Example:

✅ 사용 가능

- 영상 길이 적절
- 심한 깜빡임 없음
- 화면 멈춤 없음
- 레퍼런스와 대체로 유사

[이 Take 사용]
[다른 Take 비교]

Advanced:
[전문가 정보 보기]

For REVIEW:
⚠ 확인 필요

"2가지 항목을 확인해 주세요."

[문제 장면 보기]
[다른 Take 비교]
[다시 생성하기]

Do not show 12 raw scores simultaneously.

---

# 9. QC workflow

Selected Shot
→ Selected Take
→ "품질 검사 시작"
→ progress
→ report
→ simple decision screen
→ user chooses:
  - keep Take
  - compare Takes
  - regenerate externally
  - inspect details

No automatic provider generation.

---

# 10. Analysis cache

Avoid re-analyzing unchanged video unnecessarily.

Cache key should include:
- resolved path
- file size
- modified time
- analyzer version
- important analysis options

Cache should be separate from source video.

Do not trust stale cache if file changed.

---

# 11. Session schema

Recommended schema: 0.8

Persist:
- QC report metadata
- summary metrics
- analyzer version
- source fingerprint

Do not persist huge binary evidence.

Backward compatibility:
- 0.7 sessions load with empty QC reports

---

# 12. G5A first-pass tests

Minimum:

1. missing file → BLOCKED
2. unreadable/invalid video → BLOCKED
3. media duration probe
4. duration mismatch warning
5. simple dark frame detection
6. freeze heuristic
7. flicker heuristic
8. motion magnitude returns deterministic category
9. no source video mutation
10. cache invalidates on file modification
11. report serialization / schema 0.8
12. old 0.7 backward compatibility
13. Korean/Japanese/space paths
14. selected Take stable after QC refresh
15. unsaved session no implicit autosave
16. saved session QC report autosave
17. beginner status text exists
18. primary action is visible
19. expert metrics hidden/collapsible by default
20. full G0-G4B regression
21. PySide6 offscreen smoke
22. compileall
23. git diff --check

Stop around 87%.

---

# 13. G5B final expectations

Before 91% final:
- optional OpenCLIP gracefully available/unavailable
- prompt alignment
- reference visual similarity
- palette drift
- adjacent-shot continuity
- redundancy
- threshold calibration tests with synthetic fixtures
- false-positive-resistant wording
- beginner UI final hardening
- full regression

---

# 14. No G6 rule

Do NOT implement:
- timeline editor
- rendering
- EDL export
- final video assembly
- auto re-generation
- provider API
- browser automation

---

# Completion report for G5A

[전체 진행률]
약 87%

[G5A 상태]
PASS / FAIL

[Technical QC]

[Temporal QC]

[Beginner UI]

[Cache]

[세션]

[전체 테스트]
xx passed / xx failed

[수동 확인 필요]

[남은 위험]

[다음 단계]
G5B는 시작하지 말고 WAITING FOR REVIEW
