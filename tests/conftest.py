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
    """Dispose the shared Qt application before CPython module teardown on Windows."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return
        QApplication.closeAllWindows()
        app.processEvents()
        app.quit()
        app.processEvents()
        try:
            import shiboken6
            if shiboken6.isValid(app):
                shiboken6.delete(app)
        except (ImportError, RuntimeError):
            pass
    except (ImportError, RuntimeError):
        pass
