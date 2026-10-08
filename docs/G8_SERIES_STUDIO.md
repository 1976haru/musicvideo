# G8 Series Studio — THE FIFTH VERDICT production layer

G8 extends the existing single-song workflow with an additive five-episode series layer. Existing G0–G7 pages, Session schema `1.0`, references, shots, takes, QC, and render data remain backward compatible.

## Source of truth

The built-in **THE FIFTH VERDICT** seed follows the FINAL PROJECT BIBLE v3.0:

1. MUTE BELL
2. DOORLESS ROAD
3. SILENT WITNESS
4. MUTINY OF THE UNWRITTEN
5. GWAN: THE UNWRITTEN VERDICT

The shared base palette is deep ink navy `#162432`, dark teal `#0B7D80`, and aged paper `#E9E5DA`. The seed preserves the seven world rules about STAMP, UNWRITTEN, HOLLOW, memory cost, intervention, episode-order evidence, and the non-reset ending.

## Workflow

Open **SERIES STUDIO** from the sidebar:

`Series → Episode → Character → Assets → Continuity → Episode Graph`

Then continue through the existing:

`Story → Shot → Generate → QC → Edit / Render`

G8 is not an isolated planning island: Shot Board stores an optional Series Episode, Series Entity IDs, and Variant IDs. The Generate pack consumes those fields and injects hard entity locks plus approved Series Assets.

## Entity registry and hard locks

Required seed entities:

- YOSUMI
- SUZUGARA
- TOJI
- THE ARCHIVE
- HOLLOW
- STAMP
- GWAN_SYMBOL
- MARGIN_CITY_LOCATIONS

The first five carry full-strength Shape Grammar locks.

### YOSUMI hard contract

- exactly three separated black ink brushstroke ribbons;
- one perfectly rectangular hollow opening centered in the chest;
- only YOSUMI's anatomical left hand is matte white;
- headless, faceless, non-human;
- no fourth ribbon, topology drift, realistic fingers, extra white body parts, weapons, animal ears, fox/yokai/shrine decoration.

The Character tab separates **Silhouette rules** from **HARD LOCKED PARTS**, and ordinary forbidden rules from **HARD FORBIDDEN MUTATIONS**. Editing the hard-lock fields updates the actual ShapeGrammarLock used by Asset Factory, Continuity QC, and Generate.

## Multiple images per character

Reference Director does not assume one image per character.

For a character it normally proposes:

1. `character_sheet` — official design/topology lock;
2. `action_keyart` — same identity under a readable action;
3. `emotion_keyart` — same identity inside a narrative/emotional scene.

Episode/action/emotional variants can add further slots. This supports workflows such as YOSUMI's design-lock image, action key art, and EP1 protective-realization story key art without weakening the base identity.

Systems use `shape_reference`, locations use `environment_keyart`, props use `prop_master`, and every episode receives a `color_script` slot.

## Asset Factory

Asset Factory builds provider-neutral prompt packs. Every entity pack contains:

- Text Master;
- hard locked parts;
- hard shape rules;
- silhouette, palette and motion rules;
- applicable episode/action/emotional deltas;
- series and entity forbidden rules;
- a final identity verification instruction.

Role-specific prompt guidance distinguishes design lock, action key art, emotional story key art, environment master, prop master, color script, and shape reference.

No external image API is called.

## Download Watcher and asset review

The watcher observes one user-selected folder. New image files are registered **in place** as `candidate` assets. It never moves, renames, overwrites, or deletes source files.

The Assets tab lets the operator:

- add an existing image manually;
- assign Entity / Episode / Role;
- Approve or Reject;
- unregister metadata only.

Only **approved** Series Assets are automatically supplied to Shot → Generate packs. Unregistering never deletes the original image.

Series Asset paths are stored portably relative to the saved project session when possible.

## Shot → Generate integration

Shot Board adds optional fields:

- Series Episode
- Series Entities
- Series Variants

When a Shot is compiled, Generate automatically adds:

- the entity Text Master;
- hard Shape Grammar;
- selected/episode variants;
- entity and series negative constraints;
- hard-lock continuity summary;
- approved Series Asset paths matching the Shot.

A YOSUMI Shot therefore cannot silently lose the three-ribbon / rectangular-hollow / white-left-hand contract just because a cinematic prompt becomes more dramatic.

## Continuity QC

Episode snapshots can be checked for:

- expected entity presence;
- locked shape tokens;
- entity palette drift;
- prop-state changes;
- recurring locations;
- motif progression;
- forbidden elements;
- clue setup/payoff registration.

The QC is metadata/evidence based. Without an external visual model it does **not** claim to inspect pixels or prove identity from an image automatically.

## Episode Graph

The seed tracks the actual series causality, including:

- the silent bell / future-footstep / present-time ring chain;
- STAMP appearing before the apparent crime and later-generated testimony;
- YOSUMI's lost lullaby note reused as evidence;
- TOJI changing from apparent obstacle to keeper of choices;
- `G _ A N` becoming GWAN / Guard Without Assigning Names;
- the doorless path making the later evidence chain possible.

## Release gate

`--series-studio-smoke-test` must verify in the packaged and root EXE:

- exact five public episode titles;
- seven shared world rules;
- required eight entities;
- YOSUMI's real final Shape Grammar;
- multi-image YOSUMI reference planning;
- Asset Factory prompt generation;
- Session round-trip;
- Episode Graph and Continuity QC execution;
- Character hard-lock editing UI;
- Shot → Generate hard-lock injection;
- approved Series Asset injection.

The final user executable remains:

`D:\03 musicvideo\MV Director Studio.exe`
