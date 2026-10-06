from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import os
import statistics
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from .models import AudioMap, LyricInterpretation, LyricLine, MVTimelineCue
from .music_engine import analyze_audio, build_mv_timeline
from .optional_backends import (
    beat_this_availability, clear_backend_load_failure, functional_structure_availability,
    mark_backend_load_failed,
)


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


def _version(distribution: str, module) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return str(getattr(module, "__version__", "unknown"))


def _numbers(value) -> list[float]:
    if value is None:
        return []
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return [round(float(item), 4) for item in value]


def _tempo_from_beats(beats: list[float]) -> float:
    intervals = [b - a for a, b in zip(beats, beats[1:]) if b > a]
    return round(60.0 / statistics.median(intervals), 2) if intervals else 0.0


def _fingerprint(path: Path) -> dict:
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


class BeatThisBackend:
    backend_id = "BEAT_THIS"

    def __init__(self, checkpoint_path: str | Path | None = None):
        configured = checkpoint_path or os.environ.get("MVSTUDIO_BEAT_THIS_CHECKPOINT")
        self.checkpoint_path = Path(configured).expanduser().resolve(strict=False) if configured else None
        self.version = ""

    def analyze(self, path: Path) -> EnhancedMusicStructure:
        # File2Beats defaults to a named remote checkpoint. Require a local path to prevent downloads.
        if self.checkpoint_path is None or not self.checkpoint_path.is_file():
            raise RuntimeError("Beat This 로컬 checkpoint가 설정되지 않았습니다. 자동 다운로드는 수행하지 않습니다.")
        inference = importlib.import_module("beat_this.inference")
        package = importlib.import_module("beat_this")
        runner_class = getattr(inference, "File2Beats", None)
        if runner_class is None:
            raise RuntimeError("설치된 Beat This API에서 File2Beats를 찾지 못했습니다.")
        runner = runner_class(checkpoint_path=str(self.checkpoint_path), device="cpu", float16=False)
        output = runner(str(path))
        if isinstance(output, dict):
            beat_value = output.get("beats") if output.get("beats") is not None else output.get("beat")
            downbeat_value = output.get("downbeats") if output.get("downbeats") is not None else output.get("downbeat")
            beats = _numbers(beat_value)
            downbeats = _numbers(downbeat_value)
            tempo = float(output.get("tempo_bpm") or output.get("tempo") or _tempo_from_beats(beats))
        elif isinstance(output, (tuple, list)) and len(output) == 2:
            beats, downbeats = _numbers(output[0]), _numbers(output[1])
            tempo = _tempo_from_beats(beats)
        else:
            raise RuntimeError("Beat This 결과 형식을 해석할 수 없습니다.")
        self.version = _version("beat-this", package)
        return EnhancedMusicStructure(
            backend=self.backend_id, backend_version=self.version, tempo_bpm=max(0, tempo),
            beats=beats, downbeats=downbeats, source_fingerprint=_fingerprint(path),
        )


_LABELS = {
    "intro": "intro", "introduction": "intro", "verse": "verse",
    "prechorus": "pre_chorus", "pre_chorus": "pre_chorus", "pre-chorus": "pre_chorus",
    "chorus": "chorus", "refrain": "chorus", "bridge": "bridge",
    "outro": "outro", "ending": "outro", "end": "outro",
}


def normalize_section_label(label: str) -> str:
    normalized = "_".join(str(label).strip().casefold().replace("-", " ").split())
    for key, value in _LABELS.items():
        if normalized == key or normalized.startswith(key + "_") or normalized.endswith("_" + key):
            return value
    return "other"


class FunctionalStructureBackend:
    backend_id = "FUNCTIONAL_STRUCTURE"

    def __init__(self, allow_model_load: bool = False):
        self.allow_model_load = allow_model_load
        self.version = ""

    def analyze(self, path: Path) -> EnhancedMusicStructure:
        if not self.allow_model_load:
            raise RuntimeError("고급 구조 모델 실행이 명시적으로 허용되지 않았습니다. 자동 모델 다운로드는 수행하지 않습니다.")
        module = importlib.import_module("allin1")
        analyze = getattr(module, "analyze", None)
        if not callable(analyze):
            raise RuntimeError("설치된 Functional Structure API에서 analyze()를 찾지 못했습니다.")
        kwargs = {}
        try:
            if "device" in inspect.signature(analyze).parameters:
                kwargs["device"] = "cpu"
        except (TypeError, ValueError):
            pass
        result = analyze(str(path), **kwargs)
        if isinstance(result, list):
            if len(result) != 1:
                raise RuntimeError("Functional Structure가 단일 파일 결과를 반환하지 않았습니다.")
            result = result[0]
        get = (lambda name, default=None: result.get(name, default)) if isinstance(result, dict) else (lambda name, default=None: getattr(result, name, default))
        beats = _numbers(get("beats"))
        downbeats = _numbers(get("downbeats"))
        tempo = float(get("bpm", get("tempo", _tempo_from_beats(beats))) or 0)
        raw_segments = get("segments", []) or []
        segments = []
        for index, raw in enumerate(raw_segments, 1):
            value = (lambda name, default=None: raw.get(name, default)) if isinstance(raw, dict) else (lambda name, default=None: getattr(raw, name, default))
            start, end = float(value("start", 0)), float(value("end", 0))
            if end <= start:
                raise RuntimeError("Functional Structure 구간 시간 범위가 올바르지 않습니다.")
            segments.append(MusicStructureSegment(
                segment_id=f"FS{index:03d}", label=normalize_section_label(value("label", "other")),
                start_sec=start, end_sec=end, confidence=float(value("confidence", 0.5) or 0.5),
                source_backend=self.backend_id,
            ))
        self.version = _version("all-in-one", module)
        return EnhancedMusicStructure(
            backend=self.backend_id, backend_version=self.version, tempo_bpm=max(0, tempo),
            beats=beats, downbeats=downbeats, segments=segments, source_fingerprint=_fingerprint(path),
        )


def get_music_backend(backend_id: str, *, options: dict | None = None) -> MusicBackend:
    options = options or {}
    functional_ready = options.get("allow_model_load")
    if functional_ready is None:
        functional_ready = os.environ.get("MVSTUDIO_FUNCTIONAL_STRUCTURE_READY") == "1"
    registry = {
        "BEAT_THIS": lambda: BeatThisBackend(options.get("checkpoint_path")),
        "FUNCTIONAL_STRUCTURE": lambda: FunctionalStructureBackend(bool(functional_ready)),
    }
    try:
        return registry[backend_id]()
    except KeyError as exc:
        raise ValueError(f"Unknown music backend: {backend_id}") from exc


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
    backend_options: dict | None = None,
) -> EnhancedMusicStructure:
    source = Path(path).expanduser().resolve(strict=True)
    if backend == "LIBROSA_BASIC":
        return basic_music_structure(source, audio_map)
    if adapter is not None:
        return adapter.analyze(source)
    availability = beat_this_availability() if backend == "BEAT_THIS" else functional_structure_availability()
    options = backend_options or {}
    retry_configured = (
        backend == "BEAT_THIS" and bool(options.get("checkpoint_path") or os.environ.get("MVSTUDIO_BEAT_THIS_CHECKPOINT"))
    ) or (
        backend == "FUNCTIONAL_STRUCTURE"
        and bool(options.get("allow_model_load") or os.environ.get("MVSTUDIO_FUNCTIONAL_STRUCTURE_READY") == "1")
    )
    if availability.state == "AVAILABLE" or (availability.state == "LOAD_FAILED" and retry_configured):
        try:
            result = get_music_backend(backend, options=backend_options).analyze(source)
            clear_backend_load_failure(backend)
            return result
        except Exception as exc:
            mark_backend_load_failed(backend, str(exc))
            availability = beat_this_availability() if backend == "BEAT_THIS" else functional_structure_availability()
    fallback = basic_music_structure(source, audio_map)
    message = (
        "고급 분석을 불러오지 못했습니다. 기본 분석을 사용할 수 있습니다."
        if availability.state == "LOAD_FAILED"
        else "고급 분석 구성요소가 설치되어 있지 않습니다. 기본 분석을 사용했습니다."
    )
    fallback.warnings.append(f"{backend}: {message} 모델을 자동 다운로드하지 않았습니다.")
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
