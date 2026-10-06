from __future__ import annotations

from pathlib import Path

import pytest

from mvstudio.manual_generation import compile_manual_pack
from mvstudio.models import CameraSpec, ShotSpec, StoryBeat, WorldBible
from mvstudio.result_takes import (
    DuplicateTakePathError, GenerationTake, TakeManager, next_take_id,
    portable_take_path, resolve_take_path,
)
from mvstudio.session import LyricsWorldSession


def _shot(shot_id: str, start: float = 0) -> ShotSpec:
    return ShotSpec(
        shot_id=shot_id, beat_id="B001", start_sec=start, end_sec=start + 5,
        narrative_function="result test", subject="subject", action="action",
        environment="environment", composition="composition",
        camera=CameraSpec(framing="medium"), lighting="light", emotional_note="emotion",
    )


def _session(project_dir: Path) -> LyricsWorldSession:
    shots = [_shot("B001-S01"), _shot("B001-S02", 5)]
    return LyricsWorldSession(
        world_bible=WorldBible(premise="world", emotional_thesis="emotion"),
        story_beats=[StoryBeat(beat_id="B001", start_sec=0, end_sec=10, dramatic_question="q", change="c", visual_event="v")],
        shots=shots, project_dir=project_dir,
    )


def _video(path: Path, content: bytes = b"original video") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_generation_take_validation_and_stable_id_after_delete(tmp_path):
    with pytest.raises(ValueError):
        GenerationTake(take_id="T", shot_id="S", output_path="x.mp4", created_at="x", imported_at="x", original_filename="x.mp4", rating=6)
    session = _session(tmp_path)
    first = session.take_manager.register(_video(tmp_path / "a.mp4"), "B001-S01")
    second = session.take_manager.register(_video(tmp_path / "b.mp4"), "B001-S01")
    assert (first.take_id, second.take_id) == ("TAKE-B001-S01-001", "TAKE-B001-S01-002")
    session.take_manager.unregister(second.take_id)
    third = session.take_manager.register(_video(tmp_path / "c.mp4"), "B001-S01")
    assert third.take_id == "TAKE-B001-S01-003"
    assert next_take_id("B001-S01", {first.take_id}, 3)[0] == "TAKE-B001-S01-004"


def test_take_path_policy_and_unicode_roundtrip(tmp_path):
    project = tmp_path / "프로젝트 日本語"
    inside = _video(project / "results" / "결과 A.mp4")
    outside = _video(tmp_path / "외부 result.mov")
    assert portable_take_path(inside, project) == "results/결과 A.mp4"
    assert Path(portable_take_path(outside, project)).is_absolute()
    take = GenerationTake(take_id="T", shot_id="S", output_path="results/결과 A.mp4", created_at="x", imported_at="x", original_filename=inside.name)
    assert resolve_take_path(take, project) == inside.resolve()


def test_register_duplicate_rules_and_metadata_only_unregister(tmp_path):
    session = _session(tmp_path)
    source = _video(tmp_path / "same result.mp4", b"never change")
    take = session.take_manager.register(source, "B001-S01")
    with pytest.raises(DuplicateTakePathError):
        session.take_manager.register(source, "B001-S01")
    other = session.take_manager.register(source, "B001-S02")
    assert other.shot_id == "B001-S02"
    session.take_manager.unregister(take.take_id)
    assert source.read_bytes() == b"never change"


def test_accept_reject_restore_and_one_final_take(tmp_path):
    session = _session(tmp_path)
    a = session.take_manager.register(_video(tmp_path / "a.mp4"), "B001-S01")
    b = session.take_manager.register(_video(tmp_path / "b.mp4"), "B001-S01")
    session.take_manager.accept(a.take_id)
    session.take_manager.accept(b.take_id)
    assert a.status == "candidate" and b.status == "accepted"
    assert session.take_manager.accepted_take_for_shot("B001-S01") == b
    session.take_manager.reject(b.take_id, "motion drift")
    assert b.status == "rejected" and b.reject_reason == "motion drift"
    session.take_manager.restore_candidate(b.take_id)
    assert b.status == "candidate" and b.reject_reason == ""


def test_pack_lineage_orphan_missing_and_duplicate_warnings(tmp_path):
    session = _session(tmp_path)
    pack = compile_manual_pack(session, session.shots[0], pack_id="PACK-1")
    session.generation_packs.append(pack)
    no_pack = session.take_manager.register(_video(tmp_path / "a.mp4"), "B001-S01")
    mismatch = session.take_manager.register(_video(tmp_path / "b.mp4"), "B001-S02", "PACK-1")
    codes = {warning.code for warning in session.take_manager.warnings()}
    assert {"NO_PACK_SNAPSHOT", "PACK_SHOT_MISMATCH"} <= codes
    mismatch.pack_id = "MISSING-PACK"
    no_pack.shot_id = "MISSING-SHOT"
    Path(resolve_take_path(mismatch, tmp_path)).unlink()
    codes = {warning.code for warning in session.take_manager.warnings()}
    assert {"ORPHAN_SHOT", "ORPHAN_PACK", "MISSING_FILE"} <= codes
    duplicate = mismatch.model_copy(deep=True)
    session.generation_takes.append(duplicate)
    assert "DUPLICATE_TAKE_ID" in {warning.code for warning in session.take_manager.warnings()}


def test_schema_07_roundtrip_and_06_backward_compatibility(tmp_path):
    project = tmp_path / "세션 폴더 日本語"
    project.mkdir()
    session = _session(project)
    source = _video(project / "results" / "결과 영상.webm")
    take = session.take_manager.register(source, "B001-S01")
    session.take_manager.update_notes(take.take_id, rating=5, notes="좋음", reject_reason="")
    path = project / "session file.json"
    session.export(path)
    restored = LyricsWorldSession.import_file(path)
    assert restored.to_dict()["schema_version"] == "0.7"
    assert restored.generation_takes[0].rating == 5
    assert resolve_take_path(restored.generation_takes[0], restored.project_dir) == source.resolve()
    old = LyricsWorldSession.from_dict({"schema_version": "0.6", "lyrics_text": "old"})
    assert old.generation_takes == [] and old.take_id_counters == {}


def test_result_takes_offscreen_autosave_and_file_safety(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.session = _session(tmp_path)
    page = window.result_takes_page
    page.refresh()
    assert window.generation_tabs.count() == 2
    assert window.generation_tabs.tabText(0) == "PROMPT PACK"
    assert window.generation_tabs.tabText(1) == "RESULT / TAKES"
    assert window.nav_buttons[7].isEnabled() and not window.nav_buttons[8].isEnabled()
    source = _video(tmp_path / "UI 결과.mp4", b"ui source")
    page._register_paths([str(source)])
    assert len(window.session.generation_takes) == 1
    assert not window.autosave_timer.isActive()
    take = window.session.generation_takes[0]
    page.notes.setPlainText("메모")
    page.rating.setValue(4)
    page._save_notes()
    assert take.take_id == window.session.generation_takes[0].take_id
    window.session.export(tmp_path / "saved.json")
    page._accept()
    assert window.autosave_timer.isActive()
    window.autosave_timer.stop()
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    page._unregister()
    assert source.read_bytes() == b"ui source"
    assert window.session.generation_takes == []
    window.autosave_timer.stop()
    window.close()
