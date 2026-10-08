# MV Director Studio 1.0.2 — World Bible Save/UI Hotfix

## Branch
hotfix-1.0.2-worldbible-save-ui

## User-reported issues
1. On 04 WORLD BIBLE, the old save button could show success while no Session JSON existed.
2. The QFormLayout label column appeared white and field names were effectively invisible in the dark UI.
3. Sidebar and startup status still contained stale release/development text.

## Already patched
- Button renamed to World Bible + 세션 저장.
- First World Bible save asks for a Session JSON path and writes immediately.
- Subsequent saves write immediately to the existing Session JSON.
- Cancel explicitly says the change is only in memory and never claims disk-save success.
- Existing atomic session export / backup behavior remains.
- World Bible scroll host is dark and labels are explicit visible formLabel widgets.
- Sidebar release label uses APP_VERSION dynamically.
- Startup status uses APP_VERSION and beginner wording.
- Version bumped to 1.0.2; session schema remains 1.0.
- Regression tests added for first-save persistence, cancel behavior, dark form labels.

## Required local validation
1. Pull this branch.
2. Run full pytest.
3. Run compileall and git diff --check.
4. Run the new World Bible regression tests.
5. Run the full existing release build: staging PyInstaller, packaged smoke/music/render/stress, root deploy, root smoke/music/render/stress/GUI Music action.
6. If release-stress does not exercise World Bible save, add an offscreen save/reopen check using the same button code path.
7. Manually launch only D:\03 musicvideo\MV Director Studio.exe.
8. Open the saved 05 project session.
9. Verify no white label column; all 13 field labels are visible; button reads World Bible + 세션 저장; save creates/updates JSON; close/reopen preserves edits; sidebar shows Release 1.0.2.
10. Do not create versioned EXE filenames or permanent release folders. Root executable remains D:\03 musicvideo\MV Director Studio.exe.

## Completion report
[버전] 1.0.2
[World Bible 실제 파일 저장] PASS/FAIL
[첫 저장 경로 선택] PASS/FAIL
[재저장 동일 JSON] PASS/FAIL
[세션 재열기 보존] PASS/FAIL
[흰 배경 제거] PASS/FAIL
[13개 필드 라벨 가시성] PASS/FAIL
[전체 테스트] xx passed / xx failed
[packaged gates] PASS/FAIL
[root gates] PASS/FAIL
[실제 GUI 확인] PASS/FAIL
[실행 위치] D:\03 musicvideo\MV Director Studio.exe
[최종 상태] 1.0.2 HOTFIX READY / BLOCKED

WAITING FOR REVIEW