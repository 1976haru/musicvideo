# G5A Claude Code Handoff — Technical QC + Beginner UI

## Current state

- Branch: g5-automated-qc
- Overall progress: 83%
- G4B FINAL PASS
- This pass target: about 87%
- Do NOT declare G5 FINAL 91%
- Do NOT start G6.

## Read first

1. docs/G5_AUTOMATED_QC.md
2. docs/BEGINNER_UI_STANDARD.md
3. PROGRESS.md
4. README_KO.md
5. docs/ARCHITECTURE.md
6. src/mvstudio/result_takes.py
7. src/mvstudio/g4b_ui.py
8. src/mvstudio/session.py
9. src/mvstudio/ui_app.py
10. existing QC code
11. all tests

Run the full baseline test suite first.

## First-pass scope

Implement G5A only:

1. QC core data models
2. media probe
3. duration comparison
4. black/near-black detection
5. freeze detection
6. flicker/brightness-jump detection
7. coarse motion/jitter metric
8. deterministic PASS / REVIEW / REGENERATE / BLOCKED recommendation
9. analysis cache
10. schema 0.8 + 0.7 backward compatibility
11. beginner-first QC UI
12. autosave/report persistence
13. tests

## Beginner UI is a blocker

Do not build an engineer dashboard first.

The first screen must say in plain Korean:

"이 영상은 사용해도 될까요?"

Show:
- large status
- short reasons
- recommended next action

Technical values must be hidden under:
"전문가 정보 보기"

A first-time user must not need to know:
- luminance threshold
- optical flow
- frame delta
- codec internals
- internal IDs

Keep buttons >=44px.
Long Korean/Japanese text wraps.
At 1100x720 the main action must remain visible.

Every warning should suggest a recovery action when possible.

## Technical rules

- no source file mutation
- no transcoding
- no provider API
- no browser automation
- no auto ACCEPT
- no G6 editor
- OpenCLIP is NOT required in G5A

Prefer offline deterministic CPU-safe analysis.

If FFmpeg/ffprobe is unavailable, degrade gracefully where practical rather than crashing the whole app.

## Before implementation report

First report:
[현재 QC 구조]
[G4B 재사용]
[QC 모델]
[분석 파이프라인]
[Beginner UI]
[Cache]
[수정 예정 파일]
[테스트 계획]

Then continue implementation.

## Stop gate

Stop around 87% and use the completion report in docs/G5_AUTOMATED_QC.md.

WAITING FOR REVIEW
