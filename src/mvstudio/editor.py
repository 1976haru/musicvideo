from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

from .optional_backends import BackendState
from .result_takes import GenerationTake, resolve_take_path
from .release_runtime import app_paths, configure_logging, discover_ffmpeg

if TYPE_CHECKING:
    from .session import LyricsWorldSession


RENDERER_VERSION = "g6-renderer-1.0"


@contextmanager
def _owned_workdir(parent: Path):
    path = parent / f".mvstudio-render-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class MediaInfo(BaseModel):
    path: str
    duration_sec: float = Field(gt=0)
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    fps: float = Field(default=0, ge=0)
    codec: str = ""
    has_audio: bool = False
    backend: str = ""
    warnings: list[str] = Field(default_factory=list)


class EditClip(BaseModel):
    clip_id: str
    shot_id: str
    take_id: str
    beat_id: str | None = None
    narrative_function: str = ""
    source_path: str
    timeline_start: float = Field(ge=0)
    timeline_end: float = Field(gt=0)
    source_in: float = Field(default=0, ge=0)
    source_out: float = Field(gt=0)
    source_duration: float = Field(gt=0)
    fit_status: Literal["trim_end", "exact", "unresolved_short", "hold_last"]
    framing: Literal["cover", "contain"] = "cover"
    qc_status: str = "N/A"

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.timeline_end <= self.timeline_start:
            raise ValueError("clip timeline end must be greater than start")
        if self.source_out <= self.source_in:
            raise ValueError("clip source_out must be greater than source_in")
        return self

    @property
    def target_duration(self) -> float:
        return round(self.timeline_end - self.timeline_start, 6)

    @property
    def source_span(self) -> float:
        return round(self.source_out - self.source_in, 6)


class EditGap(BaseModel):
    gap_id: str
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    resolution: Literal["unresolved", "black", "hold_previous"] = "unresolved"

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("gap end must be greater than start")
        return self

    @property
    def duration_sec(self) -> float:
        return round(self.end_sec - self.start_sec, 6)


class EditTimeline(BaseModel):
    timeline_id: str = "EDIT-001"
    clips: list[EditClip] = Field(default_factory=list)
    gaps: list[EditGap] = Field(default_factory=list)
    overlaps: list[tuple[str, str]] = Field(default_factory=list)
    duration_sec: float = Field(default=0, ge=0)
    created_at: str = ""
    updated_at: str = ""
    renderer_version: str = RENDERER_VERSION


class RenderSettings(BaseModel):
    preset_id: str = "youtube_1080p"
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    fps: float = Field(default=30.0, gt=0, le=120)
    quality: int = Field(default=20, ge=0, le=51)
    framing: Literal["cover", "contain"] = "cover"


OUTPUT_PRESETS: dict[str, RenderSettings] = {
    "youtube_1080p": RenderSettings(),
    "youtube_4k": RenderSettings(preset_id="youtube_4k", width=3840, height=2160),
    "vertical_1080p": RenderSettings(preset_id="vertical_1080p", width=1080, height=1920),
    "square_1080p": RenderSettings(preset_id="square_1080p", width=1080, height=1080),
}


class RenderRecord(BaseModel):
    render_id: str
    kind: Literal["preview", "final"]
    output_path: str
    created_at: str
    settings: RenderSettings
    timeline_fingerprint: str
    renderer_version: str = RENDERER_VERSION
    succeeded: bool = True


class ReadinessIssue(BaseModel):
    code: str
    severity: Literal["blocker", "warning"]
    message: str
    shot_id: str | None = None
    action: str = ""


class EditReadiness(BaseModel):
    status: Literal["READY", "READY_WITH_WARNINGS", "BLOCKED"]
    issues: list[ReadinessIssue] = Field(default_factory=list)
    ready_shots: int = 0
    total_shots: int = 0


class RenderCancelled(RuntimeError):
    pass


class RenderFailure(RuntimeError):
    pass


def _status_for_executable(name: str) -> BackendState:
    return "AVAILABLE" if shutil.which(name) else "NOT_INSTALLED"


def ffmpeg_status() -> BackendState:
    return discover_ffmpeg().state


def ffprobe_status() -> BackendState:
    return discover_ffmpeg().state


def _rational(value: str | None) -> float:
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    if "/" in value:
        left, right = value.split("/", 1)
        return float(left) / float(right) if float(right) else 0.0
    return float(value)


def probe_media(path: str | Path, ffprobe_path: str | None = None) -> MediaInfo:
    source = Path(path).expanduser().resolve(strict=True)
    executable = ffprobe_path or discover_ffmpeg().ffprobe_path or None
    probe_error = ""
    if executable:
        argv = [executable, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)]
        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                check=False, shell=False,
            )
            if completed.returncode == 0:
                payload = json.loads(completed.stdout or "{}")
                streams = payload.get("streams", [])
                video = next((item for item in streams if item.get("codec_type") == "video"), {})
                duration = float(video.get("duration") or payload.get("format", {}).get("duration") or 0)
                if duration > 0:
                    return MediaInfo(
                        path=str(source), duration_sec=duration,
                        width=int(video.get("width") or 0), height=int(video.get("height") or 0),
                        fps=_rational(video.get("avg_frame_rate") or video.get("r_frame_rate")),
                        codec=str(video.get("codec_name") or ""),
                        has_audio=any(item.get("codec_type") == "audio" for item in streams), backend="ffprobe",
                    )
            probe_error = (completed.stderr or "ffprobe could not read media").strip()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            probe_error = str(exc)
    try:
        import cv2  # type: ignore
        capture = cv2.VideoCapture(str(source))
        if capture.isOpened():
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
            frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration = frames / fps if fps > 0 and frames > 0 else 0
            info = MediaInfo(
                path=str(source), duration_sec=duration,
                width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
                height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0), fps=fps,
                codec="", has_audio=False, backend="opencv",
                warnings=["오디오 정보는 확인하지 못했습니다."] + ([probe_error] if probe_error else []),
            )
            capture.release()
            return info
        capture.release()
    except (ImportError, OSError, ValueError):
        pass
    raise ValueError("미디어 파일을 읽을 수 없습니다.")


def _latest_qc_status(session: LyricsWorldSession, take_id: str) -> str:
    reports = [item for item in session.qc_reports if item.take_id == take_id]
    return reports[-1].status if reports else "N/A"


def _accepted_by_shot(session: LyricsWorldSession) -> dict[str, list[GenerationTake]]:
    result: dict[str, list[GenerationTake]] = {}
    for take in session.generation_takes:
        if take.status == "accepted":
            result.setdefault(take.shot_id, []).append(take)
    return result


def build_rough_cut(
    session: LyricsWorldSession,
    settings: RenderSettings | None = None,
    probe: Callable[[str | Path], MediaInfo] = probe_media,
) -> EditTimeline:
    settings = settings or session.render_settings
    previous = session.edit_timeline
    old_clips = {item.shot_id: item for item in previous.clips} if previous else {}
    old_gaps = {(round(item.start_sec, 3), round(item.end_sec, 3)): item for item in previous.gaps} if previous else {}
    accepted = _accepted_by_shot(session)
    shots = sorted(session.shots, key=lambda item: (item.start_sec, item.end_sec, item.shot_id))
    clips: list[EditClip] = []
    overlaps: list[tuple[str, str]] = []
    for left, right in zip(shots, shots[1:]):
        if right.start_sec < left.end_sec - 1e-6:
            overlaps.append((left.shot_id, right.shot_id))
    for shot in shots:
        matches = accepted.get(shot.shot_id, [])
        if len(matches) != 1:
            continue
        take = matches[0]
        source = resolve_take_path(take, session.project_dir)
        if not source.is_file():
            continue
        try:
            media = probe(source)
        except (OSError, ValueError):
            continue
        old = old_clips.get(shot.shot_id)
        source_in = old.source_in if old and old.take_id == take.take_id else 0.0
        source_in = min(max(source_in, 0.0), max(0.0, media.duration_sec - 0.001))
        needed = shot.duration_sec
        available = media.duration_sec - source_in
        if available + 1e-3 >= needed:
            status = "exact" if abs(available - needed) <= 1e-3 else "trim_end"
            source_out = source_in + needed
        else:
            status = "hold_last" if old and old.take_id == take.take_id and old.fit_status == "hold_last" else "unresolved_short"
            source_out = media.duration_sec
        clips.append(EditClip(
            clip_id=f"CLIP-{shot.shot_id}", shot_id=shot.shot_id, take_id=take.take_id,
            beat_id=shot.beat_id, narrative_function=shot.narrative_function,
            source_path=str(source), timeline_start=shot.start_sec, timeline_end=shot.end_sec,
            source_in=source_in, source_out=source_out, source_duration=media.duration_sec,
            fit_status=status, framing=old.framing if old and old.take_id == take.take_id else settings.framing,
            qc_status=_latest_qc_status(session, take.take_id),
        ))
    gaps: list[EditGap] = []
    cursor = 0.0
    for shot in shots:
        if shot.start_sec > cursor + 1e-6:
            key = (round(cursor, 3), round(shot.start_sec, 3))
            gaps.append(EditGap(gap_id=f"GAP-{len(gaps)+1:03d}", start_sec=cursor, end_sec=shot.start_sec,
                                resolution=old_gaps[key].resolution if key in old_gaps else "unresolved"))
        cursor = max(cursor, shot.end_sec)
    duration = session.audio_map.duration_sec if session.audio_map else (session.duration_sec or cursor)
    if duration > cursor + 1e-6:
        key = (round(cursor, 3), round(duration, 3))
        gaps.append(EditGap(gap_id=f"GAP-{len(gaps)+1:03d}", start_sec=cursor, end_sec=duration,
                            resolution=old_gaps[key].resolution if key in old_gaps else "unresolved"))
    stamp = datetime.now(timezone.utc).isoformat()
    return EditTimeline(clips=clips, gaps=gaps, overlaps=overlaps, duration_sec=max(duration, cursor),
                        created_at=previous.created_at if previous else stamp, updated_at=stamp)


def _music_path(session: LyricsWorldSession) -> Path | None:
    if not session.music_path:
        return None
    path = Path(session.music_path)
    if not path.is_absolute() and session.project_dir:
        path = session.project_dir / path
    return path.expanduser().resolve(strict=False)


def check_readiness(
    session: LyricsWorldSession,
    timeline: EditTimeline | None = None,
    settings: RenderSettings | None = None,
    probe: Callable[[str | Path], MediaInfo] = probe_media,
) -> EditReadiness:
    timeline = timeline or session.edit_timeline
    settings = settings or session.render_settings
    issues: list[ReadinessIssue] = []
    if ffmpeg_status() != "AVAILABLE":
        issues.append(ReadinessIssue(code="FFMPEG_UNAVAILABLE", severity="blocker",
                                     message="영상 내보내기 도구(FFmpeg)를 찾을 수 없습니다."))
    music = _music_path(session)
    music_duration = 0.0
    if music is None or not music.is_file():
        issues.append(ReadinessIssue(code="MUSIC_MISSING", severity="blocker", message="음악 파일이 준비되지 않았습니다."))
    else:
        try:
            probed_music = probe(music)
            music_duration = session.audio_map.duration_sec if session.audio_map else probed_music.duration_sec
        except (OSError, ValueError):
            issues.append(ReadinessIssue(code="MUSIC_UNREADABLE", severity="blocker", message="음악 파일을 읽을 수 없습니다."))
    if not session.shots:
        issues.append(ReadinessIssue(code="NO_SHOTS", severity="blocker", message="편집할 Shot이 없습니다."))
    accepted = _accepted_by_shot(session)
    for shot in session.shots:
        matches = accepted.get(shot.shot_id, [])
        if not matches:
            issues.append(ReadinessIssue(code="NO_ACCEPTED_TAKE", severity="blocker", shot_id=shot.shot_id,
                                         message=f"{shot.shot_id}: 사용할 Take가 없습니다.", action="다른 Take 선택"))
        elif len(matches) > 1:
            issues.append(ReadinessIssue(code="MULTIPLE_ACCEPTED", severity="blocker", shot_id=shot.shot_id,
                                         message=f"{shot.shot_id}: accepted Take가 중복되었습니다."))
        elif not resolve_take_path(matches[0], session.project_dir).is_file():
            issues.append(ReadinessIssue(code="ACCEPTED_FILE_MISSING", severity="blocker", shot_id=shot.shot_id,
                                         message=f"{shot.shot_id}: accepted 영상 파일이 없습니다."))
        else:
            try:
                probe(resolve_take_path(matches[0], session.project_dir))
            except (OSError, ValueError):
                issues.append(ReadinessIssue(code="ACCEPTED_UNREADABLE", severity="blocker", shot_id=shot.shot_id,
                                             message=f"{shot.shot_id}: accepted 영상 파일을 읽을 수 없습니다."))
    if settings.width <= 0 or settings.height <= 0 or settings.fps <= 0:
        issues.append(ReadinessIssue(code="INVALID_SETTINGS", severity="blocker", message="출력 설정이 올바르지 않습니다."))
    if timeline is None:
        issues.append(ReadinessIssue(code="NO_ROUGH_CUT", severity="blocker", message="먼저 자동 편집을 만드세요."))
    else:
        clip_shots = {clip.shot_id for clip in timeline.clips}
        for shot in session.shots:
            if len(accepted.get(shot.shot_id, [])) == 1 and shot.shot_id not in clip_shots:
                issues.append(ReadinessIssue(code="ROUGH_CUT_MISSING_CLIP", severity="blocker", shot_id=shot.shot_id,
                                             message=f"{shot.shot_id}: Rough Cut clip을 만들 수 없습니다."))
        for left, right in timeline.overlaps:
            issues.append(ReadinessIssue(code="SHOT_OVERLAP", severity="blocker", message=f"{left} / {right}: Shot 시간이 겹칩니다."))
        for clip in timeline.clips:
            if clip.fit_status == "unresolved_short":
                issues.append(ReadinessIssue(code="SHORT_CLIP", severity="blocker", shot_id=clip.shot_id,
                                             message=f"{clip.shot_id}: 영상 길이가 부족합니다.", action="마지막 프레임 유지 또는 다른 Take 선택"))
            if clip.fit_status == "hold_last":
                issues.append(ReadinessIssue(code="HOLD_LAST", severity="warning", shot_id=clip.shot_id,
                                             message=f"{clip.shot_id}: 마지막 프레임을 유지합니다."))
            if clip.qc_status in {"REVIEW", "REGENERATE"}:
                issues.append(ReadinessIssue(code="QC_WARNING", severity="warning", shot_id=clip.shot_id,
                                             message=f"{clip.shot_id}: QC {clip.qc_status} Take를 사용 중입니다."))
            try:
                media = probe(clip.source_path)
                source_ratio = media.width / media.height if media.height else 0
                output_ratio = settings.width / settings.height
                if source_ratio and abs(source_ratio - output_ratio) > 0.08:
                    issues.append(ReadinessIssue(code="ASPECT_MISMATCH", severity="warning", shot_id=clip.shot_id,
                                                 message=f"{clip.shot_id}: 화면 비율을 맞추기 위해 framing이 적용됩니다."))
                if media.width and (media.width < settings.width or media.height < settings.height):
                    issues.append(ReadinessIssue(code="LOW_RESOLUTION", severity="warning", shot_id=clip.shot_id,
                                                 message=f"{clip.shot_id}: 원본 해상도가 출력보다 낮습니다."))
                if media.fps and abs(media.fps - settings.fps) > 0.5:
                    issues.append(ReadinessIssue(code="FPS_MISMATCH", severity="warning", shot_id=clip.shot_id,
                                                 message=f"{clip.shot_id}: 프레임 속도를 변환합니다."))
            except (OSError, ValueError):
                pass
        for gap in timeline.gaps:
            if gap.resolution == "unresolved":
                issues.append(ReadinessIssue(code="UNRESOLVED_GAP", severity="blocker", message="Shot 사이 빈 시간을 해결해야 합니다."))
            elif gap.resolution == "black":
                issues.append(ReadinessIssue(code="BLACK_GAP", severity="warning", message="빈 시간에 검은 화면을 사용합니다."))
            else:
                issues.append(ReadinessIssue(code="HOLD_GAP", severity="warning", message="빈 시간에 이전 화면을 유지합니다."))
        if music_duration and timeline.duration_sec > music_duration + 0.05:
            issues.append(ReadinessIssue(code="VIDEO_LONGER_THAN_MUSIC", severity="blocker", message="편집 영상이 원곡보다 깁니다."))
    blockers = [item for item in issues if item.severity == "blocker"]
    status = "BLOCKED" if blockers else "READY_WITH_WARNINGS" if issues else "READY"
    return EditReadiness(status=status, issues=issues, ready_shots=len(timeline.clips) if timeline else 0,
                         total_shots=len(session.shots))


def source_fingerprint(path: str | Path) -> dict[str, Any]:
    source = Path(path).resolve(strict=True)
    stat = source.stat()
    return {"path": str(source), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def segment_cache_key(clip: EditClip, settings: RenderSettings) -> str:
    payload = {
        "source": source_fingerprint(clip.source_path), "source_in": clip.source_in,
        "source_out": clip.source_out, "target_duration": clip.target_duration,
        "width": settings.width, "height": settings.height, "fps": settings.fps,
        "framing": clip.framing, "fit": clip.fit_status, "renderer": RENDERER_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def timeline_fingerprint(timeline: EditTimeline, settings: RenderSettings) -> str:
    payload = {"timeline": timeline.model_dump(mode="json"), "settings": settings.model_dump(mode="json")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def framing_filter(framing: str, width: int, height: int, fps: float) -> str:
    if framing == "contain":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
    else:
        scale = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    return f"{scale},setsar=1,fps={fps:g},format=yuv420p"


def parse_ffmpeg_progress(line: str, duration_sec: float) -> float | None:
    key, separator, value = line.strip().partition("=")
    if not separator:
        return None
    if key in {"out_time_us", "out_time_ms"}:
        # ffmpeg commonly reports microseconds for both keys.
        seconds = float(value) / 1_000_000
        return min(100.0, max(0.0, seconds / duration_sec * 100)) if duration_sec > 0 else 0.0
    if key == "progress" and value == "end":
        return 100.0
    return None


class RenderEngine:
    def __init__(self, ffmpeg_path: str | None = None, cache_dir: str | Path | None = None,
                 probe: Callable[[str | Path], MediaInfo] = probe_media):
        self.ffmpeg_path = ffmpeg_path or discover_ffmpeg().ffmpeg_path or None
        self.cache_dir = Path(cache_dir or app_paths().cache / "render-segments")
        self.probe = probe
        self.expert_log: list[str] = []

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg_path)

    def _run(self, argv: list[str], duration: float, progress: Callable[[float], None] | None,
             cancel: threading.Event | None) -> None:
        if not self.ffmpeg_path:
            raise RenderFailure("영상 내보내기 도구(FFmpeg)를 찾을 수 없습니다.")
        safe_argv = [argv[0], "-loglevel", "error", *argv[1:]] if "-loglevel" not in argv else argv
        logger = configure_logging()
        logger.info("ffmpeg stage output=%s", Path(argv[-1]).name)
        process = subprocess.Popen(safe_argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   encoding="utf-8", errors="replace", shell=False)
        while True:
            if cancel and cancel.is_set():
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise RenderCancelled("영상 내보내기를 취소했습니다.")
            line = process.stdout.readline() if process.stdout else ""
            if line and progress:
                parsed = parse_ffmpeg_progress(line, duration)
                if parsed is not None:
                    progress(parsed)
            if process.poll() is not None:
                break
        stderr = process.stderr.read() if process.stderr else ""
        if stderr:
            self.expert_log.append(stderr)
        logger.info("ffmpeg return_code=%s output=%s", process.returncode, Path(argv[-1]).name)
        if process.returncode:
            logger.error("ffmpeg failed tail=%s", stderr[-4000:])
            raise RenderFailure("영상 내보내기에 실패했습니다. 원본 파일은 변경되지 않았습니다.")

    def _segment_argv(self, clip: EditClip, output: Path, settings: RenderSettings) -> list[str]:
        video_filter = framing_filter(clip.framing, settings.width, settings.height, settings.fps)
        if clip.fit_status == "hold_last":
            hold = max(0.0, clip.target_duration - clip.source_span)
            video_filter += f",tpad=stop_mode=clone:stop_duration={hold:.6f}"
        return [str(self.ffmpeg_path), "-hide_banner", "-y", "-ss", f"{clip.source_in:.6f}",
                "-i", clip.source_path, "-an", "-t", f"{clip.target_duration:.6f}", "-vf", video_filter,
                "-c:v", "libx264", "-preset", "fast", "-crf", str(settings.quality),
                "-progress", "pipe:1", "-nostats", str(output)]

    def _gap_argv(self, gap: EditGap, output: Path, settings: RenderSettings, previous: EditClip | None) -> list[str]:
        if gap.resolution == "hold_previous" and previous:
            seek = max(previous.source_in, previous.source_out - 0.04)
            return [str(self.ffmpeg_path), "-hide_banner", "-y", "-ss", f"{seek:.6f}", "-i", previous.source_path,
                    "-an", "-vf", framing_filter(previous.framing, settings.width, settings.height, settings.fps) +
                    f",tpad=stop_mode=clone:stop_duration={gap.duration_sec:.6f}",
                    "-t", f"{gap.duration_sec:.6f}", "-c:v", "libx264", "-preset", "fast", "-crf", str(settings.quality),
                    "-progress", "pipe:1", "-nostats", str(output)]
        return [str(self.ffmpeg_path), "-hide_banner", "-y", "-f", "lavfi", "-i",
                f"color=c=black:s={settings.width}x{settings.height}:r={settings.fps:g}:d={gap.duration_sec:.6f}",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-progress", "pipe:1", "-nostats", str(output)]

    def render(self, session: LyricsWorldSession, output_path: str | Path, *, kind: Literal["preview", "final"] = "final",
               progress: Callable[[str, int, int, float], None] | None = None,
               cancel: threading.Event | None = None) -> RenderRecord:
        timeline = session.edit_timeline
        if timeline is None:
            raise RenderFailure("먼저 자동 편집을 만드세요.")
        settings = session.render_settings.model_copy(deep=True)
        if kind == "preview":
            ratio = min(1.0, 1280 / settings.width, 720 / settings.height)
            settings.width = max(2, int(settings.width * ratio) // 2 * 2)
            settings.height = max(2, int(settings.height * ratio) // 2 * 2)
            settings.quality = max(settings.quality, 28)
        ready = check_readiness(session, timeline, session.render_settings, probe=self.probe)
        if ready.status == "BLOCKED":
            raise RenderFailure("편집 준비 문제를 먼저 해결하세요.")
        output = Path(output_path).expanduser().resolve(strict=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        music = _music_path(session)
        if not music:
            raise RenderFailure("음악 파일이 준비되지 않았습니다.")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        ordered: list[tuple[float, EditClip | EditGap]] = [(item.timeline_start, item) for item in timeline.clips]
        ordered.extend((item.start_sec, item) for item in timeline.gaps)
        ordered.sort(key=lambda pair: pair[0])
        # Keep owned intermediates beside the user-selected output. This is both
        # Windows-friendly and avoids crossing filesystems during atomic replace.
        with _owned_workdir(output.parent) as work:
            segments: list[Path] = []
            previous: EditClip | None = None
            total = len(ordered) + 2
            for index, (_, item) in enumerate(ordered, 1):
                if cancel and cancel.is_set():
                    raise RenderCancelled("영상 내보내기를 취소했습니다.")
                if isinstance(item, EditClip):
                    target = self.cache_dir / f"{segment_cache_key(item, settings)}.mp4"
                    argv = self._segment_argv(item, target, settings)
                    previous = item
                    label = f"Shot {index} / {len(ordered)}"
                else:
                    target = work / f"gap-{index:03d}.mp4"
                    argv = self._gap_argv(item, target, settings, previous)
                    label = f"빈 시간 {index} / {len(ordered)}"
                if not target.is_file():
                    self._run(argv, item.target_duration if isinstance(item, EditClip) else item.duration_sec,
                              (lambda value, i=index, lab=label: progress(lab, i, total, value) if progress else None), cancel)
                segments.append(target)
            manifest = work / "segments.txt"
            manifest.write_text(
                "".join(f"file '{item.as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n" for item in segments),
                encoding="utf-8",
            )
            joined = work / "joined.mp4"
            self._run([str(self.ffmpeg_path), "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
                       "-an", "-c:v", "copy", "-progress", "pipe:1", "-nostats", str(joined)],
                      timeline.duration_sec, lambda value: progress("영상 연결", total-1, total, value) if progress else None, cancel)
            partial = work / f"partial{output.suffix or '.mp4'}"
            self._run([str(self.ffmpeg_path), "-hide_banner", "-y", "-i", str(joined), "-i", str(music),
                       "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                       "-t", f"{timeline.duration_sec:.6f}", "-progress", "pipe:1", "-nostats", str(partial)],
                      timeline.duration_sec, lambda value: progress("원곡 연결", total, total, value) if progress else None, cancel)
            if cancel and cancel.is_set():
                raise RenderCancelled("영상 내보내기를 취소했습니다.")
            os.replace(partial, output)
        stamp = datetime.now(timezone.utc).isoformat()
        return RenderRecord(render_id=f"RENDER-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", kind=kind,
                            output_path=str(output), created_at=stamp, settings=settings,
                            timeline_fingerprint=timeline_fingerprint(timeline, settings))


def export_edit_plan(session: LyricsWorldSession, path: str | Path) -> Path:
    if session.edit_timeline is None:
        raise ValueError("먼저 자동 편집을 만드세요.")
    target = Path(path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0", "type": "MV Director Edit Plan",
        "timeline": session.edit_timeline.model_dump(mode="json"),
        "render_settings": session.render_settings.model_dump(mode="json"),
        "music_path": str(_music_path(session) or ""), "renderer_version": RENDERER_VERSION,
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    with tempfile.NamedTemporaryFile("wb", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def otio_status() -> BackendState:
    try:
        import importlib.util
        return "AVAILABLE" if importlib.util.find_spec("opentimelineio") else "NOT_INSTALLED"
    except (ImportError, ValueError):
        return "LOAD_FAILED"


def export_otio(session: LyricsWorldSession, path: str | Path) -> Path:
    if session.edit_timeline is None:
        raise ValueError("먼저 자동 편집을 만드세요.")
    try:
        import opentimelineio as otio  # type: ignore
    except (ImportError, OSError) as exc:
        raise RuntimeError("OpenTimelineIO 선택 기능을 사용할 수 없습니다.") from exc
    rate = session.render_settings.fps
    timeline = otio.schema.Timeline(name="MV Director Studio Rough Cut")
    track = otio.schema.Track(name="Video", kind=otio.schema.TrackKind.Video)
    timeline.tracks.append(track)
    shots = {shot.shot_id: shot for shot in session.shots}
    entries: list[tuple[float, EditClip | EditGap]] = [
        (item.timeline_start, item) for item in session.edit_timeline.clips
    ]
    entries.extend((item.start_sec, item) for item in session.edit_timeline.gaps)
    for _, item in sorted(entries, key=lambda entry: entry[0]):
        if isinstance(item, EditGap):
            gap = otio.schema.Gap(
                name=item.gap_id,
                source_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(0, rate),
                    duration=otio.opentime.RationalTime(item.duration_sec * rate, rate),
                ),
            )
            gap.metadata["mvstudio"] = {"resolution": item.resolution, "timeline_start": item.start_sec,
                                         "timeline_end": item.end_sec}
            track.append(gap)
            continue
        shot = shots.get(item.shot_id)
        reference = otio.schema.ExternalReference(target_url=Path(item.source_path).as_uri())
        source_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(item.source_in * rate, rate),
            duration=otio.opentime.RationalTime(item.source_span * rate, rate),
        )
        clip = otio.schema.Clip(name=item.shot_id, media_reference=reference, source_range=source_range)
        clip.metadata["mvstudio"] = {
            "shot_id": item.shot_id, "take_id": item.take_id, "beat_id": item.beat_id,
            "narrative_function": item.narrative_function, "qc_status": item.qc_status,
            "lineage": {"shot_id": item.shot_id, "take_id": item.take_id},
            "timeline_start": item.timeline_start, "timeline_end": item.timeline_end,
            "fit_status": item.fit_status, "framing": item.framing,
        }
        track.append(clip)
    target = Path(path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    otio.adapters.write_to_file(timeline, str(target))
    return target
