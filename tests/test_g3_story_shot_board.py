from mvstudio.models import (
    AudioMap, LyricLine, MVTimelineCue, ReferenceAsset, ReferenceRole, ShotSpec, StoryBeat,
)
from mvstudio.session import LyricsWorldSession
from mvstudio.story_engine import draft_shot, draft_story_beats, shot_warnings, timeline_warnings


def _lines():
    return [
        LyricLine(line_id=f"L{i:03d}", text=text, start_sec=(i - 1) * 5.0, end_sec=i * 5.0)
        for i, text in enumerate(("비가 내린다", "빈 의자를 본다", "돌아올 수 있다면", "돌아올 수 있다면", "붉은 표를 남긴다"), 1)
    ]


def test_auto_story_draft_groups_lines_and_preserves_evidence():
    cues = [
        MVTimelineCue(cue_id="MV01", time_sec=0, priority=0.8, cue_type="lyric_entry", reasons=[], lyric_line_ids=["L001"], recommended_visual_action="세계 제시"),
        MVTimelineCue(cue_id="MV02", time_sec=20, priority=0.9, cue_type="music_transition", reasons=["energy_rise"], lyric_line_ids=["L005"], recommended_visual_action="모티프 회수"),
    ]
    beats = draft_story_beats(_lines(), cues, 30, motif_pool=["붉은 표"], emotional_arc=["기다림", "작별"], world_rule_refs=["reality_rules:0"])
    assert 1 <= len(beats) < len(_lines())
    assert {line_id for beat in beats for line_id in beat.lyric_line_ids} == {line.line_id for line in _lines()}
    assert all(beat.end_sec > beat.start_sec for beat in beats)
    assert all(set(beat.music_cue_ids) <= {"MV01", "MV02"} for beat in beats)
    # A motif pool is not evidence by itself; only a group containing the motif may use it.
    assert all(beat.motif is None and beat.setup_or_payoff == "none" for beat in beats[:-1])
    assert beats[-1].setup_or_payoff == "setup"
    assert beats[0].world_rule_refs == ["reality_rules:0"]


def test_story_timeline_warns_for_gap_and_overlap():
    first = StoryBeat(beat_id="B001", start_sec=0, end_sec=4, dramatic_question="Q1", change="", visual_event="")
    second = StoryBeat(beat_id="B002", start_sec=5, end_sec=8, dramatic_question="Q2", change="", visual_event="")
    assert any(w.code == "gap" for w in timeline_warnings([first, second], 8))
    overlapping = second.model_copy(update={"start_sec": 3.5})
    assert any(w.code == "overlap" for w in timeline_warnings([first, overlapping], 8))


def test_draft_shot_carries_beat_provenance():
    beat = StoryBeat(
        beat_id="B001", start_sec=2, end_sec=8, dramatic_question="돌아설 수 있을까?", change="결심한다",
        visual_event="표를 놓고 한 걸음 물러난다", motif="붉은 표", setup_or_payoff="development",
        lyric_line_ids=["L004"], music_cue_ids=["MV02"], lyric_intent="망설임에서 결심으로",
        reference_ids=["REF001"],
    )
    shot = draft_shot(beat)
    assert shot.beat_id == "B001"
    assert shot.lyric_line_ids == ["L004"]
    assert shot.music_cue_ids == ["MV02"]
    assert shot.reference_ids == ["REF001"]
    assert shot.motif == "붉은 표"


def test_world_warning_and_continuity_comparison():
    beat = StoryBeat(beat_id="B001", start_sec=0, end_sec=8, dramatic_question="Q", change="", visual_event="")
    prior = draft_shot(beat, 1).model_copy(update={"shot_id": "S001", "start_sec": 0, "end_sec": 4, "continuity_out": ["red ticket in left hand"]})
    current = draft_shot(beat, 2).model_copy(update={"shot_id": "S002", "start_sec": 4, "end_sec": 8, "subject": "forbidden neon city", "continuity_in": ["ticket missing"], "reference_ids": ["REF999"]})
    warnings = shot_warnings(current, [beat], [prior, current], ["neon city"])
    assert any("금지 요소" in warning for warning in warnings)
    assert any("continuity" in warning for warning in warnings)
    assert any("Reference ID" in warning for warning in shot_warnings(current, [beat], [prior, current], [], reference_ids={"REF001"}))
    outside = current.model_copy(update={"start_sec": 7, "end_sec": 9})
    assert any("범위를 벗어" in warning for warning in shot_warnings(outside, [beat], [outside], []))


def test_g3_session_roundtrip_keeps_beats_shots_and_line_ids(tmp_path):
    session = LyricsWorldSession(
        lyrics_text="새벽에 돌아서\n붉은 표를 남겨", duration_sec=20,
        audio_map=AudioMap(source_path="song.wav", duration_sec=20, sample_rate=22050),
    )
    session.analyze()
    beat = StoryBeat(beat_id="B001", start_sec=0, end_sec=20, dramatic_question="무엇을 남길까?", change="", visual_event="", lyric_line_ids=["L001", "L002"], music_cue_ids=["MV01"])
    session.story_beats = [beat]
    session.shots = [draft_shot(beat)]
    session_file = tmp_path / "감독 세션 日本語.json"
    session.export(session_file)
    restored = LyricsWorldSession.import_file(session_file)
    assert restored.story_beats[0].lyric_line_ids == ["L001", "L002"]
    assert restored.story_beats[0].music_cue_ids == ["MV01"]
    assert restored.shots[0].lyric_line_ids == ["L001", "L002"]
    assert restored.shots[0].music_cue_ids == ["MV01"]


def test_offscreen_story_and_shot_pages_are_active_and_editable():
    from PySide6.QtWidgets import QApplication
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.pages.count() == 7
    assert window.nav_buttons[5].isEnabled()
    assert window.nav_buttons[6].isEnabled()
    session = window.session
    session.lines = _lines()
    session.mv_timeline = [MVTimelineCue(cue_id="MV01", time_sec=0, priority=0.8, cue_type="lyric_entry", reasons=[], lyric_line_ids=["L001"], recommended_visual_action="세계 제시")]
    session.duration_sec = 25
    window.story_room_page._auto_draft()
    assert session.story_beats
    window.shot_board_page.refresh()
    window.shot_board_page._add_shot()
    assert session.shots
    assert session.shots[0].lyric_line_ids
    assert not window.autosave_timer.isActive()  # an unsaved new session has no autosave target
    window.close()
