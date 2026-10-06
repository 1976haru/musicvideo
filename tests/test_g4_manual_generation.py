from __future__ import annotations

import json

from mvstudio.manual_generation import (
    ManualGenerationPack, compile_manual_pack, export_manual_pack,
    get_manual_site_profile, recommend_camera_preset,
)
from mvstudio.models import (
    CameraSpec, LyricLine, MVTimelineCue, ReferenceAsset, ReferenceRole,
    ReferenceScope, ShotSpec, StoryBeat, WorldBible,
)
from mvstudio.session import LyricsWorldSession


def _session(tmp_path):
    reference = tmp_path / "참조 日本語 image.png"
    reference.write_bytes(b"image")
    beat = StoryBeat(
        beat_id="B001", start_sec=0, end_sec=7.4, dramatic_question="Will she leave?",
        change="She decides", visual_event="She opens the rain-soaked door",
        lyric_line_ids=["L001"], music_cue_ids=["MV01"], world_rule_refs=["reality_rules:0"],
    )
    shot = ShotSpec(
        shot_id="B001-S01", beat_id="B001", start_sec=0, end_sec=7.4,
        narrative_function="decision", lyric_line_ids=["L001"], music_cue_ids=["MV01"],
        lyric_intent="기다림에서 결심으로", lyric_visual_strategy="metaphor",
        subject="붉은 코트를 입은 여성", action="문을 열고 비 속으로 한 걸음 나간다",
        environment="젖은 새벽 기차역", composition="중앙 대칭에서 열린 공간으로 이동",
        camera=CameraSpec(framing="medium", lens="50mm", angle="eye-level", movement="subtle push-in", movement_strength="subtle"),
        lighting="차가운 새벽빛", emotional_note="quiet resolve", motif="red ticket",
        continuity_in=["red ticket in left hand"], continuity_out=["door open"],
        reference_ids=["REF001"], world_rule_refs=["reality_rules:0"],
        negative_constraints=["identity drift"], generation_mode="i2v",
    )
    return LyricsWorldSession(
        lines=[LyricLine(line_id="L001", text="雨の駅で待っている", start_sec=0, end_sec=7.4)],
        mv_timeline=[MVTimelineCue(cue_id="MV01", time_sec=0, priority=.8, cue_type="lyric", reasons=[], lyric_line_ids=["L001"], recommended_visual_action="begin")],
        world_bible=WorldBible(premise="Memory appears only in rain", emotional_thesis="waiting becomes choice", reality_rules=["Reflections reveal memory"], visual_language=["restrained realism"], palette=["blue", "red"], forbidden_elements=["neon city"]),
        references=[ReferenceAsset(reference_id="REF001", role=ReferenceRole.CHARACTER_MASTER, path=reference.name, applies_to=ReferenceScope.PROJECT, lock_strength=.9)],
        story_beats=[beat], shots=[shot], project_dir=tmp_path,
    )


def test_generic_and_higgsfield_profiles_load_and_map_safely(tmp_path):
    generic = get_manual_site_profile("GENERIC_MANUAL")
    higgsfield = get_manual_site_profile("higgsfield")
    session = _session(tmp_path)
    assert generic.mode == "manual_web"
    assert higgsfield.supports_camera_presets
    assert higgsfield.capabilities_model_dependent
    assert higgsfield.duration_options == []
    assert 3 not in higgsfield.duration_options and 5 not in higgsfield.duration_options and 10 not in higgsfield.duration_options
    assert higgsfield.aspect_ratio_options == ["site / model dependent"]
    assert higgsfield.resolution_options == ["site / model dependent"]
    assert recommend_camera_preset(higgsfield, session.shots[0]) == "Dolly In"
    unknown = session.shots[0].model_copy(update={"camera": session.shots[0].camera.model_copy(update={"movement": "crane diagonal"})})
    assert recommend_camera_preset(higgsfield, unknown) == "Custom / no preset recommendation"


def test_manual_pack_preserves_provenance_and_distinct_prompt_layers(tmp_path):
    session = _session(tmp_path)
    original_duration = session.shots[0].duration_sec
    pack = compile_manual_pack(session, session.shots[0], "HIGGSFIELD", generation_duration_hint=10, aspect_ratio="9:16", resolution_hint="1080p")
    assert pack.shot_id == "B001-S01" and pack.beat_id == "B001"
    assert pack.lyric_line_ids == ["L001"] and pack.music_cue_ids == ["MV01"]
    assert pack.world_rule_refs == ["reality_rules:0"] and pack.reference_ids == ["REF001"]
    assert len({pack.main_prompt, pack.motion_prompt, pack.camera_prompt, pack.negative_prompt}) == 4
    assert pack.generation_duration_hint == 10 and session.shots[0].duration_sec == original_duration
    assert pack.camera_preset_recommendation == "Dolly In"
    assert "雨の駅" in pack.lyric_evidence[0]


def test_higgsfield_default_hints_are_model_dependent_and_do_not_mutate_shot(tmp_path):
    session = _session(tmp_path)
    shot = session.shots[0]
    original_times = (shot.start_sec, shot.end_sec, shot.duration_sec)
    pack = compile_manual_pack(session, shot, "HIGGSFIELD")
    assert pack.generation_duration_hint is None
    assert pack.aspect_ratio == "site / model dependent"
    assert pack.resolution_hint == "site / model dependent"
    assert (shot.start_sec, shot.end_sec, shot.duration_sec) == original_times
    assert any("model-dependent" in warning for warning in pack.warnings)


def test_readiness_warns_for_missing_and_ineligible_references(tmp_path):
    session = _session(tmp_path)
    session.references[0] = session.references[0].model_copy(update={"path": "missing.png", "applies_to": ReferenceScope.SHOT, "scope_id": "OTHER"})
    pack = compile_manual_pack(session, session.shots[0])
    assert pack.readiness == "READY_WITH_WARNINGS"
    assert any("Missing reference file" in warning for warning in pack.warnings)
    assert any("Ineligible reference scope" in warning for warning in pack.warnings)
    blocked_shot = session.shots[0].model_copy(update={"beat_id": None})
    assert compile_manual_pack(session, blocked_shot).readiness == "BLOCKED"


def test_pack_serialization_session_roundtrip_and_unicode_exports(tmp_path):
    session = _session(tmp_path)
    pack = compile_manual_pack(session, session.shots[0], created_at="2026-01-01T00:00:00+00:00", pack_id="PACK-1")
    restored_pack = ManualGenerationPack.model_validate_json(pack.model_dump_json())
    assert restored_pack == pack
    session.generation_packs.append(pack)
    session_path = tmp_path / "세션 日本語 space.json"
    session.export(session_path)
    restored = LyricsWorldSession.import_file(session_path)
    assert restored.generation_packs[0].pack_id == "PACK-1"
    txt = export_manual_pack(pack, tmp_path / "B001-S01 팩.txt")
    js = export_manual_pack(pack, tmp_path / "B001-S01 パック.json")
    assert "雨の駅" not in txt.read_text(encoding="utf-8")  # evidence IDs preserved without dumping lyrics into prompts
    assert json.loads(js.read_text(encoding="utf-8"))["main_prompt"].startswith("WORLD LOCK")


def test_offscreen_generate_page_and_copy_snapshot_autosave(tmp_path):
    from PySide6.QtWidgets import QApplication
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.session = _session(tmp_path)
    window.manual_generation_page.refresh()
    page = window.manual_generation_page
    assert window.pages.count() == 9 and window.nav_buttons[7].isEnabled()
    assert page.current_pack is not None
    higgsfield_index = page.profile_combo.findData("HIGGSFIELD")
    page.profile_combo.setCurrentIndex(higgsfield_index)
    assert page.duration_combo.count() == 1
    assert page.duration_combo.itemData(0) is None
    assert "site-model dependent" in page.duration_combo.itemText(0)
    assert "모델별 지원 옵션이 다릅니다" in page.profile_notice.text()
    assert page.profile_notice.isVisibleTo(page)
    assert page.current_pack.generation_duration_hint is None
    page._copy(page.current_pack.main_prompt)
    assert QApplication.clipboard().text() == page.current_pack.main_prompt
    assert page.feedback.text() == "복사 완료"
    page._save_snapshot()
    assert len(window.session.generation_packs) == 1
    assert not window.autosave_timer.isActive()
    window.session.export(tmp_path / "saved.json")
    page._save_snapshot()
    assert window.autosave_timer.isActive()
    window.autosave_timer.stop()
    window.close()
