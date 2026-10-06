from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class ReferenceRole(str, Enum):
    CHARACTER_MASTER = "character_master"
    CHARACTER_WARDROBE = "character_wardrobe"
    LOCATION_MASTER = "location_master"
    PROP_MASTER = "prop_master"
    COLOR_LIGHT = "color_light"
    COMPOSITION = "composition"
    CAMERA_MOTION = "camera_motion"
    TEXTURE_MATERIAL = "texture_material"


class ReferenceAsset(BaseModel):
    reference_id: str
    role: ReferenceRole
    path: str
    lock_strength: float = Field(default=0.8, ge=0, le=1)
    notes: str = ""
    provider_asset_ids: dict[str, str] = Field(default_factory=dict)


class LyricLine(BaseModel):
    line_id: str
    text: str
    start_sec: float | None = Field(default=None, ge=0)
    end_sec: float | None = Field(default=None, ge=0)
    section: str | None = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_sec is not None and self.end_sec is not None and self.end_sec < self.start_sec:
            raise ValueError("lyric end_sec must be >= start_sec")
        return self


class LyricAnchor(BaseModel):
    anchor_id: str
    anchor_type: Literal[
        "place", "weather", "object", "time", "motion", "body_sense",
        "relationship", "color_light", "nature", "abstract"
    ]
    phrase: str
    source_line_ids: list[str] = Field(default_factory=list)
    weight: float = Field(default=0.5, ge=0, le=1)


class LyricInterpretation(BaseModel):
    language_hint: str = "auto"
    synopsis: str = ""
    pov: str = "unknown"
    central_conflict: str = ""
    emotional_arc: list[str] = Field(default_factory=list)
    repeated_phrases: list[str] = Field(default_factory=list)
    anchors: list[LyricAnchor] = Field(default_factory=list)
    visual_risk_notes: list[str] = Field(default_factory=list)


class WorldConcept(BaseModel):
    concept_id: str
    title: str
    interpretation_mode: Literal["literal", "metaphoric", "hybrid", "counterpoint"]
    one_line: str
    world_rule: str
    emotional_engine: str
    recurring_motifs: list[str] = Field(default_factory=list)
    visual_language: list[str] = Field(default_factory=list)
    ending_image: str = ""
    lyric_evidence: list[str] = Field(default_factory=list)
    lyric_relevance_score: int = Field(default=0, ge=0, le=100)


class LyricVisualBridge(BaseModel):
    bridge_id: str
    beat_id: str | None = None
    source_line_ids: list[str] = Field(default_factory=list)
    lyric_intent: str
    visual_strategy: Literal[
        "literal", "metaphor", "motif", "counterpoint", "performance", "silence"
    ] = "metaphor"
    literalness: float = Field(default=0.35, ge=0, le=1)
    must_preserve: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class AudioTransition(BaseModel):
    transition_id: str
    time_sec: float = Field(ge=0)
    strength: float = Field(default=0.5, ge=0, le=1)
    character: Literal["energy_rise", "energy_drop", "texture_or_rhythm_change"]
    reasons: list[str] = Field(default_factory=list)


class AudioSection(BaseModel):
    section_id: str
    label: str
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    mean_energy: float = Field(default=0, ge=0)
    confidence: float = Field(default=0.5, ge=0, le=1)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("audio section end_sec must be greater than start_sec")
        return self


class AudioMap(BaseModel):
    source_path: str
    duration_sec: float = Field(gt=0)
    sample_rate: int = Field(gt=0)
    tempo_bpm: float = Field(default=0, ge=0)
    beat_times_sec: list[float] = Field(default_factory=list)
    onset_times_sec: list[float] = Field(default_factory=list)
    transitions: list[AudioTransition] = Field(default_factory=list)
    sections: list[AudioSection] = Field(default_factory=list)
    cut_cadence_hints: dict[str, float] = Field(default_factory=dict)
    analysis_notes: list[str] = Field(default_factory=list)


class MVTimelineCue(BaseModel):
    cue_id: str
    time_sec: float = Field(ge=0)
    priority: float = Field(default=0.5, ge=0, le=1)
    cue_type: str
    reasons: list[str] = Field(default_factory=list)
    lyric_line_ids: list[str] = Field(default_factory=list)
    recommended_visual_action: str


class WorldBible(BaseModel):
    premise: str
    emotional_thesis: str
    reality_rules: list[str] = Field(default_factory=list)
    time_period: str = ""
    visual_language: list[str] = Field(default_factory=list)
    palette: list[str] = Field(default_factory=list)
    material_language: list[str] = Field(default_factory=list)
    weather_rules: list[str] = Field(default_factory=list)
    lighting_rules: list[str] = Field(default_factory=list)
    camera_rules: list[str] = Field(default_factory=list)
    recurring_motifs: list[str] = Field(default_factory=list)
    forbidden_elements: list[str] = Field(default_factory=list)
    lyric_foundation: list[str] = Field(default_factory=list)


class CharacterBible(BaseModel):
    character_id: str
    name: str
    identity_anchor: str
    silhouette: str = ""
    appearance_locks: list[str] = Field(default_factory=list)
    wardrobe_locks: list[str] = Field(default_factory=list)
    motion_signature: list[str] = Field(default_factory=list)
    emotional_range: list[str] = Field(default_factory=list)
    forbidden_variations: list[str] = Field(default_factory=list)
    master_reference_ids: list[str] = Field(default_factory=list)


class LocationBible(BaseModel):
    location_id: str
    name: str
    architectural_grammar: str
    spatial_anchors: list[str] = Field(default_factory=list)
    lighting_rules: list[str] = Field(default_factory=list)
    signature_objects: list[str] = Field(default_factory=list)
    master_reference_ids: list[str] = Field(default_factory=list)


class StoryBeat(BaseModel):
    beat_id: str
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    dramatic_question: str
    change: str
    visual_event: str
    motif: str | None = None
    setup_or_payoff: Literal["setup", "development", "payoff", "none"] = "none"
    lyric_line_ids: list[str] = Field(default_factory=list)
    lyric_intent: str = ""

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("end_sec must be greater than start_sec")
        return self


class CameraSpec(BaseModel):
    framing: str
    lens: str = ""
    angle: str = ""
    movement: str = ""
    movement_strength: Literal["locked", "subtle", "medium", "strong"] = "subtle"


class ShotSpec(BaseModel):
    shot_id: str
    beat_id: str | None = None
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    narrative_function: str
    lyric_or_music_cue: str = ""
    lyric_line_ids: list[str] = Field(default_factory=list)
    lyric_intent: str = ""
    lyric_visual_strategy: Literal[
        "literal", "metaphor", "motif", "counterpoint", "performance", "silence"
    ] = "metaphor"
    subject: str
    action: str
    environment: str
    composition: str
    camera: CameraSpec
    lighting: str
    emotional_note: str
    motif: str | None = None
    continuity_in: list[str] = Field(default_factory=list)
    continuity_out: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)
    generation_mode: Literal["t2v", "i2v", "first_last", "extend", "v2v"] = "i2v"
    first_frame_ref: str | None = None
    last_frame_ref: str | None = None
    negative_constraints: list[str] = Field(default_factory=list)

    @property
    def duration_sec(self) -> float:
        return round(self.end_sec - self.start_sec, 3)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("end_sec must be greater than start_sec")
        return self


class MusicVideoProject(BaseModel):
    schema_version: str = "0.4"
    title: str
    song_path: str | None = None
    lyrics_path: str | None = None
    creative_thesis: str
    audio_map: AudioMap | None = None
    mv_timeline: list[MVTimelineCue] = Field(default_factory=list)
    lyric_lines: list[LyricLine] = Field(default_factory=list)
    lyric_interpretation: LyricInterpretation | None = None
    world_concepts: list[WorldConcept] = Field(default_factory=list)
    lyric_visual_bridges: list[LyricVisualBridge] = Field(default_factory=list)
    world_bible: WorldBible
    references: list[ReferenceAsset] = Field(default_factory=list)
    characters: list[CharacterBible] = Field(default_factory=list)
    locations: list[LocationBible] = Field(default_factory=list)
    story_beats: list[StoryBeat] = Field(default_factory=list)
    shots: list[ShotSpec] = Field(default_factory=list)

    def reference_map(self) -> dict[str, ReferenceAsset]:
        return {x.reference_id: x for x in self.references}

    def lyric_map(self) -> dict[str, LyricLine]:
        return {x.line_id: x for x in self.lyric_lines}
