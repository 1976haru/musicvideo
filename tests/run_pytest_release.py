from __future__ import annotations

import os
import re
import subprocess
import sys


RESULT_RE = re.compile(r"MVSTUDIO_PYTEST_RESULT=(\d+)")


def main() -> int:
    env = os.environ.copy()
    env["MVSTUDIO_RELEASE_PYTEST_CHILD"] = "1"
    process = subprocess.Popen(
        [sys.executable, "-m", "pytest", "-q"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    reported_status: int | None = None
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        match = RESULT_RE.search(line)
        if match:
            reported_status = int(match.group(1))
    native_status = process.wait()

    # The marker is emitted only after pytest has completed the full suite and computed
    # its official exit status. A later Windows DLL-unload crash must not overwrite that
    # test result. If the marker is missing, treat any child abnormality as a real failure.
    if reported_status is not None:
        if native_status != 0:
            print(
                f"[release-pytest] pytest result={reported_status}; "
                f"ignored post-result native teardown status={native_status}",
                flush=True,
            )
        return reported_status
    print(
        f"[release-pytest] missing pytest result marker; child status={native_status}",
        file=sys.stderr,
        flush=True,
    )
    return native_status if 0 <= native_status <= 255 else 1


if __name__ == "__main__":
    raise SystemExit(main())
