from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

from mvstudio.models import CameraSpec, ShotSpec
from mvstudio.result_takes import GenerationTake
from mvstudio.session import LyricsWorldSession
from mvstudio.technical_qc import TakeQCReport, analyze_take, report_is_fresh


def _shot(duration: float = 3.0) -> ShotSpec:
    return ShotSpec(
        shot_id="B001-S01", beat_id="B001", start_sec=0, end_sec=duration,
        narrative_function="QC", subject="subject", action="action", environment="place",
        composition="center", camera=CameraSpec(framing="medium"), lighting="soft", emotional_note="calm",
    )


def _take(path: Path) -> GenerationTake:
    return GenerationTake(
        take_id="TAKE-B001-S01-001", shot_id="B001-S01", output_path=str(path),
        created_at="2026-01-01T00:00:00Z", imported_at="2026-01-01T00:00:00Z",
        original_filename=path.name,
    )


def _video(path: Path, mode: str = "motion", seconds: int = 3, fps: int = 10) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (96, 64))
    assert writer.isOpened()
    for index in range(seconds * fps):
        if mode == "black":
            frame = np.zeros((64, 96, 3), dtype=np.uint8)
        elif mode == "freeze":
            frame = np.full((64, 96, 3), 90, dtype=np.uint8)
        elif mode == "flicker":
            frame = np.full((64, 96, 3), 245 if index % 2 else 15, dtype=np.uint8)
        else:
            frame = np.full((64, 96, 3), 70, dtype=np.uint8)
            cv2.rectangle(frame, (index * 3 % 75, 20), (index * 3 % 75 + 20, 42), (180, 180, 180), -1)
        writer.write(frame)
    writer.release()
    return path


def _metric(report, metric_id):
    return next(metric for metric in report.metrics if metric.metric_id == metric_id)


def test_missing_and_invalid_video_are_blocked(tmp_path):
    missing, _ = analyze_take(_take(tmp_path / "없음 日本語.mp4"), _shot(), tmp_path)
    assert missing.status == "BLOCKED" and missing.recommended_action == "파일 다시 연결"
    invalid_path = tmp_path / "손상 영상.mp4"
    invalid_path.write_bytes(b"not a video")
    invalid, _ = analyze_take(_take(invalid_path), _shot(), tmp_path)
    assert invalid.status == "BLOCKED"


def test_duration_probe_mismatch_and_coarse_motion(tmp_path):
    path = _video(tmp_path / "한글 日本語 motion.mp4", "motion", seconds=3)
    report, hit = analyze_take(_take(path), _shot(3), tmp_path)
    assert not hit
    media = _metric(report, "media_info").raw_value
    assert 2.8 <= media["duration_sec"] <= 3.2 and media["fps"] > 0
    assert _metric(report, "motion").raw_value["category"] in {"낮음", "보통", "높음"}
    mismatch, _ = analyze_take(_take(path), _shot(8), tmp_path, options={"max_samples": 100})
    assert _metric(mismatch, "duration_match").severity == "bad"


def test_black_freeze_and_flicker_detection(tmp_path):
    black, _ = analyze_take(_take(_video(tmp_path / "black.mp4", "black")), _shot(), tmp_path)
    frozen, _ = analyze_take(_take(_video(tmp_path / "freeze.mp4", "freeze")), _shot(), tmp_path)
    flicker, _ = analyze_take(_take(_video(tmp_path / "flicker.mp4", "flicker")), _shot(), tmp_path)
    assert _metric(black, "near_black").severity == "bad"
    assert _metric(frozen, "freeze").severity == "bad"
    assert _metric(flicker, "flicker").severity == "bad"
    assert flicker.status == "REGENERATE"


def test_read_only_cache_hit_and_invalidation(tmp_path):
    path = _video(tmp_path / "원본 유지.mp4")
    take = _take(path)
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    report, _ = analyze_take(take, _shot(), tmp_path)
    cached, hit = analyze_take(take, _shot(), tmp_path, cached_reports=[report])
    assert hit and cached.report_id == report.report_id
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000))
    assert not report_is_fresh(report, path, report.analysis_options)


def test_schema_08_roundtrip_and_07_backward_compatibility(tmp_path):
    path = _video(tmp_path / "세션 영상.mp4")
    take = _take(path)
    report, _ = analyze_take(take, _shot(), tmp_path)
    session = LyricsWorldSession(shots=[_shot()], generation_takes=[take], qc_reports=[report], project_dir=tmp_path)
    target = tmp_path / "QC 세션 日本語.json"
    session.export(target)
    restored = LyricsWorldSession.import_file(target)
    assert restored.to_dict()["schema_version"] == "1.0"
    assert restored.qc_reports[0].report_id == report.report_id
    old = LyricsWorldSession.from_dict({"schema_version": "0.7", "generation_takes": []})
    assert old.qc_reports == []


def test_beginner_ui_selection_autosave_and_hidden_expert(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    path = _video(tmp_path / "UI 영상.mp4")
    take = _take(path)
    window = MainWindow()
    window.session = LyricsWorldSession(shots=[_shot()], generation_takes=[take], project_dir=tmp_path)
    page = window.technical_qc_page
    page.refresh()
    selected = page.take_combo.currentData()
    assert window.nav_buttons[8].isEnabled()
    assert page.question.text() == "이 영상은 사용해도 될까요?"
    assert page.expert_text.isHidden()
    assert page.analyze_button.minimumHeight() >= 44 and page.primary_action.minimumHeight() >= 44
    page._analyze()
    assert page.take_combo.currentData() == selected
    assert page.status.text() in page.STATUS_TEXT.values()
    assert not window.autosave_timer.isActive()
    window.session.export(tmp_path / "saved.json")
    page._analyze()  # cache hit does not schedule a write
    assert not window.autosave_timer.isActive()
    path.touch()
    page._analyze()
    assert window.autosave_timer.isActive()
    window.autosave_timer.stop(); window.close()
