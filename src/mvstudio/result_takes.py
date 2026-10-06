from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .manual_generation import ManualGenerationPack
from .models import ShotSpec


VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


class DuplicateTakeIDError(ValueError):
    pass


class DuplicateTakePathError(ValueError):
    pass


class GenerationTake(BaseModel):
    take_id: str
    shot_id: str
    pack_id: str | None = None
    source_profile_id: str | None = None
    output_path: str
    created_at: str
    imported_at: str
    status: Literal["candidate", "accepted", "rejected"] = "candidate"
    reject_reason: str = ""
    notes: str = ""
    rating: int | None = Field(default=None, ge=1, le=5)
    duration_sec: float | None = Field(default=None, gt=0)
    original_filename: str
    file_size_bytes: int | None = Field(default=None, ge=0)

    def file_missing(self, project_dir: str | Path | None = None) -> bool:
        return not resolve_take_path(self, project_dir).is_file()


class TakeWarning(BaseModel):
    code: Literal[
        "ORPHAN_SHOT", "ORPHAN_PACK", "MISSING_FILE", "PACK_SHOT_MISMATCH",
        "MULTIPLE_ACCEPTED", "DUPLICATE_TAKE_ID", "NO_PACK_SNAPSHOT",
        "STALE_TAKE_COUNTER",
    ]
    message: str
    take_ids: list[str] = Field(default_factory=list)


def portable_take_path(source: str | Path, project_dir: str | Path | None) -> str:
    resolved = Path(source).expanduser().resolve(strict=False)
    if project_dir is not None:
        base = Path(project_dir).expanduser().resolve(strict=False)
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError:
            pass
    return str(resolved)


def resolve_take_path(take_or_path: GenerationTake | str, project_dir: str | Path | None) -> Path:
    stored = take_or_path.output_path if isinstance(take_or_path, GenerationTake) else take_or_path
    candidate = Path(stored)
    if not candidate.is_absolute() and project_dir is not None:
        candidate = Path(project_dir) / candidate
    return candidate.expanduser().resolve(strict=False)


def next_take_id(shot_id: str, existing_ids: set[str] | list[str], last_number: int = 0) -> tuple[str, int]:
    prefix = f"TAKE-{shot_id}-"
    numbers = []
    for take_id in existing_ids:
        if take_id.startswith(prefix) and take_id[len(prefix):].isdigit():
            numbers.append(int(take_id[len(prefix):]))
    number = max([last_number, *numbers], default=0) + 1
    take_id = f"{prefix}{number:03d}"
    while take_id in existing_ids:
        number += 1
        take_id = f"{prefix}{number:03d}"
    return take_id, number


def take_id_floor(shot_id: str, takes: list[GenerationTake]) -> int:
    prefix = f"TAKE-{shot_id}-"
    return max(
        (int(take.take_id[len(prefix):]) for take in takes
         if take.take_id.startswith(prefix) and take.take_id[len(prefix):].isdigit()),
        default=0,
    )


def reconcile_take_counters(takes: list[GenerationTake], counters: dict[str, int]) -> None:
    """Raise stale counters without changing any imported Take or decreasing a counter."""
    for shot_id in {take.shot_id for take in takes}:
        counters[shot_id] = max(counters.get(shot_id, 0), take_id_floor(shot_id, takes))


class TakeManager:
    """Metadata-only result service. It never writes, moves, renames, or deletes video files."""

    def __init__(
        self,
        takes: list[GenerationTake],
        shots: list[ShotSpec],
        packs: list[ManualGenerationPack],
        project_dir: str | Path | None,
        id_counters: dict[str, int] | None = None,
    ):
        self.takes = takes
        self.shots = shots
        self.packs = packs
        self.project_dir = Path(project_dir).resolve(strict=False) if project_dir else None
        self.id_counters = id_counters if id_counters is not None else {}

    def _take(self, take_id: str) -> GenerationTake:
        matches = [take for take in self.takes if take.take_id == take_id]
        if not matches:
            raise ValueError(f"Unknown take_id: {take_id}")
        if len(matches) > 1:
            raise DuplicateTakeIDError(f"Duplicate take_id: {take_id}")
        return matches[0]

    def register(
        self,
        source: str | Path,
        shot_id: str,
        pack_id: str | None = None,
        *,
        duration_sec: float | None = None,
        now: str | None = None,
    ) -> GenerationTake:
        source_path = Path(source).expanduser().resolve(strict=True)
        if not source_path.is_file():
            raise ValueError(f"Result video is not a file: {source_path}")
        if source_path.suffix.casefold() not in VIDEO_EXTENSIONS:
            raise ValueError(f"Unsupported result video extension: {source_path.suffix}")
        if shot_id not in {shot.shot_id for shot in self.shots}:
            raise ValueError(f"Unknown shot_id: {shot_id}")
        normalized = os.path.normcase(str(source_path))
        for take in self.takes:
            if take.shot_id == shot_id and os.path.normcase(str(resolve_take_path(take, self.project_dir))) == normalized:
                raise DuplicateTakePathError(f"This result file is already registered for {shot_id}")
        existing = {take.take_id for take in self.takes}
        take_id, number = next_take_id(shot_id, existing, self.id_counters.get(shot_id, 0))
        self.id_counters[shot_id] = number
        pack = next((item for item in self.packs if item.pack_id == pack_id), None)
        stamp = now or datetime.now(timezone.utc).isoformat()
        take = GenerationTake(
            take_id=take_id, shot_id=shot_id, pack_id=pack_id,
            source_profile_id=pack.profile_id if pack else None,
            output_path=portable_take_path(source_path, self.project_dir),
            created_at=stamp, imported_at=stamp, status="candidate",
            duration_sec=duration_sec, original_filename=source_path.name,
            file_size_bytes=source_path.stat().st_size,
        )
        if take.take_id in existing:
            raise DuplicateTakeIDError(f"Duplicate take_id: {take.take_id}")
        self.takes.append(take)
        return take

    def unregister(self, take_id: str) -> GenerationTake:
        take = self._take(take_id)
        self.takes.remove(take)
        return take

    def relink_take(self, take_id: str, source: str | Path) -> GenerationTake:
        take = self._take(take_id)
        source_path = Path(source).expanduser().resolve(strict=True)
        if not source_path.is_file():
            raise ValueError(f"Result video is not a file: {source_path}")
        if source_path.suffix.casefold() not in VIDEO_EXTENSIONS:
            raise ValueError(f"Unsupported result video extension: {source_path.suffix}")
        normalized = os.path.normcase(str(source_path))
        for other in self.takes:
            if other is not take and other.shot_id == take.shot_id:
                if os.path.normcase(str(resolve_take_path(other, self.project_dir))) == normalized:
                    raise DuplicateTakePathError(f"This result file is already registered for {take.shot_id}")
        take.output_path = portable_take_path(source_path, self.project_dir)
        take.original_filename = source_path.name
        take.file_size_bytes = source_path.stat().st_size
        return take

    def relink(self, take_id: str, source: str | Path) -> GenerationTake:
        return self.relink_take(take_id, source)

    def accept(self, take_id: str) -> GenerationTake:
        selected = self._take(take_id)
        for take in self.takes:
            if take.shot_id == selected.shot_id and take.status == "accepted":
                take.status = "candidate"
        selected.status = "accepted"
        selected.reject_reason = ""
        return selected

    def reject(self, take_id: str, reason: str) -> GenerationTake:
        take = self._take(take_id)
        take.status = "rejected"
        take.reject_reason = reason.strip()
        return take

    def restore_candidate(self, take_id: str) -> GenerationTake:
        take = self._take(take_id)
        take.status = "candidate"
        take.reject_reason = ""
        return take

    def update_notes(self, take_id: str, *, rating: int | None, notes: str, reject_reason: str) -> GenerationTake:
        take = self._take(take_id)
        validated = GenerationTake.model_validate({
            **take.model_dump(), "rating": rating, "notes": notes, "reject_reason": reject_reason,
        })
        index = self.takes.index(take)
        self.takes[index] = validated
        return validated

    def accepted_take_for_shot(self, shot_id: str) -> GenerationTake | None:
        accepted = [take for take in self.takes if take.shot_id == shot_id and take.status == "accepted"]
        return accepted[0] if len(accepted) == 1 else None

    def shot_result_status(self, shot_id: str) -> str:
        related = [take for take in self.takes if take.shot_id == shot_id]
        accepted = [take for take in related if take.status == "accepted"]
        if len(accepted) > 1:
            return "NEEDS_REVIEW"
        if accepted:
            return "FINAL_MISSING_FILE" if accepted[0].file_missing(self.project_dir) else "FINAL_ACCEPTED"
        if any(take.status == "candidate" for take in related):
            return "HAS_CANDIDATES"
        return "NEEDS_REVIEW" if related else "NO_TAKE"

    def warnings(self, take: GenerationTake | None = None) -> list[TakeWarning]:
        warnings: list[TakeWarning] = []
        target = [take] if take is not None else list(self.takes)
        shot_ids = {shot.shot_id for shot in self.shots}
        pack_map = {pack.pack_id: pack for pack in self.packs}
        for item in target:
            if item.shot_id not in shot_ids:
                warnings.append(TakeWarning(code="ORPHAN_SHOT", message=f"Shot not found: {item.shot_id}", take_ids=[item.take_id]))
            if item.pack_id is None:
                warnings.append(TakeWarning(code="NO_PACK_SNAPSHOT", message="No Pack Snapshot", take_ids=[item.take_id]))
            elif item.pack_id not in pack_map:
                warnings.append(TakeWarning(code="ORPHAN_PACK", message=f"Pack not found: {item.pack_id}", take_ids=[item.take_id]))
            elif pack_map[item.pack_id].shot_id != item.shot_id:
                warnings.append(TakeWarning(code="PACK_SHOT_MISMATCH", message=f"Pack {item.pack_id} belongs to {pack_map[item.pack_id].shot_id}", take_ids=[item.take_id]))
            if item.file_missing(self.project_dir):
                warnings.append(TakeWarning(code="MISSING_FILE", message=f"Result file missing: {item.output_path}", take_ids=[item.take_id]))
        counts: dict[str, list[str]] = {}
        for item in self.takes:
            counts.setdefault(item.take_id, []).append(item.take_id)
        for take_id, duplicates in counts.items():
            if len(duplicates) > 1:
                warnings.append(TakeWarning(code="DUPLICATE_TAKE_ID", message=f"Duplicate take_id: {take_id}", take_ids=duplicates))
        by_shot: dict[str, list[str]] = {}
        for item in self.takes:
            if item.status == "accepted":
                by_shot.setdefault(item.shot_id, []).append(item.take_id)
        for shot_id, take_ids in by_shot.items():
            if len(take_ids) > 1:
                warnings.append(TakeWarning(code="MULTIPLE_ACCEPTED", message=f"Multiple accepted takes for {shot_id}", take_ids=take_ids))
        for shot_id in {item.shot_id for item in self.takes}:
            floor = take_id_floor(shot_id, self.takes)
            if self.id_counters.get(shot_id, 0) < floor:
                warnings.append(TakeWarning(
                    code="STALE_TAKE_COUNTER",
                    message=f"Take counter for {shot_id} is below existing ID floor {floor}",
                    take_ids=[item.take_id for item in self.takes if item.shot_id == shot_id],
                ))
        return warnings

    def warnings_for_take(self, take: GenerationTake) -> list[TakeWarning]:
        """Only warnings relevant to the inspected Take/Shot."""
        return [
            warning for warning in self.warnings(take)
            if warning.code not in {"DUPLICATE_TAKE_ID", "MULTIPLE_ACCEPTED", "STALE_TAKE_COUNTER"}
            or take.take_id in warning.take_ids
        ]


def audit_take_state(
    takes: list[GenerationTake],
    shots: list[ShotSpec],
    packs: list[ManualGenerationPack],
    project_dir: str | Path | None,
    counters: dict[str, int] | None = None,
) -> list[TakeWarning]:
    """Deterministic, read-only audit for imported or live Take metadata."""
    return TakeManager(takes, shots, packs, project_dir, counters).warnings()
