from __future__ import annotations

from pathlib import Path

import pytest

from mvstudio.manual_generation import compile_manual_pack
from mvstudio.models import CameraSpec, ShotSpec, StoryBeat, WorldBible
from mvstudio.result_takes import (
    DuplicateTakeIDError, DuplicateTakePathError, GenerationTake, TakeManager,
    audit_take_state, next_take_id, portable_take_path, resolve_take_path,
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
    assert restored.to_dict()["schema_version"] == "1.0"
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
    assert window.nav_buttons[7].isEnabled() and window.nav_buttons[8].isEnabled()
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


def test_corrupt_duplicate_id_blocks_all_core_mutations(tmp_path):
    session = _session(tmp_path)
    take = session.take_manager.register(_video(tmp_path / "a.mp4"), "B001-S01")
    session.generation_takes.append(take.model_copy(deep=True))
    before = [item.model_dump() for item in session.generation_takes]
    manager = session.take_manager
    for operation in (
        lambda: manager.accept(take.take_id),
        lambda: manager.reject(take.take_id, "bad"),
        lambda: manager.restore_candidate(take.take_id),
        lambda: manager.update_notes(take.take_id, rating=2, notes="x", reject_reason=""),
        lambda: manager.unregister(take.take_id),
        lambda: manager.relink(take.take_id, tmp_path / "a.mp4"),
    ):
        with pytest.raises(DuplicateTakeIDError):
            operation()
    assert [item.model_dump() for item in session.generation_takes] == before


def test_multiple_accepted_preserved_until_explicit_accept(tmp_path):
    session = _session(tmp_path)
    a = session.take_manager.register(_video(tmp_path / "a.mp4"), "B001-S01")
    b = session.take_manager.register(_video(tmp_path / "b.mp4"), "B001-S01")
    a.status = b.status = "accepted"
    restored = LyricsWorldSession.from_dict(session.to_dict(tmp_path), project_dir=tmp_path)
    assert [take.status for take in restored.generation_takes] == ["accepted", "accepted"]
    assert restored.take_manager.shot_result_status("B001-S01") == "NEEDS_REVIEW"
    restored.take_manager.accept(b.take_id)
    assert [take.status for take in restored.generation_takes] == ["candidate", "accepted"]


def test_stale_counter_reconciles_upward_and_never_decreases(tmp_path):
    session = _session(tmp_path)
    take = session.take_manager.register(_video(tmp_path / "a.mp4"), "B001-S01")
    take.take_id = "TAKE-B001-S01-009"
    payload = session.to_dict(tmp_path)
    payload["take_id_counters"] = {"B001-S01": 2, "B001-S02": 20}
    restored = LyricsWorldSession.from_dict(payload, project_dir=tmp_path)
    assert restored.take_id_counters == {"B001-S01": 9, "B001-S02": 20}
    restored.take_manager.unregister(take.take_id)
    added = restored.take_manager.register(_video(tmp_path / "new.mp4"), "B001-S01")
    assert added.take_id == "TAKE-B001-S01-010"


def test_relink_is_metadata_only_and_preserves_history(tmp_path):
    session = _session(tmp_path)
    old = _video(tmp_path / "missing.mp4", b"old bytes")
    take = session.take_manager.register(old, "B001-S01", now="created")
    take.status, take.rating, take.notes, take.reject_reason = "rejected", 4, "note", "reason"
    old.unlink()
    new = _video(tmp_path / "새 결과.mov", b"new bytes")
    snapshot = (take.take_id, take.shot_id, take.pack_id, take.status, take.rating, take.notes, take.reject_reason, take.created_at, take.imported_at)
    session.take_manager.relink(take.take_id, new)
    assert snapshot == (take.take_id, take.shot_id, take.pack_id, take.status, take.rating, take.notes, take.reject_reason, take.created_at, take.imported_at)
    assert new.read_bytes() == b"new bytes" and resolve_take_path(take, tmp_path) == new.resolve()


def test_failed_registration_relink_and_status_edits_never_touch_files(tmp_path):
    session = _session(tmp_path)
    source = _video(tmp_path / "same.mp4", b"same immutable")
    other = _video(tmp_path / "other.mp4", b"other immutable")
    take = session.take_manager.register(source, "B001-S01")
    second = session.take_manager.register(other, "B001-S01")
    with pytest.raises(DuplicateTakePathError):
        session.take_manager.register(source, "B001-S01")
    with pytest.raises(DuplicateTakePathError):
        session.take_manager.relink(second.take_id, source)
    session.take_manager.accept(take.take_id)
    session.take_manager.reject(take.take_id, "reason")
    session.take_manager.update_notes(take.take_id, rating=5, notes="safe", reject_reason="reason")
    assert source.read_bytes() == b"same immutable"
    assert other.read_bytes() == b"other immutable"


def test_audit_and_selected_warning_scope(tmp_path):
    session = _session(tmp_path)
    first = session.take_manager.register(_video(tmp_path / "a.mp4"), "B001-S01")
    second = session.take_manager.register(_video(tmp_path / "b.mp4"), "B001-S02")
    duplicate = second.model_copy(deep=True)
    session.generation_takes.append(duplicate)
    codes = {warning.code for warning in audit_take_state(
        session.generation_takes, session.shots, session.generation_packs, tmp_path, session.take_id_counters,
    )}
    assert "DUPLICATE_TAKE_ID" in codes
    selected_codes = {warning.code for warning in session.take_manager.warnings_for_take(first)}
    assert "DUPLICATE_TAKE_ID" not in selected_codes


def test_ui_selection_duplicate_block_and_partial_batch(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.session = _session(tmp_path)
    page = window.result_takes_page
    page.refresh()
    first = _video(tmp_path / "정상 A.mp4", b"A")
    second = _video(tmp_path / "正常 B.mov", b"B")
    bad = _video(tmp_path / "unsupported.txt", b"bad")
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    page._register_paths([str(first), str(first), str(bad), str(second)])
    assert len(window.session.generation_takes) == 2
    assert page._selected_take().original_filename == second.name
    assert len(messages) == 1 and "unsupported" in messages[0]
    selected_id = page._selected_take().take_id
    page._accept()
    assert page._selected_take().take_id == selected_id
    page.reject_reason.setPlainText("manual")
    page._reject()
    assert page._selected_take().take_id == selected_id
    page._restore()
    page.notes.setPlainText("stable")
    page._save_notes()
    assert page._selected_take().take_id == selected_id

    duplicate = window.session.generation_takes[0].model_copy(deep=True)
    window.session.generation_takes.append(duplicate)
    page._refresh_takes(duplicate.take_id)
    history = [item.model_dump() for item in window.session.generation_takes]
    page._accept()
    assert [item.model_dump() for item in window.session.generation_takes] == history
    window.autosave_timer.stop()
    window.close()
