from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from .models import ReferenceRole, ShotSpec
from .optional_backends import openclip_availability
from .result_takes import GenerationTake, resolve_take_path
from .reference_vault import resolve_reference_path
from .story_engine import reference_is_eligible


SEMANTIC_ANALYZER_VERSION = "g5b-1"
PRIORITY_ROLES = {
    ReferenceRole.CHARACTER_MASTER, ReferenceRole.CHARACTER_WARDROBE,
    ReferenceRole.LOCATION_MASTER, ReferenceRole.PROP_MASTER, ReferenceRole.COLOR_LIGHT,
}


class SemanticBackend(Protocol):
    backend_id: str
    model_version: str

    def prompt_similarity(self, video_path: Path, prompt: str) -> float: ...
    def reference_similarity(self, video_path: Path, reference_paths: list[Path]) -> float: ...


class OpenClipSemanticBackend:
    """Lazy OpenCLIP adapter. It only loads an explicitly supplied local checkpoint."""

    backend_id = "OPENCLIP"

    def __init__(self, model_name: str, checkpoint_path: str | Path):
        self.model_name = model_name
        self.checkpoint_path = Path(checkpoint_path).expanduser().resolve(strict=False)
        self.model_version = f"{model_name}:{self.checkpoint_path.name}"
        self._runtime = None

    def _load(self):
        if self._runtime is not None:
            return self._runtime
        if not self.checkpoint_path.is_file():
            raise ValueError("OpenCLIP 로컬 checkpoint를 찾을 수 없습니다. 자동 다운로드는 수행하지 않습니다.")
        try:
            import open_clip
            import torch
        except ImportError as exc:
            raise RuntimeError("OpenCLIP 선택 기능을 사용할 수 없습니다.") from exc
        model, _, preprocess = open_clip.create_model_and_transforms(
            self.model_name, pretrained=str(self.checkpoint_path), device="cpu"
        )
        model.eval()
        self._runtime = (model, preprocess, open_clip.get_tokenizer(self.model_name), torch)
        return self._runtime

    def _video_images(self, video_path: Path):
        from PIL import Image
        _, frames = _representative_hsv(video_path)
        return [Image.fromarray(frame[:, :, ::-1]) for frame in frames]

    def prompt_similarity(self, video_path: Path, prompt: str) -> float:
        model, preprocess, tokenizer, torch = self._load()
        images = torch.stack([preprocess(image) for image in self._video_images(video_path)])
        text = tokenizer([prompt])
        with torch.no_grad():
            image_features = model.encode_image(images)
            text_features = model.encode_text(text)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)
        return float((image_features @ text_features.T).mean().item())

    def reference_similarity(self, video_path: Path, reference_paths: list[Path]) -> float:
        from PIL import Image
        model, preprocess, _, torch = self._load()
        video_images = self._video_images(video_path)
        reference_images = []
        for path in reference_paths:
            if path.suffix.casefold() in {".mp4", ".mov", ".webm", ".mkv", ".m4v"}:
                frames = self._video_images(path)
                reference_images.append(frames[len(frames) // 2])
            else:
                reference_images.append(Image.open(path).convert("RGB"))
        with torch.no_grad():
            video_features = model.encode_image(torch.stack([preprocess(image) for image in video_images]))
            reference_features = model.encode_image(torch.stack([preprocess(image) for image in reference_images]))
            video_features /= video_features.norm(dim=-1, keepdim=True)
            reference_features /= reference_features.norm(dim=-1, keepdim=True)
        return float((video_features @ reference_features.T).mean().item())


class VisualQCFinding(BaseModel):
    finding_id: str
    group: str
    status: str
    summary_ko: str
    technical_detail: str = ""
    value: float | None = None


class SemanticQCReport(BaseModel):
    report_id: str
    take_id: str
    shot_id: str
    analyzer_version: str = SEMANTIC_ANALYZER_VERSION
    backend: str = "NONE"
    backend_model_version: str = ""
    findings: list[VisualQCFinding] = Field(default_factory=list)
    eligible_reference_ids: list[str] = Field(default_factory=list)
    source_fingerprint: dict[str, Any] = Field(default_factory=dict)


def _representative_hsv(path: Path, positions: tuple[float, ...] = (0.1, 0.5, 0.9)):
    import cv2
    import numpy as np

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"Cannot read video: {path}")
    count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
    histograms = []
    frames = []
    for position in positions:
        capture.set(cv2.CAP_PROP_POS_FRAMES, min(count - 1, int((count - 1) * position)))
        ok, frame = capture.read()
        if not ok:
            continue
        frame = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [24, 24], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        histograms.append(hist.flatten())
        frames.append(frame)
    capture.release()
    if not histograms:
        raise ValueError(f"No readable frames: {path}")
    return np.asarray(histograms), frames


def palette_drift_score(path: str | Path) -> float:
    import cv2
    import numpy as np

    histograms, _ = _representative_hsv(Path(path))
    if len(histograms) < 2:
        return 0.0
    distances = [cv2.compareHist(a.astype("float32"), b.astype("float32"), cv2.HISTCMP_BHATTACHARYYA)
                 for a, b in zip(histograms, histograms[1:])]
    return round(float(np.mean(distances)), 4)


def palette_reference_distance(video_path: Path, reference_paths: list[Path]) -> float:
    import cv2
    import numpy as np

    video_histograms, _ = _representative_hsv(video_path)
    video_hist = np.mean(video_histograms, axis=0).astype("float32")
    distances = []
    for path in reference_paths:
        if path.suffix.casefold() in {".mp4", ".mov", ".webm", ".mkv", ".m4v"}:
            histograms, _ = _representative_hsv(path)
            reference_hist = np.mean(histograms, axis=0).astype("float32")
        else:
            image = cv2.imread(str(path))
            if image is None:
                continue
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            reference_hist = cv2.calcHist([hsv], [0, 1], None, [24, 24], [0, 180, 0, 256]).flatten()
            cv2.normalize(reference_hist, reference_hist)
        distances.append(cv2.compareHist(video_hist, reference_hist, cv2.HISTCMP_BHATTACHARYYA))
    return round(float(min(distances)), 4) if distances else 0.0


def frame_boundary_distance(previous_path: Path, next_path: Path) -> float:
    import cv2
    previous, _ = _representative_hsv(previous_path, (0.95,))
    following, _ = _representative_hsv(next_path, (0.05,))
    return round(float(cv2.compareHist(previous[0].astype("float32"), following[0].astype("float32"), cv2.HISTCMP_BHATTACHARYYA)), 4)


def eligible_visual_references(session, shot: ShotSpec):
    return sorted(
        (reference for reference in session.references
         if reference.role in PRIORITY_ROLES and reference_is_eligible(reference, shot) and reference.file_exists(session.project_dir)),
        key=lambda reference: (reference.role not in PRIORITY_ROLES, -reference.lock_strength, reference.reference_id),
    )


def semantic_source_fingerprint(session, take: GenerationTake, backend_id: str = "NONE") -> dict[str, Any]:
    path = resolve_take_path(take, session.project_dir)
    stat = path.stat()
    shot = next((item for item in session.shots if item.shot_id == take.shot_id), None)
    pack = next((item for item in session.generation_packs if item.pack_id == take.pack_id), None)
    references = eligible_visual_references(session, shot) if shot else []
    reference_state = []
    for reference in references:
        ref_path = resolve_reference_path(reference, session.project_dir)
        ref_stat = ref_path.stat()
        reference_state.append((reference.reference_id, str(ref_path.resolve()), ref_stat.st_size, ref_stat.st_mtime_ns))
    context = repr((pack.main_prompt if pack else None, reference_state)).encode("utf-8")
    return {
        "path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
        "version": SEMANTIC_ANALYZER_VERSION, "backend": backend_id,
        "context_hash": hashlib.sha256(context).hexdigest(),
    }


def semantic_report_is_fresh(session, take: GenerationTake, report: SemanticQCReport) -> bool:
    try:
        return report.source_fingerprint == semantic_source_fingerprint(session, take, report.backend)
    except OSError:
        return False


def analyze_visual_semantic(session, take: GenerationTake, backend: SemanticBackend | None = None) -> SemanticQCReport:
    path = resolve_take_path(take, session.project_dir)
    shot = next((item for item in session.shots if item.shot_id == take.shot_id), None)
    pack = next((item for item in session.generation_packs if item.pack_id == take.pack_id), None)
    findings: list[VisualQCFinding] = []
    drift = palette_drift_score(path)
    findings.append(VisualQCFinding(
        finding_id="palette_drift", group="색감 / 연속성",
        status="REVIEW" if drift > 0.55 else "PASS",
        summary_ko="클립 안에서 색감 변화가 큽니다." if drift > 0.55 else "클립 안의 색감 흐름이 안정적입니다.",
        technical_detail=f"HSV histogram drift={drift}", value=drift,
    ))
    references = eligible_visual_references(session, shot) if shot else []
    color_references = [reference for reference in references if reference.role == ReferenceRole.COLOR_LIGHT]
    if color_references:
        color_paths = [resolve_reference_path(reference, session.project_dir) for reference in color_references]
        color_distance = palette_reference_distance(path, color_paths)
        findings.append(VisualQCFinding(
            finding_id="palette_reference", group="색감 / 연속성",
            status="REVIEW" if color_distance > 0.7 else "PASS",
            summary_ko="COLOR / LIGHT 레퍼런스와 색감 차이가 있을 수 있습니다." if color_distance > 0.7 else "COLOR / LIGHT 레퍼런스와 색감이 대체로 이어집니다.",
            technical_detail=f"HSV reference distance={color_distance}", value=color_distance,
        ))
    if backend is None:
        state = openclip_availability()
        text = "선택 기능을 사용할 수 없습니다." if state.state != "AVAILABLE" else "고급 분석을 선택하면 의미 유사도를 검사할 수 있습니다."
        findings.append(VisualQCFinding(finding_id="semantic_optional", group="프롬프트 / 레퍼런스", status="N/A", summary_ko=text,
                                        technical_detail=f"OPENCLIP={state.state}; no score penalty"))
        if pack is None:
            findings.append(VisualQCFinding(finding_id="prompt_similarity", group="프롬프트 / 레퍼런스", status="N/A",
                                            summary_ko="연결된 Prompt Pack이 없어 의미 비교를 건너뜁니다."))
        if not references:
            findings.append(VisualQCFinding(finding_id="reference_similarity", group="프롬프트 / 레퍼런스", status="N/A",
                                            summary_ko="이 Shot에 적용되는 레퍼런스가 없어 비교를 건너뜁니다."))
    else:
        if pack:
            score = float(backend.prompt_similarity(path, pack.main_prompt))
            findings.append(VisualQCFinding(finding_id="prompt_similarity", group="프롬프트 / 레퍼런스",
                                            status="REVIEW" if score < 0.25 else "PASS",
                                            summary_ko="프롬프트와 장면 의미 차이를 확인해 주세요." if score < 0.25 else "프롬프트와 장면 의미가 대체로 비슷합니다.",
                                            technical_detail=f"semantic similarity={score:.4f}", value=score))
        else:
            findings.append(VisualQCFinding(finding_id="prompt_similarity", group="프롬프트 / 레퍼런스", status="N/A",
                                            summary_ko="연결된 Prompt Pack이 없어 의미 비교를 건너뜁니다."))
        if references:
            paths = [resolve_reference_path(reference, session.project_dir) for reference in references]
            score = float(backend.reference_similarity(path, paths))
            findings.append(VisualQCFinding(finding_id="reference_similarity", group="프롬프트 / 레퍼런스",
                                            status="REVIEW" if score < 0.25 else "PASS",
                                            summary_ko="레퍼런스와 시각 차이가 있을 수 있습니다." if score < 0.25 else "레퍼런스와 시각적으로 대체로 비슷합니다.",
                                            technical_detail=f"visual similarity={score:.4f}", value=score))
        else:
            findings.append(VisualQCFinding(finding_id="reference_similarity", group="프롬프트 / 레퍼런스", status="N/A",
                                            summary_ko="이 Shot에 적용되는 레퍼런스가 없어 비교를 건너뜁니다."))
    stat = path.stat()
    return SemanticQCReport(
        report_id=f"SQC-{take.take_id}-{stat.st_mtime_ns}", take_id=take.take_id, shot_id=take.shot_id,
        backend=backend.backend_id if backend else "NONE",
        backend_model_version=backend.model_version if backend else "",
        findings=findings, eligible_reference_ids=[reference.reference_id for reference in references],
        source_fingerprint=semantic_source_fingerprint(session, take, backend.backend_id if backend else "NONE"),
    )


def adjacent_visual_findings(session) -> list[VisualQCFinding]:
    accepted = {take.shot_id: take for take in session.generation_takes if take.status == "accepted"}
    ordered = sorted((shot for shot in session.shots if shot.shot_id in accepted), key=lambda shot: (shot.start_sec, shot.shot_id))
    findings: list[VisualQCFinding] = []
    for previous, current in zip(ordered, ordered[1:]):
        previous_take, current_take = accepted[previous.shot_id], accepted[current.shot_id]
        distance = frame_boundary_distance(resolve_take_path(previous_take, session.project_dir), resolve_take_path(current_take, session.project_dir))
        narrative_text = f"{previous.narrative_function} {current.narrative_function}".casefold()
        intentional_change = (
            previous.beat_id != current.beat_id
            or previous.environment.strip().casefold() != current.environment.strip().casefold()
            or any(token in narrative_text for token in ("transition", "hard cut", "전환", "몽타주"))
        )
        continuity_expected = bool(previous.continuity_out or current.continuity_in)
        if distance > 0.7 and continuity_expected and not intentional_change:
            findings.append(VisualQCFinding(finding_id=f"continuity:{previous.shot_id}:{current.shot_id}", group="색감 / 연속성", status="REVIEW",
                                            summary_ko="이어지는 두 Shot의 화면 차이가 큽니다.", technical_detail=f"boundary_distance={distance}"))
        intent_differs = previous.narrative_function != current.narrative_function or previous.camera.model_dump() != current.camera.model_dump()
        if distance < 0.08 and intent_differs:
            findings.append(VisualQCFinding(finding_id=f"redundancy:{previous.shot_id}:{current.shot_id}", group="다른 Shot과 중복", status="REVIEW",
                                            summary_ko="역할이 다른 인접 Shot의 화면이 지나치게 비슷할 수 있습니다.", technical_detail=f"boundary_distance={distance}"))
    return findings
