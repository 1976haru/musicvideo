from __future__ import annotations

import uuid
import os
from pathlib import Path

import pytest

os.environ.setdefault("MVSTUDIO_APPDATA", str(Path.cwd() / ".test_workspace" / "appdata"))


@pytest.fixture
def tmp_path(request) -> Path:
    """Use the writable workspace on restricted Windows runners."""
    root = Path.cwd() / ".test_workspace"
    root.mkdir(exist_ok=True)
    target = root / f"{request.node.name}-{uuid.uuid4().hex}"
    target.mkdir()
    return target

def pytest_sessionfinish(session, exitstatus):
    """CI child reports pytest's authoritative result before native DLL teardown."""
    if os.environ.get("MVSTUDIO_RELEASE_PYTEST_CHILD") != "1":
        return
    print(f"MVSTUDIO_PYTEST_RESULT={int(exitstatus)}", flush=True)
