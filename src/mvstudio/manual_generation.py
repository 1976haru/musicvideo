from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .models import ReferenceAsset, ShotSpec
from .reference_vault import resolve_reference_path
from .story_engine import reference_is_eligible, shot_warnings

if TYPE_CHECKING:
    from .session import LyricsWorldSession


class ManualSiteProfile(BaseModel):
    profile_id: str
    display_name: str
    mode: Literal["manual_web"] = "manual_web"
    prompt_style: str
    supports_negative_prompt: bool = True
    supports_first_frame: bool = True
    supports_last_frame: bool = False
    supports_multi_reference: bool = True
    supports_camera_presets: bool = False
    camera_presets: dict[str, str] = Field(default_factory=dict)
    duration_options: list[float] = Field(default_factory=list)
    aspect_ratio_options: list[str] = Field(default_factory=list)
    resolution_options: list[str] = Field(default_factory=list)
    generation_mode_options: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    website_label: str
    profile_version: str = "1.0"
    capabilities_model_dependent: bool = False


class ReferenceInstruction(BaseModel):
    reference_id: str
    role: str
    lock_strength: float
    scope: str
    path: str
    instruction: str
    missing: bool
    eligible: bool


class ManualGenerationPack(BaseModel):
    pack_id: str
    shot_id: str
    beat_id: str | None = None
    profile_id: str
    created_at: str
    generation_mode: str
    main_prompt: str
    motion_prompt: str
    camera_prompt: str
    negative_prompt: str
    reference_instructions: list[ReferenceInstruction] = Field(default_factory=list)
    world_rule_summary: list[str] = Field(default_factory=list)
    continuity_summary: list[str] = Field(default_factory=list)
    series_episode_id: str | None = None
    series_entity_ids: list[str] = Field(default_factory=list)
    series_variant_ids: list[str] = Field(default_factory=list)
    series_lock_summary: list[str] = Field(default_factory=list)
    series_asset_ids: list[str] = Field(default_factory=list)
    series_asset_paths: list[str] = Field(default_factory=list)
    first_frame_ref: str | None = None
    last_frame_ref: str | None = None
    duration_sec: float
    generation_duration_hint: float | None = None
    aspect_ratio: str
    resolution_hint: str
    camera_preset_recommendation: str
    lyric_line_ids: list[str] = Field(default_factory=list)
    music_cue_ids: list[str] = Field(default_factory=list)
    world_rule_refs: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)
    lyric_evidence: list[str] = Field(default_factory=list)
    lyric_strategy: str
    settings_checklist: list[str] = Field(default_factory=list)
    readiness: Literal["READY", "READY_WITH_WARNINGS", "BLOCKED"]
    warnings: list[str] = Field(default_factory=list)
    full_clipboard_text: str


GENERIC_MANUAL = ManualSiteProfile(
    profile_id="GENERIC_MANUAL",
    display_name="Generic Manual Website",
    prompt_style="structured cinematic prose",
    supports_last_frame=True,
    supports_camera_presets=False,
    duration_options=[4, 5, 6, 8, 10],
    aspect_ratio_options=["16:9", "9:16", "1:1", "2.39:1"],
    resolution_options=["1080p", "720p", "site default"],
    generation_mode_options=["t2v", "i2v", "first_last", "extend", "v2v"],
    notes=["Enter prompts and settings manually on the chosen website."],
    website_label="Manual video generation website",
)


HIGGSFIELD = ManualSiteProfile(
    profile_id="HIGGSFIELD",
    display_name="Higgsfield (Manual)",
    prompt_style="concise cinematic subject and motion instructions",
    supports_last_frame=True,
    supports_camera_presets=True,
    camera_presets={
        "subtle push-in": "Dolly In",
        "push in": "Dolly In",
        "locked": "Static",
        "static": "Static",
        "focus": "Focus Change",
        "rack focus": "Focus Change",
        "orbit": "360 Orbit / Arc",
        "arc": "360 Orbit / Arc",
        "pan": "Pan Left / Right",
        "tilt": "Tilt Up / Down",
        "handheld": "Handheld",
    },
    duration_options=[],
    aspect_ratio_options=["site / model dependent"],
    resolution_options=["site / model dependent"],
    generation_mode_options=["t2v", "i2v", "first_last", "extend", "v2v"],
    notes=[
        "Duration, aspect ratio, resolution, first/last frame, and negative-prompt support depend on the model selected on Higgsfield.",
        "supports_* means available on at least some models on this site, not guaranteed for every model.",
        "Camera preset recommendations are site-level guidance; verify current model options manually.",
    ],
    website_label="Higgsfield website",
    capabilities_model_dependent=True,
)

MANUAL_SITE_PROFILES = {profile.profile_id: profile for profile in (GENERIC_MANUAL, HIGGSFIELD)}


def get_manual_site_profile(profile_id: str) -> ManualSiteProfile:
    try:
        return MANUAL_SITE_PROFILES[profile_id.strip().upper()]
    except KeyError as exc:
        raise ValueError(f"Unknown manual site profile: {profile_id}") from exc


def recommend_camera_preset(profile: ManualSiteProfile, shot: ShotSpec) -> str:
    if not profile.supports_camera_presets:
        return "Custom / no preset recommendation"
    camera_text = " ".join((shot.camera.movement, shot.camera.movement_strength, shot.camera.angle)).casefold()
    matches = [(key, value) for key, value in profile.camera_presets.items() if key.casefold() in camera_text]
    return max(matches, key=lambda item: len(item[0]))[1] if matches else "Custom / no preset recommendation"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = " ".join(value.split())
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _known_world_rules(session: LyricsWorldSession) -> dict[str, str]:
    rules: dict[str, str] = {}
    if session.world_bible:
        for field in ("reality_rules", "weather_rules", "lighting_rules", "camera_rules"):
            rules.update({f"{field}:{index}": value for index, value in enumerate(getattr(session.world_bible, field))})
    return rules


def _reference_instruction(session: LyricsWorldSession, shot: ShotSpec, asset: ReferenceAsset) -> ReferenceInstruction:
    resolved = resolve_reference_path(asset, session.project_dir)
    eligible = reference_is_eligible(asset, shot)
    scope = asset.applies_to.value + (f":{asset.scope_id}" if asset.scope_id else "")
    strength = "strictly preserve" if asset.lock_strength >= 0.8 else "use as a strong guide" if asset.lock_strength >= 0.5 else "use as a loose visual guide"
    return ReferenceInstruction(
        reference_id=asset.reference_id,
        role=asset.role.value,
        lock_strength=asset.lock_strength,
        scope=scope,
        path=str(resolved),
        instruction=f"{strength} {asset.role.value.replace('_', ' ')}; {asset.notes}".strip("; "),
        missing=not resolved.is_file(),
        eligible=eligible,
    )


def _series_lock_bundle(session: LyricsWorldSession, shot: ShotSpec):
    """Resolve G8 identity locks and approved assets for a Shot without weakening base locks."""
    bible = getattr(session, "series_bible", None)
    entities = getattr(session, "series_entities", [])
    assets = getattr(session, "series_assets", [])
    if not bible or not shot.series_entity_ids:
        return [], [], [], [], [], []

    by_id = {entity.entity_id: entity for entity in entities}
    lock_blocks: list[str] = []
    negatives: list[str] = []
    continuity: list[str] = []
    warnings: list[str] = []

    for entity_id in shot.series_entity_ids:
        entity = by_id.get(entity_id)
        if not entity:
            warnings.append(f"Unknown series entity: {entity_id}")
            continue
        if shot.series_episode_id and entity.episode_presence and shot.series_episode_id not in entity.episode_presence:
            warnings.append(f"{entity_id} is not registered for {shot.series_episode_id}")

        applied_variants = [
            variant for variant in entity.variants
            if (
                (variant.kind == "episode" and shot.series_episode_id and variant.episode_id == shot.series_episode_id)
                or variant.variant_id in shot.series_variant_ids
            )
        ]
        parts = [
            f"ENTITY {entity.display_name} ({entity.entity_id})",
            f"TEXT MASTER: {entity.text_master}",
            "HARD LOCKED PARTS: " + "; ".join(entity.shape_grammar.locked_parts),
            "HARD SHAPE RULES: " + "; ".join(entity.shape_grammar.silhouette_rules),
            "SILHOUETTE: " + "; ".join(entity.silhouette_rules),
            "PALETTE: " + "; ".join(entity.palette_rules),
            "MOTION: " + "; ".join(entity.motion_rules),
        ]
        for variant in applied_variants:
            parts.append(f"VARIANT {variant.variant_id} ({variant.kind})")
            if variant.appearance_delta:
                parts.append("VARIANT APPEARANCE: " + "; ".join(variant.appearance_delta))
            if variant.palette_delta:
                parts.append("VARIANT PALETTE: " + "; ".join(variant.palette_delta))
            if variant.motion_delta:
                parts.append("VARIANT MOTION: " + "; ".join(variant.motion_delta))
        lock_blocks.append(" | ".join(part for part in parts if not part.endswith(": ")))
        negatives.extend(entity.forbidden_rules)
        negatives.extend(entity.shape_grammar.forbidden_mutations)
        continuity.extend(f"{entity.entity_id}: {item}" for item in entity.shape_grammar.locked_parts)

    approved_assets = [
        asset for asset in assets
        if asset.review_status == "approved"
        and asset.entity_id in shot.series_entity_ids
        and (not asset.episode_id or not shot.series_episode_id or asset.episode_id == shot.series_episode_id)
    ]
    asset_ids: list[str] = []
    asset_paths: list[str] = []
    for asset in approved_assets:
        path = Path(asset.path).expanduser().resolve(strict=False)
        asset_ids.append(asset.asset_id)
        asset_paths.append(str(path))
        if not path.is_file():
            warnings.append(f"Missing approved series asset: {asset.asset_id} ({path})")

    selected_variant_ids = {
        variant.variant_id
        for entity_id in shot.series_entity_ids
        for entity in [by_id.get(entity_id)]
        if entity
        for variant in entity.variants
        if (variant.kind == "episode" and shot.series_episode_id and variant.episode_id == shot.series_episode_id)
           or variant.variant_id in shot.series_variant_ids
    }
    unknown_variants = sorted(set(shot.series_variant_ids) - selected_variant_ids)
    if unknown_variants:
        warnings.append("Unknown/inapplicable series variants: " + ", ".join(unknown_variants))

    negatives.extend(getattr(bible, "forbidden_elements", []))
    return (
        _dedupe(lock_blocks),
        _dedupe(negatives),
        _dedupe(continuity),
        _dedupe(warnings),
        list(dict.fromkeys(asset_ids)),
        list(dict.fromkeys(asset_paths)),
    )


def _nearest_duration(duration: float, options: list[float]) -> float | None:
    return min(options, key=lambda option: (abs(option - duration), option)) if options else None


def compile_manual_pack(
    session: LyricsWorldSession,
    shot: ShotSpec,
    profile_id: str = "GENERIC_MANUAL",
    *,
    generation_duration_hint: float | None = None,
    aspect_ratio: str | None = None,
    resolution_hint: str | None = None,
    pack_id: str | None = None,
    created_at: str | None = None,
) -> ManualGenerationPack:
    profile = get_manual_site_profile(profile_id)
    bible = session.world_bible
    lyric_map = {line.line_id: line.text for line in session.lines}
    lyric_evidence = [lyric_map[line_id] for line_id in shot.lyric_line_ids if line_id in lyric_map]
    world_rules = _known_world_rules(session)
    rule_summary = [world_rules[rule_id] for rule_id in shot.world_rule_refs if rule_id in world_rules]
    ref_map = {asset.reference_id: asset for asset in session.references}
    ref_instructions = [_reference_instruction(session, shot, ref_map[ref_id]) for ref_id in shot.reference_ids if ref_id in ref_map]
    preset = recommend_camera_preset(profile, shot)
    (
        series_locks, series_negatives, series_continuity, series_warnings,
        series_asset_ids, series_asset_paths,
    ) = _series_lock_bundle(session, shot)

    world_chunks = []
    if bible:
        world_chunks = [bible.premise, bible.emotional_thesis, *bible.visual_language, *bible.palette, *bible.material_language]
    main_parts = _dedupe([
        f"WORLD LOCK: {'; '.join(_dedupe(world_chunks))}" if world_chunks else "",
        f"SERIES EPISODE: {shot.series_episode_id}" if shot.series_episode_id else "",
        ("SERIES ENTITY LOCKS:\n" + "\n".join(series_locks)) if series_locks else "",
        f"SHOT PURPOSE: {shot.narrative_function}",
        f"SUBJECT: {shot.subject}",
        f"ACTION: {shot.action}",
        f"LOCATION / ENVIRONMENT LOCK: {shot.environment}",
        f"COMPOSITION: {shot.composition}",
        f"LIGHT: {shot.lighting}",
        f"EMOTIONAL STATE: {shot.emotional_note}",
        f"MOTIF: {shot.motif}" if shot.motif else "",
        f"LYRIC INTENT ({shot.lyric_visual_strategy}): {shot.lyric_intent}" if shot.lyric_intent else "",
        f"WORLD RULE REFERENCES: {'; '.join(rule_summary)}" if rule_summary else "",
    ])
    motion_parts = _dedupe([
        f"SUBJECT MOTION: {shot.action}",
        f"PACE / STRENGTH: {shot.camera.movement_strength}",
        f"BEGINNING STATE: {'; '.join(shot.continuity_in)}" if shot.continuity_in else "",
        f"END STATE / TRANSITION: {'; '.join(shot.continuity_out)}" if shot.continuity_out else "",
        "Keep temporal change coherent; avoid simultaneous unrelated actions.",
    ])
    camera_parts = _dedupe([
        f"FRAMING: {shot.camera.framing}", f"LENS: {shot.camera.lens}",
        f"ANGLE: {shot.camera.angle}", f"CAMERA MOVEMENT: {shot.camera.movement or 'controlled'}",
        f"MOVEMENT STRENGTH: {shot.camera.movement_strength}", f"MANUAL PRESET: {preset}",
    ])
    negatives = _dedupe([*(bible.forbidden_elements if bible else []), *series_negatives, *shot.negative_constraints])

    warnings = shot_warnings(
        shot, session.story_beats, session.shots, bible.forbidden_elements if bible else [],
        lyric_line_ids=set(lyric_map), music_cue_ids={cue.cue_id for cue in session.mv_timeline},
        reference_ids=set(ref_map), world_rule_refs=set(world_rules), references=session.references,
    )
    for instruction in ref_instructions:
        if instruction.missing:
            warnings.append(f"Missing reference file: {instruction.reference_id} ({instruction.path})")
        if not instruction.eligible:
            warnings.append(f"Ineligible reference scope: {instruction.reference_id} ({instruction.scope})")
    missing_refs = [ref_id for ref_id in shot.reference_ids if ref_id not in ref_map]
    if missing_refs:
        warnings.append("Unknown reference IDs: " + ", ".join(missing_refs))
    for field_name in ("subject", "action", "environment"):
        if not getattr(shot, field_name).strip():
            warnings.append(f"Empty required prompt field: {field_name}")

    blockers: list[str] = []
    if not shot.beat_id or not any(beat.beat_id == shot.beat_id for beat in session.story_beats):
        blockers.append("Shot has no valid beat_id")
    if shot.end_sec <= shot.start_sec:
        blockers.append("Shot time range is invalid")
    if shot.generation_mode == "first_last":
        if not shot.first_frame_ref:
            blockers.append("first_last mode requires first_frame_ref")
        if not shot.last_frame_ref:
            blockers.append("first_last mode requires last_frame_ref")
    for label, frame_ref in (("first_frame_ref", shot.first_frame_ref), ("last_frame_ref", shot.last_frame_ref)):
        if not frame_ref:
            continue
        if frame_ref in ref_map:
            exists = resolve_reference_path(ref_map[frame_ref], session.project_dir).is_file()
        else:
            candidate = Path(frame_ref)
            if not candidate.is_absolute() and session.project_dir:
                candidate = session.project_dir / candidate
            exists = candidate.is_file()
        if not exists:
            warnings.append(f"Missing {label}: {frame_ref}")
    if shot.first_frame_ref and not profile.supports_first_frame and not profile.capabilities_model_dependent:
        warnings.append(f"{profile.display_name} does not advertise first-frame support")
    if shot.last_frame_ref and not profile.supports_last_frame and not profile.capabilities_model_dependent:
        warnings.append(f"{profile.display_name} does not advertise last-frame support")
    if shot.generation_mode not in profile.generation_mode_options and not profile.capabilities_model_dependent:
        warnings.append(f"Generation mode '{shot.generation_mode}' is not listed by {profile.display_name}")
    if profile.capabilities_model_dependent:
        warnings.append(
            "Higgsfield settings are model-dependent; verify duration, aspect ratio, resolution, "
            "first/last frame, negative prompt, and generation-mode support for the selected model."
        )
    warnings = _dedupe([*blockers, *series_warnings, *warnings])
    readiness = "BLOCKED" if blockers else "READY_WITH_WARNINGS" if warnings else "READY"

    duration_hint = generation_duration_hint if generation_duration_hint is not None else _nearest_duration(shot.duration_sec, profile.duration_options)
    aspect = aspect_ratio or (profile.aspect_ratio_options[0] if profile.aspect_ratio_options else "site default")
    resolution = resolution_hint or (profile.resolution_options[0] if profile.resolution_options else "site default")
    if duration_hint is not None:
        duration_checklist = f"Website Duration Hint: {duration_hint}s"
    elif profile.capabilities_model_dependent:
        duration_checklist = "Website Duration Hint: site / model dependent (verify manually)"
    else:
        duration_checklist = "Website Duration Hint: site default"
    checklist = [
        f"Site Profile: {profile.display_name}", f"Generation Mode: {shot.generation_mode}",
        f"Timeline Duration (do not overwrite): {shot.duration_sec:.2f}s",
        duration_checklist,
        f"Aspect Ratio: {aspect}", f"Resolution Hint: {resolution}", f"Camera Preset: {preset}",
        f"First Frame: {shot.first_frame_ref or '-'}", f"Last Frame: {shot.last_frame_ref or '-'}",
    ]
    main_prompt = "\n".join(main_parts)
    motion_prompt = "\n".join(motion_parts)
    camera_prompt = "\n".join(camera_parts)
    negative_prompt = "; ".join(negatives)
    reference_text = "\n".join(f"- {item.reference_id}: {item.instruction}\n  {item.path}" for item in ref_instructions) or "- No legacy reference files linked"
    series_reference_text = "\n".join(
        f"- {asset_id}: {path}" for asset_id, path in zip(series_asset_ids, series_asset_paths)
    ) or "- No approved Series Studio assets linked"
    full_text = "\n\n".join((
        f"MANUAL GENERATION PACK\nShot: {shot.shot_id}\nProfile: {profile.display_name}\nReadiness: {readiness}",
        "[MAIN PROMPT]\n" + main_prompt,
        "[MOTION PROMPT]\n" + motion_prompt,
        "[CAMERA PROMPT]\n" + camera_prompt,
        "[NEGATIVE PROMPT]\n" + (negative_prompt or "-"),
        "[REFERENCES]\n" + reference_text,
        "[SERIES ASSETS]\n" + series_reference_text,
        "[SETTINGS]\n" + "\n".join(checklist),
        "[WARNINGS]\n" + ("\n".join(f"- {warning}" for warning in warnings) or "- None"),
    ))
    return ManualGenerationPack(
        pack_id=pack_id or f"PACK-{shot.shot_id}-{uuid4().hex[:8].upper()}", shot_id=shot.shot_id,
        beat_id=shot.beat_id, profile_id=profile.profile_id,
        created_at=created_at or datetime.now(timezone.utc).isoformat(), generation_mode=shot.generation_mode,
        main_prompt=main_prompt, motion_prompt=motion_prompt, camera_prompt=camera_prompt,
        negative_prompt=negative_prompt, reference_instructions=ref_instructions,
        world_rule_summary=rule_summary,
        continuity_summary=_dedupe([*shot.continuity_in, *shot.continuity_out, *series_continuity]),
        series_episode_id=shot.series_episode_id,
        series_entity_ids=list(shot.series_entity_ids),
        series_variant_ids=list(shot.series_variant_ids),
        series_lock_summary=series_locks,
        series_asset_ids=series_asset_ids,
        series_asset_paths=series_asset_paths,
        first_frame_ref=shot.first_frame_ref, last_frame_ref=shot.last_frame_ref,
        duration_sec=shot.duration_sec, generation_duration_hint=duration_hint,
        aspect_ratio=aspect, resolution_hint=resolution, camera_preset_recommendation=preset,
        lyric_line_ids=list(shot.lyric_line_ids), music_cue_ids=list(shot.music_cue_ids),
        world_rule_refs=list(shot.world_rule_refs), reference_ids=list(shot.reference_ids),
        lyric_evidence=lyric_evidence, lyric_strategy=shot.lyric_visual_strategy,
        settings_checklist=checklist, readiness=readiness, warnings=warnings,
        full_clipboard_text=full_text,
    )


def safe_shot_filename(shot_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", shot_id).strip("._")
    return safe or "shot"


def export_manual_pack(pack: ManualGenerationPack, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.casefold() == ".json":
        content = json.dumps(pack.model_dump(mode="json"), ensure_ascii=False, indent=2)
    elif target.suffix.casefold() == ".txt":
        content = pack.full_clipboard_text
    else:
        raise ValueError("Manual pack export must use .txt or .json")
    target.write_text(content, encoding="utf-8")
    return target
