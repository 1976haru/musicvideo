from __future__ import annotations

import json
import sys

from .release_runtime import (
    APP_VERSION, begin_run, configure_logging, end_run, log_uncaught,
    music_analysis_smoke_test, render_smoke_test, smoke_test,
)


def main() -> int:
    logger = configure_logging()
    logger.info("startup app_version=%s platform=%s python=%s", APP_VERSION, sys.platform, sys.version.split()[0])
    if "--smoke-test" in sys.argv:
        ok, payload = smoke_test()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 2
    if "--music-analysis-smoke-test" in sys.argv:
        ok, payload = music_analysis_smoke_test()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 4
    if "--render-smoke-test" in sys.argv:
        ok, payload = render_smoke_test()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 3
    previous_unclean = begin_run()
    sys.excepthook = log_uncaught
    try:
        from .ui_app import run_gui
        result = run_gui(previous_unclean=previous_unclean)
    except Exception:
        logger.exception("fatal startup/runtime failure")
        raise
    else:
        end_run()
        logger.info("clean shutdown")
        return result


if __name__ == "__main__":
    raise SystemExit(main())
