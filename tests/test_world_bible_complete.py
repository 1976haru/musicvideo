from __future__ import annotations

import pytest

from mvstudio.models import (
    AudioMap, AudioTransition, LyricAnchor, LyricInterpretation, WorldConcept,
)
from mvstudio.session import LyricsWorldSession
from mvstudio.world_bible import promote_world_concept


def _analysis() -> LyricInterpretation:
    return LyricInterpretation(
        language_hint="ja",
        synopsis="새벽 바다에서 가까워지는 두 사람",
        pov="first_person",
        central_conflict="차가운 공기 속에서 말하지 못한 호감이 작은 행동으로 가까워진다.",
        emotional_arc=["distance", "warmth", "hope"],
        repeated_phrases=["寒くない"],
        anchors=[
            LyricAnchor(anchor_id="A1", anchor_type="time", phrase="夜明け", source_line_ids=["L001"], weight=.9),
            LyricAnchor(anchor_id="A2", anchor_type="place", phrase="海辺", source_line_ids=["L002"], weight=.9),
            LyricAnchor(anchor_id="A3", anchor_type="weather", phrase="冷たい風", source_line_ids=["L003"], weight=.8),
            LyricAnchor(anchor_id="A4", anchor_type="object", phrase="コートの袖", source_line_ids=["L004"], weight=.9),
            LyricAnchor(anchor_id="A5", anchor_type="nature", phrase="波", source_line_ids=["L005"], weight=.9),
            LyricAnchor(anchor_id="A6", anchor_type="color_light", phrase="朝焼け", source_line_ids=["L006"], weight=.8),
        ],
        visual_risk_notes=["과장된 판타지로 감정을 설명하지 않는다."],
    )


def _concept(mode: str = "hybrid") -> WorldConcept:
    return WorldConcept(
        concept_id="WC03",
        title="현실 80% + 시적 비현실 20%",
        interpretation_mode=mode,
        one_line="현실적인 바닷가에서 작은 반복 모티프만 감정의 문턱에서 미세하게 반응한다.",
        world_rule="대부분 현실 물리를 따르고 반복 모티프 하나만 감정 변화에서 비현실적으로 반응한다.",
        emotional_engine="거리감에서 온기로 이동한다.",
        recurring_motifs=["コートの袖", "冷たい風", "波", "朝焼け"],
        visual_language=["grounded cinematic realism", "subtle magical event"],
        ending_image="새벽빛 속에서 같은 바다가 다르게 느껴진다.",
        lyric_evidence=["L001", "L002", "L003", "L004", "L005", "L006"],
        lyric_relevance_score=97,
    )


def _audio(tempo: float = 92.3) -> AudioMap:
    return AudioMap(
        source_path="song.wav",
        duration_sec=192.0,
        sample_rate=44100,
        tempo_bpm=tempo,
        transitions=[
            AudioTransition(
                transition_id="AT001",
                time_sec=56.8,
                strength=.8,
                character="energy_rise",
                reasons=["chorus rise"],
            )
        ],
    )


def _editable_values(bible):
    return [
        bible.premise, bible.emotional_thesis, bible.reality_rules, bible.time_period,
        bible.visual_language, bible.palette, bible.material_language, bible.weather_rules,
        bible.lighting_rules, bible.camera_rules, bible.recurring_motifs, bible.forbidden_elements,
    ]


def test_complete_world_bible_populates_all_production_fields():
    bible = promote_world_concept(_concept(), _analysis(), _audio())
    assert all(bool(value) for value in _editable_values(bible))
    assert "夜明け" in bible.time_period
    assert any("pale dawn peach" in value for value in bible.palette)
    assert any("冷たい風" in value for value in bible.weather_rules)
    assert any("コートの袖" in value for value in bible.material_language)
    assert any("모든 비트" in value for value in bible.camera_rules)
    assert any("음악 변화점 1개" in value for value in bible.camera_rules)
    assert bible.lyric_foundation == ["L001", "L002", "L003", "L004", "L005", "L006"]


def test_world_bible_generation_has_safe_fallback_without_analysis_or_audio():
    bible = promote_world_concept(_concept("literal"))
    assert all(bool(value) for value in _editable_values(bible))
    assert "시대 미지정" in bible.time_period
    assert bible.palette
    assert bible.material_language
    assert bible.weather_rules
    assert bible.lighting_rules
    assert bible.camera_rules
    assert bible.lyric_foundation == ["L001", "L002", "L003", "L004", "L005", "L006"]


def test_camera_grammar_changes_with_music_tempo_without_beat_cutting():
    slow = promote_world_concept(_concept(), _analysis(), _audio(72.0))
    fast = promote_world_concept(_concept(), _analysis(), _audio(138.0))
    assert slow.camera_rules[0] != fast.camera_rules[0]
    assert "느린" in slow.camera_rules[0]
    assert "모든 비트마다 컷하지 않는다" in fast.camera_rules[0]
    assert any("모든 비트" in rule for rule in slow.camera_rules)


def test_session_promotion_passes_lyrics_and_music_evidence():
    session = LyricsWorldSession(
        analysis=_analysis(),
        concepts=[_concept()],
        selected_concept_id="WC03",
        audio_map=_audio(),
    )
    bible = session.promote_selected_concept()
    assert all(bool(value) for value in _editable_values(bible))
    assert "夜明け" in bible.time_period
    assert any("92" not in rule or rule for rule in bible.camera_rules)


def test_ui_regeneration_requires_confirmation_and_preserves_manual_edits(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.session.analysis = _analysis()
    window.session.concepts = [_concept()]
    window.session.selected_concept_id = "WC03"
    window.session.audio_map = _audio()
    window.session.promote_selected_concept()
    window.session.world_bible.emotional_thesis = "사용자가 직접 수정한 문장"
    window._refresh_from_session()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )
    assert window._promote_world_bible() is False
    assert window.session.world_bible.emotional_thesis == "사용자가 직접 수정한 문장"

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    assert window._promote_world_bible() is True
    assert window.session.world_bible.emotional_thesis != "사용자가 직접 수정한 문장"
    assert window.world_bible_draft_button.text() == "World Bible 전체 초안 다시 만들기"
    window.close()
    app.processEvents()


def test_partial_world_bible_fill_preserves_existing_user_edits():
    session = LyricsWorldSession(
        analysis=_analysis(),
        concepts=[_concept()],
        selected_concept_id="WC03",
        audio_map=_audio(),
    )
    session.promote_selected_concept()
    session.world_bible.emotional_thesis = "사용자가 직접 수정한 문장"
    session.world_bible.time_period = ""
    session.world_bible.palette = []
    session.world_bible.material_language = []
    session.world_bible.weather_rules = []
    session.world_bible.lighting_rules = []
    session.world_bible.camera_rules = []

    bible = session.promote_selected_concept(fill_missing_only=True)

    assert bible.emotional_thesis == "사용자가 직접 수정한 문장"
    assert bible.time_period
    assert bible.palette
    assert bible.material_language
    assert bible.weather_rules
    assert bible.lighting_rules
    assert bible.camera_rules
    assert all(bool(value) for value in _editable_values(bible))
