# G7 FINAL RELEASE — Claude Code Handoff

## Current
- Branch: g7-release-final
- Overall progress: 98%
- Target: 100%
- This is the final stage.

## Read first
1. docs/G7_FINAL_RELEASE_GATE.md
2. docs/BEGINNER_UI_STANDARD.md
3. PROGRESS.md
4. README_KO.md
5. docs/ARCHITECTURE.md
6. pyproject.toml
7. RUN_WINDOWS.bat
8. src/mvstudio/ui_app.py
9. src/mvstudio/session.py
10. src/mvstudio/editor.py
11. src/mvstudio/optional_backends.py
12. all tests

Run the full baseline test suite first.

## Final implementation scope
Implement in one pass:
- version/release identity
- Windows packaging
- FFmpeg discovery/capability doctor
- app-data paths
- rotating backups
- crash marker/recovery
- rotating logs
- sanitized diagnostics
- top-level exception safety
- cache cleanup
- project integrity doctor
- beginner workflow polish
- synthetic E2E fixture
- packaged smoke test
- Windows GitHub Actions build artifact
- release manifest
- README/release docs
- final no-regression testing

## Non-negotiable
- Do not claim 100% without a successfully built packaged Windows artifact and packaged smoke test.
- If build/smoke cannot be verified, report 99% RELEASE BLOCKED.
- Do not bundle secrets.
- Do not modify source media.
- Do not automatically download large optional models.
- Optional AI dependencies must not block startup.
- Do not start provider API/browser automation work.
- Do not redesign the product architecture in this final stage.

## Packaging preference
Prefer PyInstaller ONEDIR for the primary release.
Keep runtime paths portable.
Support app-local FFmpeg discovery plus PATH fallback.
Do not assume the developer's PATH.

## Before coding report
[현재 릴리스 상태]
[패키징 구조]
[FFmpeg 전략]
[복구 전략]
[로그/진단]
[E2E/패키지 smoke]
[수정 예정 파일]
[최종 테스트 계획]

Then continue without waiting for confirmation.

## Completion
Use docs/G7_FINAL_RELEASE_GATE.md completion format.

WAITING FOR REVIEW
