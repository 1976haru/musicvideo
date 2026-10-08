from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import math
import os
import tempfile

import numpy as np

from .models import (
    AudioMap,
    AudioSection,
    AudioTransition,
    LyricInterpretation,
    LyricLine,
    MVTimelineCue,
)


class MusicAnalysisError(RuntimeError):
    pass


def _librosa():
    # Numba otherwise tries to create caches beside installed librosa modules.
    # That location can be read-only (packaged app) or extremely slow on Windows.
    cache_root = Path(os.environ.get("MVSTUDIO_APPDATA", tempfile.gettempdir())) / "cache" / "numba"
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(cache_root))
    try:
        import librosa
    except ImportError as exc:
        raise MusicAnalysisError(
            "음악 분석 기능에는 librosa가 필요합니다. `pip install -e .[music]` 후 다시 실행하세요."
        ) from exc
    return librosa


def _zscore(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return values
    std = float(np.nanstd(values))
    if std < 1e-9:
        return np.zeros_like(values)
    return (values - float(np.nanmean(values))) / std


def _minmax(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return values
    lo, hi = float(np.nanmin(values)), float(np.nanmax(values))
    if hi - lo < 1e-9:
        return np.zeros_like(values)
    return (values - lo) / (hi - lo)


def _smooth(values: np.ndarray, width: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.size == 0 or width <= 1:
        return values
    width = max(1, min(int(width), values.size))
    kernel = np.ones(width, dtype=float) / width
    return np.convolve(values, kernel, mode="same")


def _pick_peaks(
    scores: np.ndarray,
    times: np.ndarray,
    *,
    min_gap_sec: float,
    max_peaks: int,
    min_time: float,
    max_time: float,
) -> list[int]:
    if len(scores) < 3:
        return []
    candidates = [
        i
        for i in range(1, len(scores) - 1)
        if scores[i] >= scores[i - 1]
        and scores[i] > scores[i + 1]
        and min_time <= float(times[i]) <= max_time
    ]
    candidates.sort(key=lambda i: float(scores[i]), reverse=True)
    selected: list[int] = []
    for idx in candidates:
        t = float(times[idx])
        if all(abs(t - float(times[j])) >= min_gap_sec for j in selected):
            selected.append(idx)
            if len(selected) >= max_peaks:
                break
    return sorted(selected, key=lambda i: float(times[i]))


def _nearest_value(times: np.ndarray, values: np.ndarray, target: float) -> float:
    if len(times) == 0 or len(values) == 0:
        return 0.0
    idx = int(np.argmin(np.abs(times - target)))
    idx = min(idx, len(values) - 1)
    return float(values[idx])


def _section_label(index: int, total: int) -> str:
    if index == 0:
        return "intro_candidate"
    if index == total - 1:
        return "outro_candidate"
    return "section_candidate"


def analyze_audio(
    audio_path: str | Path,
    *,
    analysis_sr: int = 22050,
    hop_length: int = 512,
    max_transitions: int = 14,
    min_transition_gap_sec: float = 4.0,
) -> AudioMap:
    """Analyze a song for director-oriented timing cues.

    This does not claim to identify semantic labels like Verse/Chorus from audio alone.
    It detects musically meaningful *change candidates* that the user/LLM can later label.
    """
    librosa = _librosa()
    path = Path(audio_path)
    if not path.exists():
        raise MusicAnalysisError(f"음악 파일을 찾을 수 없습니다: {path}")

    try:
        y, sr = librosa.load(path, sr=analysis_sr, mono=True)
    except Exception as exc:
        raise MusicAnalysisError(f"음악 파일을 읽지 못했습니다: {exc}") from exc

    if y is None or len(y) < sr:
        raise MusicAnalysisError("분석하려면 최소 1초 이상의 음악이 필요합니다.")

    duration = float(librosa.get_duration(y=y, sr=sr))

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    onset_times = librosa.times_like(onset_env, sr=sr, hop_length=hop_length)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=hop_length,
        backtrack=False,
        units="frames",
    )
    onset_event_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)

    tempo_value, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=hop_length,
        units="frames",
    )
    tempo = float(np.atleast_1d(tempo_value)[0]) if np.size(tempo_value) else 0.0
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)

    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop_length)[0]

    n = min(len(onset_env), len(rms), len(centroid), len(bandwidth))
    onset_env = onset_env[:n]
    rms = rms[:n]
    centroid = centroid[:n]
    bandwidth = bandwidth[:n]
    times = librosa.frames_to_time(np.arange(n), sr=sr, hop_length=hop_length)

    # Smooth over roughly 0.75 seconds. Change score compares both energy and timbre movement.
    smooth_frames = max(3, int(0.75 * sr / hop_length))
    rms_s = _smooth(rms, smooth_frames)
    centroid_s = _smooth(centroid, smooth_frames)
    bandwidth_s = _smooth(bandwidth, smooth_frames)
    onset_s = _smooth(onset_env, max(3, smooth_frames // 2))

    delta_rms = np.abs(np.diff(_zscore(rms_s), prepend=0.0))
    delta_centroid = np.abs(np.diff(_zscore(centroid_s), prepend=0.0))
    delta_bandwidth = np.abs(np.diff(_zscore(bandwidth_s), prepend=0.0))
    onset_component = _minmax(onset_s)

    novelty = (
        0.42 * _minmax(delta_rms)
        + 0.28 * _minmax(delta_centroid)
        + 0.15 * _minmax(delta_bandwidth)
        + 0.15 * onset_component
    )
    novelty = _smooth(novelty, max(3, int(0.5 * sr / hop_length)))

    peak_indices = _pick_peaks(
        novelty,
        times,
        min_gap_sec=min_transition_gap_sec,
        max_peaks=max_transitions,
        min_time=2.0,
        max_time=max(2.0, duration - 2.0),
    )

    transitions: list[AudioTransition] = []
    for i, idx in enumerate(peak_indices, 1):
        t = float(times[idx])
        score = float(np.clip(novelty[idx], 0.0, 1.0))
        # infer direction using local RMS around transition
        before = _nearest_value(times, rms_s, max(0.0, t - 1.2))
        after = _nearest_value(times, rms_s, min(duration, t + 1.2))
        if after > before * 1.15:
            character = "energy_rise"
        elif before > after * 1.15:
            character = "energy_drop"
        else:
            character = "texture_or_rhythm_change"
        transitions.append(
            AudioTransition(
                transition_id=f"AT{i:02d}",
                time_sec=round(t, 3),
                strength=round(score, 3),
                character=character,
                reasons=[
                    "audio_novelty_peak",
                    f"rms_delta={abs(after-before):.4f}",
                ],
            )
        )

    boundaries = [0.0] + [x.time_sec for x in transitions] + [round(duration, 3)]
    # Remove accidental near-duplicates and too-short sections.
    clean = [boundaries[0]]
    for b in boundaries[1:]:
        if b - clean[-1] >= 2.0 or math.isclose(b, duration, abs_tol=0.05):
            clean.append(b)
    if clean[-1] < duration - 0.05:
        clean.append(round(duration, 3))

    sections: list[AudioSection] = []
    for i in range(len(clean) - 1):
        start, end = clean[i], clean[i + 1]
        mask = (times >= start) & (times < end)
        energy = float(np.mean(rms_s[mask])) if np.any(mask) else 0.0
        sections.append(
            AudioSection(
                section_id=f"AS{i+1:02d}",
                label=_section_label(i, len(clean) - 1),
                start_sec=round(float(start), 3),
                end_sec=round(float(end), 3),
                mean_energy=round(energy, 5),
                confidence=0.55 if i not in {0, len(clean)-2} else 0.45,
            )
        )

    # director-friendly cadence, not an auto-cut mandate
    if tempo > 1:
        beat_sec = 60.0 / tempo
        cadence = {
            "4_beats_sec": round(beat_sec * 4, 3),
            "8_beats_sec": round(beat_sec * 8, 3),
            "16_beats_sec": round(beat_sec * 16, 3),
        }
    else:
        cadence = {}

    return AudioMap(
        source_path=str(path),
        duration_sec=round(duration, 3),
        sample_rate=int(sr),
        tempo_bpm=round(tempo, 2),
        beat_times_sec=[round(float(x), 3) for x in beat_times.tolist()],
        onset_times_sec=[round(float(x), 3) for x in onset_event_times.tolist()],
        transitions=transitions,
        sections=sections,
        cut_cadence_hints=cadence,
        analysis_notes=[
            "Audio section labels are candidates, not semantic Verse/Chorus claims.",
            "Use lyric repetition, user labels, or an LLM/music-structure model to assign semantic section names.",
            "Transition strength is for directing/editing priority, not a command to cut at every peak.",
        ],
    )


def _lyric_midpoint(line: LyricLine) -> float | None:
    if line.start_sec is None:
        return None
    if line.end_sec is None:
        return float(line.start_sec)
    return (float(line.start_sec) + float(line.end_sec)) / 2.0


def _nearest_transition(audio_map: AudioMap, t: float, window_sec: float = 2.0) -> AudioTransition | None:
    candidates = [x for x in audio_map.transitions if abs(x.time_sec - t) <= window_sec]
    return min(candidates, key=lambda x: abs(x.time_sec - t)) if candidates else None


def build_mv_timeline(
    audio_map: AudioMap,
    lyric_lines: list[LyricLine],
    lyric_analysis: LyricInterpretation | None = None,
) -> list[MVTimelineCue]:
    """Fuse musical transitions and lyric events into director-priority timeline cues."""
    cues: list[MVTimelineCue] = []

    # 1) Musical transitions are always candidates.
    for i, tr in enumerate(audio_map.transitions, 1):
        overlapping = [
            line.line_id
            for line in lyric_lines
            if line.start_sec is not None
            and line.end_sec is not None
            and line.start_sec - 0.6 <= tr.time_sec <= line.end_sec + 0.6
        ]
        strength = min(1.0, 0.55 + tr.strength * 0.4 + (0.08 if overlapping else 0.0))
        action = {
            "energy_rise": "카메라 이동/공간 확장/행동 강도를 한 단계 올릴 후보",
            "energy_drop": "컷을 비우거나 정지·클로즈업·여운으로 전환할 후보",
        }.get(tr.character, "장면/구도/모티프 상태를 바꿀 후보")
        cues.append(
            MVTimelineCue(
                cue_id=f"MC{i:02d}",
                time_sec=tr.time_sec,
                priority=round(strength, 3),
                cue_type="music_transition",
                reasons=[tr.character, *tr.reasons],
                lyric_line_ids=overlapping,
                recommended_visual_action=action,
            )
        )

    # 2) Lyric repetition/chorus-like returns get their own semantic cues.
    repeated = set(lyric_analysis.repeated_phrases if lyric_analysis else [])
    if repeated:
        seen: dict[str, int] = {}
        for line in lyric_lines:
            normalized = " ".join(line.text.lower().split())
            if normalized not in repeated:
                continue
            t = _lyric_midpoint(line)
            if t is None:
                continue
            seen[normalized] = seen.get(normalized, 0) + 1
            occurrence = seen[normalized]
            nearby = _nearest_transition(audio_map, t)
            priority = 0.78 + (0.1 if nearby else 0.0) + min(0.08, occurrence * 0.02)
            phase = "setup" if occurrence == 1 else "transformation" if occurrence == 2 else "payoff"
            cues.append(
                MVTimelineCue(
                    cue_id=f"LC{len(cues)+1:02d}",
                    time_sec=round(t, 3),
                    priority=round(min(priority, 1.0), 3),
                    cue_type="lyric_return",
                    reasons=[f"repeated_lyric_occurrence={occurrence}", f"motif_phase={phase}"],
                    lyric_line_ids=[line.line_id],
                    recommended_visual_action=(
                        f"같은 가사를 같은 그림으로 반복하지 말고 motif의 {phase} 단계로 의미를 발전시킬 후보"
                    ),
                )
            )

    # 3) First/last lyric anchors can be important narrative hinges.
    timed = [x for x in lyric_lines if x.start_sec is not None]
    if timed:
        for line, kind, priority, action in [
            (timed[0], "lyric_entry", 0.72, "첫 가사 진입: 세계/주인공/핵심 질문을 명료하게 제시할 후보"),
            (timed[-1], "lyric_exit", 0.82, "마지막 가사: 초반 motif를 회수하거나 결말 이미지를 잠글 후보"),
        ]:
            t = float(line.start_sec if kind == "lyric_entry" else (line.end_sec or line.start_sec))
            cues.append(
                MVTimelineCue(
                    cue_id=f"LX{len(cues)+1:02d}",
                    time_sec=round(t, 3),
                    priority=priority,
                    cue_type=kind,
                    reasons=["narrative_boundary"],
                    lyric_line_ids=[line.line_id],
                    recommended_visual_action=action,
                )
            )

    # Merge cues within 0.75 sec, preserving lyric evidence and strongest priority.
    cues.sort(key=lambda x: x.time_sec)
    merged: list[MVTimelineCue] = []
    for cue in cues:
        if merged and abs(cue.time_sec - merged[-1].time_sec) <= 0.75:
            prev = merged[-1]
            prev.priority = round(max(prev.priority, cue.priority), 3)
            prev.reasons = list(dict.fromkeys(prev.reasons + cue.reasons))
            prev.lyric_line_ids = list(dict.fromkeys(prev.lyric_line_ids + cue.lyric_line_ids))
            prev.cue_type = "music+lyrics" if prev.cue_type != cue.cue_type else prev.cue_type
            if cue.recommended_visual_action not in prev.recommended_visual_action:
                prev.recommended_visual_action += " / " + cue.recommended_visual_action
        else:
            merged.append(cue.model_copy(deep=True))

    merged.sort(key=lambda x: (-x.priority, x.time_sec))
    # Keep the director view useful, then return chronologically.
    merged = merged[:24]
    merged.sort(key=lambda x: x.time_sec)
    for idx, cue in enumerate(merged, 1):
        cue.cue_id = f"MV{idx:02d}"
    return merged


def format_timeline_text(cues: Iterable[MVTimelineCue]) -> str:
    rows = []
    for cue in cues:
        mm = int(cue.time_sec // 60)
        ss = cue.time_sec - mm * 60
        stamp = f"{mm:02d}:{ss:05.2f}"
        lyrics = ",".join(cue.lyric_line_ids) if cue.lyric_line_ids else "-"
        rows.append(
            f"{stamp}  P={cue.priority:.2f}  {cue.cue_type}  lyrics={lyrics}\n"
            f"  → {cue.recommended_visual_action}"
        )
    return "\n\n".join(rows)
