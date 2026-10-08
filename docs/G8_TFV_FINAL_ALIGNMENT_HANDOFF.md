# G8 THE FIFTH VERDICT — Final Alignment and Release Validation

## Branch
feature-1.0.3-series-studio

## Why this validation is required
The first G8 implementation had a structurally useful Series Studio but its bundled THE FIFTH VERDICT seed did not match FINAL PROJECT BIBLE v3.0. It also committed a local user session file and did not connect Series Entity locks to the existing Shot → Generate pipeline.

Those issues have now been corrected in the remote branch. Validate the corrected implementation, not the earlier local commit.

## Source-of-truth contracts
Public episode titles must be exactly:
1. MUTE BELL
2. DOORLESS ROAD
3. SILENT WITNESS
4. MUTINY OF THE UNWRITTEN
5. GWAN: THE UNWRITTEN VERDICT

YOSUMI hard contract:
- exactly three separated black ink brushstroke ribbons
- centered rectangular hollow chest
- only anatomical left hand matte white
- headless/faceless/non-human
- no fourth ribbon, topology drift, realistic fingers, extra white body parts, weapons, animal ears, fox/yokai/shrine decoration

Also validate SUZUGARA no-clapper/two-short-legs/internal vibration, TOJI exactly two closed brackets/golden gap/no face, THE ARCHIVE rotating windows + black square STAMP/no human face, and HOLLOW hollow-centered cluster + shared ring motif.

## New production integration that must work
1. Character Registry separately edits Silhouette Rules, HARD LOCKED PARTS, Forbidden Rules, HARD FORBIDDEN MUTATIONS.
2. Reference Director proposes multiple images for characters: character_sheet, action_keyart, emotion_keyart.
3. Asset Factory repeats hard identity locks in every relevant prompt.
4. Download watcher registers candidate assets non-destructively.
5. Assets UI supports manual add, Entity/Episode/Role metadata, Approve/Reject, unregister metadata only.
6. Only approved Series Assets are eligible for Shot → Generate.
7. Shot Board stores Series Episode, Series Entities, Series Variants.
8. Manual Generate pack automatically injects Text Master, hard Shape Grammar, episode/selected variants, series negative constraints, continuity locks, and approved Series Asset paths.
9. Series Asset paths remain portable in the saved project.

## Required tests
- full pytest
- compileall
- git diff --check
- tests/test_g8_series_studio.py
- legacy G0-G7 regression
- packaged smoke/music/render/stress/world-bible/series-studio
- root smoke/music/render/stress/gui-music/world-bible/series-studio

## Series Studio packaged/root PASS payload requirements
- final_episode_titles = true
- seven_world_rules = true
- required_entities = true
- shape_grammar_locked = true
- yosumi_final_contract = true
- yosumi_multi_image_plan = true
- shot_generate_series_lock = true
- shot_generate_series_negative = true
- shot_generate_approved_asset = true
- ui_hard_lock_asset_review = true
- episode_graph_nodes = 5
- episode_graph_edges >= 6

## Manual GUI validation
Open SERIES STUDIO and load THE FIFTH VERDICT seed.

Series tab:
- five exact public titles
- seven shared world rules

Character tab / YOSUMI:
- Text Master contains EXACTLY THREE ribbons
- HARD LOCKED PARTS contains three black ink ribbons / centered rectangular hollow chest / matte white left hand only
- hard forbidden mutations contain fourth ribbon and topology drift

Assets tab:
- Reference Director proposes at least character_sheet/action_keyart/emotion_keyart for YOSUMI
- Asset Factory prompt preserves the real YOSUMI contract
- add/download an image, assign metadata, Approve it
- original file bytes remain unchanged

Shot Board:
- choose EP1
- select YOSUMI
- select YOSUMI_PROTECTIVE_REALIZATION
- save shot

Generate:
- generated manual pack contains EXACTLY THREE / rectangular hollow / LEFT hand identity lock
- negative prompt contains fourth ribbon/topology drift/realistic finger restrictions
- approved YOSUMI asset path is included

Episode Graph:
- six final-bible clue/payoff chains are present

## User data rule
`data/` is local user/session data and must not be tracked by Git. Never delete user source media or session files as part of release cleanup.

## Release
Keep app version 1.0.3 and Session schema 1.0 for this additive G8 layer.
Root executable remains exactly:
D:\03 musicvideo\MV Director Studio.exe

Do not merge until all tests and packaged/root gates pass.

Completion report:
[G8 FINAL ALIGNMENT] PASS/FAIL
[tests] xx passed / 0 failed
[exact titles] PASS/FAIL
[YOSUMI contract] PASS/FAIL
[multi-image Reference Director] PASS/FAIL
[asset review workflow] PASS/FAIL
[Shot → Generate series lock] PASS/FAIL
[approved asset injection] PASS/FAIL
[portable Series Asset paths] PASS/FAIL
[Episode Graph 6 chains] PASS/FAIL
[packaged Series Studio] PASS/FAIL
[root Series Studio] PASS/FAIL
[root executable] D:\03 musicvideo\MV Director Studio.exe

WAITING FOR REVIEW