from pathlib import Path

import pytest

from mvstudio.models import ReferenceRole, WorldConcept
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
