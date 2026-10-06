# G4 Manual Generation Studio — Product & Data Contract

## 기준선

- Branch: `g4-manual-generation-studio`
- Baseline: G3 FINAL PASS
- Overall progress: 72%
- G4 target: 83%
- First gate: G4A Manual Generation Studio at 78%
- Second gate: G4B Result / Take Manager at 83%

## Critical product decision

G4 starts **without provider APIs**.

The first production workflow is:

SHOT BOARD
→ MANUAL GENERATION PACK
→ User copies instructions into a website such as Higgsfield
→ User generates the clip manually
→ User imports the generated file back into MV Director Studio
→ ACCEPT / REJECT / REGENERATE / A-B-C compare

Do not add API keys, HTTP clients, SDKs, billing logic, queues, polling, or provider credentials in G4A/G4B.

Provider automation can be added later without changing the core Shot contract.

---

# 1. Why manual-first

Video sites change quickly. The durable asset is not the website integration.

The durable chain is:

Music Cue
→ Lyric Line
→ World Bible
→ Reference
→ Story Beat
→ Shot
→ Generation Pack
→ Take
→ Final Clip

The website is an interchangeable execution surface.

G4 must therefore make a Shot understandable and executable even if the user knows almost nothing about prompt engineering.

---

# 2. G4A — Manual Generation Studio (72→78%)

## 2.1 UI goal

Enable sidebar page:

08 GENERATE

Rename or present the page as:

MANUAL GENERATION STUDIO

The beginner workflow for a selected Shot must be visually explicit:

1. Shot 확인
2. Reference 준비
3. Main Prompt 복사
4. Camera / Motion 지시 복사
5. Negative 복사
6. 사이트에서 생성
7. 결과 영상 등록

Do not overload the screen.

Recommended layout:

LEFT
- Beat / Shot selector
- Shot readiness status
- Traceability summary

CENTER
- Generation Pack sections

RIGHT
- Site Profile
- settings checklist
- copy buttons
- export pack button

---

# 3. Site profile architecture

Do not hard-code website behavior throughout the UI.

Create a provider-neutral manual-site profile model.

Recommended structure:

ManualSiteProfile
- profile_id
- display_name
- mode = "manual_web"
- prompt_style
- supports_negative_prompt
- supports_first_frame
- supports_last_frame
- supports_multi_reference
- supports_camera_presets
- camera_presets[]
- duration_options[]
- aspect_ratio_options[]
- resolution_options[]
- generation_mode_options[]
- notes[]
- website_label
- profile_version

Profiles should be data-driven where practical.

Minimum profiles:
- GENERIC_MANUAL
- HIGGSFIELD

Future profiles may include:
- KLING_WEB
- RUNWAY_WEB
- VEO_WEB

Do not require those future profiles for G4A PASS.

## Higgsfield profile principle

Higgsfield currently exposes a large set of named cinematic camera controls.
The program should support mapping CameraSpec to a suggested preset, but must never require an exact preset match.

Examples of useful preset mappings:
- subtle push-in → Dolly In
- locked camera → Static
- rack/focus emphasis → Focus Change
- orbit → 360 Orbit / Arc Left / Arc Right
- pan → Pan Left / Pan Right
- tilt → Tilt Up / Tilt Down
- handheld → Handheld

Keep this mapping configurable and fallback-safe:
- if no confident match: "Custom / no preset recommendation"

Do not couple core ShotSpec to Higgsfield-specific names.

---

# 4. ManualGenerationPack

Do not destroy the existing `GenerationPack` or existing `compile_shot()` tests.

Add a new structured contract, for example:

ManualGenerationPack
- pack_id
- shot_id
- profile_id
- created_at
- generation_mode
- main_prompt
- motion_prompt
- camera_prompt
- negative_prompt
- reference_instructions[]
- world_rule_summary[]
- continuity_summary[]
- first_frame_ref
- last_frame_ref
- duration_sec
- aspect_ratio
- resolution_hint
- camera_preset_recommendation
- lyric_evidence[]
- lyric_strategy
- settings_checklist[]
- warnings[]
- full_clipboard_text

ReferenceInstruction
- reference_id
- role
- lock_strength
- scope
- path
- instruction
- missing
- eligible

The pack is a **snapshot** of the instructions used for a generation attempt.

---

# 5. Prompt compiler layers

The Manual Generation Pack must be compiled from structured layers, not a single giant string.

Required layers:

WORLD LOCK
CHARACTER / IDENTITY LOCK
LOCATION / ENVIRONMENT LOCK
SHOT PURPOSE
SUBJECT
ACTION
COMPOSITION
CAMERA
TEMPORAL MOTION
LIGHT
MATERIAL / ATMOSPHERE
CONTINUITY IN
CONTINUITY OUT
MOTIF
WORLD RULE REFERENCES
NEGATIVE CONSTRAINTS
TRANSITION / END STATE

Lyrics must influence intent but should not be dumped as literal lyrics into every provider prompt.

Preserve:
- shot.lyric_line_ids
- shot.music_cue_ids
- shot.world_rule_refs
- shot.reference_ids
- shot.beat_id

---

# 6. Manual compiler behavior

Add a public compiler entry point, e.g.:

`compile_manual_pack(...)`

It may live in:
- `manual_generation.py`
or
- `prompt_compiler.py`

Prefer a separate module if that avoids breaking old provider-specific logic.

Important architecture issue:
The current desktop UI uses `LyricsWorldSession`, while the old `compile_shot()` uses `MusicVideoProject`.

G4 must NOT force a risky conversion of the entire app to `MusicVideoProject`.

Choose one clean solution:

A. compile directly from `LyricsWorldSession + ShotSpec`, using available World Bible / Reference data

or

B. implement an explicit adapter:
`session_to_generation_context(session)`

The adapter must be deterministic and tested.

Do not duplicate business logic between UI and compiler.

---

# 7. Prompt content rules

## Main Prompt
Focus on what the model needs to render:
- who / what
- action
- environment
- composition
- light
- emotional state
- identity / environment locks only when relevant

## Motion Prompt
Focus on temporal change:
- subject motion
- secondary motion
- pace
- beginning → change → ending state
- avoid simultaneous unrelated actions

## Camera Prompt
Separate camera behavior from subject behavior.

Example structure:
- framing
- lens
- angle
- movement
- movement strength
- suggested manual camera preset

## Negative Prompt
Combine:
- World Bible forbidden elements
- Shot negative constraints
- continuity-protection negatives where appropriate

Do not blindly create huge negative prompts.
Deduplicate and preserve high-value constraints.

---

# 8. Beginner copy UX

Each section must have an obvious copy button:

- Main Prompt 복사
- Motion 복사
- Camera 복사
- Negative 복사
- Full Pack 복사

Also include:
- Reference 경로 복사
- Shot ID 복사

Copy buttons must provide visible feedback such as:
"복사 완료"

Do not require keyboard shortcuts.

---

# 9. Generation settings checklist

A manual pack should display editable or selectable hints:

- Site Profile
- Generation Mode
- Duration
- Aspect Ratio
- Resolution Hint
- Camera Preset Recommendation
- First Frame
- Last Frame
- Reference files

These are instructions, not API parameters.

The user can change them without changing core Shot timing.

The program must distinguish:
- Shot timeline duration
- website generation duration choice

For example a 7.4-second timeline Shot may be generated as a 5s or 10s source clip and trimmed later.

Do not silently overwrite Shot start/end.

---

# 10. Readiness checks

Before a pack is marked READY, warn about:

- missing reference file
- ineligible reference scope
- missing beat_id
- invalid lyric/music/world-rule reference
- empty subject/action/environment
- invalid Shot time
- unresolved continuity warning
- first/last frame ref missing when generation mode requires it

Use statuses:
- READY
- READY_WITH_WARNINGS
- BLOCKED

Only true structural failures should be BLOCKED.

---

# 11. Pack snapshot / reproducibility

When a user generates a clip manually, they need to know what prompt/settings created it.

ManualGenerationPack must be serializable.

Store generation pack snapshots in session JSON or a compatible G4 extension.

Do not store clipboard state.

A future Take must be able to point to:
- pack_id
- shot_id
- profile_id

---

# 12. Export pack

Add an export option for a selected Shot:

- TXT or JSON
- safe filename containing Shot ID
- UTF-8
- Korean / Japanese / spaces supported

Optional later:
- batch export all Shots

G4A PASS only requires single-shot export and a reasonable batch foundation.

---

# 13. G4B — Result / Take Manager (78→83%)

Do not fully implement this during G4A unless required by architecture.

Target model:

GenerationTake
- take_id
- shot_id
- pack_id
- source_profile_id
- output_path
- created_at
- status: candidate / accepted / rejected
- reject_reason
- notes
- rating
- duration_sec optional
- file_missing state

Target workflow:

Shot
→ Pack v1
→ website generation
→ import result A
→ Pack v2
→ import result B
→ compare
→ ACCEPT one take

The original generated file must never be modified/deleted by metadata removal.

---

# 14. No API rule

For G4A and G4B, forbidden:
- API key input
- API credentials
- provider SDK installation
- HTTP generation calls
- automatic web login
- browser automation
- billing/cost API
- remote upload
- queue polling

The user explicitly starts with manual web generation.

---

# 15. Tests for G4A

Required minimum:

1. GENERIC manual profile loads
2. HIGGSFIELD profile loads
3. compiler preserves Shot provenance IDs
4. missing/ineligible refs produce warnings
5. manual pack serializes/deserializes
6. Main/Motion/Camera/Negative are distinct
7. camera mapping has safe fallback
8. duration hint does not mutate Shot duration
9. Korean/Japanese text roundtrip
10. single-shot TXT/JSON export
11. existing prompt_compiler tests still PASS
12. G0-G3 full regression PASS
13. PySide6 offscreen GENERATE page smoke
14. copy-button handlers smoke without clipboard crashes
15. compileall
16. git diff --check

---

# 16. G4A completion report

Stop at 78%.

Report:

[전체 진행률]
78%

[G4A 상태]
PASS / FAIL

[Manual Generation Studio]
...

[Site Profiles]
...

[Prompt Pack]
...

[Higgsfield Manual Profile]
...

[Readiness / Warnings]
...

[Export / Copy UX]
...

[전체 테스트]
xx passed / xx failed

[수동 확인 필요]
...

[남은 위험]
...

[다음 단계]
G4B Result / Take Manager는 시작하지 말고 WAITING FOR REVIEW

