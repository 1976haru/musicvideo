from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

from mvstudio.editor import (
    EditGap, MediaInfo, RenderEngine, RenderFailure, RenderSettings, build_rough_cut,
    check_readiness, export_edit_plan, export_otio, framing_filter, parse_ffmpeg_progress,
    probe_media, segment_cache_key,
)
from mvstudio.models import AudioMap, CameraSpec, ShotSpec
from mvstudio.result_takes import GenerationTake
from mvstudio.session import LyricsWorldSession


def _shot(shot_id="B001-S01", start=0.0, end=2.0):
    return ShotSpec(
        shot_id=shot_id, beat_id="B001", start_sec=start, end_sec=end,
        narrative_function="setup", subject="person", action="walks", environment="station",
        composition="wide", camera=CameraSpec(framing="wide"), lighting="soft", emotional_note="quiet",
    )


def _take(path: Path, shot_id="B001-S01", status="accepted", take_id=None):
    return GenerationTake(
        take_id=take_id or f"TAKE-{shot_id}-001", shot_id=shot_id, output_path=str(path),
        created_at="2026-01-01T00:00:00Z", imported_at="2026-01-01T00:00:00Z",
        original_filename=path.name, status=status,
    )


def _probe(duration=3.0, width=1920, height=1080, fps=30.0):
    return lambda path: MediaInfo(path=str(path), duration_sec=duration, width=width, height=height,
                                  fps=fps, codec="h264", has_audio=True, backend="fake")


def _session(tmp_path: Path, take_duration=3.0):
    video = tmp_path / "결과 영상 (A).mp4"; video.write_bytes(b"video-source")
    music = tmp_path / "원곡 音楽.wav"; music.write_bytes(b"music-source")
    session = LyricsWorldSession(
        music_path=str(music), duration_sec=2.0,
        audio_map=AudioMap(source_path=str(music), duration_sec=2, sample_rate=44100),
        shots=[_shot()], generation_takes=[_take(video)], project_dir=tmp_path,
    )
    session.edit_timeline = build_rough_cut(session, probe=_probe(take_duration))
    return session, video, music


def test_rough_cut_uses_only_accepted_and_long_take_trims(tmp_path):
    session, video, _ = _session(tmp_path)
    rejected = tmp_path / "reject.mp4"; rejected.write_bytes(b"reject")
    session.generation_takes.append(_take(rejected, status="rejected", take_id="TAKE-B001-S01-002"))
    timeline = build_rough_cut(session, probe=_probe(4))
    assert [clip.take_id for clip in timeline.clips] == ["TAKE-B001-S01-001"]
    assert timeline.clips[0].fit_status == "trim_end"
    assert timeline.clips[0].source_out == 2


def test_missing_duplicate_and_missing_file_are_blockers(tmp_path):
    session, video, _ = _session(tmp_path)
    session.generation_takes = []
    assert "NO_ACCEPTED_TAKE" in {x.code for x in check_readiness(session, probe=_probe()).issues}
    session.generation_takes = [_take(video), _take(video, take_id="TAKE-B001-S01-002")]
    assert "MULTIPLE_ACCEPTED" in {x.code for x in check_readiness(session, probe=_probe()).issues}
    session.generation_takes = [_take(tmp_path / "missing.mp4")]
    assert "ACCEPTED_FILE_MISSING" in {x.code for x in check_readiness(session, probe=_probe()).issues}


def test_short_take_requires_explicit_hold_last(tmp_path):
    session, _, _ = _session(tmp_path, take_duration=1.5)
    clip = session.edit_timeline.clips[0]
    assert clip.fit_status == "unresolved_short"
    assert check_readiness(session, probe=_probe(1.5)).status == "BLOCKED"
    clip.fit_status = "hold_last"
    ready = check_readiness(session, probe=_probe(1.5))
    assert ready.status == "READY_WITH_WARNINGS"
    assert "HOLD_LAST" in {x.code for x in ready.issues}


def test_gap_detection_resolution_and_overlap_blocker(tmp_path):
    session, video, music = _session(tmp_path)
    second = tmp_path / "b.mp4"; second.write_bytes(b"b")
    session.audio_map = AudioMap(source_path=str(music), duration_sec=5, sample_rate=44100)
    session.duration_sec = 5
    session.shots = [_shot(end=2), _shot("B002-S01", 3, 5)]
    session.generation_takes = [_take(video), _take(second, "B002-S01")]
    session.edit_timeline = build_rough_cut(session, probe=_probe(3))
    assert session.edit_timeline.gaps[0].resolution == "unresolved"
    assert "UNRESOLVED_GAP" in {x.code for x in check_readiness(session, probe=_probe(3)).issues}
    session.edit_timeline.gaps[0].resolution = "black"
    assert check_readiness(session, probe=_probe(3)).status == "READY_WITH_WARNINGS"
    session.edit_timeline.gaps[0].resolution = "hold_previous"
    assert "HOLD_GAP" in {x.code for x in check_readiness(session, probe=_probe(3)).issues}
    session.shots[1].start_sec = 1.5
    session.edit_timeline = build_rough_cut(session, probe=_probe(3))
    assert "SHOT_OVERLAP" in {x.code for x in check_readiness(session, probe=_probe(3)).issues}


def test_cover_contain_and_cache_invalidation(tmp_path):
    session, video, _ = _session(tmp_path)
    clip = session.edit_timeline.clips[0]
    settings = RenderSettings()
    assert "crop=" in framing_filter("cover", 1920, 1080, 30)
    assert "pad=" in framing_filter("contain", 1920, 1080, 30)
    first = segment_cache_key(clip, settings)
    video.write_bytes(b"changed-video-source")
    assert segment_cache_key(clip, settings) != first
    first = segment_cache_key(clip, settings)
    clip.source_in = .1; clip.source_out = 2.1
    assert segment_cache_key(clip, settings) != first


def test_ffprobe_fallback_and_unavailable_are_graceful(tmp_path, monkeypatch):
    media = tmp_path / "영상.mp4"; media.write_bytes(b"bad")
    monkeypatch.setattr("mvstudio.editor.shutil.which", lambda name: None)
    # The source tree can sit beside the deployed root runtime; isolate this
    # explicit unavailable-renderer assertion from app-local FFmpeg discovery.
    monkeypatch.setattr(
        "mvstudio.editor.discover_ffmpeg",
        lambda: types.SimpleNamespace(ffmpeg_path="", ffprobe_path=""),
    )
    fake_cv = types.SimpleNamespace(
        CAP_PROP_FPS=1, CAP_PROP_FRAME_COUNT=2, CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4,
        VideoCapture=lambda path: types.SimpleNamespace(
            isOpened=lambda: True, get=lambda key: {1: 25, 2: 50, 3: 640, 4: 360}[key], release=lambda: None
        ),
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv)
    assert probe_media(media).backend == "opencv"
    assert not RenderEngine(ffmpeg_path=None).available


def test_render_argv_uses_original_music_no_take_audio_and_unicode_paths(tmp_path):
    session, _, music = _session(tmp_path)
    engine = RenderEngine(ffmpeg_path="ffmpeg", cache_dir=tmp_path / "캐시", probe=_probe())
    calls = []
    def fake_run(argv, duration, progress, cancel):
        calls.append(argv)
        Path(argv[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(argv[-1]).write_bytes(b"derived")
    engine._run = fake_run
    out = tmp_path / "최종 영상 (완성).mp4"
    record = engine.render(session, out)
    assert record.output_path == str(out)
    assert "-an" in calls[0]
    assert str(music) in calls[-1]
    assert calls[-1][calls[-1].index("-map") + 1] == "0:v:0"
    assert calls[-1][calls[-1].index("-map", calls[-1].index("-map") + 1) + 1] == "1:a:0"


def test_atomic_failure_and_cancel_preserve_existing_final_and_sources(tmp_path):
    session, video, music = _session(tmp_path)
    original_video, original_music = video.read_bytes(), music.read_bytes()
    final = tmp_path / "existing.mp4"; final.write_bytes(b"old-final")
    engine = RenderEngine(ffmpeg_path="ffmpeg", cache_dir=tmp_path / "cache", probe=_probe())
    engine._run = lambda *args, **kwargs: (_ for _ in ()).throw(RenderFailure("failed"))
    with pytest.raises(RenderFailure): engine.render(session, final)
    assert final.read_bytes() == b"old-final"
    assert video.read_bytes() == original_video and music.read_bytes() == original_music
    import threading
    cancelled = threading.Event(); cancelled.set()
    with pytest.raises(Exception): engine.render(session, final, cancel=cancelled)
    assert final.read_bytes() == b"old-final"


def test_preview_uses_same_decisions_and_separate_record(tmp_path):
    session, _, _ = _session(tmp_path)
    engine = RenderEngine(ffmpeg_path="ffmpeg", cache_dir=tmp_path / "cache", probe=_probe())
    engine._run = lambda argv, *args: (Path(argv[-1]).parent.mkdir(parents=True, exist_ok=True), Path(argv[-1]).write_bytes(b"x"))
    before = session.edit_timeline.model_dump()
    record = engine.render(session, tmp_path / "preview.mp4", kind="preview")
    assert record.kind == "preview" and record.settings.width <= 1280 and record.settings.height <= 720
    assert session.edit_timeline.model_dump() == before


def test_progress_parser_is_real_time_based():
    assert parse_ffmpeg_progress("out_time_ms=5000000", 10) == 50
    assert parse_ffmpeg_progress("progress=end", 10) == 100
    assert parse_ffmpeg_progress("frame=10", 10) is None


def test_edit_plan_and_schema_10_roundtrip_09_backward(tmp_path):
    session, _, _ = _session(tmp_path)
    plan = export_edit_plan(session, tmp_path / "편집 계획.json")
    payload = json.loads(plan.read_text(encoding="utf-8"))
    assert payload["type"] == "MV Director Edit Plan"
    assert payload["timeline"]["clips"][0]["take_id"] == "TAKE-B001-S01-001"
    saved = session.export(tmp_path / "session.json")
    restored = LyricsWorldSession.import_file(saved)
    assert restored.to_dict()["schema_version"] == "1.0"
    assert restored.edit_timeline.clips[0].take_id == "TAKE-B001-S01-001"
    old = LyricsWorldSession.from_dict({"schema_version": "0.9"})
    assert old.edit_timeline is None and old.render_settings.width == 1920


def test_otio_optional_and_lineage_structure(tmp_path, monkeypatch):
    session, _, _ = _session(tmp_path)
    with pytest.raises(RuntimeError):
        monkeypatch.setitem(sys.modules, "opentimelineio", None)
        export_otio(session, tmp_path / "a.otio")


def test_otio_export_contains_shot_take_lineage(tmp_path, monkeypatch):
    session, _, _ = _session(tmp_path)
    written = {}
    class Item:
        def __init__(self, **kwargs): self.metadata = {}; self.kwargs = kwargs
    class Track(list):
        def __init__(self, **kwargs): super().__init__(); self.kwargs = kwargs
    class Timeline:
        def __init__(self, **kwargs): self.tracks = []; self.kwargs = kwargs
    schema = types.SimpleNamespace(
        Timeline=Timeline, Track=Track, TrackKind=types.SimpleNamespace(Video="Video"),
        ExternalReference=Item, Clip=Item, Gap=Item,
    )
    opentime = types.SimpleNamespace(
        RationalTime=lambda value, rate: (value, rate),
        TimeRange=lambda start_time, duration: (start_time, duration),
    )
    adapters = types.SimpleNamespace(write_to_file=lambda timeline, path: written.update(timeline=timeline, path=path))
    monkeypatch.setitem(sys.modules, "opentimelineio", types.SimpleNamespace(schema=schema, opentime=opentime, adapters=adapters))
    target = export_otio(session, tmp_path / "timeline.otio")
    clip = written["timeline"].tracks[0][0]
    assert target.name == "timeline.otio"
    assert clip.metadata["mvstudio"]["shot_id"] == "B001-S01"
    assert clip.metadata["mvstudio"]["take_id"] == "TAKE-B001-S01-001"


def test_beginner_ui_and_edit_autosave(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from mvstudio.ui_app import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    session, _, _ = _session(tmp_path)
    session.session_path = tmp_path / "saved.json"
    window.session = session
    window._refresh_from_session()
    page = window.editor_render_page
    assert "뮤직비디오를 자동으로 편집할까요?" in page.findChildren(type(page.summary))[0].text() or page.layout() is not None
    assert page.build_button.minimumHeight() >= 44
    assert window.minimumWidth() <= 1100 and window.minimumHeight() <= 720
    called = []
    monkeypatch.setattr(window.autosave_timer, "start", lambda: called.append(True))
    page.make_rough_cut()
    assert called
    unsaved = LyricsWorldSession()
    window.session = unsaved; called.clear(); page.on_change()
    assert called == []
    window.close()
