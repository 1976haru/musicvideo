# G8 Series Studio

G8 extends the existing song/project workflow with an additive five-episode series layer. Existing G0–G7 pages, session schema `1.0`, references, shots, takes, QC, and render data remain unchanged.

## Workflow

Open **SERIES STUDIO** from the sidebar. Its working order is:

`Series → Episode → Character → Assets → Continuity → Episode Graph`

Then continue through the existing `Story → Shot → Generate` pages.

## Data contract

- `SeriesBible` owns exactly five episode bibles, common world/visual rules, motifs, forbidden elements, the color system, and clue/payoff chains.
- `SeriesEntity` is the registry record for a character, prop, location, or system. It includes episode presence and relationships.
- `ShapeGrammarLock` combines locked text rules with reference IDs. A resolved variant copies this lock without relaxing it.
- `EntityVariant` layers episode, action, and emotional deltas over the base form in that order.
- `text_master` is a complete provider-neutral identity lock and remains useful before images exist.
- Series fields are optional additions to session JSON. Opening a legacy session does not silently seed or modify it.

## THE FIFTH VERDICT seed

The bundled seed contains five episodes and the required entities: YOSUMI, SUZUGARA, TOJI, THE ARCHIVE, HOLLOW, STAMP, GWAN_SYMBOL, and MARGIN_CITY_LOCATIONS. The first five have full-strength shape grammar locks. The seed is only installed when the operator explicitly chooses it.

## Reference Director and Asset Factory

Reference Director compares the series/episode/entity contract with approved assets and proposes missing slots. Asset Factory turns those slots into provider-neutral prompt packs for character sheets, action and emotion key art, environments, props, and episode color scripts. Prompts carry text-master locks and negative rules; no provider API is called.

## Download watcher

The watcher observes one operator-selected directory. New supported image files are registered in place using filename hints such as `YOSUMI__EP2__action_keyart.png`. It never moves, renames, overwrites, or deletes downloaded files. Ambiguous files are registered as `unassigned` candidates for review.

## Continuity QC

Episode snapshots can be checked for:

- required entity presence and locked shape tokens;
- entity palette drift and prop-state changes;
- recurring locations and motif progression;
- series/entity forbidden elements;
- clue setup and payoff registration.

QC is evidence-based: it reports only the structured observations registered for an episode. The episode graph presents clue/payoff edges across EP1–EP5.
