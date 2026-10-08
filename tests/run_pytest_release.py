from __future__ import annotations

import os
import sys

import pytest


def main() -> None:
    # Run the complete suite. The guarded pytest_sessionfinish hook exits with pytest's
    # real status before Windows native-extension interpreter teardown can crash.
    os.environ["MVSTUDIO_RELEASE_PYTEST_HARD_EXIT"] = "1"
    code = int(pytest.main(["-q"]))
    # Fallback for environments where the hook is not loaded.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    main()
