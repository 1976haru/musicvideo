# G4B Result / Take Manager — Product & Data Contract

## 기준선

- Branch: `g4-result-take-manager`
- Baseline: G4A FINAL PASS
- Overall progress: 78%
- G4B target: 83%
- First implementation gate: about 81%
- Final hardening gate: 83%
- G5 Automated QC must NOT start during G4B.

## Product decision

G4B manages clips created manually on sites such as Higgsfield.

No provider API is added.

Workflow:

Shot
→ ManualGenerationPack snapshot
→ user generates externally
→ user imports generated video
→ Take A / B / C
→ ACCEPT / REJECT / CANDIDATE
→ one FINAL TAKE per Shot
→ G5 QC later

The generated file itself is user data. Registration and metadata removal must never delete, rename, move, overwrite, or transcode the source video.

---

# 1. UI location

Keep sidebar item:

08 GENERATE

Do NOT activate 09 QC / EDIT yet.

Inside page 08, use two clearly separated tabs or modes:

1. PROMPT PACK
2. RESULT / TAKES

The existing G4A Prompt Pack UI remains functional.

Result / Takes should be beginner-readable.

Recommended workflow text:

1. Shot 선택
2. 생성에 사용한 Pack 선택
3. 결과 영상 등록
4. Take A/B/C 비교
5. ACCEPT 또는 REJECT
6. FINAL TAKE 확인

---

# 2. Core model — GenerationTake

Recommended model:

GenerationTake
- take_id: str
- shot_id: str
- pack_id: str | None
- source_profile_id: str | None
- output_path: str
- created_at: str
- imported_at: str
- status: candidate / accepted / rejected
- reject_reason: str
- notes: str
- rating: int | None
- duration_sec: float | None
- original_filename: str
- file_size_bytes: int | None

Do not persist a stale `file_missing` boolean.
Derive availability from the current file system.

Rating can be a simple manual 1–5 value.

Do not add automated visual QC scores here; that belongs to G5.

---

# 3. Stable Take IDs

IDs must remain stable even after deletion.

Recommended:

TAKE-{shot_id}-{NNN}

Examples:
- TAKE-B001-S01-001
- TAKE-B001-S01-002

Implement a safe allocator.

Delete → add must never create a collision.

Do not renumber existing takes.

Duplicate take_id must be detected.

---

# 4. Result path policy

Reuse the G2 reference-vault portability philosophy.

For generated video files:

- if inside session/project directory: store relative POSIX path
- if outside project directory: store normalized absolute path
- restore relative path against the session JSON parent directory
- metadata registration never changes the video file
- metadata removal never deletes the video file
- missing file keeps metadata and shows MISSING

Implement explicit helpers such as:

portable_take_path(...)
resolve_take_path(...)

Do not reuse ReferenceAsset itself for result clips.

---

# 5. Pack lineage

A Take should preferably point to the exact ManualGenerationPack snapshot used to create it.

UI behavior:

- show pack snapshots belonging to the selected Shot
- newest snapshot can be preselected
- allow "No Pack Snapshot" if the user forgot to save one
- No Pack is a warning, not a blocker
- if pack_id exists but no longer exists in session: orphan-pack warning
- if pack.shot_id does not match take.shot_id: lineage warning

Never silently rewrite pack links.

This chain must remain visible:

Shot → Pack → Take

---

# 6. Registration workflow

Support:

- "결과 영상 등록" file picker
- drag & drop video files when practical

Initial accepted extensions:
- .mp4
- .mov
- .webm
- .mkv
- .m4v

Registration requires a selected Shot.

On registration:
- assign stable take_id
- default status = candidate
- remember original filename
- record imported_at
- link selected pack if any
- record source profile from linked pack when possible
- preserve source file untouched
- autosave according to existing session policy

Do not copy the video into the project in G4B.

A future "consolidate project media" feature can do that separately.

---

# 7. Duplicate registration protection

For the SAME Shot:

If the same resolved output path is already registered, warn and do not silently add another identical Take.

The same source file may intentionally be linked to a different Shot, so do not globally prohibit it.

---

# 8. Take statuses

Allowed states:

candidate
accepted
rejected

Rules:

## candidate
Default state after import.

## accepted
Exactly one accepted Take per Shot.

When a user accepts Take B:
- Take B → accepted
- any previously accepted Take for the same Shot → candidate

Do not delete or reject the previous accepted Take automatically.

## rejected
Rejected Take stays in history.

Reject reason should be encouraged.
UI may require or strongly prompt for a reason.

Rejected Take can be restored to candidate.

Provide core functions, not UI-only mutations:
- accept_take(...)
- reject_take(...)
- restore_candidate(...)

---

# 9. Final Take invariant

For every Shot:
- zero accepted is allowed while working
- more than one accepted is invalid and must produce a warning
- normal service operations must enforce at most one accepted

The accepted Take becomes the future input to G5/G6.

Do not yet add editor/render integration.

---

# 10. Orphan safety

Do not silently destroy Take history if:
- Shot disappears
- Pack disappears
- video file moves/deletes externally

Show warnings:
- ORPHAN_SHOT
- ORPHAN_PACK
- MISSING_FILE
- PACK_SHOT_MISMATCH
- MULTIPLE_ACCEPTED
- DUPLICATE_TAKE_ID

This is historical production data.

---

# 11. Manual compare UI

No heavy video-analysis QC yet.

Result / Takes UI should show for selected Shot:

Take list/cards:
- Take A / B / C display label
- take_id
- filename
- status
- rating
- linked pack
- source profile
- file availability

Selected Take inspector:
- path
- imported time
- status
- rating 1–5
- notes
- reject reason
- linked pack
- warnings

Actions:
- 영상 열기
- ACCEPT
- REJECT
- Candidate로 복원
- 메모 저장
- 등록 해제 (원본 유지)

"등록 해제" must explicitly say original file remains untouched.

Use `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` or another safe local-open mechanism if used.
Do not embed a large new multimedia framework merely for playback in G4B.

---

# 12. Take A / B / C labels

A/B/C are display labels, not persistent identity.

Persistent identity is `take_id`.

Display order should be deterministic, e.g. imported_at then take_id.

Do not rename take IDs if a Take is removed.

---

# 13. Session schema

Advance session schema from 0.6 to 0.7.

Add:
- generation_takes

Maintain backward compatibility:
- 0.6 sessions with no generation_takes → []
- G3/G2 older sessions still load as before

Pack snapshots remain unchanged.

---

# 14. Autosave

Take operations must follow existing autosave policy:

- unsaved new session: no implicit disk target
- explicitly saved/opened session: debounce autosave
- atomic session save remains unchanged

Operations that trigger on_change/autosave:
- result register
- accept
- reject
- restore candidate
- rating/notes save
- metadata unregister

---

# 15. File safety

Hard blocker:

No G4B operation may:
- delete output source
- rename output source
- move output source
- overwrite output source
- transcode output source

Metadata-only operations must be tested against source bytes/existence.

---

# 16. Manual rating vs future QC

G4B may store:
- manual rating
- notes
- reject reason

Do NOT add:
- OpenCLIP similarity
- frame flicker detection
- palette drift score
- identity similarity
- motion score
- automatic acceptance

Those belong to G5.

---

# 17. Readiness summary for future editor

Provide helper(s) such as:

accepted_take_for_shot(shot_id)
shot_result_status(shot_id)

Suggested result statuses:
- NO_TAKE
- HAS_CANDIDATES
- FINAL_ACCEPTED
- FINAL_MISSING_FILE
- NEEDS_REVIEW

This should be deterministic and testable.

---

# 18. G4B first implementation tests (Claude gate ~81%)

Minimum:

1. GenerationTake model validation
2. stable next_take_id after delete/add
3. relative/absolute path policy
4. register Take preserves source
5. duplicate path same Shot protection
6. pack lineage valid/missing/mismatch warnings
7. accept ensures only one accepted per Shot
8. reject / restore transitions
9. unregister metadata preserves source file
10. missing file retains Take metadata
11. session 0.7 roundtrip
12. old 0.6 payload backward compatibility
13. Korean/Japanese/space video path roundtrip
14. unsaved session does not autosave
15. saved session Take mutation activates autosave
16. existing G0-G4A tests remain PASS
17. PySide6 Result/Takes page smoke
18. compileall
19. git diff --check

---

# 19. Claude first-pass stop gate

Claude Code should stop around 81%, not declare G4B FINAL PASS.

Completion report:

[전체 진행률]
약 81%

[G4B 중간상태]

[GenerationTake]

[파일 안전성]

[Pack → Take 추적성]

[Take 상태전이]

[Result / Takes UI]

[세션]

[전체 테스트]
xx passed / xx failed

[남은 과제]

[Codex hardening 추천]

WAITING FOR REVIEW

---

# 20. G4B final 83% expectations

After Claude first pass, final Codex hardening will review:

- corrupt/imported duplicate IDs
- multiple-accepted invariant
- orphan Shot/Pack history
- selected Take stability after sorting/refresh
- drag/drop multi-file behavior
- metadata-only removal
- large Take-list UI behavior
- missing file state
- pack/take cross-link integrity
- full regression

Do not start G5 until 83% final review passes.
