from __future__ import annotations

import os
import sys

import pytest


def main() -> None:
    # Run the complete suite. On Windows CI, PySide6/OpenCV/SciPy native destructors can
    # crash after pytest has already completed successfully. Exit immediately only after
    # pytest returns its real result code, preserving every test and failure.
    code = int(pytest.main(["-q"]))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    main()
