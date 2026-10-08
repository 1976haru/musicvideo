# G9 Production Orchestrator / Megagate

## Product goal
Turn the existing collection of Music/World/Series/Story/Shot/Generate/QC/Edit tools into one production system that tells the operator what is ready, what is stale, what is missing, and what must happen next.

## Invariants
- Existing 01–10 page order never changes.
- Series Studio remains additive.
- Production Control is a separate dialog.
- Original Music/Take/Reference/Series Asset bytes remain read-only.
- No cloud provider is contacted automatically.
- ComfyUI defaults to localhost only.
- No model/checkpoint is downloaded automatically.
- Session schema stays 1.0 and older sessions load with empty G9 queue/contract fields.

## Continuity Contract
`compile_shot_continuity_contract()` is deterministic and side-effect free. It includes World locks, Series rules, Entity hard locks, applicable variants, continuity in/out, negative rules, References and approved Series Assets.

`ManualGenerationPack.continuity_contract_hash` binds a prompt snapshot to the creative state that produced it. A changed contract marks the pack stale.

## Production Readiness
Fast metadata/state checks cover:
- music + AudioMap;
- lyric analysis + complete World Bible;
- Series/Reference file integrity;
- Story/Shot structure;
- Director Coverage;
- current Prompt Contract;
- accepted Take and technical/semantic QC state;
- edit/render readiness.

Readiness must not decode every accepted video when the dialog opens. Heavy visual analysis remains explicit in QC.

## Director Coverage
Warnings only:
- lyric Line-ID evidence coverage;
- high-priority music-cue relation to Shot boundaries;
- Series Episode/Entity coverage;
- visual strategy variety;
- exact repeated action runs;
- median Shot rhythm extremes.

It must never turn every beat or lyric line into an automatic cut.

## Generation Queue
Queue jobs persist in Session JSON. States:
`PENDING → RUNNING → DONE`, with FAILED/requeue and CANCELLED. Completed jobs are immutable.

## Local ComfyUI
Supported workflow placeholders:
- MV_MAIN_PROMPT
- MV_MOTION_PROMPT
- MV_CAMERA_PROMPT
- MV_NEGATIVE_PROMPT
- MV_SHOT_ID
- MV_DURATION
- MV_ASPECT_RATIO
- MV_OUTPUT_PREFIX
- MV_FIRST_REFERENCE
- MV_REFERENCE_1..4

The bridge uses only a user-managed ComfyUI server and denies non-local endpoints by default. Approved image references are uploaded through ComfyUI's image upload route before submitting the workflow.

## Final Verification
Media probe is authoritative for duration/audio/size/FPS. Black/freeze health uses bounded frame seeking. PySceneDetect is optional for actual-cut anomaly warnings.

## Automated validation

### pytest stress
- 200 Shot contracts and packs
- 1000 queue jobs
- 10 Session round-trips
- production fingerprint stability
- UI contract at 1100×720

### packaged/root Production Megagate
- THE FIFTH VERDICT seed
- 50 Shot contracts/packs
- identity locks
- stale Prompt detection
- five Session round-trips
- 500 persistent queue jobs
- ComfyUI workflow materialization and remote-endpoint rejection
- main/Production Control UI contract
- real FFmpeg test video + Final Verification

No root deployment is allowed if this Megagate fails.
