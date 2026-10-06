from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .models import ShotSpec
from .result_takes import GenerationTake, resolve_take_path


ANALYZER_VERSION = "g5a-1"
DEFAULT_OPTIONS = {"max_samples": 180, "black_threshold": 18.0, "freeze_delta": 1.5, "flicker_jump": 32.0}


class QCMetric(BaseModel):
    metric_id: str
    category: str
    label: str
    raw_value: Any = None
    normalized_score: float | None = Field(default=None, ge=0, le=100)
    severity: Literal["info", "good", "warning", "bad", "blocked"] = "info"
    summary_ko: str
    technical_detail: str = ""
    recommendation: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)


class TakeQCReport(BaseModel):
    report_id: str
    take_id: str
    shot_id: str
    created_at: str
    analyzer_version: str = ANALYZER_VERSION
    status: Literal["PASS", "REVIEW", "REGENERATE", "BLOCKED"]
    overall_score: float | None = Field(default=None, ge=0, le=100)
    metrics: list[QCMetric] = Field(default_factory=list)
    beginner_summary: list[str] = Field(default_factory=list)
    recommended_action: str
    sampled_frame_times: list[float] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    analysis_options: dict[str, Any] = Field(default_factory=dict)
    source_fingerprint: dict[str, Any] = Field(default_factory=dict)


def source_fingerprint(path: Path, options: dict[str, Any]) -> dict[str, Any]:
    stat = path.stat()
    return {
        "resolved_path": str(path.resolve(strict=False)),
        "file_size": stat.st_size,
        "modified_ns": stat.st_mtime_ns,
        "analyzer_version": ANALYZER_VERSION,
        "options": options,
    }


def fingerprint_key(fingerprint: dict[str, Any]) -> str:
    payload = json.dumps(fingerprint, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def report_is_fresh(report: TakeQCReport, path: Path, options: dict[str, Any]) -> bool:
    try:
        return report.analyzer_version == ANALYZER_VERSION and report.source_fingerprint == source_fingerprint(path, options)
    except OSError:
        return False


def _metric(metric_id: str, label: str, value: Any, severity: str, summary: str, detail: str = "", recommendation: str = "") -> QCMetric:
    return QCMetric(metric_id=metric_id, category="technical_temporal", label=label, raw_value=value,
                    severity=severity, summary_ko=summary, technical_detail=detail, recommendation=recommendation)


def _blocked(take: GenerationTake, reason: str, metric_id: str, path: Path | None = None) -> TakeQCReport:
    stamp = datetime.now(timezone.utc).isoformat()
    fingerprint = {}
    if path and path.exists():
        fingerprint = source_fingerprint(path, dict(DEFAULT_OPTIONS))
    return TakeQCReport(
        report_id=f"QC-{take.take_id}-{stamp}", take_id=take.take_id, shot_id=take.shot_id,
        created_at=stamp, status="BLOCKED", metrics=[_metric(metric_id, "파일 읽기", None, "blocked", reason)],
        beginner_summary=[reason, "현재 파일은 기술 검사를 진행할 수 없습니다.", "파일을 다시 연결한 뒤 검사를 다시 시작하세요."],
        recommended_action="파일 다시 연결", analysis_options=dict(DEFAULT_OPTIONS),
        source_fingerprint=fingerprint,
    )


def analyze_take(
    take: GenerationTake,
    shot: ShotSpec | None,
    project_dir: str | Path | None,
    *,
    options: dict[str, Any] | None = None,
    cached_reports: list[TakeQCReport] | None = None,
) -> tuple[TakeQCReport, bool]:
    """Read-only, CPU-friendly technical/temporal analysis. Returns (report, cache_hit)."""
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    path = resolve_take_path(take, project_dir)
    if not path.is_file():
        return _blocked(take, "결과 영상 파일을 찾을 수 없습니다.", "missing_file"), False
    for report in reversed(cached_reports or []):
        if report.take_id == take.take_id and report_is_fresh(report, path, opts):
            return report, True

    try:
        import cv2
        import numpy as np
    except ImportError:
        return _blocked(take, "영상 검사 구성요소(OpenCV)를 사용할 수 없습니다.", "analyzer_unavailable", path), False

    before = source_fingerprint(path, opts)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        return _blocked(take, "영상 파일을 읽을 수 없습니다.", "unreadable_video", path), False
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = frame_count / fps if fps > 0 and frame_count > 0 else 0.0
    if duration <= 0 or width <= 0 or height <= 0:
        capture.release()
        return _blocked(take, "영상 길이 또는 화면 정보를 확인할 수 없습니다.", "invalid_duration", path), False

    stride = max(1, frame_count // max(2, int(opts["max_samples"])))
    gray_frames: list[Any] = []
    times: list[float] = []
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if index % stride == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_frames.append(cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA))
            times.append(round(index / fps, 3))
        index += 1
    capture.release()
    if len(gray_frames) < 2:
        return _blocked(take, "분석할 수 있는 영상 프레임이 부족합니다.", "unreadable_frames", path), False

    luminance = np.array([float(frame.mean()) for frame in gray_frames])
    deltas = np.array([float(np.mean(cv2.absdiff(a, b))) for a, b in zip(gray_frames, gray_frames[1:])])
    sample_interval = stride / fps
    black_ratio = float(np.mean(luminance < float(opts["black_threshold"])))
    freeze_mask = deltas < float(opts["freeze_delta"])
    longest = run = 0
    for frozen in freeze_mask:
        run = run + 1 if frozen else 0
        longest = max(longest, run)
    freeze_sec = longest * sample_interval
    brightness_jumps = np.abs(np.diff(luminance))
    flicker_ratio = float(np.mean(brightness_jumps > float(opts["flicker_jump"]))) if len(brightness_jumps) else 0.0
    max_jump = float(brightness_jumps.max()) if len(brightness_jumps) else 0.0
    motion_mean = float(deltas.mean()) if len(deltas) else 0.0
    motion_category = "낮음" if motion_mean < 2.5 else "보통" if motion_mean < 10 else "높음"
    jitter_ratio = float(np.mean(deltas > max(18.0, motion_mean * 2.5))) if len(deltas) else 0.0

    metrics = [
        _metric("media_info", "영상 정보", {"duration_sec": duration, "fps": fps, "width": width, "height": height}, "good",
                "영상 파일을 정상적으로 읽었습니다.", f"{width}x{height}, {fps:.3f} fps, {duration:.3f}s"),
    ]
    expected = shot.duration_sec if shot else None
    mismatch = abs(duration - expected) / expected if expected and expected > 0 else 0.0
    if mismatch > 0.5:
        sev, summary = "bad", "필요한 Shot 길이와 결과 영상 길이 차이가 매우 큽니다."
    elif mismatch > 0.15:
        sev, summary = "warning", "필요한 Shot 길이와 결과 영상 길이가 다릅니다."
    else:
        sev, summary = "good", "영상 길이가 Shot에 적절합니다."
    metrics.append(_metric("duration_match", "길이 비교", round(mismatch, 4), sev, summary,
                           f"expected={expected}, actual={duration:.3f}, mismatch_ratio={mismatch:.4f}"))

    black_sev = "bad" if black_ratio > 0.55 else "warning" if black_ratio > 0.20 else "good"
    metrics.append(_metric("near_black", "어두운 화면", round(black_ratio, 4), black_sev,
                           "검은 화면이 너무 오래 이어집니다." if black_sev == "bad" else "어두운 구간을 확인해 주세요." if black_sev == "warning" else "지속되는 검은 화면이 없습니다.",
                           f"near_black_ratio={black_ratio:.4f}, threshold={opts['black_threshold']}"))
    freeze_sev = "bad" if freeze_sec >= max(2.0, duration * 0.45) else "warning" if freeze_sec >= 1.0 else "good"
    metrics.append(_metric("freeze", "멈춘 화면", round(freeze_sec, 3), freeze_sev,
                           "화면이 오래 멈춘 구간이 있습니다." if freeze_sev == "bad" else "화면이 멈춘 듯한 구간을 확인해 주세요." if freeze_sev == "warning" else "화면이 오래 멈춘 구간이 없습니다.",
                           f"longest_near_freeze_sec={freeze_sec:.3f}, delta_threshold={opts['freeze_delta']}"))
    flicker_sev = "bad" if flicker_ratio > 0.25 or max_jump > 100 else "warning" if flicker_ratio > 0.08 or max_jump > 65 else "good"
    metrics.append(_metric("flicker", "깜빡임", {"ratio": round(flicker_ratio, 4), "max_jump": round(max_jump, 3)}, flicker_sev,
                           "심한 밝기 깜빡임이 감지되었습니다." if flicker_sev == "bad" else "밝기가 갑자기 변하는 구간을 확인해 주세요." if flicker_sev == "warning" else "심한 깜빡임이 없습니다.",
                           f"jump_ratio={flicker_ratio:.4f}, max_jump={max_jump:.3f}"))
    jitter_sev = "warning" if jitter_ratio > 0.18 else "good"
    metrics.append(_metric("motion", "움직임", {"mean_delta": round(motion_mean, 3), "category": motion_category}, "info",
                           f"전체 움직임은 {motion_category} 수준입니다.", f"mean_frame_delta={motion_mean:.3f}"))
    metrics.append(_metric("instability", "화면 불안정", round(jitter_ratio, 4), jitter_sev,
                           "움직임이 불안정한 구간이 의심됩니다." if jitter_sev == "warning" else "심한 화면 불안정 징후가 없습니다.",
                           f"instability_spike_ratio={jitter_ratio:.4f}"))

    severities = {metric.severity for metric in metrics}
    status = "REGENERATE" if "bad" in severities else "REVIEW" if "warning" in severities else "PASS"
    score = max(0.0, 100.0 - 30 * sum(m.severity == "bad" for m in metrics) - 12 * sum(m.severity == "warning" for m in metrics))
    labels = {"PASS": "이 영상은 사용 가능한 상태입니다.", "REVIEW": "몇 가지 항목을 확인해 주세요.", "REGENERATE": "다시 생성하는 것을 권장합니다."}
    actions = {"PASS": "이 Take 사용", "REVIEW": "문제 장면 확인", "REGENERATE": "다시 생성하기"}
    reasons = [m.summary_ko for m in metrics if m.metric_id != "motion" and m.severity in {"bad", "warning"}]
    reasons += [m.summary_ko for m in metrics if m.severity == "good"]
    stamp = datetime.now(timezone.utc).isoformat()
    report = TakeQCReport(
        report_id=f"QC-{take.take_id}-{fingerprint_key(before)[:12]}", take_id=take.take_id, shot_id=take.shot_id,
        created_at=stamp, status=status, overall_score=score, metrics=metrics,
        beginner_summary=[labels[status], *reasons[:4]], recommended_action=actions[status],
        sampled_frame_times=times, analysis_options=opts, source_fingerprint=before,
    )
    return report, False
