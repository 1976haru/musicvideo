from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from mvstudio.editor import RenderEngine, build_rough_cut, discover_ffmpeg
from mvstudio.manual_generation import compile_manual_pack
from mvstudio.models import AudioMap, CameraSpec, ReferenceAsset, ReferenceRole, ShotSpec
from mvstudio.release_runtime import (
    APP_VERSION, AppPaths, app_paths, backup_session, begin_run, cache_size,
    clear_owned_cache, create_diagnostic_bundle, discover_ffmpeg, end_run,
    configure_logging, inspect_project, log_uncaught, run_startup_doctor,
    should_show_startup_doctor, mark_startup_doctor_seen, valid_recovery_sessions,
    music_analysis_smoke_test,
)
from mvstudio.result_takes import GenerationTake
from mvstudio.session import LyricsWorldSession
from mvstudio.technical_qc import analyze_take
from mvstudio.semantic_qc import analyze_visual_semantic
from mvstudio.story_engine import draft_story_beats


def _paths(root: Path) -> AppPaths:
    return AppPaths(root, root / "config", root / "logs", root / "cache", root / "recovery", root / "temp").ensure()


def _shot():
    return ShotSpec(
        shot_id="B001-S01", beat_id="B001", start_sec=0, end_sec=1,
        narrative_function="setup", subject="performer", action="turns",
        environment="blue room", composition="center", camera=CameraSpec(framing="medium"),
        lighting="soft blue", emotional_note="calm",
    )


def test_release_version_and_visible_title(monkeypatch):
    assert APP_VERSION == "1.0.1"
    assert 'version = "1.0.1"' in Path("pyproject.toml").read_text(encoding="utf-8")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from mvstudio.ui_app import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert "1.0" in window.windowTitle()
    window.close()


def test_app_paths_unicode_are_writable_and_not_install_dir(tmp_path):
    paths = app_paths(tmp_path / "사용자 データ")
    assert all(path.is_dir() for path in (paths.config, paths.logs, paths.cache, paths.recovery, paths.temp))
    probe = paths.cache / "ok"; probe.write_text("ok", encoding="utf-8")
    assert probe.read_text() == "ok"


def test_ffmpeg_discovery_explicit_priority_and_encoder_support(tmp_path, monkeypatch):
    tool_dir = tmp_path / "tools"; tool_dir.mkdir()
    (tool_dir / "ffmpeg.exe").write_bytes(b"x"); (tool_dir / "ffprobe.exe").write_bytes(b"x")
    class Result:
        returncode = 0; stderr = ""
        stdout = "ffmpeg version release\n" + " V..... libx264 H.264\n A..... aac AAC\n"
    monkeypatch.setattr("mvstudio.release_runtime.subprocess.run", lambda *args, **kwargs: Result())
    result = discover_ffmpeg(tool_dir)
    assert result.source == "configured" and result.render_ready


def test_missing_ffmpeg_doctor_required_optional_split(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    monkeypatch.setattr("mvstudio.release_runtime._candidate_tool_pair", lambda explicit=None: [])
    checks = run_startup_doctor(paths)
    ffmpeg = next(item for item in checks if item.check_id == "ffmpeg")
    openclip = next(item for item in checks if item.check_id == "openclip")
    assert ffmpeg.required and ffmpeg.state == "ACTION_REQUIRED"
    assert not openclip.required and openclip.state in {"READY", "OPTIONAL_MISSING"}


def test_app_local_then_path_discovery_and_encoder_blocker(tmp_path, monkeypatch):
    root = tmp_path / "app"; local = root / "tools" / "ffmpeg" / "bin"; local.mkdir(parents=True)
    for name in ("ffmpeg.exe", "ffprobe.exe"): (local / name).write_bytes(b"x")
    class Result:
        returncode = 0; stderr = ""; stdout = "ffmpeg version test\n V..... libx264 H.264\n"
    monkeypatch.setattr("mvstudio.release_runtime.application_root", lambda: root)
    monkeypatch.setattr("mvstudio.release_runtime.subprocess.run", lambda *args, **kwargs: Result())
    result = discover_ffmpeg()
    assert result.source == "app-local" and not result.render_ready and not result.aac_encoder
    for name in ("ffmpeg.exe", "ffprobe.exe"): (local / name).unlink()
    path_dir = tmp_path / "path"; path_dir.mkdir()
    for name in ("ffmpeg.exe", "ffprobe.exe"): (path_dir / name).write_bytes(b"x")
    monkeypatch.setattr("mvstudio.release_runtime.shutil.which", lambda name: str(path_dir / f"{name}.exe"))
    assert discover_ffmpeg().source == "PATH"


def test_backup_rotation_crash_marker_and_validation(tmp_path):
    paths = _paths(tmp_path / "appdata")
    session_file = tmp_path / "프로젝트.json"
    session_file.write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
    for index in range(8):
        session_file.write_text(json.dumps({"schema_version": "1.0", "lyrics_text": str(index)}), encoding="utf-8")
        backup_session(session_file, paths, limit=5)
    assert len(list(paths.recovery.rglob("*.json"))) == 5
    (paths.recovery / "broken.json").write_text("not-json", encoding="utf-8")
    assert len(valid_recovery_sessions(paths)) == 5
    assert begin_run(paths) is False
    assert begin_run(paths) is True
    end_run(paths)
    assert not (paths.recovery / "running.marker").exists()
    assert should_show_startup_doctor(False, paths)
    mark_startup_doctor_seen(paths)
    assert not should_show_startup_doctor(False, paths) and should_show_startup_doctor(True, paths)


def test_rotating_log_and_uncaught_exception_are_recorded(tmp_path, monkeypatch):
    paths = _paths(tmp_path / "appdata")
    logger = configure_logging(paths)
    for _ in range(1500): logger.info("bounded diagnostic line %s", "x" * 1000)
    assert len(list(paths.logs.glob("mvstudio.log*"))) <= 4
    monkeypatch.setenv("MVSTUDIO_APPDATA", str(paths.root))
    try: raise RuntimeError("safe-test-error")
    except RuntimeError:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        log_uncaught(exc_type, exc_value, exc_traceback)
    for handler in logger.handlers: handler.flush()
    assert "safe-test-error" in (paths.logs / "mvstudio.log").read_text(encoding="utf-8")


def test_session_save_backup_and_failed_replace_preserve_old(tmp_path, monkeypatch):
    target = tmp_path / "session.json"
    session = LyricsWorldSession(lyrics_text="old"); session.export(target)
    old = target.read_bytes(); session.lyrics_text = "new"
    monkeypatch.setattr("mvstudio.session.os.replace", lambda *_: (_ for _ in ()).throw(OSError("fail")))
    with pytest.raises(OSError): session.export(target)
    assert target.read_bytes() == old


def test_cache_cleanup_and_diagnostic_sanitization(tmp_path):
    paths = _paths(tmp_path / "appdata")
    source = tmp_path / "music.wav"; source.write_bytes(b"source")
    final = tmp_path / "final.mp4"; final.write_bytes(b"final")
    session = tmp_path / "session.json"; session.write_text("{}")
    (paths.cache / "nested").mkdir(); (paths.cache / "nested" / "cache.bin").write_bytes(b"cache")
    assert cache_size(paths) == 5
    clear_owned_cache(paths)
    assert source.read_bytes() == b"source" and final.read_bytes() == b"final" and session.exists()
    (paths.logs / "mvstudio.log").write_text("api_key=abcd token:xyz C:\\Users\\private\\project.json", encoding="utf-8")
    bundle = create_diagnostic_bundle(tmp_path / "diag.zip", paths)
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist(); log = archive.read("recent.log").decode()
    assert names == ["diagnostics.json", "recent.log"]
    assert "abcd" not in log and "xyz" not in log and "private" not in log and source.name not in names


def test_project_integrity_missing_media_and_no_repair(tmp_path):
    shot = _shot()
    take = GenerationTake(take_id="TAKE-B001-S01-001", shot_id=shot.shot_id, output_path="missing.mp4",
                          created_at="x", imported_at="x", original_filename="missing.mp4", status="accepted")
    session = LyricsWorldSession(music_path="missing.wav", shots=[shot], generation_takes=[take], project_dir=tmp_path)
    before = session.to_dict(tmp_path)
    findings = inspect_project(session)
    assert any(item.state in {"RELINK", "BLOCKED"} for item in findings)
    assert session.to_dict(tmp_path) == before


@pytest.mark.skipif(not discover_ffmpeg().render_ready, reason="Release E2E requires FFmpeg with libx264/AAC")
def test_synthetic_no_api_e2e_final_render_and_reopen(tmp_path):
    tools = discover_ffmpeg()
    music = tmp_path / "합성 음악.wav"; video = tmp_path / "합성 Take.mp4"
    subprocess.run([tools.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=1", str(music)], check=True, shell=False)
    subprocess.run([tools.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=blue:s=320x180:r=24:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True, shell=False)
    reference = tmp_path / "reference.ppm"
    reference.write_bytes(b"P6\n1 1\n255\n" + bytes((0, 0, 255)))
    original = {path: path.read_bytes() for path in (music, video, reference)}
    shot = _shot(); session = LyricsWorldSession(
        music_path=str(music), audio_map=AudioMap(source_path=str(music), duration_sec=1, sample_rate=44100),
        lyrics_text="푸른 방에서 돌아봐", duration_sec=1, shots=[shot], project_dir=tmp_path,
        references=[ReferenceAsset(reference_id="REF-001", role=ReferenceRole.COLOR_LIGHT, path=str(reference))],
    )
    session.analyze()
    session.promote_selected_concept()
    session.story_beats = draft_story_beats(session.lines, session.mv_timeline, 1.0)
    if session.story_beats:
        shot.beat_id = session.story_beats[0].beat_id
        shot.start_sec = max(0.0, session.story_beats[0].start_sec)
        shot.end_sec = min(1.0, session.story_beats[0].end_sec)
        if shot.end_sec <= shot.start_sec:
            shot.start_sec, shot.end_sec = 0.0, 1.0
    pack = compile_manual_pack(session, shot, pack_id="PACK-001"); session.generation_packs.append(pack)
    take = session.take_manager.register(video, shot.shot_id, pack.pack_id); session.take_manager.accept(take.take_id)
    report, _ = analyze_take(take, shot, tmp_path); session.qc_reports.append(report)
    session.semantic_qc_reports.append(analyze_visual_semantic(session, take, backend=None))
    session.edit_timeline = build_rough_cut(session)
    final = tmp_path / "최종 결과.mp4"
    record = RenderEngine(ffmpeg_path=tools.ffmpeg_path, cache_dir=tmp_path / "cache").render(session, final)
    session.render_records.append(record); session.final_path = str(final)
    saved = session.export(tmp_path / "project.json")
    reopened = LyricsWorldSession.import_file(saved)
    assert Path(reopened.final_path).is_file() and reopened.render_records[-1].succeeded
    assert all(path.read_bytes() == data for path, data in original.items())


def test_music_analysis_smoke_exercises_real_librosa_scipy_path(tmp_path, monkeypatch):
    monkeypatch.setenv("MVSTUDIO_APPDATA", str(tmp_path / "appdata"))
    ok, payload = music_analysis_smoke_test()
    assert ok, payload
    assert payload["music_analysis"] == "PASS"
    assert payload["duration_sec"] >= 1.9


def test_release_files_ci_manifest_and_no_obvious_secret():
    required = ["build_windows.ps1", "MV_Director_Studio.spec", "README_FIRST.txt", "CHANGELOG.md",
                "docs/RELEASE_NOTES_1.0.1.md", "docs/KNOWN_LIMITATIONS.md", ".github/workflows/windows-release.yml"]
    assert all(Path(item).is_file() for item in required)
    workflow = Path(required[-1]).read_text(encoding="utf-8")
    assert "PyInstaller" not in workflow or "package" in workflow
    tracked_text = "\n".join(Path(item).read_text(encoding="utf-8", errors="ignore") for item in required)
    assert "sk-" not in tracked_text and "BEGIN PRIVATE KEY" not in tracked_text


def test_release_gate_scripts_are_consistent():
    workflow = Path(".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    build = Path("build_windows.ps1").read_text(encoding="utf-8")
    cli = Path("src/mvstudio/cli.py").read_text(encoding="utf-8")
    progress = Path("PROGRESS.md").read_text(encoding="utf-8")
    assert "-ArtifactOnly" in workflow
    assert "-OutputRoot" not in workflow
    assert "--music-analysis-smoke-test" in workflow
    assert "--render-smoke-test" in workflow
    assert "--release-stress-test" in workflow
    assert "--release-stress-test" in build
    assert "root GUI music action" in build
    assert "MV Director Studio 1.0.0" not in cli
    assert "1.0.1" in progress
