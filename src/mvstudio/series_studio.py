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
    episode_titles = [
        "EP1 — The Margin", "EP2 — The Bell", "EP3 — The Archive",
        "EP4 — Hollow Testimony", "EP5 — The Fifth Verdict",
    ]
    episodes = [EpisodeBible(episode_id=f"EP{i}", title=title, order=i) for i, title in enumerate(episode_titles, 1)]
    chains = [
        CluePayoffLink(chain_id="CHAIN_STAMP", clue="A verdict stamp appears incomplete", setup_episode="EP1", payoff_episode="EP5", progression=["EP1", "EP3", "EP5"]),
        CluePayoffLink(chain_id="CHAIN_GWAN", clue="The GWAN symbol changes orientation", setup_episode="EP2", payoff_episode="EP4", progression=["EP2", "EP3", "EP4"]),
    ]
    bible = SeriesBible(
        series_id="THE_FIFTH_VERDICT", title="THE FIFTH VERDICT", episode_titles=episode_titles,
        series_logline="Five linked verdicts expose who controls memory inside the Margin City archive.",
        common_world_rules=["Records can alter civic memory but cannot create a person", "Every verdict leaves a physical trace"],
        common_visual_rules=["One dominant action per shot", "Geometric silhouettes remain readable in wide shots", "Episode changes may layer onto but never replace entity masters"],
        recurring_motifs=["margin line", "verdict stamp", "rotating GWAN symbol", "missing page"],
        forbidden_elements=["unmotivated modern logos", "shape-changing faces", "ornamental fantasy armor"],
        color_system={"base": ["ink black", "paper ivory"], "clue": ["verdict red"], "archive": ["oxidized cyan"], "hollow": ["ash violet"]},
        clue_payoff_chain=chains, episodes=episodes,
    )
    all_eps = [f"EP{i}" for i in range(1, 6)]
    def lock(parts, silhouette, forbidden, material=None):
        return ShapeGrammarLock(locked_parts=parts, silhouette_rules=silhouette, material_rules=material or [], forbidden_mutations=forbidden, lock_strength=1.0)
    entities = [
        SeriesEntity(entity_id="YOSUMI", display_name="YOSUMI", entity_type="character", role="primary witness", episode_presence=all_eps,
            silhouette_rules=["four-corner coat hem", "narrow upright torso"], palette_rules=["ink black", "verdict red accent"], motion_rules=["measured turns", "hands remain close to body"], forbidden_rules=["rounded coat silhouette"],
            shape_grammar=lock(["four-corner coat", "single red cuff"], ["four distinct lower corners visible"], ["cape", "rounded hem", "extra cuffs"]),
            text_master="YOSUMI is a narrow upright witness defined by a four-corner coat hem and one red cuff; facial and body proportions remain constant.",
            variants=[
                EntityVariant(variant_id="YOSUMI_EP5", kind="episode", episode_id="EP5", appearance_delta=["paper dust on unchanged coat"], palette_delta=["red cuff becomes brighter"]),
                EntityVariant(variant_id="YOSUMI_STAMP_ACTION", kind="action", episode_id="EP1", trigger="stamp", motion_delta=["one controlled vertical stamp action"]),
                EntityVariant(variant_id="YOSUMI_DOUBT", kind="emotional", episode_id="EP2", trigger="doubt", appearance_delta=["chin lowers while the four-corner silhouette remains unchanged"]),
            ]),
        SeriesEntity(entity_id="SUZUGARA", display_name="SUZUGARA", entity_type="character", role="bell-bearing guide", episode_presence=all_eps,
            silhouette_rules=["bell-shaped shoulder line", "long split sleeves"], palette_rules=["paper ivory", "oxidized cyan"], motion_rules=["pendulum-like pauses"], forbidden_rules=["visible modern jewelry"],
            shape_grammar=lock(["bell shoulders", "split sleeves"], ["shoulders form a stable bell trapezoid"], ["round shoulders", "short sleeves"]),
            text_master="SUZUGARA has a bell-trapezoid shoulder silhouette, long split sleeves, and a deliberate pendulum motion rhythm."),
        SeriesEntity(entity_id="TOJI", display_name="TOJI", entity_type="character", role="archive adjudicator", episode_presence=["EP2", "EP3", "EP4", "EP5"],
            silhouette_rules=["rectangular collar frame", "asymmetric ledger block"], palette_rules=["charcoal", "aged brass"], motion_rules=["straight-line movement"], forbidden_rules=["flowing robe"],
            shape_grammar=lock(["rectangular collar", "left ledger block"], ["rigid rectangular upper frame"], ["symmetrical ledger", "soft collar"]),
            text_master="TOJI is locked by a rigid rectangular collar and an asymmetric ledger block carried on the left."),
        SeriesEntity(entity_id="THE_ARCHIVE", display_name="THE ARCHIVE", entity_type="location", role="recurring memory institution", episode_presence=all_eps,
            silhouette_rules=["stacked horizontal strata", "one vertical index void"], palette_rules=["paper ivory", "oxidized cyan", "ink black"], motion_rules=["architecture never flexes"], forbidden_rules=["open sky inside archive"],
            shape_grammar=lock(["horizontal strata", "index void"], ["mass reads as layered records"], ["gothic spires", "organic walls"], ["paper", "oxidized metal", "black glass"]),
            text_master="THE ARCHIVE is a layered horizontal record-mass cut by one vertical index void; materials are paper, oxidized metal, and black glass."),
        SeriesEntity(entity_id="HOLLOW", display_name="HOLLOW", entity_type="system", role="absence made visible", episode_presence=["EP3", "EP4", "EP5"],
            silhouette_rules=["negative-space human aperture", "no facial features"], palette_rules=["ash violet", "absolute black"], motion_rules=["surroundings move; aperture does not"], forbidden_rules=["eyes", "mouth", "solid skin"],
            shape_grammar=lock(["featureless aperture", "unbroken rim"], ["human-scale negative space"], ["face", "limbs detached from aperture", "glowing eyes"]),
            text_master="HOLLOW is a human-scale negative-space aperture with an unbroken rim and no face, eyes, mouth, or solid skin."),
        SeriesEntity(entity_id="STAMP", display_name="Verdict Stamp", entity_type="prop", role="verdict mechanism", episode_presence=all_eps,
            silhouette_rules=["square head", "short cylindrical handle"], palette_rules=["verdict red", "aged brass"], motion_rules=["single vertical strike"], forbidden_rules=["round seal"], text_master="A square verdict stamp with a short cylindrical aged-brass handle and red ink."),
        SeriesEntity(entity_id="GWAN_SYMBOL", display_name="GWAN Symbol", entity_type="system", role="clue orientation system", episode_presence=all_eps,
            silhouette_rules=["three unequal nested angles"], palette_rules=["oxidized cyan"], motion_rules=["rotates only between episodes"], forbidden_rules=["circular glyph"], text_master="Three unequal nested angles; orientation changes only as a deliberate episode clue."),
        SeriesEntity(entity_id="MARGIN_CITY_LOCATIONS", display_name="Margin City Locations", entity_type="location", role="shared exterior system", episode_presence=all_eps,
            silhouette_rules=["buildings align to visible margin grids"], palette_rules=["ink black", "paper ivory", "episode accent"], motion_rules=["traffic follows ruled lines"], forbidden_rules=["generic neon cyberpunk"], text_master="A city organized by visible page margins and ruled transit lines, never generic neon cyberpunk."),
    ]
    lookup = {e.entity_id: e for e in entities}
    lookup["YOSUMI"].relationships = [RelationshipEdge(target_entity_id="SUZUGARA", relation="trust moves from distance to alliance", episode_ids=all_eps), RelationshipEdge(target_entity_id="TOJI", relation="witness versus adjudicator", episode_ids=["EP2", "EP3", "EP5"])]
    lookup["SUZUGARA"].relationships = [RelationshipEdge(target_entity_id="THE_ARCHIVE", relation="former guide of", episode_ids=all_eps)]
    for episode in bible.episodes:
        episode.entity_ids = [e.entity_id for e in entities if episode.episode_id in e.episode_presence]
        episode.clue_ids = [c.chain_id for c in chains if c.setup_episode == episode.episode_id]
        episode.payoff_ids = [c.chain_id for c in chains if c.payoff_episode == episode.episode_id]
    return bible, entities


def suggest_reference_slots(series: SeriesBible, entities: list[SeriesEntity], assets: list[SeriesAsset]) -> list[ReferenceSlot]:
    approved = {(a.entity_id, a.episode_id, a.role) for a in assets if a.review_status == "approved"}
    slots: list[ReferenceSlot] = []
    for entity in entities:
        base_role = "character_sheet" if entity.entity_type == "character" else ("environment_keyart" if entity.entity_type == "location" else "prop_master")
        if (entity.entity_id, None, base_role) not in approved:
            slots.append(ReferenceSlot(slot_id=f"SLOT_{entity.entity_id}_BASE", role=base_role, entity_id=entity.entity_id,
                reason="Lock base form before episode production", covered_by_text_master=bool(entity.text_master)))
        for variant in entity.variants:
            role = {"episode": "character_sheet", "action": "action_keyart", "emotional": "emotion_keyart"}[variant.kind]
            if (entity.entity_id, variant.episode_id, role) not in approved:
                slots.append(ReferenceSlot(slot_id=f"SLOT_{variant.variant_id}", role=role, entity_id=entity.entity_id, episode_id=variant.episode_id,
                    reason=f"Reference for {variant.kind} variant {variant.variant_id}", covered_by_text_master=False))
    for episode in series.episodes:
        if (None, episode.episode_id, "color_script") not in approved:
            slots.append(ReferenceSlot(slot_id=f"SLOT_{episode.episode_id}_COLOR", role="color_script", episode_id=episode.episode_id,
                reason="Track the series-wide color system through this episode", required=True))
    return slots


def build_asset_prompt_packs(series: SeriesBible, entities: list[SeriesEntity], slots: list[ReferenceSlot]) -> list[AssetPromptPack]:
    by_id = {e.entity_id: e for e in entities}
    packs = []
    for slot in slots:
        entity = by_id.get(slot.entity_id or "")
        continuity = []
        if entity:
            continuity = entity.shape_grammar.locked_parts + entity.shape_grammar.silhouette_rules
            positive = "; ".join([entity.text_master] + entity.silhouette_rules + entity.palette_rules + entity.motion_rules)
            negative = "; ".join(series.forbidden_elements + entity.forbidden_rules + entity.shape_grammar.forbidden_mutations)
        else:
            positive = f"{series.title}, {slot.episode_id} color script; " + "; ".join(series.common_visual_rules + sum(series.color_system.values(), []))
            negative = "; ".join(series.forbidden_elements)
            continuity = list(series.color_system)
        packs.append(AssetPromptPack(pack_id=f"PACK_{slot.slot_id}", slot_id=slot.slot_id, kind=slot.role,
            prompt=f"{slot.role}. {positive}. Preserve series continuity.", negative_prompt=negative,
            continuity_keys=list(dict.fromkeys(continuity))))
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
