from __future__ import annotations

import json
import sys

from .release_runtime import (
    APP_VERSION, begin_run, configure_logging, end_run, log_uncaught,
    g3_dark_ui_smoke_test, gui_music_test, music_analysis_smoke_test, production_megagate_test,
    release_stress_test, render_smoke_test, series_studio_smoke_test, smoke_test, world_bible_smoke_test,
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
    if "--release-stress-test" in sys.argv:
        ok, payload = release_stress_test()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 5
    if "--gui-music-test" in sys.argv:
        index = sys.argv.index("--gui-music-test")
        path = sys.argv[index + 1] if index + 1 < len(sys.argv) else ""
        ok, payload = gui_music_test(path)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 6
    if "--world-bible-smoke-test" in sys.argv:
        ok, payload = world_bible_smoke_test()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 7
    if "--series-studio-smoke-test" in sys.argv:
        ok, payload = series_studio_smoke_test()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 8
    if "--g3-dark-ui-smoke-test" in sys.argv:
        ok, payload = g3_dark_ui_smoke_test()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 9
    if "--production-megagate-test" in sys.argv:
        ok, payload = production_megagate_test()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 10
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
