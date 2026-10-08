from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from mvstudio.release_runtime import g3_dark_ui_smoke_test


def test_story_room_and_shot_board_do_not_render_windows_white_backgrounds(tmp_path, monkeypatch):
    monkeypatch.setenv("MVSTUDIO_APPDATA", str(tmp_path / "appdata"))
    ok, payload = g3_dark_ui_smoke_test()
    assert ok, payload
    assert payload["selectors_ok"]
    assert payload["object_names_ok"]
    assert payload["max_white_ratio"] < payload["threshold"]
    assert payload["story_white_ratios"]["evidence"] < 0.30
    assert payload["story_white_ratios"]["beat_list"] < 0.30
    assert payload["shot_white_ratios"]["shot_list"] < 0.30
