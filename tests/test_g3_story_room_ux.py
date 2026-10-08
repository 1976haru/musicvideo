from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from mvstudio.g3_ui import StoryRoomPage
from mvstudio.models import AudioMap, StoryBeat
from mvstudio.session import LyricsWorldSession


def _beat(beat_id: str, start: float, end: float, question: str = "기존 질문") -> StoryBeat:
    return StoryBeat(
        beat_id=beat_id, start_sec=start, end_sec=end,
        dramatic_question=question, change="", visual_event="",
    )


def _page(session: LyricsWorldSession, calls: list[str]):
    app = QApplication.instance() or QApplication([])
    page = StoryRoomPage(lambda: session, lambda: calls.append("changed"))
    page.resize(1100, 720)
    page.show()
    app.processEvents()
    return app, page


def test_beat_edit_dirty_click_save_feedback_and_selection_stability():
    calls: list[str] = []
    session = LyricsWorldSession(
        duration_sec=20,
        audio_map=AudioMap(source_path="song.wav", duration_sec=20, sample_rate=44100),
        story_beats=[_beat("B001", 0, 10), _beat("B002", 10, 20)],
    )
    app, page = _page(session, calls)
    assert page.beat_list.currentItem().data(Qt.UserRole) == "B001"
    assert not page.dirty
    assert not page.save_button.isEnabled()
    assert page.edit_status.text() == "변경 없음"

    page.question.setText("한글과 日本語가 남는 새로운 극적 질문")
    app.processEvents()
    assert page.dirty
    assert page.save_button.isEnabled()
    assert "아직 적용하지 않음" in page.edit_status.text()

    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    assert session.story_beats[0].dramatic_question == "한글과 日本語가 남는 새로운 극적 질문"
    assert not page.dirty
    assert not page.save_button.isEnabled()
    assert page.beat_list.currentItem().data(Qt.UserRole) == "B001"
    assert "B001 변경 적용 완료" in page.edit_status.text()
    assert "세션 저장" in page.edit_status.text()
    assert "한글과 日本語" in page.beat_list.currentItem().text()
    assert calls == ["changed"]
    page.close()


def test_invalid_time_blocks_save_and_reports_failure(monkeypatch):
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=10, story_beats=[_beat("B001", 0, 5)])
    app, page = _page(session, calls)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    page.start.setValue(6)
    page.end.setValue(5)
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    assert (session.story_beats[0].start_sec, session.story_beats[0].end_sec) == (0, 5)
    assert page.dirty
    assert "변경 적용 실패" in page.edit_status.text()
    assert calls == []
    page.close()


def test_add_beat_uses_selected_following_gap_and_preserves_existing_beats():
    calls: list[str] = []
    originals = [_beat("B001", 0, 2), _beat("B002", 4, 6), _beat("B003", 8, 10)]
    session = LyricsWorldSession(duration_sec=10, story_beats=[item.model_copy(deep=True) for item in originals])
    app, page = _page(session, calls)
    page.beat_list.setCurrentRow(0)
    before = {beat.beat_id: beat.model_dump() for beat in session.story_beats}
    QTest.mouseClick(page.add_button, Qt.LeftButton)
    app.processEvents()
    added = next(beat for beat in session.story_beats if beat.beat_id not in before)
    assert (added.start_sec, added.end_sec) == (2, 4)
    assert all(next(item for item in session.story_beats if item.beat_id == key).model_dump() == value for key, value in before.items())
    assert calls == ["changed"]
    page.close()


def test_add_first_beat_never_spans_entire_song():
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=192.04)
    app, page = _page(session, calls)
    QTest.mouseClick(page.add_button, Qt.LeftButton)
    app.processEvents()
    assert len(session.story_beats) == 1
    added = session.story_beats[0]
    assert added.start_sec == 0
    assert 0.10 <= added.end_sec <= 10.0
    assert added.end_sec < 192.04
    page.close()


def test_add_when_timeline_full_keeps_all_beats(monkeypatch):
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=10, story_beats=[_beat("B001", 0, 5), _beat("B002", 5, 10)])
    app, page = _page(session, calls)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    before = [beat.model_dump() for beat in session.story_beats]
    QTest.mouseClick(page.add_button, Qt.LeftButton)
    app.processEvents()
    assert [beat.model_dump() for beat in session.story_beats] == before
    assert "이미 Story Beat로 채워져" in page.edit_status.text()
    assert calls == []
    page.close()


def test_add_beat_never_mutates_existing_b001_through_b016():
    calls: list[str] = []
    beats = []
    cursor = 0.0
    for index in range(1, 17):
        beats.append(_beat(f"B{index:03d}", cursor, cursor + 1.0, f"질문 {index}"))
        cursor += 1.0
        if index == 8:
            cursor += 2.0
    session = LyricsWorldSession(duration_sec=18, story_beats=[beat.model_copy(deep=True) for beat in beats])
    app, page = _page(session, calls)
    b008_row = next(i for i in range(page.beat_list.count()) if page.beat_list.item(i).data(Qt.UserRole) == "B008")
    page.beat_list.setCurrentRow(b008_row)
    before = {beat.beat_id: beat.model_dump() for beat in session.story_beats}
    QTest.mouseClick(page.add_button, Qt.LeftButton)
    app.processEvents()
    assert len(session.story_beats) == 17
    assert all(next(item for item in session.story_beats if item.beat_id == key).model_dump() == value for key, value in before.items())
    added = next(item for item in session.story_beats if item.beat_id not in before)
    assert (added.start_sec, added.end_sec) == (8.0, 10.0)
    page.close()


def test_overlap_save_is_nonblocking_but_visibly_warned():
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=10, story_beats=[_beat("B001", 0, 5), _beat("B002", 5, 10)])
    app, page = _page(session, calls)
    page.end.setValue(7)
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    assert session.story_beats[0].end_sec == 7
    assert "겹침" in page.edit_status.text()
    assert calls == ["changed"]
    page.close()


def test_beat_save_keeps_main_window_autosave_contract(tmp_path):
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(1100, 720)
    window.session.duration_sec = 10
    window.session.story_beats = [_beat("B001", 0, 10)]
    window.session.export(tmp_path / "자동저장 세션.json")
    page = window.story_room_page
    page.refresh()
    page.question.setText("자동저장 예약 확인")
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    assert window.autosave_timer.isActive()
    assert "세션 자동저장 예약" in page.edit_status.text()
    window.autosave_timer.stop()
    window.close()
