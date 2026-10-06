# G6 MEGAGATE — Editor / Rough Cut / Render / OTIO

## Baseline
- Branch: g6-editor-render
- Baseline: G5 FINAL PASS
- Overall progress: 92%
- Target: 98%
- This is ONE large implementation stage.
- G7 packaging/release must NOT start here.

## Product goal
Turn approved production data into a real music-video rough cut and final rendered file.

Pipeline:
ACCEPTED TAKES → EDIT PLAN → READINESS CHECK → PREVIEW → FINAL RENDER → OTIO EXPORT

The original music file is authoritative audio.
Generated Take audio is muted/ignored by default.

## 1. Beginner-first UI
Follow docs/BEGINNER_UI_STANDARD.md.

Main question:
"뮤직비디오를 자동으로 편집할까요?"

Summary example:
- 사용할 영상 18/18 준비
- 음악 파일 준비됨
- 길이가 부족한 Shot 2개
- 누락 파일 없음

Primary actions:
- 자동 편집 만들기
- 미리보기 만들기
- 최종 영상 내보내기

Secondary:
- 문제 Shot 확인
- 다른 Take 선택
- 전문가 편집 설정

Do not lead with FFmpeg/codec/timebase/OTIO terms.
Buttons >=44px.
1100x720 usable.
Long KR/JP text wraps.
Render progress/cancel visible.

## 2. Core edit models
Create clear validated models.

EditClip:
- clip_id
- shot_id
- take_id
- timeline_start_sec
- timeline_end_sec
- timeline_duration_sec
- source_path
- source_in_sec
- source_out_sec
- source_duration_sec
- fit_strategy
- framing_strategy
- warnings
- locked

fit_strategy:
- trim_end
- hold_last
- unresolved_short

framing_strategy:
- cover
- contain

Do not time-stretch by default.

EditGap:
- start_sec
- end_sec
- duration_sec
- resolution_strategy
- warnings

gap strategies:
- unresolved
- black
- hold_previous

EditTimeline:
- timeline_id
- created_at
- music_path
- duration_sec
- clips
- gaps
- output_aspect
- output_width
- output_height
- output_fps
- source_fingerprint
- warnings

RenderSettings:
- width
- height
- fps
- video_codec
- quality preset
- audio_codec
- audio_bitrate
- framing_strategy
- preview_mode
- output_path

RenderRecord:
- render_id
- timeline_id
- created_at
- settings snapshot
- output_path
- status
- source fingerprint
- warnings
- ffmpeg_version optional

## 3. Rough Cut builder
Build from sorted ShotSpec timeline, exactly one accepted GenerationTake per Shot, and original music duration.

Accepted Take only.
Never silently use candidate/rejected Take.

If accepted Take missing:
- readiness issue
- no substitution

If file missing:
- blocker
- recovery: 파일 다시 연결

Shot start/end are authoritative.

If Take longer than Shot:
- source_in default 0
- trim end
- no source mutation

If Take shorter than Shot:
- default unresolved_short
- final render BLOCKED until user explicitly chooses:
  1. 다른 Take 선택
  2. 마지막 프레임 유지
  3. Story/Shot Board에서 Shot 길이 조정

No automatic loop.
No automatic speed-fit.

Detect gaps before/between/after Shots relative to music.
Default gap unresolved.
Explicit choices:
- black
- hold previous

Shot overlap is a blocker.
Do not silently reorder or trim neighboring Shot timing.

## 4. Readiness
Deterministic states:
- READY
- READY_WITH_WARNINGS
- BLOCKED

Blockers:
- missing/unreadable music
- no Shots
- missing accepted Take
- missing accepted file
- multiple accepted Take state
- overlap
- unresolved_short
- unresolved gap
- invalid output settings

Warnings:
- selected Take has QC REVIEW/REGENERATE
- aspect mismatch
- very low source resolution
- fps mismatch
- hold_last used
- black gap used

QC never automatically changes accepted status.

## 5. Media probe
Use ffprobe when available.

Collect:
- duration
- width/height
- fps
- codec
- audio presence

Fallback to OpenCV for basic video metadata when practical.

FFmpeg/ffprobe availability:
- AVAILABLE
- NOT_INSTALLED
- LOAD_FAILED

App startup must not fail if missing.

Beginner message:
"영상 내보내기 도구(FFmpeg)를 찾을 수 없습니다."

## 6. Robust Windows render architecture
Prefer:
A. per-clip normalized cache
B. concat normalized clips
C. mux original music
D. atomic final output

### Clip normalization
Each derived segment:
- exact required duration
- common resolution
- common fps
- square pixels
- no source audio
- broadly compatible intermediate codec

trim_end:
- trim only derived segment

hold_last:
- freeze final frame for explicit remainder

framing:
- cover = scale + crop
- contain = scale + pad
- never stretch

Cache key includes:
- source fingerprint
- source in/out
- target duration
- resolution/fps
- framing
- fit strategy
- renderer version

### Concat
Normalized segments share format.
Use concat file or similarly bounded strategy.
Avoid Windows command-line explosion.

### Original music
Final audio = session.music_path.
Generated clip audio ignored.
Music starts at timeline 0.
Do not modify source music.

If timeline extends beyond song, block.

### Atomic output
Render to partial/temp final.
Move/replace final only after success.
On failure/cancel preserve old final and all source media.

## 7. FFmpeg command safety
Never shell=True.
Use argv arrays.
Support Unicode and spaces.
Do not build shell command strings from raw paths.

Capture stderr to technical log.
Beginner failure:
"영상 내보내기에 실패했습니다. 원본 파일은 변경되지 않았습니다."

## 8. Progress / cancel
Do not block UI thread.

Use QProcess/QThread/safe worker.
Use FFmpeg progress output where practical.

Show:
- current stage
- current Shot / N
- progress percent
- 취소

Cancel:
- terminate owned child
- preserve source files
- preserve previous final
- clean only owned temp partials

No fake progress.

## 9. Preview
Low-cost preview:
- 1280x720 or lower
- fast encoding
- same edit decisions
- original music

Preview path must not overwrite final.
Provide "미리보기 열기".
System player is sufficient.
Do not add a large playback framework unless stable.

## 10. Simple edit adjustment UI
Not a Premiere clone.

Per Shot show:
- Shot time
- accepted Take
- required duration
- actual duration
- fit status
- framing
- QC status
- issue/recovery

Allow:
- 화면 채우기 / 전체 보이기
- source start offset when Take is longer
- 마지막 프레임 유지 for short clip
- 검은 화면 / 이전 화면 유지 for gaps

"다른 Take 선택" should navigate to Result/Takes flow rather than silently replace accepted state.

Do not support arbitrary timeline reorder if it breaks Shot/Story provenance.

## 11. OpenTimelineIO
Use OTIO as optional professional interchange, not renderer.

Implement optional core OTIO export:
- timeline
- video track
- clip order
- source ranges
- external media refs
- useful markers/metadata

Metadata:
- shot_id
- take_id
- beat_id
- narrative_function
- QC status
- lineage when practical

Core .otio export is available when opentimelineio is installed.

If absent:
- app/render still works
- show optional feature notice

EDL/FCP/AAF adapters are optional and not required for G6 PASS.
Do not claim direct Premiere/Resolve project creation unless a real supported adapter exists.

Always provide MV Director edit-plan JSON export.

## 12. Output presets
Beginner presets:
- YouTube 1080p 16:9 (default)
- YouTube 4K 16:9
- Vertical 1080x1920 9:16
- Square 1080x1080 1:1

Expert:
- width
- height
- fps
- quality
- framing

## 13. Session schema
Advance 0.9 → 1.0.

Persist:
- edit timeline/plan
- clip decisions
- explicit short/gap resolutions
- render settings
- render records metadata
- preview/final paths
- renderer versions/fingerprints

Do not embed media/cache bytes.

0.9 loads with empty edit data.

Autosave:
- saved-session-only
- edit decision changes schedule autosave
- render progress does not spam autosave
- successful render record schedules save

## 14. File safety
Music/Takes/References are read-only.

Never modify/move/rename/delete/transcode in place.

Derived only:
- normalized cache
- preview
- final output
- OTIO
- edit-plan JSON

Final output overwrite requires confirmation.

## 15. Tests
Minimum:
1. accepted Takes only
2. candidate/rejected never silently used
3. missing accepted blocker
4. missing Take file blocker
5. longer Take → trim_end
6. shorter Take → unresolved blocker
7. explicit hold_last resolves
8. gap detection
9. explicit black/hold gap resolution
10. overlap blocker
11. original music only final audio
12. source bytes unchanged
13. cover plan
14. contain plan
15. KR/JP/space paths
16. FFmpeg unavailable graceful
17. ffprobe/fallback behavior
18. cache invalidation
19. failed render preserves prior final
20. cancel preserves prior final and sources
21. atomic success
22. preview same decisions
23. progress parser
24. edit-plan JSON export
25. OTIO unavailable graceful
26. OTIO structure with fake/installed dependency
27. OTIO metadata lineage
28. schema 1.0 roundtrip
29. 0.9 backward compatibility
30. saved-session edit autosave
31. beginner UI and >=44px primary buttons
32. 1100x720 offscreen smoke
33. full G0-G5 regression
34. compileall
35. git diff --check

Use synthetic tiny media where practical.

## Completion report
[전체 진행률]
98%

[G6 Editor/Render 상태]
PASS / FAIL

[Rough Cut]

[Readiness]

[FFmpeg Render]

[Preview / Progress / Cancel]

[OTIO / Edit Plan Export]

[Beginner UI]

[파일 안전성]

[세션]

[전체 테스트]
xx passed / 0 failed

[수동 확인 필요]

[남은 위험]

[다음 단계]
G7 Packaging/Recovery/Release는 시작하지 말고 WAITING FOR REVIEW

Stop there.
