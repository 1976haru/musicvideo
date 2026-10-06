from __future__ import annotations
from dataclasses import dataclass
from .models import MusicVideoProject, ShotSpec


@dataclass
class GenerationPack:
    provider: str
    shot_id: str
    prompt: str
    negative_prompt: str
    duration_sec: float
    references: list[str]
    first_frame_ref: str | None
    last_frame_ref: str | None
    lyric_evidence: list[str]
    lyric_strategy: str
    notes: list[str]


def _join(items: list[str]) -> str:
    return "; ".join(x.strip() for x in items if x and x.strip())


def _world_lock(project: MusicVideoProject) -> str:
    w = project.world_bible
    parts = [
        f"World premise: {w.premise}",
        f"Emotional thesis: {w.emotional_thesis}",
        f"Lyric foundation: {_join(w.lyric_foundation)}" if w.lyric_foundation else "",
        f"Visual language: {_join(w.visual_language)}" if w.visual_language else "",
        f"Palette: {_join(w.palette)}" if w.palette else "",
        f"Materials: {_join(w.material_language)}" if w.material_language else "",
        f"Lighting rules: {_join(w.lighting_rules)}" if w.lighting_rules else "",
        f"Camera rules: {_join(w.camera_rules)}" if w.camera_rules else "",
    ]
    return ". ".join(p for p in parts if p)


def _character_locks(project: MusicVideoProject, shot: ShotSpec) -> str:
    text = []
    for c in project.characters:
        if any(ref in shot.reference_ids for ref in c.master_reference_ids):
            text.append(
                f"{c.name}: {c.identity_anchor}; appearance locks: {_join(c.appearance_locks)}; wardrobe locks: {_join(c.wardrobe_locks)}"
            )
    return " | ".join(text)


def _location_locks(project: MusicVideoProject, shot: ShotSpec) -> str:
    text = []
    for loc in project.locations:
        if any(ref in shot.reference_ids for ref in loc.master_reference_ids):
            text.append(f"{loc.name}: {loc.architectural_grammar}; anchors: {_join(loc.spatial_anchors)}")
    return " | ".join(text)


def _lyrics_for_shot(project: MusicVideoProject, shot: ShotSpec) -> list[str]:
    lyric_map = project.lyric_map()
    return [lyric_map[x].text for x in shot.lyric_line_ids if x in lyric_map]


def _generic_prompt(project: MusicVideoProject, shot: ShotSpec) -> str:
    lyric_lines = _lyrics_for_shot(project, shot)
    lyric_context = ""
    if lyric_lines or shot.lyric_intent:
        lyric_context = (
            f"Lyric meaning for this shot: {shot.lyric_intent}. Source lyric: {_join(lyric_lines)}. "
            f"Visual strategy: {shot.lyric_visual_strategy}. Translate meaning into action, spatial change, motif, light, or camera behavior; "
            "do not merely illustrate every noun in the lyric."
        )
    chunks = [
        _world_lock(project), _character_locks(project, shot), _location_locks(project, shot), lyric_context,
        f"Shot purpose: {shot.narrative_function}.",
        f"Subject: {shot.subject}. Action: {shot.action}.",
        f"Environment: {shot.environment}.", f"Composition: {shot.composition}.",
        f"Camera: {shot.camera.framing}, {shot.camera.lens}, {shot.camera.angle}, {shot.camera.movement} ({shot.camera.movement_strength}).",
        f"Lighting: {shot.lighting}.", f"Emotion: {shot.emotional_note}.",
        f"Continuity in: {_join(shot.continuity_in)}." if shot.continuity_in else "",
        f"Continuity out: {_join(shot.continuity_out)}." if shot.continuity_out else "",
        f"Motif: {shot.motif}." if shot.motif else "",
    ]
    return " ".join(x for x in chunks if x).replace("..", ".")


def compile_shot(project: MusicVideoProject, shot: ShotSpec, provider: str) -> GenerationPack:
    provider = provider.lower().strip()
    generic = _generic_prompt(project, shot)
    ref_map = project.reference_map()
    refs = [ref_map[rid].path for rid in shot.reference_ids if rid in ref_map]
    negatives = list(project.world_bible.forbidden_elements) + list(shot.negative_constraints)
    lyric_lines = _lyrics_for_shot(project, shot)
    notes: list[str] = []

    if provider == "runway" and shot.generation_mode in {"i2v", "first_last", "extend"}:
        lyric_motion = f"The motion should express this lyric intent: {shot.lyric_intent}. " if shot.lyric_intent else ""
        prompt = (
            f"{shot.subject} {shot.action}. {lyric_motion}Camera {shot.camera.movement or 'remains controlled'}; "
            f"{shot.camera.framing}, {shot.camera.lens}. Temporal progression is coherent and physically plausible. "
            f"Emotion: {shot.emotional_note}. Preserve all visual identity, wardrobe, environment, lighting and composition from the reference. "
            f"Use {shot.lyric_visual_strategy} interpretation rather than literal lyric illustration."
        )
        notes.append("Runway I2V: reference carries identity/composition; prompt emphasizes temporal behavior.")
    elif provider == "veo":
        prompt = generic + " Preserve continuity from the previous shot and end in a composition usable by the next shot."
        if shot.first_frame_ref or shot.last_frame_ref:
            notes.append("Veo: bind first/last frame in the adapter.")
    elif provider == "luma":
        prompt = generic + " Motion should evolve continuously between anchors without identity drift or abrupt geometry changes."
        notes.append("Luma: keyframe/extend-friendly.")
    elif provider in {"kling", "fal", "kling_fal"}:
        prompt = (
            f"{shot.subject}. {shot.action}. Lyric intent: {shot.lyric_intent}. Visual strategy: {shot.lyric_visual_strategy}. "
            f"Scene: {shot.environment}. Camera: {shot.camera.framing}; {shot.camera.movement}. Lighting: {shot.lighting}. "
            f"Emotion: {shot.emotional_note}. Maintain reference identity and wardrobe exactly."
        )
    elif provider == "comfyui":
        prompt = generic
        notes.append("ComfyUI: export text, lyric evidence, references, seed and workflow variables separately.")
    else:
        prompt = generic
        notes.append("Generic/manual provider pack.")

    return GenerationPack(
        provider=provider, shot_id=shot.shot_id, prompt=prompt.strip(), negative_prompt=_join(negatives),
        duration_sec=shot.duration_sec, references=refs, first_frame_ref=shot.first_frame_ref,
        last_frame_ref=shot.last_frame_ref, lyric_evidence=lyric_lines, lyric_strategy=shot.lyric_visual_strategy,
        notes=notes,
    )
