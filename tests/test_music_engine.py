from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from mvstudio.lyrics_engine import analyze_lyrics, parse_lyrics_text
from mvstudio.music_engine import analyze_audio, build_mv_timeline


def _make_test_song(path: Path, sr: int = 22050, bpm: float = 120.0, duration: float = 24.0) -> None:
    n = int(sr * duration)
    y = np.zeros(n, dtype=np.float32)
    beat_interval = 60.0 / bpm
    # Low-level tonal bed. Energy changes at 8s and 16s create meaningful transition candidates.
    t = np.arange(n) / sr
    amp = np.where(t < 8, 0.03, np.where(t < 16, 0.10, 0.045))
    y += (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    for beat_t in np.arange(0.5, duration, beat_interval):
        start = int(beat_t * sr)
        length = min(int(0.035 * sr), n - start)
        if length <= 0:
            continue
        env = np.exp(-np.linspace(0, 7, length))
        y[start:start+length] += (0.75 * env).astype(np.float32)
    sf.write(path, y, sr)


def test_audio_analysis_detects_tempo_and_transitions(tmp_path):
    song = tmp_path / "test_song.wav"
    _make_test_song(song)
    audio_map = analyze_audio(song, max_transitions=8, min_transition_gap_sec=3.0)
    assert 110 <= audio_map.tempo_bpm <= 130
    assert 23.5 <= audio_map.duration_sec <= 24.5
    assert len(audio_map.beat_times_sec) >= 30
    assert len(audio_map.sections) >= 2
    assert audio_map.cut_cadence_hints["8_beats_sec"] > 0


def test_music_and_lyrics_fuse_into_mv_timeline(tmp_path):
    song = tmp_path / "test_song.wav"
    _make_test_song(song)
    audio_map = analyze_audio(song, max_transitions=8, min_transition_gap_sec=3.0)
    lyrics = "비가 창을 적셔\n다시 돌아오면 손을 흔들게\n밤이 지나가고\n다시 돌아오면 손을 흔들게\n이제 표를 놓고 떠나"
    lines = parse_lyrics_text(lyrics, suffix=".txt", song_duration=audio_map.duration_sec)
    analysis = analyze_lyrics(lines)
    cues = build_mv_timeline(audio_map, lines, analysis)
    assert len(cues) >= 3
    assert any(c.lyric_line_ids for c in cues)
    assert all(0 <= c.priority <= 1 for c in cues)
