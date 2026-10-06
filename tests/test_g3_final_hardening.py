from __future__ import annotations

from mvstudio.models import (
    CameraSpec, ReferenceAsset, ReferenceRole, ReferenceScope, ShotSpec, StoryBeat,
)
from mvstudio.session import LyricsWorldSession
from mvstudio.story_engine import (
    cinematic_warnings, draft_shot, duplicate_id_warnings, literalization_warnings,
    motif_progression_warnings, next_beat_id, next_shot_id, reference_is_eligible,
    shot_timeline_warnings, shot_warnings,
)


def beat(beat_id="B001", start=0, end=10, phase="none", motif=None):
    return StoryBeat(beat_id=beat_id, start_sec=start, end_sec=end, dramatic_question="Q", change="", visual_event="", setup_or_payoff=phase, motif=motif)


def shot(shot_id, linked="B001", start=0, end=2):
    return ShotSpec(shot_id=shot_id, beat_id=linked, start_sec=start, end_sec=end, narrative_function="n", subject="s", action="a", environment="e", composition="c", camera=CameraSpec(framing="medium", lens="50mm", angle="eye", movement="push", movement_strength="subtle"), lighting="l", emotional_note="e")


def test_unique_id_allocators_survive_delete_add_and_detect_duplicates():
    assert next_beat_id({"B001", "B003"}) == "B002"
    assert next_shot_id("B001", {"B001-S01", "B001-S03"}) == "B001-S02"
    warnings = duplicate_id_warnings([beat(), beat()], [shot("S1"), shot("S1")])
    assert {warning.code for warning in warnings} == {"duplicate_beat_id", "duplicate_shot_id"}


def test_shot_timeline_all_coverage_warning_types():
    b = beat(end=10)
    shots = [shot("S1", start=1, end=3), shot("S2", start=4, end=7), shot("S3", start=6, end=9), shot("S4", start=9, end=11), shot("S5", linked="missing", start=0, end=1)]
    codes = {warning.code for warning in shot_timeline_warnings([b], shots)}
    assert {"shot_leading_gap", "shot_gap", "shot_overlap", "outside_beat", "invalid_beat_id"} <= codes
    assert "shot_trailing_gap" in {warning.code for warning in shot_timeline_warnings([b], [shot("S1", start=0, end=8)])}


def test_traceability_world_refs_subset_duration_and_roundtrip(tmp_path):
    b = beat()
    b.lyric_line_ids, b.music_cue_ids, b.world_rule_refs = ["L1"], ["M1"], ["reality_rules:0"]
    s = draft_shot(b)
    assert s.world_rule_refs == ["reality_rules:0"]
    bad = s.model_copy(update={"lyric_line_ids": ["L2"], "music_cue_ids": ["M2"], "world_rule_refs": ["bad"], "end_sec": 20})
    warnings = shot_warnings(bad, [b], [bad], [], lyric_line_ids={"L1"}, music_cue_ids={"M1"}, reference_ids=set(), world_rule_refs={"reality_rules:0"})
    assert any("subset" in warning for warning in warnings)
    assert any("World rule" in warning for warning in warnings)
    assert any("duration" in warning for warning in warnings)
    session = LyricsWorldSession(story_beats=[b], shots=[s])
    path = tmp_path / "한글 日本語 session.json"
    session.export(path)
    restored = LyricsWorldSession.import_file(path)
    assert restored.shots[0].world_rule_refs == ["reality_rules:0"]
    assert restored.to_dict()["schema_version"] == "0.9"


def test_reference_scope_policy_uses_beat_as_g3_scene():
    s = shot("B001-S01")
    project = ReferenceAsset(reference_id="P", role=ReferenceRole.COMPOSITION, path="p", applies_to=ReferenceScope.PROJECT)
    scene_ok = ReferenceAsset(reference_id="SC", role=ReferenceRole.COMPOSITION, path="p", applies_to=ReferenceScope.SCENE, scope_id="B001")
    scene_bad = scene_ok.model_copy(update={"reference_id": "SC2", "scope_id": "B002"})
    shot_ok = ReferenceAsset(reference_id="SH", role=ReferenceRole.COMPOSITION, path="p", applies_to=ReferenceScope.SHOT, scope_id="B001-S01")
    assert reference_is_eligible(project, s) and reference_is_eligible(scene_ok, s) and reference_is_eligible(shot_ok, s)
    assert not reference_is_eligible(scene_bad, s)


def test_motif_continuity_camera_and_literal_warnings():
    beats = [beat("B1", 0, 2, "payoff", "key"), beat("B2", 2, 4, "setup", "key"), beat("B3", 4, 6, "setup", "key")]
    codes = {warning.code for warning in motif_progression_warnings(beats)}
    assert "payoff_before_setup" in codes and "repeated_setup" in codes
    shots = [shot(f"S{i}", start=i, end=i + 2).model_copy(update={"lyric_line_ids": [f"L{i}"], "lyric_visual_strategy": "literal", "action": "rain falls"}) for i in range(3)]
    assert cinematic_warnings(shots)[0].code == "repeated_camera"
    assert literalization_warnings(shots)[0].code == "literalization"
    shots[0].continuity_out = [" Red  Ticket ", "red ticket"]
    shots[1].continuity_in = ["RED TICKET"]
    assert not any("continuity" in warning for warning in shot_warnings(shots[1], [beat()], shots, []))


def test_g2_payload_without_g3_fields_is_backward_compatible():
    restored = LyricsWorldSession.from_dict({"schema_version": "0.4", "lyrics_text": "old"})
    assert restored.story_beats == [] and restored.shots == []


def test_story_room_sorted_selection_edits_stable_beat_id():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    early = beat("B002", 0, 4)
    late = beat("B001", 5, 9)
    window.session.story_beats = [late, early]  # deliberately different from visual order
    page = window.story_room_page
    page.refresh()
    assert page.beat_list.item(0).data(Qt.UserRole) == "B002"
    page.beat_list.setCurrentRow(0)
    page.question.setText("edited early beat")
    page._save_selected()
    assert next(item for item in window.session.story_beats if item.beat_id == "B002").dramatic_question == "edited early beat"
    assert next(item for item in window.session.story_beats if item.beat_id == "B001").dramatic_question == "Q"
    window.close()


def test_story_shot_mutation_autosaves_only_with_explicit_target(tmp_path):
    from PySide6.QtWidgets import QApplication
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.session.story_beats = [beat()]
    window.story_room_page.refresh()
    window.story_room_page._add_beat()
    assert not window.autosave_timer.isActive()
    window.session.export(tmp_path / "saved session.json")
    window.shot_board_page.refresh()
    window.shot_board_page._add_shot()
    assert window.autosave_timer.isActive()
    window.autosave_timer.stop()
    window.close()
