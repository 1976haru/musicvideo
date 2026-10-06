from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from .models import AudioMap, LyricInterpretation, LyricLine, MVTimelineCue
from .music_engine import analyze_audio, build_mv_timeline
from .optional_backends import beat_this_availability, functional_structure_availability


class MusicStructureSegment(BaseModel):
    segment_id: str
    label: Literal["intro", "verse", "pre_chorus", "chorus", "bridge", "outro", "other"]
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    confidence: float = Field(default=0.5, ge=0, le=1)
    source_backend: str

    @model_validator(mode="after")
    def valid_range(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("music structure end_sec must be greater than start_sec")
        return self


class EnhancedMusicStructure(BaseModel):
    backend: str
    backend_version: str = ""
    tempo_bpm: float = Field(default=0, ge=0)
    beats: list[float] = Field(default_factory=list)
    downbeats: list[float] = Field(default_factory=list)
    segments: list[MusicStructureSegment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_fingerprint: dict = Field(default_factory=dict)


class MusicBackend(Protocol):
    backend_id: str
    version: str

    def analyze(self, path: Path) -> EnhancedMusicStructure: ...


def basic_music_structure(path: str | Path, audio_map: AudioMap | None = None) -> EnhancedMusicStructure:
    path = Path(path).expanduser().resolve(strict=True)
    audio_map = audio_map or analyze_audio(path)
    stat = path.stat()
    return EnhancedMusicStructure(
        backend="LIBROSA_BASIC", backend_version="librosa-compatible-1.x",
        tempo_bpm=audio_map.tempo_bpm, beats=audio_map.beat_times_sec,
        warnings=["기본 분석은 Verse/Chorus 같은 기능적 구간을 확정하지 않습니다."],
        source_fingerprint={"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
    )


def analyze_music_intelligence(
    path: str | Path,
    backend: Literal["LIBROSA_BASIC", "BEAT_THIS", "FUNCTIONAL_STRUCTURE"] = "LIBROSA_BASIC",
    *,
    audio_map: AudioMap | None = None,
    adapter: MusicBackend | None = None,
) -> EnhancedMusicStructure:
    source = Path(path).expanduser().resolve(strict=True)
    if backend == "LIBROSA_BASIC":
        return basic_music_structure(source, audio_map)
    availability = beat_this_availability() if backend == "BEAT_THIS" else functional_structure_availability()
    if adapter is not None:
        return adapter.analyze(source)
    fallback = basic_music_structure(source, audio_map)
    fallback.warnings.append(
        f"{backend}: 선택 backend가 {availability.state} 상태이므로 기본 분석을 사용했습니다. "
        "모델을 자동 다운로드하지 않았습니다."
    )
    return fallback


def fuse_music_structure_timeline(
    audio_map: AudioMap,
    lyric_lines: list[LyricLine],
    lyric_analysis: LyricInterpretation | None,
    structure: EnhancedMusicStructure | None,
) -> list[MVTimelineCue]:
    cues = build_mv_timeline(audio_map, lyric_lines, lyric_analysis)
    if not structure or not structure.segments:
        return cues
    chorus_count = 0
    for segment in structure.segments:
        boundary = segment.start_sec
        nearby = [cue for cue in cues if abs(cue.time_sec - boundary) <= 2.0]
        overlapping_lines = [line.line_id for line in lyric_lines
                             if line.start_sec is not None and line.end_sec is not None
                             and line.start_sec - 0.5 <= boundary <= line.end_sec + 0.5]
        if nearby:
            target = max(nearby, key=lambda cue: cue.priority)
            evidence_bonus = 0.08 if overlapping_lines else 0.04
            target.priority = round(min(1.0, target.priority + evidence_bonus * segment.confidence), 3)
            target.reasons.append(f"functional_section={segment.label}")
            target.reasons.append(f"structure_backend={structure.backend}")
            target.lyric_line_ids = list(dict.fromkeys([*target.lyric_line_ids, *overlapping_lines]))
            continue
        phase = ""
        if segment.label == "chorus":
            chorus_count += 1
            phase = "setup" if chorus_count == 1 else "transformation" if chorus_count == 2 else "payoff"
        cues.append(MVTimelineCue(
            cue_id=f"FS{len(cues)+1:02d}", time_sec=round(boundary, 3),
            priority=round(min(0.9, 0.55 + segment.confidence * 0.25 + (0.08 if overlapping_lines else 0)), 3),
            cue_type="functional_structure",
            reasons=[f"functional_section={segment.label}", f"structure_backend={structure.backend}"] + ([f"motif_phase={phase}"] if phase else []),
            lyric_line_ids=overlapping_lines,
            recommended_visual_action=(
                f"{segment.label.replace('_', ' ').title()} 시작: "
                + (f"반복 이미지를 {phase} 단계로 발전시킬 후보" if phase else "장면의 서사 기능을 전환할 후보")
            ),
        ))
    return sorted(cues, key=lambda cue: (cue.time_sec, cue.cue_id))
