from __future__ import annotations

import uuid
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path(request) -> Path:
    """Use the writable workspace on restricted Windows runners."""
    root = Path.cwd() / ".test_workspace"
    root.mkdir(exist_ok=True)
    target = root / f"{request.node.name}-{uuid.uuid4().hex}"
    target.mkdir()
    return target
