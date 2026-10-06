# G3 Codex FINAL Handoff — Story Room + Shot Board Hardening

## 현재 기준선

- Branch: `g3-story-shot-board`
- Current progress: about 65%
- Target: G3 FINAL PASS at 72%
- Main already contains G2 FINAL.
- Claude Code completed the first G3 UI/data implementation.
- Do NOT start G4/provider/API work.

## First rule

Read before editing:

1. README_KO.md
2. PROGRESS.md
3. docs/ARCHITECTURE.md
4. src/mvstudio/models.py
5. src/mvstudio/session.py
6. src/mvstudio/story_engine.py
7. src/mvstudio/g3_ui.py
8. src/mvstudio/ui_app.py
9. tests/test_g3_story_shot_board.py
10. all existing tests

Run the existing full test suite first and report the baseline.

## Product principle

This is not a prompt-list maker.

The trace chain must remain:

Music Cue
→ Lyric Line ID
→ World Concept
→ World Bible
→ Reference
→ Story Beat
→ Shot

The user must be able to understand why each Story Beat and Shot exists.

Do not create one cut for every beat or one scene for every lyric line.
The story must progress.

---

# Mandatory fixes discovered in final review

## 1. Fix Story Room sorted-selection bug

Current Story Room renders Story Beats sorted by time, but `_load_selected(row)` reads directly from the unsorted `session.story_beats[row]`.

After time edits, the list order can differ from the session list and the inspector can edit the wrong Beat.

Fix this by resolving the selected Beat by stable `beat_id`, never by visual row index.

Add regression tests:
- beats stored in one order
- displayed sorted in another
- selecting/editing a visible item must update the correct beat_id

This is a G3 blocker.

## 2. Guarantee unique stable Beat and Shot IDs

Current add logic based on `len(...) + 1` can create duplicate IDs after deletion.

Implement ID allocation helpers, e.g.:
- next_beat_id(existing_ids)
- next_shot_id(beat_id, existing_ids)

Never renumber existing IDs merely because order changes.

Add duplicate-ID validation/warnings for:
- StoryBeat.beat_id
- ShotSpec.shot_id

Tests must include delete → add cycles.

## 3. Add Shot timeline coverage validation

Create a shot-timeline validator per Story Beat.

Detect:
- leading gap inside Beat
- internal gap
- overlap
- trailing gap
- Shot outside linked Beat
- Shot with missing/invalid beat_id

Warnings should identify involved IDs and time spans.

Do not force every Beat to be fully covered when the user is still drafting, but show clear warnings.

## 4. Strengthen traceability rules

For each Story Beat validate:
- lyric_line_ids exist
- music_cue_ids exist
- reference_ids exist
- world_rule_refs exist

For each Shot validate:
- beat_id exists
- lyric_line_ids exist
- music_cue_ids exist
- reference_ids exist
- lyric_line_ids should normally be a subset of the linked Beat's lyric_line_ids
- music_cue_ids should normally be a subset of the linked Beat's music_cue_ids

Subset mismatches are warnings, not destructive auto-fixes.

## 5. Add World-rule provenance to ShotSpec

Current StoryBeat has `world_rule_refs`, but ShotSpec does not.

Add:
- `world_rule_refs: list[str]`

Requirements:
- draft_shot() copies the linked Beat's world_rule_refs
- Shot Inspector displays/edits the refs
- session JSON roundtrip preserves them
- validators check they point to existing World Bible rules

This is important for later provider prompt compilation and QC.

## 6. Reference scope eligibility

Reference models already support PROJECT / SCENE / SHOT.

G3 must stop treating every reference as equally valid for every Shot.

Implement one explicit eligibility function in core code, not UI-only logic.

Minimum policy:
- PROJECT reference: eligible everywhere
- SHOT reference: eligible only when `scope_id == shot.shot_id`
- SCENE reference: do not silently apply it everywhere

Because there is no independent Scene model yet, choose and document ONE safe policy:
A) StoryBeat is the temporary G3 scene-scope unit, so SCENE.scope_id must match beat_id
OR
B) SCENE refs remain visible but ineligible/unresolved until a scene entity exists.

Do not invent hidden string conventions.

The UI should show scope and disable or clearly mark ineligible references.
Existing stored metadata must remain backward compatible.

Add mixed-scope tests.

## 7. Improve motif progression validation

Current auto draft can fall back to the first motif for every group, creating mechanical:
SETUP → DEVELOPMENT → PAYOFF
even when the lyric group does not support that motif.

Do not force a motif merely because a motif pool exists.

Prefer:
- explicit lyric/motif evidence when present
- bridge/anchor evidence where available
- otherwise motif=None

Add motif-progression warnings:
- PAYOFF before SETUP
- DEVELOPMENT before SETUP
- repeated SETUP with no development
- motif introduced but never developed/paid off (warning only)
- payoff with no earlier occurrence

Do not auto-rewrite user choices.

## 8. Continuity hardening

Current continuity comparison uses exact set equality.

Keep a simple deterministic system, but normalize:
- trim whitespace
- case-insensitive comparison
- ignore duplicate tokens

Report:
- missing expected carry-over
- unexpected changed token

Do not add an LLM dependency in G3.

## 9. Cinematic repetition warnings

Add non-blocking warnings for obvious storyboard monotony within adjacent Shots, e.g. repeated:
- same framing
- same lens
- same angle
- same movement
- same movement_strength

Do not demand constant variation.
Warn only when several consecutive shots are effectively identical.

The goal is to prevent a visually flat AI-video list.

## 10. Literalization / one-line-one-shot warning

Add a heuristic warning, not a ban, when:
- many consecutive Shots map 1:1 to single lyric lines
- visual strategy is repeatedly `literal`
- action/environment closely duplicate the lyric evidence without narrative change

Keep it deterministic and conservative.
No external LLM/API.

## 11. Shot duration warnings

Add configurable warning thresholds only.

Suggested defaults:
- very short: < 1.2 sec
- long: > 12 sec

Do not reject these durations because intentional montage/long takes may be valid.

## 12. Session schema / backward compatibility

G3 adds persistent Story Beat and Shot fields.

Update the session schema version from 0.4 to a new version (recommended 0.5) while keeping imports of old G2 JSON working.

Do not break existing 0.4 sessions.

Add backward-compatibility tests:
- import old G2-style payload with no story_beats/shots
- import/export new G3 payload
- Korean/Japanese/space path roundtrip

## 13. Autosave and restore regression

All Story/Shot changes must continue to use the existing debounced autosave policy:
- no implicit target for unsaved new sessions
- autosave only after explicit save or opening an existing session
- atomic save preserved

Test G3 Story/Shot mutation → autosave target behavior.

## 14. UI usability hardening

Keep the beginner-readable design.

Required:
- main controls >= 42–44px
- long Korean/Japanese text wraps instead of destroying layout
- selected Beat/Shot remains stable after refresh
- warnings are readable and grouped
- many Beat/Shot items remain scrollable

Do not redesign the entire app.

---

# Do not do

- Do NOT start G4.
- Do NOT integrate Runway, Veo, Kling, Luma, fal, ComfyUI.
- Do NOT add API keys.
- Do NOT delete or rename reference source files.
- Do NOT remove lyric_line_ids or music_cue_ids.
- Do NOT replace the existing autosave design.
- Do NOT perform an unrelated large refactor.

---

# Required tests before G3 PASS

Keep all existing tests passing and add coverage for at least:

1. sorted Story Room selection edits correct beat_id
2. Beat ID uniqueness after delete/add
3. Shot ID uniqueness after delete/add/duplicate
4. Shot timeline gap/overlap/outside-Beat warnings
5. invalid lyric/music/reference/world-rule IDs
6. Shot evidence subset mismatch vs linked Beat
7. Shot world_rule_refs roundtrip
8. mixed PROJECT/SCENE/SHOT reference eligibility
9. motif progression order warnings
10. continuity normalization
11. repeated-camera warning
12. literalization heuristic warning
13. duration warning
14. G2 JSON backward compatibility
15. G3 session roundtrip
16. autosave target regression
17. PySide6 offscreen smoke
18. compileall
19. git diff --check

Run the full suite, not only G3 tests.

---

# Completion report

Only declare G3 PASS if all blocker items pass.

Report exactly:

[전체 진행률]
72%

[G3 FINAL 상태]
PASS / FAIL

[핵심 수정]
...

[추적성]
...

[Story Timeline 검증]
...

[Shot Timeline 검증]
...

[Reference Scope]
...

[Motif / Continuity / Cinematic QC]
...

[세션 호환성]
...

[전체 테스트]
xx passed / xx failed

[수동 확인 필요]
...

[남은 위험]
...

[다음 단계]
G4는 시작하지 말고 WAITING FOR REVIEW

Stop there.
