# G6 MEGAGATE Claude Code Handoff

## Current
- Branch: g6-editor-render
- Overall progress: 92%
- Target: 98%
- G5 FINAL PASS
- Do not start G7.

## Read first
1. docs/G6_EDITOR_RENDER_MEGAGATE.md
2. docs/BEGINNER_UI_STANDARD.md
3. PROGRESS.md
4. README_KO.md
5. docs/ARCHITECTURE.md
6. src/mvstudio/models.py
7. src/mvstudio/session.py
8. src/mvstudio/result_takes.py
9. src/mvstudio/technical_qc.py
10. src/mvstudio/semantic_qc.py
11. src/mvstudio/ui_app.py
12. pyproject.toml
13. all tests

Run the full baseline test suite first.

## Implement as one stage
1. edit models
2. rough-cut builder from accepted Takes
3. readiness/invariants
4. ffprobe/media probe
5. FFmpeg availability
6. per-clip normalized cache pipeline
7. concat
8. original-song audio mux
9. atomic final render
10. progress + cancel worker
11. preview render
12. simple edit adjustment UI
13. output presets
14. edit-plan JSON export
15. optional OpenTimelineIO export
16. schema 1.0
17. autosave
18. full tests

## Critical product rules
- Shot timing is authoritative.
- Generated clip audio is ignored.
- Original song is final audio.
- Long Take: trim end by default.
- Short Take: BLOCK until explicit hold-last or user repair.
- No automatic looping.
- No automatic speed changes.
- No silent gap fill.
- No full NLE clone.
- No shell=True.
- Source files remain read-only.
- Final output must be atomic.
- UI remains beginner-first.

## OTIO
Use OpenTimelineIO as optional interchange only.
Core final rendering must NOT depend on OTIO.
Do not require EDL/FCP/AAF plugins for PASS.

## Before coding report
[현재 편집/렌더 구조]
[G5 재사용 요소]
[Edit 모델]
[Rough Cut 정책]
[FFmpeg pipeline]
[Beginner UI]
[OTIO export]
[수정 예정 파일]
[테스트 계획]

Then continue implementation without waiting.

## Completion
Stop at 98% and use the report format in docs/G6_EDITOR_RENDER_MEGAGATE.md.

WAITING FOR REVIEW
