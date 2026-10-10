# MV Director Studio 1.1.1 — Story Room Editing Hotfix

1.1.1 is a focused hotfix for STORY ROOM Beat editing. Session schema stays **1.0**; existing
sessions open unchanged and no Beat/Shot data is migrated or rewritten.

## Fixed

- **Time precision** — Beat start/end spinboxes now use 3 decimals (0.001s step). A Beat ending
  exactly at the song end (e.g. `192.046s`) is no longer rounded to `192.05s` and rejected.
- **Timestamp preservation** — editing only text/notes/motif keeps the stored `start_sec` /
  `end_sec` exactly (e.g. `1.234–5.678`, or sub-millisecond values from analysis). Only a time
  field the user actually changed is written back.
- **Song-length boundary** — Story Room and PRODUCTION CONTROL share one effective duration:
  analysed audio length first, then the session length; `0` is treated as unknown. Values within
  half a display unit (0.0005s) of the song end are normalized to the song end; a meaningful
  overflow (e.g. `193.000s` for a `192.046s` song) is blocked with a `0.000 ~ 192.046초` message.
- **Unapplied edits are never silently lost** — selecting another Beat, Beat 추가, 자동 초안
  만들기, Beat 삭제, opening a session or a recovery copy asks
  *“현재 Beat에 적용하지 않은 변경이 있습니다.”* with **변경 적용 / 버리기 / 취소**.
  Cancel restores the previous Beat selection and keeps the typed values; a failed apply cancels
  the action. Background refreshes keep unapplied edits.
- **Accurate dirty state** — the form is compared with a snapshot taken at load time, so
  `q → q2 → q` returns to “변경 없음” and disables the save button again.
- **Save button states** — `QPushButton#primary:disabled/:hover/:pressed` styles make disabled,
  enabled and pressed states clearly different in the dark theme. Status line reports
  “Beat 변경 적용 완료 · 세션 자동저장 예약” (or the [세션 저장] hint when the session has no file),
  failures, and overlap warnings right after saving.
- **1100×720 layout** — the four Story Room actions use a 2×2 grid (min height 44) so no label is
  clipped. The packaged/root G3 dark UI gate now verifies button fit and save-button states.
- Version metadata (EXE file/product version, CI artifact name) aligned to 1.1.1.

## Unchanged

- Safe gap-based Beat 추가 (never a 0→full-song Beat, never edits existing Beats or Shots).
- Timeline warnings remain warnings (full-duration overlap, gaps, overlaps); no new blockers.
- G9 Production Control, Continuity Contract, Generation Queue, ComfyUI bridge, Final Verification.
