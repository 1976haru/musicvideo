from pathlib import Path
import os

import pytest

from mvstudio.models import AudioMap, MVTimelineCue, ReferenceRole, WorldConcept
from mvstudio.reference_vault import DuplicateReferenceIDError, ReferenceVault, resolve_reference_path
from mvstudio.session import LyricsWorldSession
from mvstudio.thumbnail_cache import ThumbnailCache
from mvstudio.world_bible import promote_world_concept


def _concept() -> WorldConcept:
    return WorldConcept(
        concept_id="WC03",
        title="Hybrid",
        interpretation_mode="hybrid",
        one_line="비가 기억을 비추는 역",
        world_rule="감정의 문턱에서만 빗물이 과거를 반사한다.",
        emotional_engine="기다림에서 작별로 이동한다.",
        recurring_motifs=["표", "비", "표"],
        visual_language=["grounded realism", "visual restraint"],
        lyric_evidence=["L001", "L005", "L012", "L005"],
        lyric_relevance_score=97,
    )


def test_world_concept_promotes_to_traceable_world_bible():
    bible = promote_world_concept(_concept())
    assert bible.source_concept_id == "WC03"
    assert bible.premise == "비가 기억을 비추는 역"
    assert bible.reality_rules
    assert bible.lyric_foundation == ["L001", "L005", "L012"]


def test_reference_add_remove_only_changes_metadata(tmp_path):
    source = tmp_path / "원본 이미지.jpg"
    source.write_bytes(b"untouched")
    vault = ReferenceVault(project_dir=tmp_path)
    asset = vault.add(source, ReferenceRole.CHARACTER_MASTER, is_master=True)
    assert asset.path == "원본 이미지.jpg"
    assert vault.status(asset) == "available"
    removed = vault.remove(asset.reference_id)
    assert removed.reference_id == asset.reference_id
    assert source.read_bytes() == b"untouched"


def test_duplicate_reference_id_is_rejected(tmp_path):
    vault = ReferenceVault(project_dir=tmp_path)
    vault.add(tmp_path / "a.png", reference_id="REF001")
    with pytest.raises(DuplicateReferenceIDError):
        vault.add(tmp_path / "b.png", reference_id="REF001")


def test_missing_file_status_is_graceful(tmp_path):
    vault = ReferenceVault(project_dir=tmp_path)
    asset = vault.add(tmp_path / "missing.png")
    assert vault.status(asset) == "missing"
    assert resolve_reference_path(asset, tmp_path).name == "missing.png"


def test_windows_unicode_space_path_and_thumbnail_key(tmp_path):
    folder = tmp_path / "한글 日本語 space"
    folder.mkdir()
    source = folder / "참고 画像.png"
    source.write_bytes(b"image")
    vault = ReferenceVault(project_dir=tmp_path)
    asset = vault.add(source)
    assert resolve_reference_path(asset, tmp_path) == source.resolve()
    target = ThumbnailCache(tmp_path / "cache").target_for(source)
    assert target.suffix == ".png"
    assert str(source) not in target.name


def test_g2_session_export_import_roundtrip(tmp_path):
    project_dir = tmp_path / "프로젝트 日本語"
    reference_dir = project_dir / "references_local"
    reference_dir.mkdir(parents=True)
    source = reference_dir / "캐릭터 master.png"
    source.write_bytes(b"original")
    session = LyricsWorldSession(
        concepts=[_concept()], selected_concept_id="WC03", project_dir=project_dir
    )
    session.promote_selected_concept()
    session.add_reference(source, ReferenceRole.CHARACTER_MASTER, is_master=True)
    session_file = project_dir / "세션 파일.json"
    session.export(session_file)

    restored = LyricsWorldSession.import_file(session_file)
    assert restored.world_bible.source_concept_id == "WC03"
    assert restored.world_bible.lyric_foundation == ["L001", "L005", "L012"]
    assert len(restored.references) == 1
    assert restored.references[0].path == "references_local/캐릭터 master.png"
    assert restored.reference_vault.status(restored.references[0]) == "available"
    assert source.read_bytes() == b"original"


def test_session_import_reports_corrupt_json(tmp_path):
    broken = tmp_path / "손상된 セッション.json"
    broken.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(ValueError, match="손상되었거나"):
        LyricsWorldSession.import_file(broken)


def test_atomic_export_keeps_previous_file_on_replace_failure(tmp_path, monkeypatch):
    target = tmp_path / "프로젝트 日本語 session.json"
    target.write_bytes(b"previous valid session")
    session = LyricsWorldSession(lyrics_text="새벽에 역에 서 있어", duration_sec=30)
    session.analyze()

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        session.export(target)
    assert target.read_bytes() == b"previous valid session"
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))


def test_new_session_has_no_implicit_autosave_target():
    session = LyricsWorldSession(lyrics_text="비 내리는 역", duration_sec=20)
    session.analyze()
    assert session.session_path is None
    with pytest.raises(ValueError, match="경로를 지정"):
        session.export()


def test_ui_offscreen_session_open_restores_all_g2_panels(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    session_file = tmp_path / "열린 세션 日本語.json"
    session = LyricsWorldSession(
        lyrics_text="새벽 역에서 비를 기다려\n붉은 표를 남긴다", duration_sec=60,
        concepts=[_concept()], selected_concept_id="WC03",
        audio_map=AudioMap(
            source_path="song.wav", duration_sec=60, sample_rate=22050, tempo_bpm=120,
            beat_times_sec=[0.5, 1.0],
        ),
        mv_timeline=[MVTimelineCue(
            cue_id="MV01", time_sec=0, priority=0.8, cue_type="lyric_entry",
            reasons=["test"], lyric_line_ids=["L001"], recommended_visual_action="첫 장면을 제시",
        )],
    )
    session.analyze()
    session.select_concept("WC03")
    session.promote_selected_concept()
    source = tmp_path / "reference 原본.png"
    source.write_bytes(b"reference")
    session.add_reference(source, ReferenceRole.CHARACTER_MASTER, is_master=True)
    session.export(session_file)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(session_file), ""))
    window = MainWindow()
    assert not window.autosave_timer.isActive()
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)

    window._open_session()
    app.processEvents()

    assert window.pages.currentIndex() == 0
    assert window.session.project_dir == tmp_path.resolve()
    assert window.lyrics.toPlainText() == session.lyrics_text
    assert window.summary.text() == session.analysis.synopsis
    assert "WC03" in window.concept_cards
    assert window.concept_cards["WC03"].property("selected") is True
    assert window.bible_fields["premise"].toPlainText() == session.world_bible.premise
    assert window.reference_layout.count() == 2  # one card and the trailing stretch
    assert window.music_duration.text() == "60.0s"
    assert "lyrics=L001" in window.timeline_summary.toPlainText()
    assert window.session.session_path == session_file.resolve()
    assert window.autosave_timer.isActive()  # refresh scheduled only because this is a saved session
    window.autosave_timer.stop()
    window.close()
