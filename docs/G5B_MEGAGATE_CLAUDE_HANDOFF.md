# G5B MEGAGATE Claude Code Handoff

## Goal
Current: about 87%
Target: about 92%

This is one large implementation pass:
- Visual/Semantic QC
- Director Intelligence manual exchange
- Music Intelligence optional backends
- Beginner UI hardening

Do NOT start Editor/Render.
Do NOT add provider APIs.

## Read first
1. docs/G5B_MEGAGATE.md
2. docs/G5_AUTOMATED_QC.md
3. docs/BEGINNER_UI_STANDARD.md
4. src/mvstudio/technical_qc.py
5. src/mvstudio/g5a_ui.py
6. src/mvstudio/lyrics_engine.py
7. src/mvstudio/music_engine.py
8. src/mvstudio/story_engine.py
9. src/mvstudio/manual_generation.py
10. src/mvstudio/result_takes.py
11. src/mvstudio/session.py
12. src/mvstudio/ui_app.py
13. pyproject.toml
14. all tests

Run the full baseline test suite before edits.

## Implementation order
1. define optional backend availability interfaces
2. visual semantic QC core
3. palette/continuity/redundancy core
4. Director Intelligence models + strict import validation
5. Director prompt/export/import/compare/selective-apply UI
6. Music Intelligence models + backend interface
7. modern librosa compatibility
8. optional Beat backend
9. optional functional music structure backend
10. timeline fusion
11. beginner UI integration
12. schema 0.9
13. cache/versioning
14. full tests

## Critical rules
- existing heuristic lyrics/music analysis remains fallback
- optional dependencies must never break startup
- no automatic model downloads without user-visible consent
- no exact face identity claims
- no automatic ACCEPT/REJECT
- no silent overwrite of World Bible / Beats / Shots
- no editor/render work
- no provider API/browser automation
- source media remains read-only

## Beginner UI blocker
A first-time user must understand:
- what the result means
- what action is recommended
- how to use deeper Director analysis
- how to choose basic vs advanced music analysis

Internal backend/model names stay in expert details.

## Completion
Stop around 92%.

Use the completion report from docs/G5B_MEGAGATE.md and end:
WAITING FOR REVIEW
