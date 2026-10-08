# MV Director Studio 1.1.0 — Production Orchestrator

1.1.0 is a production-control release rather than another isolated feature page.

## Production Control
A separate sidebar control room audits the existing 01–10 workflow without changing page indices. It shows stage readiness, blockers, warnings and recommended next actions.

## Continuity Contract
Every Shot can compile a deterministic contract from:
- World Bible;
- THE FIFTH VERDICT Series Bible;
- Entity Shape Grammar and variants;
- Shot continuity;
- Reference Vault and approved Series Assets;
- negative constraints.

ManualGenerationPack stores the contract hash. If any source lock changes, the existing pack becomes stale and Production Control blocks it until regenerated.

## Director Coverage
Rule-based warnings check lyric evidence coverage, strong music-cue alignment, Series context coverage, visual-strategy/action repetition and extreme Shot rhythm. These are warnings only and do not rewrite creative choices.

## Local ComfyUI
Optional localhost-only automation can:
- submit an exported API-format workflow;
- replace MV prompt/camera/duration/output placeholders;
- upload up to four approved image references to ComfyUI input;
- persist prompt/job state in the Session JSON;
- register completed video outputs as candidate Takes when the output folder is configured.

It does not install ComfyUI or download models.

## Final Verification
Final media is checked for:
- duration against the song/timeline;
- audio track;
- requested size/FPS;
- sampled black/freeze ratios;
- optional PySceneDetect scene-cut anomaly warnings.

## Release Megagate
The packaged and root EXE must pass the legacy release gates plus a G9 Production Megagate covering a synthetic five-episode project, 50 Shot contracts/packs, stale detection, 500 queue jobs, five session round-trips, 1100×720 UI contracts, ComfyUI workflow materialization, and a real FFmpeg final MP4.

Session schema remains 1.0. Root executable remains `D:\03 musicvideo\MV Director Studio.exe`.
