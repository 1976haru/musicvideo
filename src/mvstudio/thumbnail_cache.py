from __future__ import annotations

import hashlib
from pathlib import Path


class ThumbnailCache:
    """Owns derived thumbnail locations only; source reference files remain read-only."""

    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir)

    def target_for(self, source: str | Path, size: int = 320) -> Path:
        source_path = Path(source).resolve(strict=False)
        fingerprint = hashlib.sha256(f"{source_path}|{size}".encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{fingerprint}.png"

    def prepare(self) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir
