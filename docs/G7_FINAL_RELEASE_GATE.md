# G7 FINAL RELEASE GATE — Packaging / Recovery / Windows Release

## Baseline
- Branch: g7-release-final
- Baseline: G6 FINAL PASS
- Overall progress: 98%
- Target: 100%
- This is the final implementation/release stage.
- No new creative scope. No provider APIs.

## Product goal
A beginner should be able to:
1. install/start MV Director Studio,
2. create/open a project,
3. bring in music/lyrics/references,
4. build World/Story/Shots,
5. generate prompt packs,
6. register/select Takes,
7. run QC,
8. build a rough cut,
9. render a final music video,
10. recover safely from ordinary crashes or missing files.

The final PASS is based on end-to-end usability and recoverability, not only unit tests.

---

# 1. Release identity

Move product to a coherent 1.0 release identity.

- package/app version: 1.0.0
- session schema remains 1.0 unless a schema change is strictly necessary
- visible app title includes MV Director Studio 1.0
- README/PROGRESS/CHANGELOG align
- create release notes / known limitations

Do not change schema merely to match app version.

---

# 2. Windows packaging strategy

Use PyInstaller or an equally stable installed packaging route already compatible with the project.

Prefer Windows ONEDIR for primary release because:
- PySide6
- OpenCV
- librosa
- optional ML components
- external FFmpeg tooling
are easier to diagnose and update than in one-file mode.

Optional one-file experiment is not required for PASS.

Deliver:
- reproducible build script
- spec file if needed
- icon handling only if an existing legal icon is available
- no hidden dependency on developer machine paths
- clean build/dist folders
- portable relative runtime paths

Expected release layout example:

MV_Director_Studio/
  MV Director Studio.exe
  _internal/...
  tools/
    ffmpeg/ (optional packaged location)
  logs/
  cache/
  recovery/
  README_FIRST.txt or equivalent

Do not include private keys, tokens, local absolute paths, or developer-only files.

---

# 3. FFmpeg discovery

Centralize FFmpeg/ffprobe discovery.

Search order:
1. explicitly configured application path
2. app-local bundled tools/ffmpeg/bin
3. system PATH

Do not rely on developer machine PATH only.

Expose a diagnostics result:
- FFmpeg found
- ffprobe found
- version
- encoder support relevant to our render defaults

At minimum verify:
- H.264 encoder actually available for chosen default
- AAC encoder available for MP4 default

If default encoder missing:
- beginner-readable blocker
- show how to fix or choose a supported fallback if implemented
- no destructive behavior

Do not silently download FFmpeg in the background.

If a release bundle includes FFmpeg binaries, document source/license/redistribution obligations.
Do not commit giant binaries into Git unless explicitly intended.

---

# 4. First-run / environment doctor

Create a beginner-first startup diagnostics flow.

Main question:
"뮤직비디오 제작 준비가 되었나요?"

Check:
- writable app data/cache/log/recovery folders
- FFmpeg / ffprobe
- PySide6 runtime
- basic media decode
- optional OpenCLIP
- optional Beat This
- optional Functional Structure
- optional OpenTimelineIO

Separate:
Required:
- core desktop app
- basic music analysis
- media handling required for final render
Optional:
- enhanced music structure
- semantic QC
- OTIO export

Do not block startup because optional tools are absent.

Show:
✅ 준비됨
⚠ 선택 기능 없음
⛔ 필수 도구 확인 필요

Include one clear recovery/action per blocker.

---

# 5. App data directories

Stop relying on arbitrary current working directory for runtime-generated data.

Provide central path helpers for:
- config
- logs
- cache
- recovery
- temp-owned files

Use a Windows user-writable app data location or clearly defined project-local locations where appropriate.

Rules:
- user project/source files remain where user chose
- derived cache can be deleted safely
- logs/recovery belong to app data
- no write attempts inside Program Files installation directory

Test Unicode Windows usernames/path components where practical.

---

# 6. Recovery and backups

Atomic session save already exists; keep it.

Add recovery protection:

## Rotating session backups
For an existing saved session:
- before replacing a good session with a new saved version, retain a bounded number of recovery snapshots
- e.g. latest 3 or 5
- never alter source media
- do not create unbounded backup growth

## Crash marker / startup recovery
On normal app start:
- create a lightweight run marker
On clean exit:
- clear it

If previous run appears unclean:
- offer:
  [최근 정상 세션 열기]
  [복구본 보기]
  [그냥 시작]

Do not automatically overwrite the user project.

## Recovery validation
A recovery snapshot must pass JSON/Pydantic validation before it is offered as good.

## Failed save
A failed autosave/export must not destroy:
- existing session
- recovery snapshot
- source media

---

# 7. Logs and support diagnostics

Add bounded rotating logs.

Log:
- app version
- platform/python runtime
- startup checks
- session open/save failures
- optional backend availability
- FFmpeg command stage + return code
- render failure technical tail
- uncaught exception trace

Do NOT log:
- API secrets
- environment secrets
- full private lyric/project content unless strictly needed
- binary media

Beginner UI:
[진단 정보 열기]

Optional:
[진단 보고서 만들기]

Diagnostic bundle may contain:
- app version
- dependency availability
- recent sanitized logs
- configuration flags
- no source media
- no secrets

---

# 8. Global exception safety

Install a top-level exception handler for GUI events where practical.

Unexpected exception:
- write technical log
- show short beginner-safe message
- preserve session/source files
- point to diagnostics/recovery

Do not expose huge stack traces in the beginner dialog.

Do not swallow errors silently.

---

# 9. Cache management

Provide:
[캐시 정리]

Show estimated cache size.

Safe-to-delete:
- thumbnails
- semantic derived cache
- normalized render segments
- preview cache if user agrees

Never delete:
- source music
- source Takes
- References
- saved session
- final output

After cache clear:
- app can regenerate derived data.

Do not recursively delete arbitrary user-selected directories.

---

# 10. Project integrity doctor

Add a project-level integrity check.

Check:
- session JSON valid
- referenced music exists
- references exist/missing
- accepted Takes exist
- pack/take lineage
- duplicate IDs/invariant audits
- QC stale state
- edit timeline stale against accepted Takes if detectable
- final output metadata path existence
- recovery backups

Beginner output:
"프로젝트 상태를 확인했습니다."

Groups:
✅ 정상
⚠ 다시 연결 필요
⚠ 다시 검사 권장
⛔ 작업 전 해결 필요

No automatic destructive repair.

---

# 11. Beginner workflow polish

Audit all major pages from first-time-user perspective.

The main navigation should communicate a single path:
1. MUSIC
2. WORLD
3. REFERENCES
4. STORY
5. SHOTS
6. GENERATE
7. RESULTS
8. QC
9. EDIT/RENDER

If existing numbering differs internally, avoid destabilizing architecture; improve labels/help rather than unnecessary rewrites.

Each active page should have:
- what this step is
- current status
- primary next action
- next step
- recovery guidance for common blockers

Use the Beginner UI Standard.

Add a compact "처음 사용하는 분" onboarding overlay/page if it materially improves navigation, but avoid a large tutorial system.

---

# 12. End-to-end demo project / smoke fixture

Create a tiny deterministic fixture for CI/local smoke.

It should exercise the pipeline without external AI APIs:
- tiny synthetic/fixture audio
- tiny lyrics
- World/Story/Shot fixture
- tiny generated/sample Take media or programmatically synthesized test media
- accepted Takes
- QC
- rough cut
- preview/final render when FFmpeg available

Do not ship copyrighted media.

This may be test-only generated content.

Goal:
prove the full internal pipeline works.

---

# 13. Full E2E release test

Add one release-level automated or semi-automated smoke:

New project
→ lyrics/music import
→ analysis/session save
→ World selection
→ Story/Shot creation fixture
→ manual pack compile
→ Take registration/accept
→ technical QC
→ semantic QC graceful optional behavior
→ rough cut
→ render
→ reopen session
→ verify final record/path
→ verify sources unchanged

Use tiny synthetic media.

If FFmpeg unavailable in CI:
- mark render integration test with a clear conditional skip
- but run it in the Windows release build job where FFmpeg is provisioned.

---

# 14. Packaging smoke

Built application must be tested, not merely created.

At minimum:
- packaged app launches
- main window appears
- no developer PYTHONPATH required
- create/open session
- core page imports do not fail
- FFmpeg discovery works in intended release layout
- optional modules absent do not crash startup

Prefer an automated short-lived launch/smoke mode if GUI automation is fragile.

Possible CLI/internal flag:
--smoke-test

It should validate imports/runtime paths and exit 0 without requiring user interaction.

---

# 15. GitHub Actions release workflow

Add a Windows workflow that can:
- checkout
- setup supported Python
- install project/build deps
- run tests
- run compileall
- run packaging build
- run packaged smoke test
- archive release artifact

Do not publish a GitHub Release automatically unless explicitly configured.
Artifact upload from CI is enough for PASS.

Pin action major versions sensibly.
Avoid secrets.

Optional heavy AI extras should not be required in release CI.

---

# 16. Release manifest

Generate a build/release manifest containing:
- app version
- git commit
- build timestamp
- Python version
- platform
- FFmpeg strategy
- included optional components
- schema version

This helps support/debugging.

No secret/environment dump.

---

# 17. README for a beginner

README_KO final should begin with practical usage, not architecture.

Include:
- what the app does
- Windows start/install
- 9-step workflow
- FFmpeg requirement
- what is optional
- where projects are saved
- recovery
- cache cleanup
- known limitations

Keep developer architecture later.

Also create a concise first-run guide in the app or packaged docs.

---

# 18. Known limitations — be explicit

Document at least:
- video generation remains manual website workflow unless later provider automation is added
- OpenCLIP/Beat This/functional structure/OTIO are optional
- AI semantic QC is advisory
- AI Director JSON exchange is manual/API-free by design
- external model/package changes may require adapter updates
- OTIO interoperability depends on receiving editor/plugins
- exact face identity is not guaranteed by OpenCLIP
- long renders depend on local CPU/GPU/FFmpeg capabilities

Do not claim unsupported features.

---

# 19. No-regression / file safety

Final hard rules:
- source music immutable
- source Take immutable
- Reference immutable
- no secret bundled
- no silent deletion
- no session destructive repair
- no hidden auto-download of large models
- no provider API required
- no candidate Take silently used for final render

---

# 20. Tests / Release Gate

Minimum final checks:

1. version 1.0.0 visible
2. packaged runtime paths do not use developer absolute paths
3. no secrets in tracked/build config fixture
4. FFmpeg app-local discovery
5. FFmpeg PATH discovery
6. missing FFmpeg beginner blocker
7. encoder capability check
8. first-run doctor required vs optional distinction
9. app data dirs writable
10. backup rotation bounded
11. clean exit clears crash marker
12. stale crash marker triggers recovery state
13. invalid recovery backup not offered as valid
14. failed save preserves old session
15. rotating logs bounded
16. diagnostic bundle excludes source media/secrets
17. global exception log test
18. cache size/clear only owned cache
19. cache clear preserves source/final/session
20. project integrity detects missing reference/take
21. project integrity detects stale QC where applicable
22. no destructive auto repair
23. beginner navigation/primary actions present
24. synthetic end-to-end pipeline smoke
25. final render source bytes unchanged
26. reopen final session roundtrip
27. packaged app import smoke
28. packaged app launch/smoke flag
29. optional dependencies absent startup PASS
30. CI workflow syntax/config present
31. release artifact build path
32. release manifest fields
33. README beginner workflow
34. known limitations documented
35. all previous 86+ tests green
36. compileall
37. git diff --check

Where practical:
- use temporary directories
- use tiny synthetic media
- avoid network
- avoid heavy optional AI models

---

# 21. 100% PASS definition

Do NOT declare 100% merely because code compiles.

100% FINAL PASS requires:
- all core tests green
- packaged Windows artifact successfully built
- packaged smoke test passes
- core no-API workflow opens/runs
- FFmpeg render path verified
- recovery/backup behavior verified
- no source mutation
- README/release docs done

If packaging cannot be fully verified in the current environment:
report 99% / RELEASE BLOCKED rather than falsely claiming 100%.

---

# Completion report

[전체 진행률]
100% or 99% RELEASE BLOCKED

[G7 FINAL RELEASE 상태]
PASS / FAIL

[Windows Packaging]

[First-run Doctor]

[Recovery / Backup]

[Logs / Diagnostics]

[Cache / Integrity]

[Beginner UX]

[E2E Workflow]

[Release CI]

[파일 안전성]

[전체 테스트]
xx passed / xx failed

[패키징 검증]
build: PASS/FAIL
packaged smoke: PASS/FAIL
FFmpeg render smoke: PASS/FAIL

[남은 위험 / 알려진 제한]

[최종 상태]
MV Director Studio 1.0 RELEASE READY
or
RELEASE BLOCKED — reason

Stop there.
