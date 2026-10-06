from __future__ import annotations

import re
from pathlib import Path

from .models import ReferenceAsset, ReferenceRole, ReferenceScope

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class DuplicateReferenceIDError(ValueError):
    pass


def portable_path(source: str | Path, project_dir: str | Path | None) -> str:
    """Store paths inside a project relatively; keep external files absolute."""
    source_path = Path(source).expanduser().resolve(strict=False)
    if project_dir is not None:
        root = Path(project_dir).expanduser().resolve(strict=False)
        try:
            return source_path.relative_to(root).as_posix()
        except ValueError:
            pass
    return str(source_path)


def resolve_reference_path(asset: ReferenceAsset, project_dir: str | Path | None) -> Path:
    path = Path(asset.path)
    if not path.is_absolute() and project_dir is not None:
        path = Path(project_dir) / path
    return path.resolve(strict=False)


class ReferenceVault:
    """Metadata-only vault. It never moves, renames, modifies, or deletes source files."""

    def __init__(self, assets: list[ReferenceAsset] | None = None, project_dir: str | Path | None = None):
        self.assets = assets if assets is not None else []
        self.project_dir = Path(project_dir).resolve(strict=False) if project_dir else None
        self._ensure_unique()

    def _ensure_unique(self) -> None:
        ids = [asset.reference_id for asset in self.assets]
        if len(ids) != len(set(ids)):
            raise DuplicateReferenceIDError("reference_id values must be unique")

    def next_id(self) -> str:
        used = {asset.reference_id for asset in self.assets}
        number = 1
        while f"REF{number:03d}" in used:
            number += 1
        return f"REF{number:03d}"

    def add(
        self,
        source: str | Path,
        role: ReferenceRole = ReferenceRole.COMPOSITION,
        *,
        reference_id: str | None = None,
        lock_strength: float = 0.8,
        applies_to: ReferenceScope = ReferenceScope.PROJECT,
        scope_id: str | None = None,
        notes: str = "",
        is_master: bool = False,
    ) -> ReferenceAsset:
        reference_id = reference_id or self.next_id()
        if not _ID_PATTERN.fullmatch(reference_id):
            raise ValueError("reference_id may contain only letters, numbers, '.', '_' and '-'")
        if any(item.reference_id == reference_id for item in self.assets):
            raise DuplicateReferenceIDError(f"Duplicate reference_id: {reference_id}")
        asset = ReferenceAsset(
            reference_id=reference_id,
            role=role,
            path=portable_path(source, self.project_dir),
            lock_strength=lock_strength,
            applies_to=applies_to,
            scope_id=scope_id,
            notes=notes,
            is_master=is_master,
        )
        self.assets.append(asset)
        return asset

    def remove(self, reference_id: str) -> ReferenceAsset:
        for index, asset in enumerate(self.assets):
            if asset.reference_id == reference_id:
                return self.assets.pop(index)
        raise KeyError(reference_id)

    def status(self, asset: ReferenceAsset) -> str:
        return "available" if resolve_reference_path(asset, self.project_dir).is_file() else "missing"
