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
    assert "B001" in page.edit_status.text()
    assert "Beat 변경 적용 완료" in page.edit_status.text()
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


# ---------------------------------------------------------------- 1.1.1 hardening

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QPushButton  # noqa: E402

from mvstudio.story_engine import effective_duration, timeline_warnings  # noqa: E402


def _row_of(page: StoryRoomPage, beat_id: str) -> int:
    return next(i for i in range(page.beat_list.count()) if page.beat_list.item(i).data(Qt.UserRole) == beat_id)


def _answer_pending_dialog(choice: str, seen: list[str]):
    """Click a real button of the modal pending-changes dialog once it is shown."""
    def attempt(remaining: int = 100):
        dialog = QApplication.activeModalWidget()
        if dialog is not None and dialog.objectName() == "g3PendingChangesDialog":
            button = dialog.findChild(QPushButton, choice)
            seen.append(button.text())
            QTest.mouseClick(button, Qt.LeftButton)
            return
        if remaining:
            QTimer.singleShot(20, lambda: attempt(remaining - 1))
    QTimer.singleShot(0, attempt)


def _click_row(page: StoryRoomPage, beat_id: str):
    list_widget = page.beat_list
    rect = list_widget.visualItemRect(list_widget.item(_row_of(page, beat_id)))
    QTest.mouseClick(list_widget.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())


def test_end_at_exact_song_duration_survives_text_only_save():
    calls: list[str] = []
    session = LyricsWorldSession(
        duration_sec=192.046,
        audio_map=AudioMap(source_path="song.wav", duration_sec=192.046, sample_rate=44100),
        story_beats=[_beat("B001", 0, 100.0), _beat("B002", 100.0, 192.046)],
    )
    app, page = _page(session, calls)
    _click_row(page, "B002")
    app.processEvents()
    assert page.beat_list.currentItem().data(Qt.UserRole) == "B002"
    assert page.end.decimals() == 3 and abs(page.end.singleStep() - 0.001) < 1e-12
    assert f"{page.end.value():.3f}" == "192.046"
    page.question.setText("곡 끝까지 이어지는 질문")
    app.processEvents()
    assert page.save_button.isEnabled()
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    saved = next(beat for beat in session.story_beats if beat.beat_id == "B002")
    assert saved.dramatic_question == "곡 끝까지 이어지는 질문"
    assert saved.end_sec == 192.046
    assert saved.start_sec == 100.0
    assert calls == ["changed"]
    assert "Beat 변경 적용 완료" in page.edit_status.text()
    assert page.beat_list.currentItem().data(Qt.UserRole) == "B002"
    page.close()


def test_text_and_notes_only_save_preserves_exact_timestamps():
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=20, story_beats=[_beat("B001", 1.234, 5.678)])
    app, page = _page(session, calls)
    page.notes.setPlainText("메모만 바꿈")
    page.question.setText("질문도 바꿈")
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    beat = session.story_beats[0]
    assert (beat.start_sec, beat.end_sec) == (1.234, 5.678)
    assert beat.notes == "메모만 바꿈"
    assert calls == ["changed"]

    # Sub-millisecond source timestamps are never re-quantized by a text-only edit.
    session.story_beats[0] = beat.model_copy(update={"start_sec": 1.23449, "end_sec": 5.67851})
    page.refresh()
    page.notes.setPlainText("두 번째 메모")
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    assert (session.story_beats[0].start_sec, session.story_beats[0].end_sec) == (1.23449, 5.67851)
    page.close()


def test_real_time_edit_is_applied_with_millisecond_precision():
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=20, story_beats=[_beat("B001", 1.234, 5.678)])
    app, page = _page(session, calls)
    page.start.setFocus()
    page.start.selectAll()
    QTest.keyClicks(page.start, "1.235")
    QTest.keyClick(page.start, Qt.Key_Tab)
    app.processEvents()
    assert page.dirty
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    assert abs(session.story_beats[0].start_sec - 1.235) < 1e-9
    assert session.story_beats[0].end_sec == 5.678
    assert calls == ["changed"]
    page.close()


def test_dirty_reverts_to_clean_when_value_restored():
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=20, story_beats=[_beat("B001", 1.234, 5.678, "q")])
    app, page = _page(session, calls)
    page.question.setText("q2")
    assert page.dirty and page.save_button.isEnabled()
    page.question.setText("q")
    assert not page.dirty
    assert not page.save_button.isEnabled()
    assert page.edit_status.text() == "변경 없음"
    page.start.setValue(1.5)
    assert page.dirty
    page.start.setValue(1.234)
    assert not page.dirty and not page.save_button.isEnabled()
    page.close()


def test_unsaved_edit_selection_cancel_discard_apply():
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=20, story_beats=[_beat("B001", 0, 5, "q1"), _beat("B002", 5, 10, "q2")])
    app, page = _page(session, calls)
    seen: list[str] = []

    page.question.setText("편집 중")
    _answer_pending_dialog("g3PendingCancel", seen)
    _click_row(page, "B002")
    app.processEvents()
    assert seen == ["취소"]
    assert page.beat_list.currentItem().data(Qt.UserRole) == "B001"
    assert page.question.text() == "편집 중"
    assert page.dirty
    assert session.story_beats[0].dramatic_question == "q1"

    _answer_pending_dialog("g3PendingDiscard", seen)
    _click_row(page, "B002")
    app.processEvents()
    assert seen[-1] == "버리기"
    assert page.beat_list.currentItem().data(Qt.UserRole) == "B002"
    assert page.question.text() == "q2"
    assert not page.dirty
    assert session.story_beats[0].dramatic_question == "q1"
    assert calls == []

    page.question.setText("B002 적용")
    _answer_pending_dialog("g3PendingApply", seen)
    _click_row(page, "B001")
    app.processEvents()
    assert seen[-1] == "변경 적용"
    assert session.story_beats[1].dramatic_question == "B002 적용"
    assert page.beat_list.currentItem().data(Qt.UserRole) == "B001"
    assert page.question.text() == "q1"
    assert not page.dirty
    assert calls == ["changed"]
    page.close()


def test_unsaved_edit_apply_failure_keeps_current_beat(monkeypatch):
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=20, story_beats=[_beat("B001", 0, 5), _beat("B002", 5, 10)])
    app, page = _page(session, calls)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    seen: list[str] = []
    page.end.setValue(0)
    _answer_pending_dialog("g3PendingApply", seen)
    _click_row(page, "B002")
    app.processEvents()
    assert seen == ["변경 적용"]
    assert page.beat_list.currentItem().data(Qt.UserRole) == "B001"
    assert page.dirty
    assert "변경 적용 실패" in page.edit_status.text()
    assert (session.story_beats[0].start_sec, session.story_beats[0].end_sec) == (0, 5)
    assert calls == []
    page.close()


def test_dirty_add_auto_draft_delete_cancel_do_not_touch_beats():
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=30, story_beats=[_beat("B001", 0, 5, "q1")])
    app, page = _page(session, calls)
    before = [beat.model_dump() for beat in session.story_beats]
    seen: list[str] = []
    page.question.setText("편집 중")

    _answer_pending_dialog("g3PendingCancel", seen)
    QTest.mouseClick(page.add_button, Qt.LeftButton)
    app.processEvents()
    assert [beat.model_dump() for beat in session.story_beats] == before
    assert page.question.text() == "편집 중" and page.dirty

    _answer_pending_dialog("g3PendingCancel", seen)
    QTest.mouseClick(page.auto_button, Qt.LeftButton)
    app.processEvents()
    assert [beat.model_dump() for beat in session.story_beats] == before
    assert page.question.text() == "편집 중" and page.dirty

    _answer_pending_dialog("g3PendingCancel", seen)
    QTest.mouseClick(page.delete_button, Qt.LeftButton)
    app.processEvents()
    assert [beat.model_dump() for beat in session.story_beats] == before
    assert page.question.text() == "편집 중" and page.dirty
    assert seen == ["취소", "취소", "취소"]
    assert calls == []
    page.close()


def test_dirty_add_apply_saves_then_adds():
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=30, story_beats=[_beat("B001", 0, 5, "q1")])
    app, page = _page(session, calls)
    seen: list[str] = []
    page.question.setText("적용 후 추가")
    _answer_pending_dialog("g3PendingApply", seen)
    QTest.mouseClick(page.add_button, Qt.LeftButton)
    app.processEvents()
    assert seen == ["변경 적용"]
    assert session.story_beats[0].dramatic_question == "적용 후 추가"
    assert (session.story_beats[0].start_sec, session.story_beats[0].end_sec) == (0, 5)
    assert len(session.story_beats) == 2
    assert (session.story_beats[1].start_sec, session.story_beats[1].end_sec) == (5, 15)
    assert calls == ["changed", "changed"]
    page.close()


def test_background_refresh_keeps_unapplied_edits():
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=30, story_beats=[_beat("B001", 0, 5, "q1")])
    app, page = _page(session, calls)
    page.notes.setPlainText("아직 적용 안 한 메모")
    page.refresh()
    assert page.notes.toPlainText() == "아직 적용 안 한 메모"
    assert page.dirty and page.save_button.isEnabled()
    page.close()


def test_start_not_before_end_blocks_save(monkeypatch):
    calls: list[str] = []
    session = LyricsWorldSession(duration_sec=20, story_beats=[_beat("B001", 2, 5)])
    app, page = _page(session, calls)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    page.start.setValue(5)
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    assert (session.story_beats[0].start_sec, session.story_beats[0].end_sec) == (2, 5)
    assert "변경 적용 실패" in page.edit_status.text()
    assert page.dirty
    assert calls == []
    page.close()


def test_meaningful_duration_overflow_blocks_save_with_three_decimals(monkeypatch):
    calls: list[str] = []
    session = LyricsWorldSession(
        duration_sec=200,
        audio_map=AudioMap(source_path="song.wav", duration_sec=192.046, sample_rate=44100),
        story_beats=[_beat("B001", 100, 192.046)],
    )
    app, page = _page(session, calls)
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text, *a, **k: messages.append(text) or QMessageBox.Ok)
    page.end.setValue(193.0)
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    assert session.story_beats[0].end_sec == 192.046
    assert "0.000 ~ 192.046초" in messages[-1]
    assert "0.000 ~ 192.046초" in page.edit_status.text()
    page.end.setValue(192.047)
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    assert session.story_beats[0].end_sec == 192.046
    assert len(messages) == 2
    assert calls == []
    page.close()


def test_effective_duration_prefers_audio_and_ignores_zero():
    audio = AudioMap(source_path="a.wav", duration_sec=192.046, sample_rate=44100)
    assert effective_duration(LyricsWorldSession(duration_sec=50, audio_map=audio)) == 192.046
    zero_audio = AudioMap.model_construct(source_path="a.wav", duration_sec=0, sample_rate=44100)
    assert effective_duration(LyricsWorldSession(duration_sec=50, audio_map=zero_audio)) == 50
    assert effective_duration(LyricsWorldSession(duration_sec=0)) is None
    assert effective_duration(LyricsWorldSession()) is None


def test_production_readiness_uses_same_effective_duration():
    from mvstudio.production_orchestrator import build_production_readiness

    session = LyricsWorldSession(
        duration_sec=300,
        audio_map=AudioMap(source_path="song.wav", duration_sec=192.046, sample_rate=44100),
        story_beats=[_beat("B001", 0, 100), _beat("B002", 100, 192.046)],
    )
    story = build_production_readiness(session).stage("story")
    codes = {issue.code for issue in story.issues}
    assert "TRAILING_GAP" not in codes, codes
    session.story_beats = [_beat("B001", 0, 100)]
    story = build_production_readiness(session).stage("story")
    trailing = [issue for issue in story.issues if issue.code == "TRAILING_GAP"]
    assert trailing and "92.05s" in trailing[0].message


def test_full_duration_and_leading_gap_timeline_warnings():
    beats = [_beat("B001", 0, 192.046), _beat("B002", 10, 20), _beat("B003", 20, 40)]
    assert "full_duration_overlap" in [w.code for w in timeline_warnings(beats, 192.046)]
    normal = [_beat("B001", 0, 120), _beat("B002", 120, 192.046)]
    normal_codes = [w.code for w in timeline_warnings(normal, 192.046)]
    assert "full_duration_overlap" not in normal_codes and "overlap" not in normal_codes
    single = [_beat("B001", 0, 192.046)]
    assert timeline_warnings(single, 192.046) == []
    gap_codes = [w.code for w in timeline_warnings([_beat("B001", 5, 192.046)], 192.046)]
    assert "leading_gap" in gap_codes


def _story_window():
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.session.duration_sec = 20
    window.session.story_beats = [_beat("B001", 0, 10, "q1"), _beat("B002", 10, 20, "q2")]
    window.story_room_page.refresh()
    window.resize(1100, 720)
    window.show()
    window._switch(window.pages.indexOf(window.story_room_page))
    app.processEvents()
    return app, window


def test_story_room_action_buttons_fit_at_1100x720():
    app, window = _story_window()
    page = window.story_room_page
    assert (window.width(), window.height()) == (1100, 720)
    assert page.isVisible()
    page.question.setText("dirty")  # enable Save so its real (bold) style is laid out
    app.processEvents()
    buttons = [page.auto_button, page.add_button, page.save_button, page.delete_button]
    for button in buttons:
        assert button.isVisible()
        assert button.height() >= 44
        text_width = button.fontMetrics().horizontalAdvance(button.text())
        assert button.sizeHint().width() <= button.width(), (button.text(), button.sizeHint(), button.width())
        assert text_width < button.width(), (button.text(), text_width, button.width())
        assert button.visibleRegion().boundingRect().width() == button.width()
    # 2×2 layout: auto | add on the first row, save | delete on the second.
    assert page.auto_button.y() == page.add_button.y() < page.save_button.y() == page.delete_button.y()
    assert page.auto_button.x() == page.save_button.x() < page.add_button.x() == page.delete_button.x()
    window.close()


def _sample_color(button):
    image = QImage(button.size(), QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    button.render(image)
    return image.pixelColor(6, image.height() // 2)


def test_primary_save_button_states_are_visually_distinct():
    app, window = _story_window()
    page = window.story_room_page
    style = window.styleSheet()
    for selector in ("QPushButton#primary:disabled", "QPushButton#primary:hover", "QPushButton#primary:pressed"):
        assert selector in style
    assert not page.save_button.isEnabled()
    disabled = _sample_color(page.save_button)
    page.question.setText("dirty")
    app.processEvents()
    assert page.save_button.isEnabled()
    enabled = _sample_color(page.save_button)
    page.save_button.setDown(True)
    app.processEvents()
    pressed = _sample_color(page.save_button)
    page.save_button.setDown(False)

    def distance(a, b):
        return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())

    assert distance(disabled, enabled) > 60, (disabled.name(), enabled.name())
    assert distance(enabled, pressed) > 40, (enabled.name(), pressed.name())
    # Dark theme: none of the states may turn into a light/white surface.
    assert all(color.lightness() < 160 for color in (disabled, enabled, pressed))
    window.close()


def test_main_window_story_room_click_save_keeps_selection():
    app, window = _story_window()
    page = window.story_room_page
    assert page.beat_list.currentItem().data(Qt.UserRole) == "B001"
    page.question.setText("B001 새 질문")
    QTest.mouseClick(page.save_button, Qt.LeftButton)
    app.processEvents()
    assert window.session.story_beats[0].dramatic_question == "B001 새 질문"
    assert page.beat_list.currentItem().data(Qt.UserRole) == "B001"
    assert "상단 [세션 저장]" in page.edit_status.text()
    assert not page.save_button.isEnabled()
    window.close()
