# G4B Codex FINAL Hardening — Result / Take Manager

## Baseline

- Branch: `g4-result-take-manager`
- Current progress: about 81%
- Target: G4B FINAL PASS at 83%
- G4A is FINAL PASS.
- Claude Code completed the first G4B implementation.
- Do NOT start G5 Automated QC.
- Do NOT add provider APIs or browser automation.

## Read first

1. docs/G4B_RESULT_TAKE_MANAGER.md
2. docs/G4B_CLAUDE_HANDOFF.md
3. src/mvstudio/result_takes.py
4. src/mvstudio/g4b_ui.py
5. src/mvstudio/session.py
6. src/mvstudio/ui_app.py
7. tests/test_g4b_result_takes.py
8. all existing tests

Run the full baseline test suite first.

---

# Final review findings

The first implementation is structurally good:

- metadata-only file registration/unregister
- stable persistent take counters
- portable relative/absolute paths
- Shot → Pack → Take provenance
- candidate / accepted / rejected
- one accepted Take through normal service operations
- missing/orphan warnings
- schema 0.7
- Prompt Pack / Result-Takes separation
- G5 remains disabled

The remaining work is hardening against corrupted/imported historical state and improving recovery UX.

---

# 1. Add non-destructive session Take audit

Create one deterministic core audit function/service, for example:

`audit_take_state(...)`

It must inspect imported or manually edited JSON without silently deleting or rewriting history.

Detect at minimum:

- DUPLICATE_TAKE_ID
- MULTIPLE_ACCEPTED
- ORPHAN_SHOT
- ORPHAN_PACK
- PACK_SHOT_MISMATCH
- MISSING_FILE
- invalid / stale take counter relationship where useful

The audit must be callable after session import and from UI refresh.

Important:
- do not auto-delete takes
- do not auto-renumber duplicated take IDs
- do not silently choose one accepted Take as final
- corrupted history remains visible for manual repair

Normal valid old sessions must still load.

---

# 2. Duplicate take_id must never silently target the first object

Current UI lookup uses the persistent `take_id`.
In a corrupted JSON with duplicate take IDs, `_selected_take()` can silently return the first matching object.

This is a FINAL blocker.

Required behavior:

- if a selected take_id has more than one matching record, mutation actions must be disabled or blocked
- show a clear DUPLICATE_TAKE_ID repair warning
- ACCEPT / REJECT / RESTORE / SAVE / UNREGISTER / RELINK must not mutate an arbitrary first match
- TakeManager's existing duplicate error behavior should remain the core source of truth

The list may display corrupted duplicate records for history visibility, but it must not pretend they are uniquely addressable.

A UI-local ephemeral row/index key is allowed only to display them.
Do not rewrite the persistent take_id behind the user's back.

Add regression tests.

---

# 3. Multiple accepted invariant repair UX

Normal `accept()` already enforces one accepted Take per Shot.

Imported/manual JSON can still contain multiple accepted Takes.

Required:

- audit reports MULTIPLE_ACCEPTED
- `accepted_take_for_shot()` remains conservative: return a Take only when exactly one is accepted
- Shot result status should remain NEEDS_REVIEW when multiple accepted exist
- UI must clearly show that FINAL TAKE is unresolved

Add an explicit non-destructive repair action if practical:

`Resolve as Final` / ACCEPT on one of the duplicated accepted takes

When the user explicitly accepts one Take:
- selected → accepted
- all other accepted Takes for same Shot → candidate
- history is preserved

Do not auto-resolve at import time.

Test corrupted multiple-accepted payload → explicit accept repair.

---

# 4. Reconcile take ID counters safely after import

The permanent counter is good, but imported JSON may have:

- no counter
- stale low counter
- malformed counter value already rejected by parsing
- existing IDs higher than the saved counter

Add a deterministic reconciliation helper that calculates the safe next counter floor from existing IDs.

Requirements:

- never decrease an existing valid higher counter
- never renumber existing Take IDs
- delete → reopen → add still advances without collision
- old 0.6/0.7 payload without counters remains safe

Prefer normalization of the counter metadata, not Take identity.

Add tests.

---

# 5. Missing result file Relink UX

G4B FINAL should allow recovery when a user moves a generated video externally.

Add core metadata-only helper, e.g.:

`relink_take(take_id, new_path)`

Rules:

- new file must exist
- extension must be supported
- update only metadata path (and current file size if appropriate)
- preserve take_id
- preserve Shot / Pack lineage
- preserve status / rating / notes / reject reason
- preserve created/imported history
- do NOT delete, move, rename, copy, overwrite, or transcode either old or new file
- store portable path using current project_dir policy

UI:
- show "파일 다시 연결" only/enabled especially for missing file, but allowing deliberate relink is acceptable
- file picker uses video extensions
- after relink, MISSING_FILE clears
- autosave follows existing rules

If the relink target is already registered for the same Shot by a different Take, warn and block unless there is an explicit safe policy. Prefer block.

Add source-byte preservation tests for both old existing source (when present) and new selected file.

---

# 6. Stable selection after sort / refresh / status changes

Current refresh already tries to restore by take_id, which is correct for valid IDs.

Add tests for:
- imported_at sort order differs from underlying session list
- ACCEPT changes labels/status and refresh does not select a different Take
- rating/notes save retains selected stable Take
- reject/restore retains selected stable Take
- unregister selects a deterministic remaining Take
- duplicate-ID corrupted state does not silently mutate first match

Use stable identity, never visual row as business identity.

---

# 7. Scope warnings to the relevant Take / Shot in inspector

Current `warnings(take)` performs item-specific checks but also appends global duplicate/multiple-accepted warnings across all Takes.

Avoid confusing a selected Take with unrelated warnings from another Shot.

Provide one of:
- `warnings_for_take(take)`
- optional scope/filter parameter
- UI filtering against `warning.take_ids`

Inspector should show:
- warnings relevant to selected take
- multiple-accepted for selected take's Shot
- duplicate-ID involving selected take_id

Project-wide audit can be shown separately if needed.

Do not remove global audit capability.

---

# 8. Reject reason UX

Reject reason is not a hard schema requirement, but rejecting with an empty reason loses useful production history.

Required minimum:
- if user presses REJECT with empty reason, show confirmation/warning or a clear non-blocking prompt
- do not silently manufacture a reason
- core may still permit empty reason for backward compatibility

No modal spam during import.

---

# 9. Drag/drop multi-file behavior

Hardening requirements:

- unsupported files are ignored or reported clearly
- each valid file gets a unique stable Take ID
- duplicate same-shot file failures do not stop other valid files
- final selected Take should be the last successfully registered file
- only one autosave schedule is needed per batch
- source files remain untouched

Add a multi-file test with:
- 2 valid unique videos
- 1 duplicate path
- 1 unsupported file

---

# 10. Metadata-only failure injection

Add stronger tests proving file safety when metadata operations fail.

Examples:
- duplicate registration raises and source bytes unchanged
- relink validation fails and both old/new sources unchanged
- unregister metadata then session export failure does not alter video file
- reject/accept/update notes do not touch file mtime/bytes where practical

Do not overengineer OS-level mocking if unnecessary; source existence/bytes is the main contract.

---

# 11. Session import / corruption boundaries

Keep schema 0.7.

Backward compatibility:
- 0.6 no takes
- older G2/G3 sessions still load

For structurally valid but logically inconsistent Take data:
- load non-destructively
- surface audit warnings

For Pydantic-invalid Take fields:
- existing import error behavior may remain

Do not silently discard malformed records.

---

# 12. Result status helpers

Verify deterministic behavior:

- no Takes → NO_TAKE
- candidate exists → HAS_CANDIDATES
- exactly one accepted and file exists → FINAL_ACCEPTED
- exactly one accepted but file missing → FINAL_MISSING_FILE
- multiple accepted → NEEDS_REVIEW
- only rejected Takes → NEEDS_REVIEW

Add tests.

---

# 13. No G5 rule

Do NOT implement:

- OpenCLIP
- DINO
- frame similarity
- identity scoring
- flicker/jitter metrics
- palette drift
- motion analysis
- automated acceptance
- rendering/editor timeline
- provider APIs

G4B ends with human Take selection and safe result history.

---

# 14. Required FINAL tests

Keep all existing tests passing and add coverage for at least:

1. imported duplicate take_id audit
2. duplicate take_id UI mutation blocked
3. imported multiple accepted audit
4. explicit Accept repairs multiple-accepted state
5. stale/missing counter reconciliation
6. delete → reopen → add counter stability
7. relink missing file
8. relink duplicate same-shot target blocked
9. relink preserves lineage/status/rating/notes
10. relink source bytes untouched
11. stable selection after ACCEPT
12. stable selection after REJECT / RESTORE
13. stable selection after note save
14. selected inspector warnings scoped correctly
15. empty reject reason UX
16. multi-file drag/drop partial success
17. metadata-only failure safety
18. result status helper states
19. schema 0.7 roundtrip
20. 0.6 backward compatibility
21. Korean/Japanese/space relink path
22. autosave target regression
23. full G0-G4A regression
24. PySide6 offscreen smoke
25. compileall
26. git diff --check

---

# 15. Documentation

Update PROGRESS.md / README_KO.md only when G4B FINAL passes.

At PASS:
- overall 83%
- G4B FINAL PASS
- 09 QC / EDIT remains disabled until G5 starts
- manual web workflow remains the default generation workflow
- no API integration claimed

---

# Completion report

Only declare PASS if blockers are fixed and full suite passes.

[전체 진행률]
83%

[G4B FINAL 상태]
PASS / FAIL

[Take invariant audit]
...

[Take ID / Counter]
...

[파일 안전성 / Relink]
...

[Pack → Take 추적성]
...

[상태전이 / Final Take]
...

[UI 선택 안정성]
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
G5는 시작하지 말고 WAITING FOR REVIEW

Stop there.
