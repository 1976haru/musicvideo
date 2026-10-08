from __future__ import annotations

"""Series-level planning, reference direction, and continuity services.

The module is intentionally provider-neutral.  It produces durable plans and prompt
packs, but never uploads assets or calls an image-generation API.
"""

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


EntityType = Literal["character", "prop", "location", "system"]
VariantKind = Literal["episode", "action", "emotional"]


class CluePayoffLink(BaseModel):
    chain_id: str
    clue: str
    setup_episode: str
    payoff_episode: str
    progression: list[str] = Field(default_factory=list)


class EpisodeBible(BaseModel):
    episode_id: str
    title: str
    order: int = Field(ge=1, le=5)
    logline: str = ""
    world_overrides: list[str] = Field(default_factory=list)
    visual_overrides: list[str] = Field(default_factory=list)
    color_arc: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    clue_ids: list[str] = Field(default_factory=list)
    payoff_ids: list[str] = Field(default_factory=list)


class SeriesBible(BaseModel):
    series_id: str
    title: str
    episode_titles: list[str]
    series_logline: str
    common_world_rules: list[str] = Field(default_factory=list)
    common_visual_rules: list[str] = Field(default_factory=list)
    recurring_motifs: list[str] = Field(default_factory=list)
    forbidden_elements: list[str] = Field(default_factory=list)
    color_system: dict[str, list[str]] = Field(default_factory=dict)
    clue_payoff_chain: list[CluePayoffLink] = Field(default_factory=list)
    episodes: list[EpisodeBible]

    @model_validator(mode="after")
    def validate_five_episode_contract(self):
        if len(self.episode_titles) != 5 or len(self.episodes) != 5:
            raise ValueError("A series bible must contain exactly five episodes")
        if sorted(ep.order for ep in self.episodes) != [1, 2, 3, 4, 5]:
            raise ValueError("Episode order must be 1 through 5")
        return self


class RelationshipEdge(BaseModel):
    target_entity_id: str
    relation: str
    episode_ids: list[str] = Field(default_factory=list)


class ShapeGrammarLock(BaseModel):
    locked_parts: list[str] = Field(default_factory=list)
    silhouette_rules: list[str] = Field(default_factory=list)
    proportion_rules: list[str] = Field(default_factory=list)
    material_rules: list[str] = Field(default_factory=list)
    forbidden_mutations: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)
    lock_strength: float = Field(default=1.0, ge=0, le=1)


class EntityVariant(BaseModel):
    variant_id: str
    kind: VariantKind
    episode_id: str | None = None
    trigger: str = ""
    appearance_delta: list[str] = Field(default_factory=list)
    palette_delta: list[str] = Field(default_factory=list)
    motion_delta: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)


class SeriesEntity(BaseModel):
    entity_id: str
    display_name: str
    entity_type: EntityType
    role: str
    silhouette_rules: list[str] = Field(default_factory=list)
    palette_rules: list[str] = Field(default_factory=list)
    motion_rules: list[str] = Field(default_factory=list)
    forbidden_rules: list[str] = Field(default_factory=list)
    episode_presence: list[str] = Field(default_factory=list)
    relationships: list[RelationshipEdge] = Field(default_factory=list)
    shape_grammar: ShapeGrammarLock = Field(default_factory=ShapeGrammarLock)
    text_master: str = ""
    reference_ids: list[str] = Field(default_factory=list)
    variants: list[EntityVariant] = Field(default_factory=list)


class ResolvedEntityVariant(BaseModel):
    entity_id: str
    episode_id: str
    applied_variant_ids: list[str] = Field(default_factory=list)
    appearance_rules: list[str] = Field(default_factory=list)
    palette_rules: list[str] = Field(default_factory=list)
    motion_rules: list[str] = Field(default_factory=list)
    forbidden_rules: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)
    shape_grammar: ShapeGrammarLock
    text_master: str


class SeriesAsset(BaseModel):
    asset_id: str
    path: str
    role: Literal[
        "character_sheet", "action_keyart", "emotion_keyart", "environment_keyart",
        "prop_master", "color_script", "shape_reference", "unassigned"
    ] = "unassigned"
    entity_id: str | None = None
    episode_id: str | None = None
    variant_ids: list[str] = Field(default_factory=list)
    source: Literal["manual", "download_watcher"] = "manual"
    review_status: Literal["candidate", "approved", "rejected"] = "candidate"


class ReferenceSlot(BaseModel):
    slot_id: str
    role: str
    reason: str
    entity_id: str | None = None
    episode_id: str | None = None
    required: bool = True
    covered_by_text_master: bool = False


class AssetPromptPack(BaseModel):
    pack_id: str
    slot_id: str
    kind: str
    prompt: str
    negative_prompt: str
    continuity_keys: list[str] = Field(default_factory=list)


class EntityContinuityState(BaseModel):
    entity_id: str
    shape_tokens: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    prop_states: dict[str, str] = Field(default_factory=dict)
    location_id: str | None = None
    motifs: list[str] = Field(default_factory=list)
    detected_forbidden: list[str] = Field(default_factory=list)


class EpisodeContinuitySnapshot(BaseModel):
    episode_id: str
    entities: list[EntityContinuityState] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    motifs: list[str] = Field(default_factory=list)
    clues_set_up: list[str] = Field(default_factory=list)
    payoffs: list[str] = Field(default_factory=list)


class ContinuityFinding(BaseModel):
    category: Literal[
        "character_shape", "color", "prop", "location", "motif",
        "forbidden", "clue_payoff", "presence"
    ]
    severity: Literal["info", "warning", "error"]
    episode_id: str
    entity_id: str | None = None
    message: str


class SeriesContinuityReport(BaseModel):
    passed: bool
    findings: list[ContinuityFinding] = Field(default_factory=list)


class EpisodeGraphNode(BaseModel):
    node_id: str
    label: str
    order: int


class EpisodeGraphEdge(BaseModel):
    edge_id: str
    source: str
    target: str
    label: str
    chain_id: str


class EpisodeGraph(BaseModel):
    nodes: list[EpisodeGraphNode]
    edges: list[EpisodeGraphEdge]


def resolve_entity_variant(
    entity: SeriesEntity,
    episode_id: str,
    action: str = "",
    emotion: str = "",
) -> ResolvedEntityVariant:
    """Layer episode, action, then emotional deltas without weakening base locks."""
    variants = []
    for kind, trigger in (("episode", episode_id), ("action", action), ("emotional", emotion)):
        matches = [v for v in entity.variants if v.kind == kind and (
            (kind == "episode" and v.episode_id == episode_id)
            or (kind != "episode" and v.trigger.casefold() == trigger.casefold() and (not v.episode_id or v.episode_id == episode_id))
        )]
        variants.extend(matches)
    return ResolvedEntityVariant(
        entity_id=entity.entity_id,
        episode_id=episode_id,
        applied_variant_ids=[v.variant_id for v in variants],
        appearance_rules=entity.silhouette_rules + [x for v in variants for x in v.appearance_delta],
        palette_rules=entity.palette_rules + [x for v in variants for x in v.palette_delta],
        motion_rules=entity.motion_rules + [x for v in variants for x in v.motion_delta],
        forbidden_rules=list(dict.fromkeys(entity.forbidden_rules + entity.shape_grammar.forbidden_mutations)),
        reference_ids=list(dict.fromkeys(entity.reference_ids + entity.shape_grammar.reference_ids + [x for v in variants for x in v.reference_ids])),
        shape_grammar=entity.shape_grammar.model_copy(deep=True),
        text_master=entity.text_master,
    )


def seed_the_fifth_verdict() -> tuple[SeriesBible, list[SeriesEntity]]:
    """Return the production seed from THE FIFTH VERDICT FINAL PROJECT BIBLE v3.0.

    This seed is intentionally conservative: where the project bible has not locked an
    exact visual geometry (for example the final GWAN glyph), the seed preserves the
    narrative constraint instead of inventing a new design.
    """
    episode_titles = [
        "MUTE BELL",
        "DOORLESS ROAD",
        "SILENT WITNESS",
        "MUTINY OF THE UNWRITTEN",
        "GWAN: THE UNWRITTEN VERDICT",
    ]
    episodes = [
        EpisodeBible(
            episode_id="EP1", title=episode_titles[0], order=1,
            logline="A bell that has never rung is sentenced for a sound it did not make.",
            world_overrides=[
                "An un-rung transparent bell is falsely marked as dangerous.",
                "YOSUMI learns that removing a possible action also removes a small personal memory.",
            ],
            visual_overrides=["Folded alley/road geometry", "black square STAMP fracture", "silent-bell protection space"],
        ),
        EpisodeBible(
            episode_id="EP2", title=episode_titles[1], order=2,
            logline="The road keeps removing every choice made to escape.",
            world_overrides=[
                "The DOORLESS ROAD erases routes as choices are made.",
                "TOJI appears hostile but is preserving deleted choices from dispersing.",
            ],
            visual_overrides=["Doorless road", "erased signs", "footsteps that have not happened yet"],
        ),
        EpisodeBible(
            episode_id="EP3", title=episode_titles[2], order=3,
            logline="A testimony is recorded before anyone exists to speak.",
            world_overrides=[
                "THE ARCHIVE generates testimony after STAMP in order to justify an already-fixed verdict.",
                "A missing lullaby note from YOSUMI's memory appears inside fabricated testimony.",
            ],
            visual_overrides=["Empty witness chair", "paper witness without a body", "record windows and black square seals"],
        ),
        EpisodeBible(
            episode_id="EP4", title=episode_titles[3], order=4,
            logline="The condemned refuse to disappear for a crime they have not committed.",
            world_overrides=[
                "THE ARCHIVE attempts to remove all HOLLOW entities.",
                "YOSUMI refuses the destruction order and first redirects danger without deleting a choice.",
            ],
            visual_overrides=["Mass black STAMP field", "HOLLOW clusters protecting one another's erased paths", "unfinished G _ A N clause"],
        ),
        EpisodeBible(
            episode_id="EP5", title=episode_titles[4], order=5,
            logline="To protect someone, the world must stop deciding what they will become.",
            world_overrides=[
                "Destroying THE ARCHIVE only multiplies STAMP, so YOSUMI changes the verdict condition instead.",
                "GWAN blocks present danger without assigning a guilty identity to an unwritten future.",
            ],
            visual_overrides=["Open white palm", "multiple restored paths", "SUZUGARA rings in the present", "EP1 image returns with changed meaning"],
        ),
    ]

    chains = [
        CluePayoffLink(
            chain_id="CHAIN_BELL_SILENCE",
            clue="EP1: SUZUGARA has not rung.",
            setup_episode="EP1", payoff_episode="EP5",
            progression=["EP1 silent bell", "EP2 unheard future footsteps", "EP5 bell rings in the present"],
        ),
        CluePayoffLink(
            chain_id="CHAIN_STAMP_CAUSALITY",
            clue="EP1: the black square STAMP appears before the apparent crime.",
            setup_episode="EP1", payoff_episode="EP5",
            progression=["EP1 STAMP before collapse", "EP3 testimony generated after STAMP", "EP5 STAMP is revealed as the intervention that distorted events"],
        ),
        CluePayoffLink(
            chain_id="CHAIN_LULLABY_MEMORY",
            clue="EP1: one lullaby note disappears when YOSUMI strikes.",
            setup_episode="EP1", payoff_episode="EP3",
            progression=["EP1 memory note lost", "EP3 same note found inside witness record"],
        ),
        CluePayoffLink(
            chain_id="CHAIN_TOJI_ALLY",
            clue="EP2: TOJI first appears to block escape.",
            setup_episode="EP2", payoff_episode="EP4",
            progression=["EP2 preserves erased choices", "EP3 removes the sentence-ending period", "EP4 choice-preservation becomes necessary to resist mass deletion"],
        ),
        CluePayoffLink(
            chain_id="CHAIN_GWAN_NAME",
            clue="EP4: the empty clause reads G _ A N.",
            setup_episode="EP4", payoff_episode="EP5",
            progression=["EP1 five points inside SUZUGARA", "EP4 G _ A N", "EP5 GWAN = Guard Without Assigning Names"],
        ),
        CluePayoffLink(
            chain_id="CHAIN_DOORLESS_PATH",
            clue="EP1: a broken road opens without a door.",
            setup_episode="EP1", payoff_episode="EP5",
            progression=["EP1 road opens", "EP2–EP4 evidence is collected in sequence", "EP5 resolution depends on the original rescue"],
        ),
    ]

    bible = SeriesBible(
        series_id="THE_FIFTH_VERDICT",
        title="THE FIFTH VERDICT",
        episode_titles=episode_titles,
        series_logline=(
            "A guardian who deletes possibilities to protect a city discovers that the system "
            "which declares predicted evil guilty is creating the very anomalies it condemns."
        ),
        common_world_rules=[
            "Observation alone is not guilt; only STAMP forces an uncertain prediction into a fixed fact and cuts away alternatives.",
            "STAMP is not perfect prophecy; it reduces risk by coercing the future toward one selected outcome.",
            "Deleted possibilities are pushed into UNWRITTEN; when they aggregate, they become HOLLOW.",
            "YOSUMI's strike does not destroy flesh; it removes one possible action and costs YOSUMI a small personal memory.",
            "An innocent entity can be harmed by a false STAMP, while an actually occurring dangerous act may still be stopped.",
            "Evidence recovered in one episode opens the next locked record; episode order is causally meaningful.",
            "The ending is not a time reset: past harm remains, but automatic guilt based only on prediction stops.",
        ],
        common_visual_rules=[
            "Original non-human 2.5D ink-and-paper fantasy animation with subtle 3D depth, matte surfaces, and physical camera movement.",
            "Violence is visualized through spatial gaps, missing tempo, erased text, and collapsing paths rather than blood or dismemberment.",
            "Recurring geography across five episodes includes the same street corner, empty bridge, archive window, bell tower, witness stone, and ring plaza.",
            "One dominant action per shot; character topology and geographic continuity outrank spectacle.",
            "Each episode may add only one auxiliary accent color while preserving the shared base palette.",
        ],
        recurring_motifs=[
            "black square STAMP",
            "five-note musical motif",
            "missing/erased path",
            "open versus striking hand",
            "five-part/incomplete GWAN clue",
        ],
        forbidden_elements=[
            "live-action human faces",
            "recognizable celebrities or existing franchise characters",
            "fox ears or animal ears",
            "yokai masks or generic traditional-yokai decoration",
            "torii or shrine motifs added by default",
            "swords or decorative fantasy weapons",
            "crowns",
            "realistic human fingers added to abstract entities",
            "changing body topology",
            "logos or watermarks",
            "generic neon cyberpunk styling",
        ],
        color_system={
            "base": ["deep ink navy #162432", "dark teal #0B7D80", "aged paper #E9E5DA"],
            "episode_rule": ["preserve the base palette; add at most one episode-specific auxiliary color"],
        },
        clue_payoff_chain=chains,
        episodes=episodes,
    )

    all_eps = [f"EP{i}" for i in range(1, 6)]

    def lock(parts, silhouette, forbidden, material=None):
        return ShapeGrammarLock(
            locked_parts=parts,
            silhouette_rules=silhouette,
            material_rules=material or [],
            forbidden_mutations=forbidden,
            lock_strength=1.0,
        )

    entities = [
        SeriesEntity(
            entity_id="YOSUMI", display_name="YOSUMI", entity_type="character",
            role="guardian protagonist who learns to protect without deleting choice",
            episode_presence=all_eps,
            silhouette_rules=[
                "exactly three clearly separated black ink brushstroke ribbons",
                "perfectly rectangular empty opening centered in the chest",
                "only YOSUMI's anatomical left hand is solid matte white",
                "headless, faceless, nonhuman abstract guardian",
            ],
            palette_rules=["deep ink navy #162432", "dark teal #0B7D80", "aged paper #E9E5DA", "no other white body part"],
            motion_rules=[
                "disciplined, economical martial movement",
                "early strikes remove a possible action",
                "open white left palm becomes the non-destructive GWAN gesture",
            ],
            forbidden_rules=[
                "human face", "eyes", "mouth", "hair", "realistic fingers", "extra hands", "extra limbs",
                "fourth ribbon", "extra ribbon fragments", "armor", "clothing", "sword", "crown",
                "animal ears", "fox mask", "yokai motifs", "torii", "shrine motifs",
            ],
            shape_grammar=lock(
                ["three black ink ribbons", "centered rectangular hollow chest", "matte white left hand only"],
                [
                    "three principal ribbons remain countable in every view",
                    "rectangular chest opening stays clean, vertical, visible, and unobstructed",
                    "no head shape appears above the upper ribbon",
                ],
                [
                    "fourth ribbon", "extra appendage", "topology drift", "covered chest rectangle",
                    "white right hand", "additional white body part", "realistic hand anatomy",
                ],
                ["handmade paper fiber", "matte ink pigment", "subtle dimensional layering"],
            ),
            text_master=(
                "YOSUMI is a singular headless and faceless non-human guardian made from EXACTLY THREE "
                "separated black ink brushstroke ribbons, with one perfectly rectangular empty chest opening "
                "and ONLY the anatomical LEFT hand in solid matte white. Preserve this topology over mood or spectacle."
            ),
            variants=[
                EntityVariant(
                    variant_id="YOSUMI_EP4_OPEN_HAND", kind="episode", episode_id="EP4",
                    trigger="unfinished GWAN",
                    motion_delta=["first incomplete open-hand redirection that changes attack direction without deleting a choice"],
                ),
                EntityVariant(
                    variant_id="YOSUMI_EP5_GWAN", kind="episode", episode_id="EP5",
                    trigger="GWAN",
                    motion_delta=["fully open white left palm maintains multiple possibilities while blocking present danger"],
                ),
                EntityVariant(
                    variant_id="YOSUMI_PROTECTIVE_REALIZATION", kind="emotional", episode_id="EP1",
                    trigger="protective realization",
                    motion_delta=["hesitation becomes a protective non-aggressive stance"],
                ),
            ],
        ),
        SeriesEntity(
            entity_id="SUZUGARA", display_name="SUZUGARA", entity_type="character",
            role="silent bell carrying a sound that has not yet happened",
            episode_presence=all_eps,
            silhouette_rules=[
                "transparent bell form",
                "no clapper",
                "two short legs",
                "thin internal line of light/vibration",
            ],
            palette_rules=["transparent/aged-paper body", "subtle dark teal internal vibration"],
            motion_rules=["small restrained vibration", "does not ring until the present-time payoff in EP5"],
            forbidden_rules=["clapper", "human face", "human arms", "ornamental shrine-bell conversion"],
            shape_grammar=lock(
                ["transparent bell body", "no clapper", "two short legs", "thin internal vibration light"],
                ["bell silhouette stays transparent and immediately readable", "internal vibration remains thin and contained"],
                ["added clapper", "human face", "extra legs", "opaque metal body"],
            ),
            text_master=(
                "SUZUGARA is a transparent non-human bell with NO CLAPPER, exactly two short legs, "
                "and a thin internal light vibration that carries a sound which has not yet rung."
            ),
            variants=[
                EntityVariant(
                    variant_id="SUZUGARA_EP5_PRESENT_RING", kind="episode", episode_id="EP5",
                    motion_delta=["rings for the first time in the present rather than as a predicted sound"],
                ),
            ],
        ),
        SeriesEntity(
            entity_id="TOJI", display_name="TOJI", entity_type="character",
            role="keeper that prevents erased choices from dispersing",
            episode_presence=["EP2", "EP3", "EP4", "EP5"],
            silhouette_rules=[
                "exactly two closed bracket forms facing one another",
                "golden gap between the brackets",
                "no face or expression",
            ],
            palette_rules=["ink/paper body", "restrained gold only in the central gap"],
            motion_rules=["contains and holds paths rather than destroying them"],
            forbidden_rules=["human face", "eyes", "mouth", "third bracket", "decorative robe"],
            shape_grammar=lock(
                ["two facing closed brackets", "single golden gap"],
                ["the two brackets remain independently countable", "central gap remains visible"],
                ["third bracket", "merged bracket mass", "face", "limb anatomy"],
            ),
            text_master=(
                "TOJI is an abstract entity made of EXACTLY TWO closed bracket forms facing each other, "
                "with one restrained golden gap and no face, eyes, mouth, or human expression."
            ),
        ),
        SeriesEntity(
            entity_id="THE_ARCHIVE", display_name="THE ARCHIVE", entity_type="system",
            role="preventive record institution whose automatic verdict logic creates the anomaly",
            episode_presence=all_eps,
            silhouette_rules=[
                "countless rotating window frames",
                "black square STAMP mechanism",
                "no human face",
            ],
            palette_rules=["deep ink navy #162432", "dark teal #0B7D80", "aged paper #E9E5DA", "black square STAMP"],
            motion_rules=["window frames rotate and classify", "system persists through structure rather than a humanoid body"],
            forbidden_rules=["human face", "single humanoid villain body", "gothic castle styling"],
            shape_grammar=lock(
                ["rotating window-frame system", "black square STAMP interface"],
                ["reads as an institutional structure, never as a human character"],
                ["human face", "human hands", "ornamental throne", "gothic spires"],
                ["aged paper", "matte ink", "dark structural frames"],
            ),
            text_master=(
                "THE ARCHIVE is a non-human institutional structure of innumerable rotating window frames "
                "and black square STAMP mechanisms; it has no human face and must not become a humanoid villain."
            ),
        ),
        SeriesEntity(
            entity_id="HOLLOW", display_name="HOLLOW", entity_type="system",
            role="aggregate of deleted possibilities wrongly perceived as monsters",
            episode_presence=["EP4", "EP5"],
            silhouette_rules=[
                "cluster of geometric forms with hollow centers",
                "shared ring motif across varied textures",
                "no single human face",
            ],
            palette_rules=["shared series base palette", "texture may vary without losing the hollow-center/ring grammar"],
            motion_rules=["clusters support one another's disappearing paths"],
            forbidden_rules=["solid filled center", "human face", "glowing monster eyes", "generic demon anatomy"],
            shape_grammar=lock(
                ["hollow-centered geometric bodies", "shared ring motif"],
                ["center remains visibly empty", "cluster members may vary in texture but share the ring grammar"],
                ["filled center", "human face", "horned demon silhouette", "glowing eyes"],
            ),
            text_master=(
                "HOLLOW is a collective of varied geometric forms whose centers are visibly empty; "
                "all members share a recurring ring motif and must never collapse into a generic demon or human figure."
            ),
        ),
        SeriesEntity(
            entity_id="STAMP", display_name="STAMP", entity_type="prop",
            role="black square certainty mark that fixes one predicted future as fact",
            episode_presence=all_eps,
            silhouette_rules=["black square mark/seal", "visually cuts away nearby branching paths after activation"],
            palette_rules=["absolute/matte black against the shared paper-and-ink world"],
            motion_rules=["appears as a decisive square imprint before alternatives disappear"],
            forbidden_rules=["round seal", "decorative calligraphy stamp", "logo-like branding"],
            text_master=(
                "STAMP is a stark BLACK SQUARE certainty mark. It is not prophecy itself: when applied, "
                "it forces one uncertain prediction into fact and visibly erases nearby alternatives."
            ),
        ),
        SeriesEntity(
            entity_id="GWAN_SYMBOL", display_name="GWAN / Guard Without Assigning Names",
            entity_type="system", role="new protection principle completed in EP5",
            episode_presence=["EP1", "EP4", "EP5"],
            silhouette_rules=[
                "five-part/incomplete-to-complete clue structure",
                "EP1 five points and EP4 G _ A N foreshadow completion",
                "final exact glyph geometry remains design-lock pending and must not be invented by the seed",
            ],
            palette_rules=["uses the shared base palette; meaning comes from completion, not decorative glow"],
            motion_rules=["paired with the transition from striking fist to open white left palm"],
            forbidden_rules=["invented occult sigil", "generic magic rune", "unmotivated circular glyph"],
            text_master=(
                "GWAN means Guard Without Assigning Names: block immediate danger without fixing identity or future guilt. "
                "Preserve the five-part clue progression; do not invent a final ornamental glyph until separately design-locked."
            ),
        ),
        SeriesEntity(
            entity_id="MARGIN_CITY_LOCATIONS", display_name="MARGIN CITY / recurring locations",
            entity_type="location", role="shared geography for the five-episode series",
            episode_presence=all_eps,
            silhouette_rules=[
                "recurring street corner",
                "empty bridge",
                "archive window",
                "bell tower",
                "witness stone",
                "ring plaza",
                "folded roads and thin layered surfaces of possible futures",
            ],
            palette_rules=["deep ink navy #162432", "dark teal #0B7D80", "aged paper #E9E5DA", "one auxiliary accent color per episode maximum"],
            motion_rules=["subtle 2.5D parallax", "physical camera movement", "geography remains recognizable across episodes"],
            forbidden_rules=["generic neon cyberpunk", "default shrine/torii scenery", "unreadable decorative signage"],
            text_master=(
                "MARGIN CITY is a 2.5D ink-and-paper city built on thin overlapping layers of possible futures, "
                "with recurring street corner, empty bridge, archive window, bell tower, witness stone, and ring plaza geography."
            ),
        ),
    ]

    lookup = {entity.entity_id: entity for entity in entities}
    lookup["YOSUMI"].relationships = [
        RelationshipEdge(
            target_entity_id="SUZUGARA",
            relation="misjudged as dangerous in EP1, then protected; SUZUGARA later contributes the present-time sound needed for GWAN",
            episode_ids=all_eps,
        ),
        RelationshipEdge(
            target_entity_id="TOJI",
            relation="initially mistaken for an obstructing pursuer, later recognized as a keeper of deleted choices",
            episode_ids=["EP2", "EP3", "EP4", "EP5"],
        ),
        RelationshipEdge(
            target_entity_id="HOLLOW",
            relation="initially treated as a threat category, later recognized as condemned unwritten futures protecting one another",
            episode_ids=["EP4", "EP5"],
        ),
    ]

    for episode in bible.episodes:
        episode.entity_ids = [entity.entity_id for entity in entities if episode.episode_id in entity.episode_presence]
        episode.clue_ids = [chain.chain_id for chain in chains if chain.setup_episode == episode.episode_id]
        episode.payoff_ids = [chain.chain_id for chain in chains if chain.payoff_episode == episode.episode_id]

    return bible, entities

def suggest_reference_slots(
    series: SeriesBible,
    entities: list[SeriesEntity],
    assets: list[SeriesAsset],
) -> list[ReferenceSlot]:
    """Plan multiple reference assets per entity instead of assuming one master image."""
    approved = {
        (asset.entity_id, asset.episode_id, asset.role)
        for asset in assets
        if asset.review_status == "approved"
    }
    slots: list[ReferenceSlot] = []
    seen: set[str] = set()

    def add(slot: ReferenceSlot) -> None:
        if slot.slot_id not in seen:
            seen.add(slot.slot_id)
            slots.append(slot)

    for entity in entities:
        if entity.entity_type == "character":
            base_roles = [
                ("character_sheet", True, "Lock the official base design/topology before episode production."),
                ("action_keyart", False, "Verify the same identity under one readable action pose."),
                ("emotion_keyart", False, "Verify the same identity inside a narrative/emotional scene."),
            ]
        elif entity.entity_type == "location":
            base_roles = [
                ("environment_keyart", True, "Lock recurring geography, material and lighting anchors."),
            ]
        elif entity.entity_type == "prop":
            base_roles = [
                ("prop_master", True, "Lock the recurring prop silhouette, material and state."),
            ]
        else:
            base_roles = [
                ("shape_reference", True, "Lock the non-character system/entity shape grammar before production."),
            ]

        for role, required, reason in base_roles:
            if (entity.entity_id, None, role) not in approved:
                add(ReferenceSlot(
                    slot_id=f"SLOT_{entity.entity_id}_{role.upper()}",
                    role=role,
                    entity_id=entity.entity_id,
                    reason=reason,
                    required=required,
                    covered_by_text_master=bool(entity.text_master),
                ))

        for variant in entity.variants:
            role = {
                "episode": "character_sheet" if entity.entity_type == "character" else "shape_reference",
                "action": "action_keyart",
                "emotional": "emotion_keyart",
            }[variant.kind]
            if (entity.entity_id, variant.episode_id, role) not in approved:
                add(ReferenceSlot(
                    slot_id=f"SLOT_{variant.variant_id}",
                    role=role,
                    entity_id=entity.entity_id,
                    episode_id=variant.episode_id,
                    reason=f"Lock {variant.kind} variant {variant.variant_id} without weakening the base identity.",
                    required=True,
                    covered_by_text_master=False,
                ))

    for episode in series.episodes:
        if (None, episode.episode_id, "color_script") not in approved:
            add(ReferenceSlot(
                slot_id=f"SLOT_{episode.episode_id}_COLOR",
                role="color_script",
                episode_id=episode.episode_id,
                reason="Track the shared base palette plus this episode's one permitted auxiliary accent.",
                required=True,
            ))
    return slots


def build_asset_prompt_packs(
    series: SeriesBible,
    entities: list[SeriesEntity],
    slots: list[ReferenceSlot],
) -> list[AssetPromptPack]:
    """Compile provider-neutral, role-specific reference prompts with hard identity locks."""
    by_id = {entity.entity_id: entity for entity in entities}
    by_episode = {episode.episode_id: episode for episode in series.episodes}
    role_instruction = {
        "character_sheet": (
            "OFFICIAL DESIGN LOCK. Full body and highly readable silhouette; neutral presentation; "
            "identity topology overrides drama. Create a clean master suitable for front/side/rear/3/4/action/"
            "small-silhouette follow-up references. Recommended framing 3:4."
        ),
        "action_keyart": (
            "ACTION IDENTITY LOCK. Show one controlled, readable action only. Preserve all hard topology and "
            "locked parts exactly; motion may not create extra limbs, fragments, or silhouette drift. Recommended 3:4."
        ),
        "emotion_keyart": (
            "CINEMATIC STORY KEY ART. Add emotional/narrative atmosphere while preserving the approved entity "
            "identity exactly. Identity lock overrides scenic drama. Recommended 16:9."
        ),
        "environment_keyart": (
            "ENVIRONMENT MASTER. Lock geography, spatial anchors, materials and recurring silhouette; no random "
            "location replacement. Recommended 16:9."
        ),
        "prop_master": (
            "PROP MASTER. Isolate the recurring prop clearly enough to verify silhouette, material and state. "
            "Avoid decorative redesign. Recommended 1:1 or 3:4."
        ),
        "color_script": (
            "EPISODE COLOR SCRIPT. Preserve the shared series base palette and show controlled progression; "
            "introduce at most one episode-specific auxiliary accent. Recommended 16:9."
        ),
        "shape_reference": (
            "SHAPE GRAMMAR REFERENCE. Prioritize countable locked parts, negative space and topology over mood; "
            "use a plain or minimal background. Recommended 3:4."
        ),
    }

    packs: list[AssetPromptPack] = []
    for slot in slots:
        entity = by_id.get(slot.entity_id or "")
        episode = by_episode.get(slot.episode_id or "")
        continuity: list[str] = []
        positive_parts: list[str] = [role_instruction.get(slot.role, slot.role)]

        if entity:
            continuity = list(dict.fromkeys(
                entity.shape_grammar.locked_parts
                + entity.shape_grammar.silhouette_rules
                + entity.shape_grammar.reference_ids
            ))
            positive_parts.extend([
                f"SERIES: {series.title}.",
                f"ENTITY: {entity.display_name} ({entity.entity_id}).",
                f"TEXT MASTER: {entity.text_master}",
                "HARD LOCKED PARTS: " + "; ".join(entity.shape_grammar.locked_parts),
                "HARD SHAPE RULES: " + "; ".join(entity.shape_grammar.silhouette_rules),
                "SILHOUETTE RULES: " + "; ".join(entity.silhouette_rules),
                "PALETTE RULES: " + "; ".join(entity.palette_rules),
                "MOTION RULES: " + "; ".join(entity.motion_rules),
            ])

            variant = next(
                (v for v in entity.variants if slot.slot_id == f"SLOT_{v.variant_id}"),
                None,
            )
            episode_variants = [
                v for v in entity.variants
                if v.kind == "episode" and slot.episode_id and v.episode_id == slot.episode_id
            ]
            applied = []
            for item in [*episode_variants, *([variant] if variant and variant not in episode_variants else [])]:
                applied.append(item.variant_id)
                if item.appearance_delta:
                    positive_parts.append("VARIANT APPEARANCE: " + "; ".join(item.appearance_delta))
                if item.palette_delta:
                    positive_parts.append("VARIANT PALETTE: " + "; ".join(item.palette_delta))
                if item.motion_delta:
                    positive_parts.append("VARIANT MOTION: " + "; ".join(item.motion_delta))
            if applied:
                positive_parts.append("APPLIED VARIANTS: " + ", ".join(applied))

            negative = "; ".join(dict.fromkeys(
                series.forbidden_elements
                + entity.forbidden_rules
                + entity.shape_grammar.forbidden_mutations
            ))
        else:
            positive_parts.extend([
                f"SERIES: {series.title}.",
                f"EPISODE: {slot.episode_id or 'SERIES'}.",
                "COMMON VISUAL RULES: " + "; ".join(series.common_visual_rules),
                "COLOR SYSTEM: " + "; ".join(
                    f"{key}={', '.join(values)}" for key, values in series.color_system.items()
                ),
            ])
            negative = "; ".join(series.forbidden_elements)
            continuity = list(series.color_system)

        if episode:
            positive_parts.extend([
                f"EPISODE TITLE: {episode.title}.",
                f"EPISODE LOGLINE: {episode.logline}",
                "EPISODE VISUAL OVERRIDES: " + "; ".join(episode.visual_overrides),
                "EPISODE COLOR ARC: " + ("; ".join(episode.color_arc) if episode.color_arc else "follow shared base palette; one auxiliary accent maximum"),
            ])

        positive_parts.append(
            "FINAL CHECK: hard locked parts must remain countable/readable and no forbidden mutation may be introduced."
        )
        prompt = "\n".join(part for part in positive_parts if part and not part.endswith(": "))
        packs.append(AssetPromptPack(
            pack_id=f"PACK_{slot.slot_id}",
            slot_id=slot.slot_id,
            kind=slot.role,
            prompt=prompt,
            negative_prompt=negative,
            continuity_keys=list(dict.fromkeys(continuity)),
        ))
    return packs


class DownloadWatcher:
    """Non-destructive download scanner. Files remain at their original paths."""
    extensions = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
    roles = {"character_sheet", "action_keyart", "emotion_keyart", "environment_keyart", "prop_master", "color_script", "shape_reference"}

    def __init__(self, folder: str | Path):
        self.folder = Path(folder).expanduser().resolve(strict=False)
        self._known = self._scan_paths()

    def _scan_paths(self) -> set[Path]:
        if not self.folder.is_dir():
            return set()
        return {p.resolve() for p in self.folder.iterdir() if p.is_file() and p.suffix.lower() in self.extensions}

    def detect_new(self) -> list[Path]:
        current = self._scan_paths()
        new = sorted(current - self._known, key=lambda p: p.name.casefold())
        self._known = current
        return new

    def ingest(self, paths: list[str | Path], entities: list[SeriesEntity], existing: list[SeriesAsset]) -> list[SeriesAsset]:
        entity_ids = {e.entity_id for e in entities}
        existing_paths = {str(Path(a.path).resolve(strict=False)).casefold() for a in existing}
        added = []
        for raw in paths:
            path = Path(raw).expanduser().resolve(strict=False)
            if not path.is_file() or path.suffix.lower() not in self.extensions or str(path).casefold() in existing_paths:
                continue
            tokens = [x.upper() for x in path.stem.replace("-", "_").split("_") if x]
            entity_id = next((eid for eid in entity_ids if eid.upper() in path.stem.upper()), None)
            episode_id = next((f"EP{i}" for i in range(1, 6) if f"EP{i}" in tokens), None)
            lower = path.stem.casefold()
            role = next((role for role in self.roles if role in lower), "unassigned")
            digest = hashlib.sha1(str(path).casefold().encode("utf-8")).hexdigest()[:12]
            asset = SeriesAsset(asset_id=f"ASSET_{digest}", path=str(path), role=role, entity_id=entity_id,
                episode_id=episode_id, source="download_watcher")
            existing.append(asset)
            added.append(asset)
            existing_paths.add(str(path).casefold())
        return added


def run_series_continuity_qc(series: SeriesBible, entities: list[SeriesEntity], snapshots: list[EpisodeContinuitySnapshot]) -> SeriesContinuityReport:
    findings: list[ContinuityFinding] = []
    by_entity = {e.entity_id: e for e in entities}
    by_episode = {s.episode_id: s for s in snapshots}
    prop_history: dict[tuple[str, str], tuple[str, str]] = {}
    for snapshot in snapshots:
        observed_ids = {state.entity_id for state in snapshot.entities}
        for entity in entities:
            if snapshot.episode_id in entity.episode_presence and entity.entity_id not in observed_ids:
                findings.append(ContinuityFinding(category="presence", severity="warning", episode_id=snapshot.episode_id, entity_id=entity.entity_id, message="Expected recurring entity is not registered in this episode snapshot"))
        for state in snapshot.entities:
            entity = by_entity.get(state.entity_id)
            if not entity:
                continue
            required = {x.casefold() for x in entity.shape_grammar.locked_parts}
            observed = {x.casefold() for x in state.shape_tokens}
            if required and observed and not required.issubset(observed):
                findings.append(ContinuityFinding(category="character_shape", severity="error", episode_id=snapshot.episode_id, entity_id=entity.entity_id, message=f"Shape lock drift; missing: {', '.join(sorted(required - observed))}"))
            allowed_colors = {x.casefold() for x in entity.palette_rules}
            observed_colors = {x.casefold() for x in state.colors}
            if allowed_colors and observed_colors and not observed_colors.intersection(allowed_colors):
                findings.append(ContinuityFinding(category="color", severity="warning", episode_id=snapshot.episode_id, entity_id=entity.entity_id, message="Observed palette does not contain a locked entity color"))
            forbidden = {x.casefold() for x in series.forbidden_elements + entity.forbidden_rules + entity.shape_grammar.forbidden_mutations}
            hits = sorted(forbidden.intersection(x.casefold() for x in state.detected_forbidden))
            if hits:
                findings.append(ContinuityFinding(category="forbidden", severity="error", episode_id=snapshot.episode_id, entity_id=entity.entity_id, message="Forbidden elements detected: " + ", ".join(hits)))
            for prop, value in state.prop_states.items():
                key = (entity.entity_id, prop)
                if key in prop_history and prop_history[key][1] != value:
                    findings.append(ContinuityFinding(category="prop", severity="warning", episode_id=snapshot.episode_id, entity_id=entity.entity_id, message=f"{prop} changed from {prop_history[key][1]} ({prop_history[key][0]}) to {value}"))
                prop_history[key] = (snapshot.episode_id, value)
        expected_locations = {e.entity_id for e in entities if e.entity_type == "location" and snapshot.episode_id in e.episode_presence}
        if snapshot.locations and expected_locations and not expected_locations.intersection(snapshot.locations):
            findings.append(ContinuityFinding(category="location", severity="warning", episode_id=snapshot.episode_id, message="No recurring registered location is present"))
    for motif in series.recurring_motifs:
        count = sum(motif.casefold() in {x.casefold() for x in s.motifs} for s in snapshots)
        if snapshots and count < 2:
            findings.append(ContinuityFinding(category="motif", severity="warning", episode_id="SERIES", message=f"Recurring motif lacks progression: {motif}"))
    for chain in series.clue_payoff_chain:
        setup = by_episode.get(chain.setup_episode)
        payoff = by_episode.get(chain.payoff_episode)
        if setup and chain.chain_id not in setup.clues_set_up:
            findings.append(ContinuityFinding(category="clue_payoff", severity="error", episode_id=chain.setup_episode, message=f"Missing clue setup: {chain.chain_id}"))
        if payoff and chain.chain_id not in payoff.payoffs:
            findings.append(ContinuityFinding(category="clue_payoff", severity="error", episode_id=chain.payoff_episode, message=f"Missing payoff: {chain.chain_id}"))
    return SeriesContinuityReport(passed=not any(f.severity == "error" for f in findings), findings=findings)


def build_episode_graph(series: SeriesBible) -> EpisodeGraph:
    nodes = [EpisodeGraphNode(node_id=e.episode_id, label=e.title, order=e.order) for e in sorted(series.episodes, key=lambda x: x.order)]
    edges = [EpisodeGraphEdge(edge_id=f"EDGE_{c.chain_id}", source=c.setup_episode, target=c.payoff_episode, label=c.clue, chain_id=c.chain_id) for c in series.clue_payoff_chain]
    return EpisodeGraph(nodes=nodes, edges=edges)
