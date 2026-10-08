from __future__ import annotations

import json
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
import zipfile
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .optional_backends import (
    beat_this_availability, functional_structure_availability, openclip_availability,
)


APP_NAME = "MV Director Studio"
APP_VERSION = "1.0.3"
SESSION_SCHEMA = "1.0"
BACKUP_LIMIT = 5


@dataclass(frozen=True)
class AppPaths:
    root: Path
    config: Path
    logs: Path
    cache: Path
    recovery: Path
    temp: Path

    def ensure(self) -> "AppPaths":
        for path in (self.root, self.config, self.logs, self.cache, self.recovery, self.temp):
            path.mkdir(parents=True, exist_ok=True)
        return self


def app_paths(base: str | Path | None = None) -> AppPaths:
    if base is not None:
        root = Path(base).expanduser().resolve(strict=False)
    else:
        override = os.environ.get("MVSTUDIO_APPDATA")
        if override:
            root = Path(override).expanduser().resolve(strict=False)
            return AppPaths(root, root / "config", root / "logs", root / "cache", root / "recovery", root / "temp").ensure()
        local = os.environ.get("LOCALAPPDATA")
        root = (Path(local) if local else Path.home() / "AppData" / "Local") / "MVDirectorStudio"
    return AppPaths(root, root / "config", root / "logs", root / "cache", root / "recovery", root / "temp").ensure()


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def load_runtime_config(paths: AppPaths | None = None) -> dict[str, Any]:
    target = (paths or app_paths()).config / "settings.json"
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_runtime_config(data: dict[str, Any], paths: AppPaths | None = None) -> Path:
    paths = (paths or app_paths()).ensure()
    target = paths.config / "settings.json"
    temporary = paths.config / f".settings-{uuid.uuid4().hex}.tmp"
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)
    return target


def should_show_startup_doctor(previous_unclean: bool, paths: AppPaths | None = None) -> bool:
    return previous_unclean or load_runtime_config(paths).get("doctor_seen_version") != APP_VERSION


def mark_startup_doctor_seen(paths: AppPaths | None = None) -> None:
    data = load_runtime_config(paths)
    data["doctor_seen_version"] = APP_VERSION
    save_runtime_config(data, paths)


@dataclass(frozen=True)
class ToolInfo:
    state: Literal["AVAILABLE", "NOT_INSTALLED", "LOAD_FAILED"]
    ffmpeg_path: str = ""
    ffprobe_path: str = ""
    source: str = ""
    version: str = ""
    h264_encoder: bool = False
    aac_encoder: bool = False
    detail: str = ""

    @property
    def render_ready(self) -> bool:
        return self.state == "AVAILABLE" and bool(self.ffmpeg_path and self.ffprobe_path and self.h264_encoder and self.aac_encoder)


def _candidate_tool_pair(explicit: str | Path | None = None) -> list[tuple[str, Path, Path]]:
    candidates: list[tuple[str, Path, Path]] = []
    if explicit:
        path = Path(explicit).expanduser().resolve(strict=False)
        directory = path if path.is_dir() else path.parent
        candidates.append(("configured", directory / "ffmpeg.exe", directory / "ffprobe.exe"))
    local = application_root() / "tools" / "ffmpeg" / "bin"
    candidates.append(("app-local", local / "ffmpeg.exe", local / "ffprobe.exe"))
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg or ffprobe:
        candidates.append(("PATH", Path(ffmpeg or ""), Path(ffprobe or "")))
    return candidates


def discover_ffmpeg(explicit: str | Path | None = None) -> ToolInfo:
    if explicit is None:
        explicit = load_runtime_config().get("ffmpeg_path")
    for source, ffmpeg, ffprobe in _candidate_tool_pair(explicit):
        if not ffmpeg.is_file() or not ffprobe.is_file():
            continue
        try:
            version_run = subprocess.run([str(ffmpeg), "-version"], capture_output=True, text=True,
                                         encoding="utf-8", errors="replace", timeout=10, shell=False)
            encoders_run = subprocess.run([str(ffmpeg), "-hide_banner", "-encoders"], capture_output=True, text=True,
                                          encoding="utf-8", errors="replace", timeout=15, shell=False)
            probe_run = subprocess.run([str(ffprobe), "-version"], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=10, shell=False)
            if version_run.returncode or probe_run.returncode:
                return ToolInfo("LOAD_FAILED", str(ffmpeg), str(ffprobe), source=source,
                                detail="FFmpeg 또는 FFprobe를 실행하지 못했습니다.")
            encoder_text = encoders_run.stdout + encoders_run.stderr
            version = (version_run.stdout.splitlines() or [""])[0].strip()
            return ToolInfo(
                "AVAILABLE", str(ffmpeg), str(ffprobe), source=source, version=version,
                h264_encoder="libx264" in encoder_text, aac_encoder=bool(re.search(r"\bAAC\b|\baac\b", encoder_text)),
                detail="" if encoders_run.returncode == 0 else "인코더 목록을 확인하지 못했습니다.",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return ToolInfo("LOAD_FAILED", str(ffmpeg), str(ffprobe), source=source, detail=str(exc))
    return ToolInfo("NOT_INSTALLED", detail="영상 내보내기 도구(FFmpeg/FFprobe)를 찾을 수 없습니다.")


@dataclass(frozen=True)
class DoctorCheck:
    check_id: str
    label: str
    required: bool
    state: Literal["READY", "OPTIONAL_MISSING", "ACTION_REQUIRED"]
    reason: str
    action: str = ""


def run_startup_doctor(paths: AppPaths | None = None, explicit_ffmpeg: str | Path | None = None) -> list[DoctorCheck]:
    paths = (paths or app_paths()).ensure()
    checks: list[DoctorCheck] = []
    try:
        probe = paths.temp / ".write-test"
        probe.write_text("ok", encoding="utf-8"); probe.unlink()
        checks.append(DoctorCheck("app_data", "프로그램 데이터 경로", True, "READY", "사용자 쓰기 경로가 준비되었습니다."))
    except OSError as exc:
        checks.append(DoctorCheck("app_data", "프로그램 데이터 경로", True, "ACTION_REQUIRED", str(exc), "폴더 권한을 확인하세요."))
    try:
        import PySide6  # noqa: F401
        checks.append(DoctorCheck("desktop", "기본 프로그램", True, "READY", "화면 구성 요소가 준비되었습니다."))
    except ImportError:
        checks.append(DoctorCheck("desktop", "기본 프로그램", True, "ACTION_REQUIRED", "PySide6를 불러오지 못했습니다.", "프로그램을 다시 설치하세요."))
    try:
        import numpy  # noqa: F401
        import librosa  # noqa: F401
        checks.append(DoctorCheck("music", "음악 분석", True, "READY", "기본 분석 구성 요소가 준비되었습니다."))
    except ImportError:
        checks.append(DoctorCheck("music", "음악 분석", True, "ACTION_REQUIRED", "기본 음악 분석 구성 요소가 없습니다.", "프로그램을 다시 설치하세요."))
    tools = discover_ffmpeg(explicit_ffmpeg)
    if tools.render_ready:
        checks.append(DoctorCheck("ffmpeg", "FFmpeg / FFprobe", True, "READY", f"{tools.source}: {tools.version}"))
        checks.append(DoctorCheck("render", "Final Render", True, "READY", "H.264와 AAC 인코더를 사용할 수 있습니다."))
    else:
        reason = tools.detail or "필수 인코더를 사용할 수 없습니다."
        if tools.state == "AVAILABLE" and not tools.h264_encoder:
            reason = "현재 FFmpeg에서 기본 H.264(libx264) 인코더를 사용할 수 없습니다."
        elif tools.state == "AVAILABLE" and not tools.aac_encoder:
            reason = "현재 FFmpeg에서 기본 AAC 인코더를 사용할 수 없습니다."
        checks.append(DoctorCheck("ffmpeg", "FFmpeg / FFprobe", True, "ACTION_REQUIRED", reason,
                                  "설정 경로 또는 프로그램의 tools/ffmpeg/bin을 확인하세요."))
        checks.append(DoctorCheck("render", "Final Render", True, "ACTION_REQUIRED", "최종 영상 내보내기를 사용할 수 없습니다.",
                                  "FFmpeg 상태를 먼저 해결하세요."))
    optional = [
        ("openclip", "OpenCLIP", openclip_availability().state),
        ("beat_this", "Beat This", beat_this_availability().state),
        ("functional", "Functional Structure", functional_structure_availability().state),
    ]
    try:
        import importlib.util
        optional.append(("otio", "OpenTimelineIO", "AVAILABLE" if importlib.util.find_spec("opentimelineio") else "NOT_INSTALLED"))
    except (ImportError, ValueError):
        optional.append(("otio", "OpenTimelineIO", "LOAD_FAILED"))
    for check_id, label, state in optional:
        checks.append(DoctorCheck(check_id, label, False, "READY" if state == "AVAILABLE" else "OPTIONAL_MISSING",
                                  "선택 기능이 준비되었습니다." if state == "AVAILABLE" else "선택 기능 없음",
                                  "필요할 때 선택 dependency를 설치할 수 있습니다."))
    return checks


def configure_logging(paths: AppPaths | None = None) -> logging.Logger:
    paths = (paths or app_paths()).ensure()
    logger = logging.getLogger("mvstudio")
    logger.setLevel(logging.INFO)
    target = str((paths.logs / "mvstudio.log").resolve(strict=False))
    for existing in list(logger.handlers):
        if isinstance(existing, RotatingFileHandler) and existing.baseFilename != target:
            logger.removeHandler(existing); existing.close()
    if not logger.handlers:
        handler = RotatingFileHandler(paths.logs / "mvstudio.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def crash_marker_path(paths: AppPaths | None = None) -> Path:
    return (paths or app_paths()).recovery / "running.marker"


def begin_run(paths: AppPaths | None = None) -> bool:
    marker = crash_marker_path(paths)
    previous_unclean = marker.exists()
    marker.write_text(json.dumps({"version": APP_VERSION, "started_at": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    return previous_unclean


def end_run(paths: AppPaths | None = None) -> None:
    crash_marker_path(paths).unlink(missing_ok=True)


def backup_session(session_path: str | Path, paths: AppPaths | None = None, limit: int = BACKUP_LIMIT) -> Path | None:
    source = Path(session_path).resolve(strict=False)
    if not source.is_file():
        return None
    try:
        from .session import LyricsWorldSession
        LyricsWorldSession.import_file(source)
    except (OSError, ValueError):
        return None
    paths = (paths or app_paths()).ensure()
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", source.stem)[:45] or "session"
    key = f"{safe_name}-{hashlib.sha256(str(source).encode()).hexdigest()[:10]}"
    directory = paths.recovery / key
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = directory / f"{key}.{stamp}.json"
    shutil.copy2(source, target)
    backups = sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime_ns, reverse=True)
    for old in backups[max(1, limit):]:
        old.unlink(missing_ok=True)
    return target


def valid_recovery_sessions(paths: AppPaths | None = None) -> list[Path]:
    from .session import LyricsWorldSession
    candidates = []
    for path in (paths or app_paths()).recovery.rglob("*.json"):
        try:
            LyricsWorldSession.import_file(path)
            candidates.append(path)
        except (OSError, ValueError):
            continue
    return sorted(candidates, key=lambda item: item.stat().st_mtime_ns, reverse=True)


def cache_size(paths: AppPaths | None = None) -> int:
    root = (paths or app_paths()).cache.resolve(strict=False)
    return sum(item.stat().st_size for item in root.rglob("*") if item.is_file())


def clear_owned_cache(paths: AppPaths | None = None) -> int:
    paths = (paths or app_paths()).ensure()
    root = paths.cache.resolve(strict=False)
    if root != paths.cache.resolve(strict=False) or root == Path(root.anchor):
        raise ValueError("안전한 프로그램 cache 경로가 아닙니다.")
    before = cache_size(paths)
    for item in list(root.iterdir()):
        if item.is_dir(): shutil.rmtree(item)
        else: item.unlink()
    return before


def sanitize_text(text: str) -> str:
    patterns = [
        (re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[^\s,;]+"), r"\1=[REDACTED]"),
        (re.compile(r"(?i)Bearer\s+[A-Za-z0-9._-]+"), "Bearer [REDACTED]"),
    ]
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    text = re.sub(r"(?i)(?:[A-Z]:\\|\\\\)[^\r\n\"']+", "[PATH]", text)
    text = re.sub(r"(?<![:\w])/(?:home|users|tmp|var)/[^\s\"']+", "[PATH]", text)
    return text


def release_manifest() -> dict[str, Any]:
    manifest_path = application_root() / "release_manifest.json"
    if manifest_path.is_file():
        try: return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError): pass
    return {"app_version": APP_VERSION, "session_schema": SESSION_SCHEMA, "build": "development"}


def create_diagnostic_bundle(target: str | Path, paths: AppPaths | None = None) -> Path:
    paths = (paths or app_paths()).ensure()
    target = Path(target).resolve(strict=False)
    checks = [asdict(item) for item in run_startup_doctor(paths)]
    logs = ""
    log_file = paths.logs / "mvstudio.log"
    if log_file.is_file():
        logs = sanitize_text(log_file.read_text(encoding="utf-8", errors="replace")[-100_000:])
    summary = {
        "app_version": APP_VERSION, "session_schema": SESSION_SCHEMA,
        "platform": platform.platform(), "python": platform.python_version(),
        "doctor": checks, "release_manifest": release_manifest(),
    }
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostics.json", json.dumps(summary, ensure_ascii=False, indent=2))
        archive.writestr("recent.log", logs)
    return target


@dataclass(frozen=True)
class IntegrityFinding:
    state: Literal["NORMAL", "RELINK", "RECHECK", "BLOCKED"]
    message: str


def inspect_project(session) -> list[IntegrityFinding]:
    from .result_takes import audit_take_state, resolve_take_path
    from .reference_vault import resolve_reference_path
    findings: list[IntegrityFinding] = []
    if session.session_path:
        if not Path(session.session_path).is_file():
            findings.append(IntegrityFinding("RECHECK", "저장된 session JSON을 다시 확인하세요."))
        else:
            try:
                from .session import LyricsWorldSession
                LyricsWorldSession.import_file(session.session_path)
            except (OSError, ValueError):
                findings.append(IntegrityFinding("BLOCKED", "Session JSON 검증에 실패했습니다. 복구본을 확인하세요."))
    music = Path(session.music_path) if session.music_path else None
    if music and not music.is_absolute() and session.project_dir: music = session.project_dir / music
    if not music or not music.is_file(): findings.append(IntegrityFinding("BLOCKED", "음악 파일을 다시 연결해야 합니다."))
    for reference in session.references:
        if not resolve_reference_path(reference, session.project_dir).is_file():
            findings.append(IntegrityFinding("RELINK", f"Reference를 다시 연결하세요: {reference.reference_id}"))
    for take in session.generation_takes:
        if take.status == "accepted" and not resolve_take_path(take, session.project_dir).is_file():
            findings.append(IntegrityFinding("RELINK", f"accepted Take를 다시 연결하세요: {take.take_id}"))
    for warning in audit_take_state(session.generation_takes, session.shots, session.generation_packs,
                                    session.project_dir, session.take_id_counters):
        state = "BLOCKED" if warning.code in {"DUPLICATE_TAKE_ID", "MULTIPLE_ACCEPTED"} else "RECHECK"
        findings.append(IntegrityFinding(state, warning.message))
    take_ids = {item.take_id for item in session.generation_takes if item.status == "accepted"}
    if session.edit_timeline and any(item.take_id not in take_ids for item in session.edit_timeline.clips):
        findings.append(IntegrityFinding("RECHECK", "Rough Cut이 현재 accepted Take와 다릅니다. 다시 만드세요."))
    from .technical_qc import DEFAULT_OPTIONS, report_is_fresh
    for take in session.generation_takes:
        if take.status != "accepted": continue
        reports = [item for item in session.qc_reports if item.take_id == take.take_id]
        if reports and not report_is_fresh(reports[-1], resolve_take_path(take, session.project_dir), dict(DEFAULT_OPTIONS)):
            findings.append(IntegrityFinding("RECHECK", f"QC를 다시 실행하세요: {take.take_id}"))
    if session.final_path and not Path(session.final_path).is_file():
        findings.append(IntegrityFinding("RECHECK", "기록된 최종 영상 파일을 찾을 수 없습니다."))
    return findings or [IntegrityFinding("NORMAL", "프로젝트 상태를 확인했습니다. 정상입니다.")]


def log_uncaught(exc_type, exc_value, exc_traceback) -> None:
    configure_logging().error("uncaught exception\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))


def smoke_test() -> tuple[bool, dict[str, Any]]:
    paths = app_paths()
    checks = run_startup_doctor(paths)
    from .session import LyricsWorldSession
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from .ui_app import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    ui_pages = window.pages.count()
    ui_title = window.windowTitle()
    window.close()
    directory = paths.temp / f"smoke-{uuid.uuid4().hex}"
    directory.mkdir()
    try:
        target = directory / "smoke.json"
        LyricsWorldSession(lyrics_text="smoke").export(target)
        reopened = LyricsWorldSession.import_file(target)
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    required_failures = [item.check_id for item in checks if item.required and item.state == "ACTION_REQUIRED"]
    payload = {
        "app": APP_NAME, "version": APP_VERSION, "session_schema": reopened.to_dict()["schema_version"],
        "application_root": str(application_root()), "app_data": str(paths.root),
        "ui_pages": ui_pages, "ui_title": ui_title,
        "doctor": [asdict(item) for item in checks], "required_failures": required_failures,
    }
    return not required_failures, payload



def music_analysis_smoke_test() -> tuple[bool, dict[str, Any]]:
    """Exercise the packaged librosa -> scipy analysis path with a real WAV.

    This specifically guards against PyInstaller missing dynamically imported SciPy
    Array API compatibility modules.
    """
    import math
    import struct
    import wave

    paths = app_paths()
    directory = paths.temp / f"music-smoke-{uuid.uuid4().hex}"
    directory.mkdir()
    try:
        audio = directory / "synthetic-music.wav"
        sample_rate = 22050
        duration_sec = 2.0
        frame_count = int(sample_rate * duration_sec)
        with wave.open(str(audio), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(sample_rate)
            frames = bytearray()
            for index in range(frame_count):
                value = int(12000 * math.sin(2 * math.pi * 440 * index / sample_rate))
                frames.extend(struct.pack("<h", value))
            stream.writeframes(bytes(frames))

        from .music_engine import analyze_audio
        audio_map = analyze_audio(audio)
        ok = audio_map.duration_sec >= 1.9 and audio_map.sample_rate > 0
        return ok, {
            "music_analysis": "PASS" if ok else "FAIL",
            "duration_sec": audio_map.duration_sec,
            "sample_rate": audio_map.sample_rate,
            "tempo_bpm": audio_map.tempo_bpm,
            "transitions": len(audio_map.transitions),
        }
    except Exception as exc:
        configure_logging(paths).exception("packaged music analysis smoke failed")
        return False, {"music_analysis": "FAIL", "error": str(exc)}
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def render_smoke_test() -> tuple[bool, dict[str, Any]]:
    tools = discover_ffmpeg()
    if not tools.render_ready:
        return False, {"error": "FFmpeg render requirements are not ready", "tools": asdict(tools)}
    paths = app_paths()
    directory = paths.temp / f"render-smoke-{uuid.uuid4().hex}"
    directory.mkdir()
    try:
        music = directory / "synthetic-audio.wav"
        video = directory / "synthetic-take.mp4"
        final = directory / "synthetic-final.mp4"
        subprocess.run([tools.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1", str(music)], check=True, shell=False)
        subprocess.run([tools.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=blue:s=320x180:r=24:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
                       check=True, shell=False)
        source_before = {str(path): path.read_bytes() for path in (music, video)}
        from .models import AudioMap, CameraSpec, ShotSpec
        from .result_takes import GenerationTake
        from .session import LyricsWorldSession
        from .editor import RenderEngine, build_rough_cut, probe_media
        shot = ShotSpec(
            shot_id="B001-S01", beat_id="B001", start_sec=0, end_sec=1,
            narrative_function="release smoke", subject="shape", action="moves", environment="blue field",
            composition="center", camera=CameraSpec(framing="wide"), lighting="soft", emotional_note="calm",
        )
        take = GenerationTake(
            take_id="TAKE-B001-S01-001", shot_id=shot.shot_id, output_path=str(video),
            created_at="smoke", imported_at="smoke", original_filename=video.name, status="accepted",
        )
        session = LyricsWorldSession(
            music_path=str(music), audio_map=AudioMap(source_path=str(music), duration_sec=1, sample_rate=44100),
            shots=[shot], generation_takes=[take], project_dir=directory,
        )
        session.edit_timeline = build_rough_cut(session)
        record = RenderEngine(ffmpeg_path=tools.ffmpeg_path, cache_dir=paths.cache / "release-smoke").render(session, final)
        info = probe_media(final, tools.ffprobe_path)
        immutable = all(Path(path).read_bytes() == content for path, content in source_before.items())
        payload = {
            "render": "PASS" if final.is_file() and info.has_audio and immutable else "FAIL",
            "output_size": final.stat().st_size if final.is_file() else 0,
            "duration_sec": info.duration_sec, "has_original_music_audio": info.has_audio,
            "sources_immutable": immutable, "record": record.model_dump(mode="json"),
            "ffmpeg_source": tools.source,
        }
        return payload["render"] == "PASS", payload
    except Exception as exc:
        configure_logging(paths).exception("packaged render smoke failed")
        return False, {"render": "FAIL", "error": str(exc)}
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _write_synthetic_wav(path: Path, duration_sec: float = 2.0, sample_rate: int = 22050) -> None:
    """Write deterministic PCM without depending on an audio library."""
    import math
    import struct
    import wave

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        frames = bytearray()
        for index in range(int(sample_rate * duration_sec)):
            # A pulse plus two tones gives onset/beat/spectral code real input.
            pulse = 0.45 if (index % (sample_rate // 2)) < 600 else 0.0
            value = (0.35 * math.sin(2 * math.pi * 220 * index / sample_rate) +
                     0.20 * math.sin(2 * math.pi * 660 * index / sample_rate) + pulse)
            frames.extend(struct.pack("<h", max(-32767, min(32767, int(16000 * value)))))
        stream.writeframes(bytes(frames))


def gui_music_test(audio_path: str | Path) -> tuple[bool, dict[str, Any]]:
    """Run the same MainWindow action used by the MUSIC button, offscreen."""
    if str(audio_path):
        path = Path(audio_path).expanduser().resolve(strict=False)
    else:
        path = app_paths().temp / "05 - 寒くないって笑った.wav"
        _write_synthetic_wav(path, duration_sec=3.0)
    if not path.is_file():
        return False, {"gui_music": "FAIL", "error": f"Audio file not found: {path}"}
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from .ui_app import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        window.session.music_path = str(path)
        window.lyrics.setPlainText("차가운 밤을 걷는다\n다시 빛을 향해 간다")
        window.music_source.setText(f"Selected music: {path.name}")
        window._analyze_music()
        app.processEvents()
        audio_map = window.session.audio_map
        payload = {
            "gui_music": "PASS",
            "file": path.name,
            "duration": window.music_duration.text(),
            "tempo": window.music_tempo.text(),
            "beat": window.music_beats.text(),
            "transitions": window.music_transitions.text(),
            "audio_map": bool(audio_map and window.audio_summary.toPlainText().strip()),
            "mv_timeline": bool(window.session.mv_timeline and window.timeline_summary.toPlainText().strip()),
        }
        window.close()
        ok = all(payload[key] for key in ("audio_map", "mv_timeline")) and all(
            payload[key] != "-" for key in ("duration", "tempo", "beat", "transitions")
        )
        payload["gui_music"] = "PASS" if ok else "FAIL"
        return ok, payload
    except Exception as exc:
        configure_logging().exception("GUI music path test failed")
        return False, {"gui_music": "FAIL", "file": path.name, "error": str(exc)}


def world_bible_smoke_test() -> tuple[bool, dict[str, Any]]:
    """Exercise the real World Bible save button path and dark form UI."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    paths = app_paths()
    directory = paths.temp / f"world-bible-smoke-{uuid.uuid4().hex}"
    directory.mkdir(parents=True)
    target = directory / "05_寒くないって笑った_session.json"
    try:
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QMessageBox, QWidget
        from .session import LyricsWorldSession
        from .ui_app import MainWindow

        app = QApplication.instance() or QApplication([])
        window = MainWindow(); window.resize(1100, 720); window.show(); app.processEvents()
        from .models import AudioMap, AudioTransition
        window.session.lyrics_text = "차가운 밤을 걷는다\n바람과 파도 소리를 듣는다\n다시 빛을 향해 간다\n새벽의 문을 연다"
        window.session.duration_sec = 30.0
        window.session.audio_map = AudioMap(
            source_path="synthetic-world-bible.wav",
            duration_sec=30.0,
            sample_rate=44100,
            tempo_bpm=92.3,
            transitions=[
                AudioTransition(
                    transition_id="AT001", time_sec=14.0, strength=0.8,
                    character="energy_rise", reasons=["world bible smoke"],
                )
            ],
        )
        window.session.analyze(); window.session.promote_selected_concept(); window._refresh_from_session()

        # Simulate a 1.0.2 partial World Bible: preserve user edits and fill only missing fields.
        manual_thesis = "사용자가 직접 수정한 기존 감정 논지"
        window.session.world_bible.emotional_thesis = manual_thesis
        window.session.world_bible.time_period = ""
        window.session.world_bible.palette = []
        window.session.world_bible.material_language = []
        window.session.world_bible.weather_rules = []
        window.session.world_bible.lighting_rules = []
        window.session.world_bible.camera_rules = []
        window._refresh_from_session()
        partial_button = window.world_bible_draft_button.text()
        partial_fill_ok = window._promote_world_bible()
        partial_preserved = (
            partial_fill_ok
            and window.session.world_bible.emotional_thesis == manual_thesis
            and not window._world_bible_missing_keys()
            and "빈 항목 자동 보강" in partial_button
        )

        dialog_calls = 0
        original_dialog = QFileDialog.getSaveFileName
        original_information = QMessageBox.information
        original_critical = QMessageBox.critical
        def choose_target(*args, **kwargs):
            nonlocal dialog_calls
            dialog_calls += 1
            return str(target), "JSON (*.json)"
        QFileDialog.getSaveFileName = choose_target
        QMessageBox.information = lambda *args, **kwargs: None
        QMessageBox.critical = lambda *args, **kwargs: None
        try:
            first_value = "패키지 첫 저장 감정 원칙"
            window.bible_fields["emotional_thesis"].setPlainText(first_value)
            window._save_world_bible()
            first_exists = target.is_file() and window.session.session_path == target.resolve()
            first_reopen = LyricsWorldSession.import_file(target)
            first_preserved = bool(first_reopen.world_bible and first_reopen.world_bible.emotional_thesis == first_value)
            second_value = "같은 JSON 재저장 감정 원칙"
            window.bible_fields["emotional_thesis"].setPlainText(second_value)
            window._save_world_bible()
            second_reopen = LyricsWorldSession.import_file(target)
            second_preserved = bool(second_reopen.world_bible and second_reopen.world_bible.emotional_thesis == second_value)
            window.session.session_path = None
            QFileDialog.getSaveFileName = lambda *args, **kwargs: ("", "")
            window.bible_fields["emotional_thesis"].setPlainText("메모리에만 남는 변경")
            window._save_world_bible()
            cancel_message = window.statusBar().currentMessage()
            cancel_safe = "저장 완료" not in cancel_message and "파일 저장이 취소" in cancel_message
        finally:
            QFileDialog.getSaveFileName = original_dialog
            QMessageBox.information = original_information
            QMessageBox.critical = original_critical

        expected_labels = {
            "Premise", "Emotional thesis", "Reality rules", "Time period", "Visual language",
            "Palette", "Materials", "Weather rules", "Lighting rules", "Camera rules",
            "Recurring motifs", "Forbidden elements", "Lyric foundation (읽기 전용)",
        }
        host = window.findChild(QWidget, "worldBibleHost")
        labels = window.findChildren(QLabel, "formLabel")
        window._switch(3); app.processEvents()
        color = host.palette().color(QPalette.Window) if host else None
        dark_host = bool(color and max(color.red(), color.green(), color.blue()) < 80)
        editable_keys = (
            "premise", "emotional_thesis", "reality_rules", "time_period",
            "visual_language", "palette", "material_language", "weather_rules",
            "lighting_rules", "camera_rules", "recurring_motifs", "forbidden_elements",
        )
        generated_complete = all(bool(getattr(window.session.world_bible, key)) for key in editable_keys)
        camera_uses_music = any(
            ("모든 비트" in rule or "음악 변화점" in rule or "dolly" in rule or "medium" in rule)
            for rule in window.session.world_bible.camera_rules
        )
        payload = {
            "world_bible": "PASS", "file": target.name,
            "generated_fields": sum(bool(getattr(window.session.world_bible, key)) for key in editable_keys),
            "generated_complete": generated_complete,
            "camera_uses_music": camera_uses_music,
            "partial_fill_preserved": partial_preserved,
            "first_save_exists": first_exists, "first_save_preserved": first_preserved,
            "same_json_resave": second_preserved and dialog_calls == 1, "dialog_calls": dialog_calls,
            "cancel_safe": cancel_safe, "cancel_message": cancel_message, "label_count": len(labels),
            "labels_complete": {label.text() for label in labels} == expected_labels,
            "dark_host": dark_host, "usable_1100x720": window.width() >= 1100 and window.height() >= 720,
            "window_title": window.windowTitle() == f"MV Director Studio {APP_VERSION}",
            "sidebar_release": any(f"Release {APP_VERSION}" in label.text() for label in window.findChildren(QLabel)),
            "session_schema": SESSION_SCHEMA,
        }
        window.close(); app.processEvents()
        ok = payload["label_count"] == 13 and all(payload[key] for key in (
            "first_save_exists", "first_save_preserved", "same_json_resave", "cancel_safe",
            "labels_complete", "dark_host", "usable_1100x720", "window_title", "sidebar_release",
            "generated_complete", "camera_uses_music", "partial_fill_preserved",
        ))
        payload["world_bible"] = "PASS" if ok else "FAIL"
        return ok, payload
    except Exception as exc:
        configure_logging(paths).exception("World Bible packaged smoke failed")
        return False, {"world_bible": "FAIL", "error": str(exc)}
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def release_stress_test() -> tuple[bool, dict[str, Any]]:
    """Packaged, real-dependency release exercise. No media-analysis mocks."""
    paths = app_paths()
    directory = paths.temp / f"release-stress-{uuid.uuid4().hex}"
    unicode_dir = directory / "한글 日本語 space"
    unicode_dir.mkdir(parents=True)
    results: dict[str, Any] = {"release_stress": "FAIL"}
    try:
        import importlib.util
        import numpy
        import scipy
        import librosa
        import soundfile
        from .editor import RenderEngine, RenderCancelled, build_rough_cut, probe_media
        from .models import AudioMap, CameraSpec, ReferenceRole, ShotSpec
        from .reference_vault import ReferenceVault
        from .result_takes import GenerationTake, TakeManager
        from .session import LyricsWorldSession
        from .technical_qc import analyze_take
        from .music_engine import analyze_audio

        music = unicode_dir / "05 - 寒くないって笑った.wav"
        _write_synthetic_wav(music)
        music_hash = hashlib.sha256(music.read_bytes()).hexdigest()

        maps = [analyze_audio(music) for _ in range(10)]
        if not all(item.duration_sec > 0 and item.sample_rate > 0 and
                   item.onset_times_sec is not None and item.beat_times_sec is not None and
                   item.transitions is not None and item.sections for item in maps):
            raise AssertionError("music analysis result is incomplete")

        session_path = unicode_dir / "세션 保存 session.json"
        session = LyricsWorldSession(music_path=str(music), audio_map=maps[-1], project_dir=unicode_dir)
        reference = unicode_dir / "참조 日本語 image.png"
        reference.write_bytes(b"reference-source")
        ReferenceVault(session.references, unicode_dir).add(reference, ReferenceRole.COMPOSITION)
        for _ in range(20):
            session.export(session_path)
            session = LyricsWorldSession.import_file(session_path)
        if not session.references or not session.references[0].file_exists(session.project_dir):
            detail = session.references[0].path if session.references else "<missing metadata>"
            raise AssertionError(f"reference path did not survive session round-trip: {detail}")

        tools = discover_ffmpeg()
        if not tools.render_ready:
            raise AssertionError("FFmpeg render requirements are unavailable")
        video = unicode_dir / "Take 日本語 01.mp4"
        subprocess.run([tools.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=blue:s=320x180:r=24:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
                       check=True, shell=False)
        video_hash = hashlib.sha256(video.read_bytes()).hexdigest()
        shot = ShotSpec(shot_id="B001-S01", beat_id="B001", start_sec=0, end_sec=2,
                        narrative_function="stress", subject="shape", action="moves", environment="field",
                        composition="center", camera=CameraSpec(framing="wide"), lighting="soft",
                        emotional_note="calm")
        session.shots = [shot]
        manager = TakeManager(session.generation_takes, session.shots, [], unicode_dir, session.take_id_counters)
        take = manager.register(video, shot.shot_id, now="stress")
        manager.accept(take.take_id)
        rejected = GenerationTake(**{**take.model_dump(), "take_id": "TAKE-B001-S01-002", "status": "rejected"})
        candidate = GenerationTake(**{**take.model_dump(), "take_id": "TAKE-B001-S01-003", "status": "candidate"})
        session.generation_takes.extend([rejected, candidate])
        session.edit_timeline = build_rough_cut(session)
        if [clip.take_id for clip in session.edit_timeline.clips] != [take.take_id]:
            raise AssertionError("rough cut included a non-accepted take")
        qc, _ = analyze_take(take, shot, unicode_dir)
        if qc.status == "BLOCKED":
            raise AssertionError("technical QC blocked valid synthetic video")

        finals = []
        renderer = RenderEngine(ffmpeg_path=tools.ffmpeg_path, cache_dir=paths.cache / "release-stress")
        for index in range(3):
            final = unicode_dir / f"Final 결과 {index + 1}.mp4"
            renderer.render(session, final)
            if not final.is_file() or not probe_media(final, tools.ffprobe_path).has_audio:
                raise AssertionError("final render output is invalid")
            finals.append(final)

        protected_final = unicode_dir / "Final protected.mp4"
        protected_final.write_bytes(b"existing-final")
        cancelled = threading.Event(); cancelled.set()
        try:
            renderer.render(session, protected_final, cancel=cancelled)
        except RenderCancelled:
            pass
        if protected_final.read_bytes() != b"existing-final":
            raise AssertionError("cancel changed an existing final")
        if hashlib.sha256(music.read_bytes()).hexdigest() != music_hash or hashlib.sha256(video.read_bytes()).hexdigest() != video_hash:
            raise AssertionError("source media changed")

        owned_cache = paths.cache / "owned-stress.tmp"
        owned_cache.write_bytes(b"cache")
        clear_owned_cache(paths)
        if any(not item.exists() for item in (music, video, reference, session_path, protected_final, *finals)):
            raise AssertionError("cache cleanup removed user data")

        # Missing assets must produce recoverable findings/reports, never terminate the process.
        missing = GenerationTake(**{**take.model_dump(), "take_id": "TAKE-MISSING-001",
                                    "output_path": str(unicode_dir / "missing.mp4")})
        missing_qc, _ = analyze_take(missing, shot, unicode_dir)
        if missing_qc.status != "BLOCKED":
            raise AssertionError("missing take did not produce a recoverable QC result")

        for _ in range(10):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            from PySide6.QtWidgets import QApplication
            from .ui_app import MainWindow
            app = QApplication.instance() or QApplication([])
            window = MainWindow(); window.close(); app.processEvents()

        gui_ok, gui_payload = gui_music_test(music)
        if not gui_ok:
            raise AssertionError(f"GUI music action failed: {gui_payload}")
        optional = {name: bool(importlib.util.find_spec(name)) for name in
                    ("open_clip", "beat_this", "allin1", "opentimelineio")}
        results.update({
            "release_stress": "PASS", "session_round_trips": 20, "music_analysis_runs": 10,
            "ui_create_close_runs": 10, "final_render_runs": 3, "formats": ["WAV"],
            "qc": qc.status, "sources_immutable": True, "cancel_safety": True,
            "cache_safety": True, "missing_file_recovery": True,
            "optional_dependencies": optional, "gui_music": gui_payload,
            "dependency_versions": {"numpy": numpy.__version__, "scipy": scipy.__version__,
                                    "librosa": librosa.__version__, "soundfile": soundfile.__version__},
        })
        return True, results
    except Exception as exc:
        configure_logging(paths).exception("release stress test failed")
        results["error"] = str(exc)
        return False, results
    finally:
        shutil.rmtree(directory, ignore_errors=True)
