# G4B Claude Code Handoff — Result / Take Manager

## Current state

- Branch: g4-result-take-manager
- Overall progress: 78%
- G4A Manual Generation Studio: FINAL PASS
- Target of this pass: about 81%
- Do NOT declare G4B final 83%.
- Do NOT start G5.

## Read first

1. docs/G4B_RESULT_TAKE_MANAGER.md
2. PROGRESS.md
3. README_KO.md
4. docs/ARCHITECTURE.md
5. src/mvstudio/manual_generation.py
6. src/mvstudio/g4_ui.py
7. src/mvstudio/session.py
8. src/mvstudio/ui_app.py
9. src/mvstudio/reference_vault.py
10. existing tests

Run the full test suite before edits.

## Implementation priority

1. GenerationTake core model
2. take path portability / resolution
3. stable take ID allocator
4. core TakeManager/service
5. pack lineage validation
6. candidate / accepted / rejected state transitions
7. one accepted Take per Shot
8. missing/orphan warnings
9. session schema 0.7 + backward compatibility
10. Result / Takes UI inside page 08 GENERATE
11. result file select + drag/drop if cleanly achievable
12. manual rating / notes / reject reason
13. open result in default local player
14. unregister metadata only
15. autosave integration
16. tests

## UI rule

Do not enable 09 QC / EDIT.

08 GENERATE should contain:
- Prompt Pack
- Result / Takes

Use a tabbed or similarly clear beginner UI.

Keep main buttons >=44px and long KR/JP text wrapped.

## File safety

Registration is metadata-only.
Unregister is metadata-only.

NEVER delete, move, rename, overwrite, or transcode the user's generated result video.

## No API / No G5

Do not add:
- provider APIs
- HTTP
- browser automation
- OpenCLIP
- automatic visual QC
- render/editor pipeline

## Before implementation report

First report:
[현재 구조]
[G4A 재사용 요소]
[GenerationTake 설계]
[TakeManager 설계]
[파일 경로 정책]
[UI 구조]
[수정 예정 파일]
[테스트 계획]

Then continue implementation.

## Stop gate

Stop at about 81%.

Use the completion report format from docs/G4B_RESULT_TAKE_MANAGER.md and end with:

WAITING FOR REVIEW
