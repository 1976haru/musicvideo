from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .models import (
    CameraSpec, LyricLine, LyricVisualBridge, MVTimelineCue, ReferenceAsset,
    ReferenceScope, ShotSpec, StoryBeat,
)


@dataclass(frozen=True)
class TimelineWarning:
    code: str
    message: str
    item_ids: tuple[str, ...] = ()


def _next_numeric_id(prefix: str, existing_ids: set[str], width: int) -> str:
    number = 1
    while f"{prefix}{number:0{width}d}" in existing_ids:
        number += 1
    return f"{prefix}{number:0{width}d}"


def next_beat_id(existing_ids: set[str] | list[str]) -> str:
    return _next_numeric_id("B", set(existing_ids), 3)


def next_shot_id(beat_id: str, existing_ids: set[str] | list[str]) -> str:
    return _next_numeric_id(f"{beat_id}-S", set(existing_ids), 2)


def duplicate_id_warnings(beats: list[StoryBeat], shots: list[ShotSpec]) -> list[TimelineWarning]:
    warnings: list[TimelineWarning] = []
    for code, label, ids in (
        ("duplicate_beat_id", "Story Beat", [item.beat_id for item in beats]),
        ("duplicate_shot_id", "Shot", [item.shot_id for item in shots]),
    ):
        for item_id, count in Counter(ids).items():
            if count > 1:
                warnings.append(TimelineWarning(code, f"Duplicate {label} ID: {item_id} ({count})", (item_id,)))
    return warnings


def _normalized_tokens(values: list[str]) -> set[str]:
    return {" ".join(value.split()).casefold() for value in values if value.strip()}


def cinematic_warnings(shots: list[ShotSpec], run_length: int = 3) -> list[TimelineWarning]:
    warnings: list[TimelineWarning] = []
    ordered = sorted(shots, key=lambda shot: (shot.start_sec, shot.end_sec, shot.shot_id))
    signatures = [tuple(" ".join(value.split()).casefold() for value in (
        shot.camera.framing, shot.camera.lens, shot.camera.angle,
        shot.camera.movement, shot.camera.movement_strength,
    )) for shot in ordered]
    for end in range(run_length - 1, len(ordered)):
        if len(set(signatures[end-run_length+1:end+1])) == 1:
            ids = tuple(shot.shot_id for shot in ordered[end-run_length+1:end+1])
            warnings.append(TimelineWarning("repeated_camera", f"Repeated camera treatment across {', '.join(ids)}", ids))
    return warnings


def literalization_warnings(shots: list[ShotSpec], lyric_text_by_id: dict[str, str] | None = None, run_length: int = 3) -> list[TimelineWarning]:
    warnings: list[TimelineWarning] = []
    ordered = sorted(shots, key=lambda shot: (shot.start_sec, shot.end_sec, shot.shot_id))
    flags: list[bool] = []
    for shot in ordered:
        one_line = len(set(shot.lyric_line_ids)) == 1
        literal = shot.lyric_visual_strategy == "literal"
        duplicate = False
        if lyric_text_by_id and one_line:
            lyric = " ".join(lyric_text_by_id.get(shot.lyric_line_ids[0], "").split()).casefold()
            visual = " ".join(f"{shot.action} {shot.environment}".split()).casefold()
            lyric_tokens = {token for token in lyric.split() if len(token) >= 2}
            duplicate = bool(lyric_tokens) and len(lyric_tokens & set(visual.split())) / len(lyric_tokens) >= 0.8
        flags.append(one_line and literal and (duplicate or not lyric_text_by_id))
    for end in range(run_length - 1, len(ordered)):
        if all(flags[end-run_length+1:end+1]):
            ids = tuple(shot.shot_id for shot in ordered[end-run_length+1:end+1])
            warnings.append(TimelineWarning("literalization", f"Consecutive one-line literal shots may flatten narrative progression: {', '.join(ids)}", ids))
    return warnings


def reference_is_eligible(asset: ReferenceAsset, shot: ShotSpec) -> bool:
    """G3 policy: StoryBeat is the temporary scene-scope unit."""
    if asset.applies_to == ReferenceScope.PROJECT:
        return True
    if asset.applies_to == ReferenceScope.SCENE:
        return bool(shot.beat_id and asset.scope_id == shot.beat_id)
    return asset.scope_id == shot.shot_id


def _duration(lines: list[LyricLine], cues: list[MVTimelineCue], duration_sec: float | None) -> float:
    if duration_sec and duration_sec > 0:
        return duration_sec
    line_end = max((line.end_sec or 0 for line in lines), default=0)
    cue_end = max((cue.time_sec for cue in cues), default=0)
    return max(line_end, cue_end, 1.0)


def draft_story_beats(
    lines: list[LyricLine],
    cues: list[MVTimelineCue],
    duration_sec: float | None,
    *,
    motif_pool: list[str] | None = None,
    emotional_arc: list[str] | None = None,
    world_rule_refs: list[str] | None = None,
    bridges: list[LyricVisualBridge] | None = None,
) -> list[StoryBeat]:
    """Draft a small number of narrative units, grouping lines instead of mapping 1:1."""
    duration = _duration(lines, cues, duration_sec)
    valid_lines = sorted(
        (line for line in lines if line.start_sec is not None and line.end_sec is not None),
        key=lambda line: (line.start_sec, line.end_sec, line.line_id),
    )
    if not valid_lines:
        return []

    # Prefer groups of 2–4 lines. Strong cue boundaries and repeated lines can split a group.
    repeated = Counter(line.text.strip() for line in valid_lines if line.text.strip())
    boundaries = {0, len(valid_lines)}
    for idx in range(4, len(valid_lines), 4):
        boundaries.add(idx)
    for idx, line in enumerate(valid_lines):
        if idx and repeated[line.text.strip()] > 1:
            boundaries.add(idx)
        if idx and line.section and valid_lines[idx - 1].section != line.section:
            boundaries.add(idx)
    for cue in cues:
        if cue.priority >= 0.78:
            nearest = min(range(len(valid_lines)), key=lambda i: abs(valid_lines[i].start_sec - cue.time_sec))
            if nearest not in (0, len(valid_lines)):
                boundaries.add(nearest)
    points = sorted(boundaries)
    groups = [(valid_lines[a:b]) for a, b in zip(points, points[1:]) if a < b]
    if not groups:
        groups = [valid_lines]
    grouped: list[list[LyricLine]] = []
    index = 0
    while index < len(groups):
        group = groups[index]
        if len(group) == 1 and index + 1 < len(groups):
            group = [*group, *groups[index + 1]]
            index += 1
        if len(group) == 1 and grouped:
            grouped[-1].extend(group)
        else:
            grouped.append(group)
        index += 1
    groups = grouped

    motifs = motif_pool or []
    motif_counts: Counter[str] = Counter()
    result: list[StoryBeat] = []
    cursor = 0.0
    for index, group in enumerate(groups, start=1):
        start = max(cursor, min(line.start_sec for line in group) or 0.0)
        next_start = groups[index][0].start_sec if index < len(groups) else duration
        end = max(start + 0.1, min(duration, max(max(line.end_sec or start for line in group), next_start or duration)))
        if end <= start:
            end = min(duration, start + max(0.25, duration / len(groups)))
        cursor = end
        line_ids = [line.line_id for line in group]
        group_cues = [cue for cue in cues if start <= cue.time_sec < end]
        group_ids = set(line_ids)
        bridge_intents = [bridge.lyric_intent for bridge in (bridges or []) if group_ids.intersection(bridge.source_line_ids)]
        group_text = " ".join(line.text for line in group)
        matching_motifs = [value for value in motifs if value and value in group_text]
        motif = matching_motifs[0] if matching_motifs else None
        phase = "none"
        if motif:
            motif_counts[motif] += 1
            phase = {1: "setup", 2: "development"}.get(motif_counts[motif], "payoff")
        arc = emotional_arc or []
        emotional_state = arc[min(len(arc) - 1, round((index - 1) * max(0, len(arc) - 1) / max(1, len(groups) - 1)))] if arc else ""
        result.append(StoryBeat(
            beat_id=f"B{index:03d}",
            start_sec=round(start, 3),
            end_sec=round(end, 3),
            dramatic_question=f"이 구간에서 무엇이 달라질까? ({', '.join(line_ids)})",
            change="감정과 인물의 선택이 다음 상태로 이동한다.",
            visual_event="한 가지 행동과 시각 변화를 중심으로 장면을 설계한다.",
            motif=motif,
            setup_or_payoff=phase,
            lyric_line_ids=line_ids,
            music_cue_ids=[cue.cue_id for cue in group_cues],
            lyric_intent=" / ".join(dict.fromkeys(bridge_intents or [line.text for line in group])),
            emotional_state=emotional_state,
            world_rule_refs=list(world_rule_refs or []),
            notes="자동 초안 · 연출 의도에 맞게 편집하세요.",
        ))
    if result:
        result[0].start_sec = 0.0
        result[-1].end_sec = duration
    return result


def timeline_warnings(beats: list[StoryBeat], duration_sec: float | None, tolerance: float = 0.05) -> list[TimelineWarning]:
    warnings: list[TimelineWarning] = []
    ordered = sorted(beats, key=lambda beat: (beat.start_sec, beat.end_sec, beat.beat_id))
    duration = duration_sec or (ordered[-1].end_sec if ordered else 0)
    if not ordered:
        return warnings
    if ordered[0].start_sec > tolerance:
        warnings.append(TimelineWarning("leading_gap", f"Timeline 시작 전 {ordered[0].start_sec:.2f}s 빈 구간", (ordered[0].beat_id,)))
    for previous, current in zip(ordered, ordered[1:]):
        delta = current.start_sec - previous.end_sec
        if delta > tolerance:
            warnings.append(TimelineWarning("gap", f"{previous.beat_id}–{current.beat_id} 사이 {delta:.2f}s 빈 구간", (previous.beat_id, current.beat_id)))
        elif delta < -tolerance:
            warnings.append(TimelineWarning("overlap", f"{previous.beat_id}와 {current.beat_id}가 {abs(delta):.2f}s 겹침", (previous.beat_id, current.beat_id)))
    if duration and duration - ordered[-1].end_sec > tolerance:
        warnings.append(TimelineWarning("trailing_gap", f"Timeline 끝에 {duration - ordered[-1].end_sec:.2f}s 빈 구간", (ordered[-1].beat_id,)))
    return warnings


def beat_traceability_warnings(
    beat: StoryBeat,
    lyric_line_ids: set[str],
    music_cue_ids: set[str],
    reference_ids: set[str],
    world_rule_refs: set[str],
) -> list[str]:
    warnings: list[str] = []
    for label, values, known in (
        ("Lyric Line ID", beat.lyric_line_ids, lyric_line_ids),
        ("Music Cue ID", beat.music_cue_ids, music_cue_ids),
        ("Reference ID", beat.reference_ids, reference_ids),
        ("World rule ref", beat.world_rule_refs, world_rule_refs),
    ):
        missing = [value for value in values if value not in known]
        if missing:
            warnings.append(f"연결 대상이 없는 {label}: {', '.join(missing)}")
    return warnings


def shot_timeline_warnings(beats: list[StoryBeat], shots: list[ShotSpec], tolerance: float = 0.05) -> list[TimelineWarning]:
    warnings: list[TimelineWarning] = []
    beat_map = {beat.beat_id: beat for beat in beats}
    for shot in shots:
        beat = beat_map.get(shot.beat_id or "")
        if beat is None:
            warnings.append(TimelineWarning("invalid_beat_id", f"{shot.shot_id}: missing/invalid beat_id {shot.beat_id or '-'}", (shot.shot_id,)))
        elif shot.start_sec < beat.start_sec - tolerance or shot.end_sec > beat.end_sec + tolerance:
            warnings.append(TimelineWarning("outside_beat", f"{shot.shot_id} [{shot.start_sec:.2f}, {shot.end_sec:.2f}] outside {beat.beat_id} [{beat.start_sec:.2f}, {beat.end_sec:.2f}]", (shot.shot_id, beat.beat_id)))
    for beat in beats:
        ordered = sorted((shot for shot in shots if shot.beat_id == beat.beat_id), key=lambda shot: (shot.start_sec, shot.end_sec, shot.shot_id))
        if not ordered:
            continue
        if ordered[0].start_sec - beat.start_sec > tolerance:
            warnings.append(TimelineWarning("shot_leading_gap", f"{beat.beat_id}: leading gap [{beat.start_sec:.2f}, {ordered[0].start_sec:.2f}]", (beat.beat_id, ordered[0].shot_id)))
        for previous, current in zip(ordered, ordered[1:]):
            delta = current.start_sec - previous.end_sec
            if delta > tolerance:
                warnings.append(TimelineWarning("shot_gap", f"{beat.beat_id}: gap [{previous.end_sec:.2f}, {current.start_sec:.2f}] between {previous.shot_id} and {current.shot_id}", (previous.shot_id, current.shot_id)))
            elif delta < -tolerance:
                warnings.append(TimelineWarning("shot_overlap", f"{beat.beat_id}: overlap [{current.start_sec:.2f}, {previous.end_sec:.2f}] between {previous.shot_id} and {current.shot_id}", (previous.shot_id, current.shot_id)))
        if beat.end_sec - ordered[-1].end_sec > tolerance:
            warnings.append(TimelineWarning("shot_trailing_gap", f"{beat.beat_id}: trailing gap [{ordered[-1].end_sec:.2f}, {beat.end_sec:.2f}]", (ordered[-1].shot_id, beat.beat_id)))
    return warnings


def motif_progression_warnings(beats: list[StoryBeat]) -> list[TimelineWarning]:
    warnings: list[TimelineWarning] = []
    by_motif: dict[str, list[StoryBeat]] = {}
    for beat in sorted(beats, key=lambda item: (item.start_sec, item.end_sec, item.beat_id)):
        if beat.motif and beat.motif.strip():
            by_motif.setdefault(beat.motif.strip().casefold(), []).append(beat)
    for motif, occurrences in by_motif.items():
        seen_setup = False
        setup_run = 0
        for beat in occurrences:
            phase = beat.setup_or_payoff
            if phase == "setup":
                setup_run += 1
                seen_setup = True
                if setup_run >= 2:
                    warnings.append(TimelineWarning("repeated_setup", f"Motif '{motif}' repeats SETUP without development at {beat.beat_id}", (beat.beat_id,)))
            else:
                setup_run = 0
            if phase in {"development", "payoff"} and not seen_setup:
                warnings.append(TimelineWarning(f"{phase}_before_setup", f"Motif '{motif}' has {phase.upper()} before SETUP at {beat.beat_id}", (beat.beat_id,)))
        phases = {beat.setup_or_payoff for beat in occurrences}
        if "setup" in phases and not ({"development", "payoff"} & phases):
            warnings.append(TimelineWarning("unresolved_motif", f"Motif '{motif}' is introduced but never developed or paid off", tuple(beat.beat_id for beat in occurrences)))
    return warnings


def draft_shot(beat: StoryBeat, ordinal: int = 1) -> ShotSpec:
    return ShotSpec(
        shot_id=f"{beat.beat_id}-S{ordinal:02d}", beat_id=beat.beat_id,
        start_sec=beat.start_sec, end_sec=beat.end_sec,
        narrative_function=beat.dramatic_question,
        lyric_or_music_cue=beat.lyric_intent,
        lyric_line_ids=list(beat.lyric_line_ids), music_cue_ids=list(beat.music_cue_ids),
        lyric_intent=beat.lyric_intent,
        lyric_visual_strategy="motif" if beat.motif else "metaphor",
        subject="주인공 또는 핵심 오브젝트", action=beat.visual_event,
        environment="World Bible의 장소 규칙을 따르는 공간",
        composition="주요 행동이 한눈에 읽히는 단일 구도",
        camera=CameraSpec(framing="medium", lens="50mm", angle="eye-level", movement="subtle push-in", movement_strength="subtle"),
        lighting="World Bible 조명 규칙을 따른다.", emotional_note=beat.emotional_state or beat.change,
        motif=beat.motif, reference_ids=list(beat.reference_ids), world_rule_refs=list(beat.world_rule_refs),
        negative_constraints=[],
    )


def shot_warnings(
    shot: ShotSpec,
    beats: list[StoryBeat],
    shots: list[ShotSpec],
    forbidden_elements: list[str],
    *,
    lyric_line_ids: set[str] | None = None,
    music_cue_ids: set[str] | None = None,
    reference_ids: set[str] | None = None,
    world_rule_refs: set[str] | None = None,
    references: list[ReferenceAsset] | None = None,
    short_duration_sec: float = 1.2,
    long_duration_sec: float = 12.0,
) -> list[str]:
    warnings: list[str] = []
    fields = " ".join([
        shot.subject, shot.action, shot.environment, shot.composition, shot.lighting,
        shot.emotional_note, shot.camera.framing, shot.camera.angle, shot.camera.movement,
        *shot.negative_constraints,
    ])
    for forbidden in forbidden_elements:
        token = forbidden.strip()
        if token and token.casefold() in fields.casefold():
            warnings.append(f"World Bible 금지 요소 문구와 일치: {token}")
    if shot.start_sec < 0 or shot.end_sec <= shot.start_sec:
        warnings.append("Shot 시간 범위가 올바르지 않습니다.")
    linked_beat = next((beat for beat in beats if beat.beat_id == shot.beat_id), None)
    if shot.beat_id and linked_beat is None:
        warnings.append(f"연결된 Story Beat를 찾을 수 없습니다: {shot.beat_id}")
    elif linked_beat and (shot.start_sec < linked_beat.start_sec or shot.end_sec > linked_beat.end_sec):
        warnings.append("Shot 시간 범위가 연결된 Story Beat 범위를 벗어납니다.")
    for label, values, known in (
        ("Lyric Line ID", shot.lyric_line_ids, lyric_line_ids),
        ("Music Cue ID", shot.music_cue_ids, music_cue_ids),
        ("Reference ID", shot.reference_ids, reference_ids),
        ("World rule ref", shot.world_rule_refs, world_rule_refs),
    ):
        if known is not None:
            missing = [value for value in values if value not in known]
            if missing:
                warnings.append(f"연결 대상이 없는 {label}: {', '.join(missing)}")
    if linked_beat:
        extra_lines = sorted(set(shot.lyric_line_ids) - set(linked_beat.lyric_line_ids))
        extra_cues = sorted(set(shot.music_cue_ids) - set(linked_beat.music_cue_ids))
        if extra_lines:
            warnings.append(f"Shot lyric evidence is not a subset of {linked_beat.beat_id}: {', '.join(extra_lines)}")
        if extra_cues:
            warnings.append(f"Shot music evidence is not a subset of {linked_beat.beat_id}: {', '.join(extra_cues)}")
    if references is not None:
        asset_map = {asset.reference_id: asset for asset in references}
        ineligible = [ref_id for ref_id in shot.reference_ids if ref_id in asset_map and not reference_is_eligible(asset_map[ref_id], shot)]
        if ineligible:
            warnings.append(f"Reference scope is ineligible for {shot.shot_id}: {', '.join(ineligible)}")
    if shot.duration_sec < short_duration_sec:
        warnings.append(f"Shot duration is very short: {shot.duration_sec:.2f}s (< {short_duration_sec:.2f}s)")
    elif shot.duration_sec > long_duration_sec:
        warnings.append(f"Shot duration is long: {shot.duration_sec:.2f}s (> {long_duration_sec:.2f}s)")
    ordered = sorted((item for item in shots if item.beat_id == shot.beat_id), key=lambda item: item.start_sec)
    index = next((i for i, item in enumerate(ordered) if item.shot_id == shot.shot_id), -1)
    if index > 0:
        prior = _normalized_tokens(ordered[index - 1].continuity_out)
        current = _normalized_tokens(shot.continuity_in)
        if prior != current and (prior or current):
            if prior - current:
                warnings.append("continuity missing expected carry-over: " + ", ".join(sorted(prior - current)))
            if current - prior:
                warnings.append("continuity unexpected changed token: " + ", ".join(sorted(current - prior)))
            warnings.append("앞 Shot의 continuity_out과 이 Shot의 continuity_in이 다릅니다.")
    if 0 <= index < len(ordered) - 1:
        current = _normalized_tokens(shot.continuity_out)
        following = _normalized_tokens(ordered[index + 1].continuity_in)
        if current != following and (current or following):
            if current - following:
                warnings.append("continuity missing expected carry-over: " + ", ".join(sorted(current - following)))
            if following - current:
                warnings.append("continuity unexpected changed token: " + ", ".join(sorted(following - current)))
            warnings.append("이 Shot의 continuity_out과 다음 Shot의 continuity_in이 다릅니다.")
    return warnings
