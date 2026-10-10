from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QSplitter, QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .models import CameraSpec, ShotSpec, StoryBeat
from .story_engine import (
    beat_traceability_warnings, cinematic_warnings, draft_shot, draft_story_beats,
    duplicate_id_warnings, effective_duration, literalization_warnings, motif_progression_warnings,
    next_beat_id, next_shot_id, reference_is_eligible, shot_timeline_warnings,
    shot_warnings, timeline_warnings,
)


def _text(value: str = "", height: int = 68) -> QTextEdit:
    widget = QTextEdit()
    widget.setPlainText(value)
    widget.setMinimumHeight(height)
    return widget


def _line(value: str = "") -> QLineEdit:
    widget = QLineEdit(value)
    widget.setMinimumHeight(42)
    return widget


TIME_DECIMALS = 3
# Half of one displayed time unit (0.001s): absorbs UI rounding / float noise, nothing more.
TIME_TOLERANCE = 0.5 * 10 ** -TIME_DECIMALS + 1e-9


def _time(value: float = 0.0) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setRange(0, 86400)
    widget.setDecimals(TIME_DECIMALS)
    widget.setSingleStep(0.001)
    widget.setSuffix(" s")
    widget.setMinimumHeight(42)
    widget.setValue(value)
    return widget


def _pane(title: str, child: QWidget) -> QWidget:
    pane = QWidget()
    pane.setObjectName("g3Pane")
    pane.setAutoFillBackground(False)
    layout = QVBoxLayout(pane)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(10)
    heading = QLabel(title)
    heading.setObjectName("smallTitle")
    layout.addWidget(heading)
    layout.addWidget(child, 1)
    return pane


class StoryRoomPage(QWidget):
    def __init__(self, session_getter, on_change):
        super().__init__()
        self.setObjectName("g3StoryRoom")
        self.session_getter = session_getter
        self.on_change = on_change
        self._loading = False
        self._selection_guard = False
        self.dirty = False
        # Beat currently shown in the form, the model it was loaded from, the spinbox
        # values right after loading (to detect real time edits) and the form snapshot.
        self._editing_beat_id: str | None = None
        self._loaded_beat: StoryBeat | None = None
        self._loaded_times: tuple[float, float] = (0.0, 0.0)
        self._snapshot: tuple | None = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(12)
        title = QLabel("STORY ROOM · 노래 전체를 서사 Beat로 설계")
        title.setObjectName("sectionTitle")
        outer.addWidget(title)
        outer.addWidget(QLabel("가사와 음악 cue를 근거로 묶어 장면의 변화와 모티프 진행을 계획합니다. 한 줄마다 한 Beat를 만들 필요는 없습니다."))
        self.chain_label = QLabel("World Concept → World Bible 연결 대기")
        self.chain_label.setObjectName("muted")
        outer.addWidget(self.chain_label)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("g3Splitter")
        self.evidence = QListWidget()
        self.evidence.setObjectName("g3EvidenceList")
        self.beat_list = QListWidget()
        self.beat_list.setObjectName("g3BeatList")
        splitter.addWidget(_pane("음악 + 가사 근거", self.evidence))
        splitter.addWidget(_pane("Story Beat 순서", self.beat_list))

        detail_host = QWidget()
        detail_host.setObjectName("g3DetailHost")
        detail_host.setAutoFillBackground(False)
        detail_outer = QVBoxLayout(detail_host)
        detail_scroll = QScrollArea()
        detail_scroll.setObjectName("g3Scroll")
        detail_scroll.setWidgetResizable(True)
        detail_scroll.viewport().setAutoFillBackground(False)
        form_host = QWidget()
        form_host.setObjectName("g3FormHost")
        form_host.setAutoFillBackground(False)
        form = QFormLayout(form_host)
        form.setSpacing(8)
        self.start = _time()
        self.end = _time()
        self.question = _line()
        self.change = _text()
        self.visual = _text()
        self.motif = _line()
        self.phase = QComboBox()
        for key, label in [("none", "없음"), ("setup", "SETUP"), ("development", "DEVELOPMENT / TRANSFORMATION"), ("payoff", "PAYOFF")]:
            self.phase.addItem(label, key)
        self.lyric_ids = _line()
        self.cue_ids = _line()
        self.lyric_intent = _text()
        self.emotion = _line()
        self.world_refs = _text()
        self.reference_ids = _line()
        self.notes = _text()
        for label, widget in [
            ("시작 / 종료", self._time_row()),
            ("극적 질문", self.question), ("변화", self.change), ("시각 사건", self.visual),
            ("Motif", self.motif), ("Motif 단계", self.phase), ("Lyric Line ID", self.lyric_ids),
            ("Music Cue ID", self.cue_ids), ("가사 의도", self.lyric_intent), ("감정 상태", self.emotion),
            ("World rule refs (한 줄마다 하나)", self.world_refs), ("Reference ID", self.reference_ids), ("메모", self.notes),
        ]:
            form.addRow(label, widget)
        detail_scroll.setWidget(form_host)
        detail_outer.addWidget(detail_scroll, 1)
        self.warning_label = QLabel("시간 경고 없음")
        self.warning_label.setWordWrap(True)
        detail_outer.addWidget(self.warning_label)
        self.edit_status = QLabel("변경 없음")
        self.edit_status.setObjectName("g3BeatEditStatus")
        self.edit_status.setWordWrap(True)
        detail_outer.addWidget(self.edit_status)
        # 2×2 grid: four buttons in one row were clipped (~79px each) at 1100×720.
        actions = QGridLayout()
        actions.setHorizontalSpacing(8)
        actions.setVerticalSpacing(8)
        self.auto_button = QPushButton("자동 초안 만들기")
        self.add_button = QPushButton("Beat 추가")
        self.save_button = QPushButton("Beat 변경 적용")
        self.delete_button = QPushButton("Beat 삭제")
        self.save_button.setObjectName("primary")
        for index, button in enumerate((self.auto_button, self.add_button, self.save_button, self.delete_button)):
            button.setMinimumHeight(44)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            actions.addWidget(button, index // 2, index % 2)
        actions.setColumnStretch(0, 1)
        actions.setColumnStretch(1, 1)
        detail_outer.addLayout(actions)
        splitter.addWidget(_pane("선택 Beat 편집", detail_host))
        splitter.setSizes([300, 420, 560])
        outer.addWidget(splitter, 1)
        self.beat_list.currentRowChanged.connect(self._on_row_changed)
        self.auto_button.clicked.connect(self._auto_draft)
        self.add_button.clicked.connect(self._add_beat)
        self.save_button.clicked.connect(self._save_selected)
        self.delete_button.clicked.connect(self._delete_selected)
        for widget in (self.start, self.end):
            widget.valueChanged.connect(self._mark_dirty)
        for widget in (self.question, self.motif, self.lyric_ids, self.cue_ids, self.emotion, self.reference_ids):
            widget.textChanged.connect(self._mark_dirty)
        for widget in (self.change, self.visual, self.lyric_intent, self.world_refs, self.notes):
            widget.textChanged.connect(self._mark_dirty)
        self.phase.currentIndexChanged.connect(self._mark_dirty)
        self.refresh()

    def _time_row(self):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.start)
        layout.addWidget(QLabel("→"))
        layout.addWidget(self.end)
        return row

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in text.replace("\n", ",").split(",") if item.strip()))

    def refresh(self):
        session = self.session_getter()
        previous_id = self._editing_beat_id
        # Background refreshes (music analysis, session save, …) must not wipe edits the
        # user has not applied yet, as long as the underlying Beat is unchanged.
        current_model = next((beat for beat in session.story_beats if beat.beat_id == previous_id), None)
        keep_edits = self.dirty and current_model is not None and current_model == self._loaded_beat
        self.evidence.clear()
        if session.audio_map:
            for section in session.audio_map.sections:
                self.evidence.addItem(f"{section.start_sec:6.2f}–{section.end_sec:6.2f}s  MUSIC · {section.label}")
        for cue in session.mv_timeline:
            self.evidence.addItem(f"{cue.time_sec:6.2f}s  CUE {cue.cue_id} · P={cue.priority:.2f} · {cue.recommended_visual_action}")
        if session.world_bible:
            for field, label in (("reality_rules", "Reality"), ("weather_rules", "Weather"), ("lighting_rules", "Lighting"), ("camera_rules", "Camera")):
                for idx, rule in enumerate(getattr(session.world_bible, field)):
                    self.evidence.addItem(f"WORLD RULE {field}:{idx} · {label}: {rule}")
        for line in session.lines:
            start = f"{line.start_sec:.2f}" if line.start_sec is not None else "--"
            self.evidence.addItem(f"{start}s  {line.line_id} · {line.text}")
        concept_id = session.selected_concept_id or "-"
        bible_source = session.world_bible.source_concept_id if session.world_bible and session.world_bible.source_concept_id else "-"
        self.chain_label.setText(
            f"선택 World Concept {concept_id} → World Bible {bible_source} → Beat 근거 ID → Shot의 beat_id / Reference ID"
        )
        self.beat_list.blockSignals(True)
        self.beat_list.clear()
        for beat in sorted(session.story_beats, key=lambda item: (item.start_sec, item.end_sec, item.beat_id)):
            item = QListWidgetItem(
                f"{beat.start_sec:7.3f}–{beat.end_sec:7.3f}s  {beat.beat_id} · {beat.setup_or_payoff.upper()} · {beat.motif or 'motif 없음'}\n{beat.dramatic_question}"
            )
            item.setData(Qt.UserRole, beat.beat_id)
            self.beat_list.addItem(item)
        if self.beat_list.count():
            restored = self._row_for(previous_id)
            self.beat_list.setCurrentRow(restored if restored >= 0 else 0)
        self.beat_list.blockSignals(False)
        row = self.beat_list.currentRow()
        restored_id = self.beat_list.item(row).data(Qt.UserRole) if row >= 0 else None
        if keep_edits and restored_id == previous_id:
            self._set_dirty(self.dirty)
        else:
            self._load_beat(restored_id)
        self._refresh_warnings()

    def _refresh_warnings(self):
        session = self.session_getter()
        warnings = timeline_warnings(session.story_beats, effective_duration(session))
        warnings.extend(duplicate_id_warnings(session.story_beats, session.shots))
        warnings.extend(motif_progression_warnings(session.story_beats))
        messages = [warning.message for warning in warnings]
        selected = self._selected_beat()
        if selected:
            known_rules = set()
            if session.world_bible:
                for field in ("reality_rules", "weather_rules", "lighting_rules", "camera_rules"):
                    known_rules.update(f"{field}:{idx}" for idx, _ in enumerate(getattr(session.world_bible, field)))
            messages.extend(beat_traceability_warnings(
                selected,
                {line.line_id for line in session.lines},
                {cue.cue_id for cue in session.mv_timeline},
                {asset.reference_id for asset in session.references},
                known_rules,
            ))
        self.warning_label.setText("\n".join(messages) if messages else "시간 및 근거 경고 없음 · Beat 연결을 확인했습니다.")

    def _row_for(self, beat_id: str | None) -> int:
        if beat_id is None:
            return -1
        return next((i for i in range(self.beat_list.count()) if self.beat_list.item(i).data(Qt.UserRole) == beat_id), -1)

    def _select_row_silently(self, beat_id: str | None):
        """Move the list highlight without triggering the pending-change guard."""
        self._selection_guard = True
        try:
            self.beat_list.setCurrentRow(self._row_for(beat_id))
        finally:
            self._selection_guard = False

    def _select_beat(self, beat_id: str | None):
        self._select_row_silently(beat_id)
        self._load_beat(beat_id)
        self._refresh_warnings()

    def _selected_beat(self):
        if self._editing_beat_id is None:
            return None
        return next((beat for beat in self.session_getter().story_beats if beat.beat_id == self._editing_beat_id), None)

    def _form_snapshot(self) -> tuple:
        return (
            round(self.start.value(), TIME_DECIMALS), round(self.end.value(), TIME_DECIMALS),
            self.question.text(), self.change.toPlainText(), self.visual.toPlainText(),
            self.motif.text(), self.phase.currentData(), self.lyric_ids.text(), self.cue_ids.text(),
            self.lyric_intent.toPlainText(), self.emotion.text(), self.world_refs.toPlainText(),
            self.reference_ids.text(), self.notes.toPlainText(),
        )

    def _set_dirty(self, value: bool, message: str | None = None):
        self.dirty = bool(value)
        active = self._selected_beat() is not None
        self.save_button.setEnabled(active and self.dirty)
        if message is not None:
            self.edit_status.setText(message)
        elif self.dirty:
            self.edit_status.setText("변경됨 · 아직 적용하지 않음")
        else:
            self.edit_status.setText("변경 없음")

    def _mark_dirty(self, *_):
        if self._loading or self._selected_beat() is None or self._snapshot is None:
            return
        # Dirty only while the form really differs from what was loaded (q → q2 → q is clean).
        self._set_dirty(self._form_snapshot() != self._snapshot)

    def _on_row_changed(self, row: int):
        if self._selection_guard:
            return
        target_id = self.beat_list.item(row).data(Qt.UserRole) if row >= 0 else None
        if target_id == self._editing_beat_id:
            return
        if not self.resolve_pending_changes():
            # Cancel (or a failed apply): put the highlight back on the Beat being edited.
            self._select_row_silently(self._editing_beat_id)
            return
        self._select_beat(target_id)

    def resolve_pending_changes(self) -> bool:
        """Ask what to do with unapplied edits. True means the caller may proceed."""
        if not self.dirty or self._selected_beat() is None:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("적용하지 않은 변경")
        box.setText(f"현재 Beat({self._editing_beat_id})에 적용하지 않은 변경이 있습니다.")
        box.setInformativeText("변경 적용: 저장 후 진행 · 버리기: 편집 내용을 버리고 진행 · 취소: 현재 편집 유지")
        box.setObjectName("g3PendingChangesDialog")
        apply_button = box.addButton("변경 적용", QMessageBox.AcceptRole)
        discard_button = box.addButton("버리기", QMessageBox.DestructiveRole)
        cancel_button = box.addButton("취소", QMessageBox.RejectRole)
        apply_button.setObjectName("g3PendingApply")
        discard_button.setObjectName("g3PendingDiscard")
        cancel_button.setObjectName("g3PendingCancel")
        box.setDefaultButton(apply_button)
        box.setEscapeButton(cancel_button)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()
        if clicked is apply_button:
            return self._save_selected()
        if clicked is discard_button:
            self._load_beat(self._editing_beat_id, "변경 사항을 버렸습니다")
            return True
        self.edit_status.setText("취소됨 · 현재 Beat 편집을 유지합니다 (아직 적용하지 않음)")
        return False

    def _load_selected(self, row: int):
        beat_id = self.beat_list.item(row).data(Qt.UserRole) if row >= 0 else None
        self._load_beat(beat_id)

    def _load_beat(self, beat_id: str | None, message: str | None = None):
        session = self.session_getter()
        beat = next((item for item in session.story_beats if item.beat_id == beat_id), None)
        self._editing_beat_id = beat.beat_id if beat else None
        self._loaded_beat = beat.model_copy(deep=True) if beat else None
        active = beat is not None
        for widget in (self.start, self.end, self.question, self.change, self.visual, self.motif, self.phase, self.lyric_ids, self.cue_ids, self.lyric_intent, self.emotion, self.world_refs, self.reference_ids, self.notes, self.delete_button):
            widget.setEnabled(active)
        if not active:
            self._snapshot = None
            self._set_dirty(False, message)
            return
        self._loading = True
        try:
            self.start.setValue(beat.start_sec)
            self.end.setValue(beat.end_sec)
            self.question.setText(beat.dramatic_question)
            self.change.setPlainText(beat.change)
            self.visual.setPlainText(beat.visual_event)
            self.motif.setText(beat.motif or "")
            phase_index = self.phase.findData(beat.setup_or_payoff)
            self.phase.setCurrentIndex(max(0, phase_index))
            self.lyric_ids.setText(", ".join(beat.lyric_line_ids))
            self.cue_ids.setText(", ".join(beat.music_cue_ids))
            self.lyric_intent.setPlainText(beat.lyric_intent)
            self.emotion.setText(beat.emotional_state)
            self.world_refs.setPlainText("\n".join(beat.world_rule_refs))
            self.reference_ids.setText(", ".join(beat.reference_ids))
            self.notes.setPlainText(beat.notes)
        finally:
            self._loading = False
        self._loaded_times = (self.start.value(), self.end.value())
        self._snapshot = self._form_snapshot()
        self._set_dirty(False, message)

    def _resolved_times(self, original: StoryBeat) -> tuple[float, float, bool, bool]:
        """Model times to store; untouched fields keep the original full-precision value."""
        start_edited = round(self.start.value(), TIME_DECIMALS) != round(self._loaded_times[0], TIME_DECIMALS)
        end_edited = round(self.end.value(), TIME_DECIMALS) != round(self._loaded_times[1], TIME_DECIMALS)
        start = self.start.value() if start_edited else original.start_sec
        end = self.end.value() if end_edited else original.end_sec
        return start, end, start_edited, end_edited

    def _auto_draft(self):
        if not self.resolve_pending_changes():
            return
        session = self.session_getter()
        bible = session.world_bible
        rules = []
        if bible:
            for field in ("reality_rules", "weather_rules", "lighting_rules", "camera_rules"):
                rules.extend(f"{field}:{idx}" for idx, _ in enumerate(getattr(bible, field)))
        session.story_beats = draft_story_beats(
            session.lines, session.mv_timeline,
            effective_duration(session),
            motif_pool=bible.recurring_motifs if bible else [],
            emotional_arc=session.analysis.emotional_arc if session.analysis else [],
            world_rule_refs=rules,
            bridges=session.bridges,
        )
        self.refresh()
        self.on_change()

    def _add_beat(self):
        if not self.resolve_pending_changes():
            return
        session = self.session_getter()
        beats = session.story_beats
        duration = float(effective_duration(session) or 10.0)
        ordered = sorted(beats, key=lambda item: (item.start_sec, item.end_sec, item.beat_id))
        occupied: list[tuple[float, float]] = []
        for item in ordered:
            start = max(0.0, min(duration, item.start_sec))
            end = max(0.0, min(duration, item.end_sec))
            if end <= start:
                continue
            if occupied and start <= occupied[-1][1] + 0.001:
                occupied[-1] = (occupied[-1][0], max(occupied[-1][1], end))
            else:
                occupied.append((start, end))
        gaps: list[tuple[float, float]] = []
        cursor = 0.0
        for start, end in occupied:
            if start - cursor >= 0.10:
                gaps.append((cursor, start))
            cursor = max(cursor, end)
        if duration - cursor >= 0.10:
            gaps.append((cursor, duration))
        if not gaps:
            message = "현재 전체 구간이 이미 Story Beat로 채워져 있습니다.\n새 Beat를 추가하려면 기존 Beat를 분할하거나 시간을 조정하세요."
            self.edit_status.setText(message)
            return
        selected = self._selected_beat()
        preferred = None
        if selected:
            preferred = next((gap for gap in gaps if abs(gap[0] - selected.end_sec) <= 0.05), None)
        gap_start, gap_end = preferred or max(gaps, key=lambda gap: (gap[1] - gap[0], -gap[0]))
        # A first Beat should be useful to edit, but must never consume the entire song by default.
        new_end = min(gap_end, gap_start + min(10.0, max(0.10, gap_end - gap_start)))
        beat_id = next_beat_id({beat.beat_id for beat in beats})
        beat = StoryBeat(beat_id=beat_id, start_sec=gap_start, end_sec=new_end, dramatic_question="이 구간의 질문은 무엇인가?", change="", visual_event="")
        beats.append(beat)
        self.refresh()
        self._select_beat(beat_id)
        self._set_dirty(False, f"{beat_id} 추가 완료 · 빈 구간 {gap_start:.3f}–{new_end:.3f}s")
        self.on_change()

    def _fail_save(self, title: str, message: str) -> bool:
        self.edit_status.setText("변경 적용 실패 · " + message)
        QMessageBox.warning(self, title, message)
        return False

    def _save_selected(self) -> bool:
        session = self.session_getter()
        selected = self._selected_beat()
        if selected is None:
            return False
        if not self.dirty:
            self._set_dirty(False, "저장할 변경이 없습니다")
            return True
        beat = selected
        row = session.story_beats.index(beat)
        start, end, start_edited, end_edited = self._resolved_times(self._loaded_beat or beat)
        duration = effective_duration(session)
        if start_edited and start < 0:
            return self._fail_save("Beat 시간을 확인하세요", "시작 시간은 0.000초 이상이어야 합니다.")
        if duration is not None:
            limit = f"Beat 시간은 음악 범위 0.000 ~ {duration:.3f}초 안에 있어야 합니다."
            # Only values the user actually typed are range-checked; untouched times keep
            # their stored value (existing out-of-range Beats stay a warning, not a blocker).
            if end_edited and end > duration:
                if end - duration > TIME_TOLERANCE:
                    return self._fail_save("Beat 시간을 확인하세요", limit + f" (입력 종료 {end:.3f}초)")
                end = duration
            if start_edited and start > duration:
                if start - duration > TIME_TOLERANCE:
                    return self._fail_save("Beat 시간을 확인하세요", limit + f" (입력 시작 {start:.3f}초)")
                start = duration
        if start >= end:
            return self._fail_save("Beat 시간을 확인하세요", f"시작 시간({start:.3f}초)은 종료 시간({end:.3f}초)보다 작아야 합니다.")
        changes = {
            "start_sec": start, "end_sec": end,
            "dramatic_question": self.question.text(), "change": self.change.toPlainText(),
            "visual_event": self.visual.toPlainText(), "motif": self.motif.text().strip() or None,
            "setup_or_payoff": self.phase.currentData(), "lyric_line_ids": self._tokens(self.lyric_ids.text()),
            "music_cue_ids": self._tokens(self.cue_ids.text()), "lyric_intent": self.lyric_intent.toPlainText(),
            "emotional_state": self.emotion.text(), "world_rule_refs": self._tokens(self.world_refs.toPlainText()),
            "reference_ids": self._tokens(self.reference_ids.text()), "notes": self.notes.toPlainText(),
        }
        try:
            updated = StoryBeat.model_validate({**beat.model_dump(), **changes})
        except Exception as exc:
            QMessageBox.warning(self, "Beat 값을 확인하세요", str(exc))
            self.edit_status.setText(f"변경 적용 실패 · {exc}")
            return False
        session.story_beats[row] = updated
        beat_id = beat.beat_id
        self.dirty = False
        self.refresh()
        self._select_beat(beat_id)
        overlap_messages = [
            warning.message for warning in timeline_warnings(session.story_beats, duration)
            if warning.code == "overlap" and beat_id in warning.item_ids
        ]
        if session.session_path:
            message = f"✓ {beat_id} · Beat 변경 적용 완료 · 세션 자동저장 예약"
        else:
            message = f"✓ {beat_id} · Beat 변경 적용 완료 · 상단 [세션 저장]으로 파일을 저장하세요"
        if overlap_messages:
            message += "\n⚠ 다른 Beat와 겹침: " + " / ".join(overlap_messages)
        self._set_dirty(False, message)
        self.on_change()
        return True

    def _delete_selected(self):
        beat = self._selected_beat()
        if beat is None:
            return
        if not self.resolve_pending_changes():
            return
        session = self.session_getter()
        beat = self._selected_beat()
        if beat is None:
            return
        removed = session.story_beats.pop(session.story_beats.index(beat))
        session.shots = [shot for shot in session.shots if shot.beat_id != removed.beat_id]
        self.refresh()
        self.on_change()


class ShotBoardPage(QWidget):
    def __init__(self, session_getter, on_change):
        super().__init__()
        self.setObjectName("g3ShotBoard")
        self.session_getter = session_getter
        self.on_change = on_change
        self._building = False
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(12)
        heading = QLabel("SHOT BOARD · Beat를 생성 단위 Shot으로 나누기")
        heading.setObjectName("sectionTitle")
        outer.addWidget(heading)
        outer.addWidget(QLabel("한 Shot에는 주요 행동 하나, 카메라 의도 하나, 감정 목적 하나를 둡니다. 각 Shot의 가사·음악 근거와 연속성을 확인하세요."))
        self.beat_combo = QComboBox()
        self.beat_combo.setMinimumHeight(44)
        outer.addWidget(self.beat_combo)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("g3Splitter")
        self.shot_list = QListWidget()
        self.shot_list.setObjectName("g3ShotList")
        splitter.addWidget(_pane("Storyboard 순서", self.shot_list))
        detail_host = QWidget()
        detail_host.setObjectName("g3DetailHost")
        detail_host.setAutoFillBackground(False)
        detail_layout = QVBoxLayout(detail_host)
        detail_scroll = QScrollArea()
        detail_scroll.setObjectName("g3Scroll")
        detail_scroll.setWidgetResizable(True)
        detail_scroll.viewport().setAutoFillBackground(False)
        form_host = QWidget()
        form_host.setObjectName("g3FormHost")
        form_host.setAutoFillBackground(False)
        form = QFormLayout(form_host)
        form.setSpacing(8)
        self.start, self.end = _time(), _time()
        self.narrative = _line()
        self.line_ids = _line()
        self.cue_ids = _line()
        self.intent = _text()
        self.strategy = QComboBox()
        for value in ("literal", "metaphor", "motif", "counterpoint", "performance", "silence"):
            self.strategy.addItem(value, value)
        self.subject, self.action, self.environment, self.composition = _text(), _text(), _text(), _text()
        self.framing, self.lens, self.angle, self.movement = _line(), _line(), _line(), _line()
        self.movement_strength = QComboBox()
        for value in ("locked", "subtle", "medium", "strong"):
            self.movement_strength.addItem(value, value)
        self.lighting, self.emotion, self.motif = _text(), _text(), _line()
        self.world_refs = _text()
        self.series_episode = QComboBox()
        self.series_episode.setMinimumHeight(42)
        self.series_entities = QListWidget()
        self.series_entities.setMaximumHeight(150)
        self.series_variants = QListWidget()
        self.series_variants.setMaximumHeight(150)
        self.continuity_in, self.continuity_out = _text(), _text()
        self.generation_mode = QComboBox()
        for value in ("t2v", "i2v", "first_last", "extend", "v2v"):
            self.generation_mode.addItem(value, value)
        self.negative = _text()
        self.references = QListWidget()
        self.references.setMaximumHeight(150)
        for label, widget in [
            ("시간", self._time_row()), ("연출 기능", self.narrative), ("Lyric Line ID", self.line_ids),
            ("Music Cue ID", self.cue_ids), ("가사 의도", self.intent), ("시각 전략", self.strategy),
            ("주체", self.subject), ("행동", self.action), ("환경", self.environment), ("구도", self.composition),
            ("Framing", self.framing), ("Lens", self.lens), ("Angle", self.angle), ("Camera movement", self.movement),
            ("Movement strength", self.movement_strength), ("Lighting", self.lighting), ("감정 목적", self.emotion),
            ("Motif", self.motif),
            ("Series Episode", self.series_episode),
            ("Series Entities", self.series_entities),
            ("Series Variants", self.series_variants),
            ("Continuity in", self.continuity_in), ("Continuity out", self.continuity_out),
            ("World rule refs", self.world_refs),
            ("Reference ID 선택", self.references), ("Generation mode", self.generation_mode), ("금지 요소", self.negative),
        ]:
            form.addRow(label, widget)
        detail_scroll.setWidget(form_host)
        detail_layout.addWidget(detail_scroll, 1)
        self.warning_label = QLabel("World Bible / continuity 경고 없음")
        self.warning_label.setWordWrap(True)
        detail_layout.addWidget(self.warning_label)
        controls = QHBoxLayout()
        self.add_button = QPushButton("Shot 추가")
        self.split_button = QPushButton("선택 Shot 시간 분할")
        self.duplicate_button = QPushButton("Shot 복제")
        self.delete_button = QPushButton("Shot 삭제")
        self.save_button = QPushButton("Shot 변경 저장")
        self.save_button.setObjectName("primary")
        for button in (self.add_button, self.split_button, self.duplicate_button, self.delete_button, self.save_button):
            button.setMinimumHeight(44)
            controls.addWidget(button)
        detail_layout.addLayout(controls)
        splitter.addWidget(_pane("선택 Shot Inspector", detail_host))
        splitter.setSizes([320, 780])
        outer.addWidget(splitter, 1)
        self.beat_combo.currentIndexChanged.connect(self.refresh_shots)
        self.shot_list.currentRowChanged.connect(self._load_selected)
        self.add_button.clicked.connect(self._add_shot)
        self.split_button.clicked.connect(self._split_shot)
        self.duplicate_button.clicked.connect(self._duplicate_shot)
        self.delete_button.clicked.connect(self._delete_shot)
        self.save_button.clicked.connect(self._save_selected)
        self.series_episode.currentIndexChanged.connect(self._on_series_episode_changed)
        self.series_entities.itemChanged.connect(lambda *_: self._refresh_series_variants())
        self.refresh()

    def _time_row(self):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.start)
        layout.addWidget(QLabel("→"))
        layout.addWidget(self.end)
        return row

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in text.replace("\n", ",").split(",") if item.strip()))

    def refresh(self):
        self._building = True
        session = self.session_getter()
        old = self.beat_combo.currentData()
        old_episode = self.series_episode.currentData()
        self.beat_combo.clear()
        for beat in session.story_beats:
            self.beat_combo.addItem(f"{beat.beat_id} · {beat.start_sec:.3f}–{beat.end_sec:.3f}s · {beat.motif or 'motif 없음'}", beat.beat_id)
        index = self.beat_combo.findData(old)
        self.beat_combo.setCurrentIndex(index if index >= 0 else (0 if self.beat_combo.count() else -1))

        self.series_episode.blockSignals(True)
        self.series_episode.clear()
        self.series_episode.addItem("단편 / Series 미지정", None)
        if session.series_bible:
            for episode in sorted(session.series_bible.episodes, key=lambda item: item.order):
                self.series_episode.addItem(f"{episode.episode_id} · {episode.title}", episode.episode_id)
        episode_index = self.series_episode.findData(old_episode)
        self.series_episode.setCurrentIndex(episode_index if episode_index >= 0 else 0)
        self.series_episode.blockSignals(False)
        self.series_episode.setEnabled(bool(session.series_bible))
        self._building = False
        self.refresh_shots()

    def _active_beat(self):
        beat_id = self.beat_combo.currentData()
        return next((beat for beat in self.session_getter().story_beats if beat.beat_id == beat_id), None)

    def refresh_shots(self):
        if self._building:
            return
        session = self.session_getter()
        beat = self._active_beat()
        current = self.shot_list.currentItem()
        previous_id = current.data(Qt.UserRole) if current else None
        self.shot_list.blockSignals(True)
        self.shot_list.clear()
        shots = [shot for shot in session.shots if beat and shot.beat_id == beat.beat_id]
        for shot in sorted(shots, key=lambda item: (item.start_sec, item.shot_id)):
            self.shot_list.addItem(f"{shot.start_sec:6.2f}–{shot.end_sec:6.2f}s  {shot.shot_id}\n{shot.narrative_function}")
        for index, shot in enumerate(sorted(shots, key=lambda item: (item.start_sec, item.shot_id))):
            self.shot_list.item(index).setData(Qt.UserRole, shot.shot_id)
        if shots:
            restored = next((i for i in range(self.shot_list.count()) if self.shot_list.item(i).data(Qt.UserRole) == previous_id), 0)
            self.shot_list.setCurrentRow(restored)
        self.shot_list.blockSignals(False)
        self._refresh_reference_choices()
        self._load_selected(self.shot_list.currentRow())

    def _selected_series_entity_ids(self) -> list[str]:
        return [
            self.series_entities.item(i).data(Qt.UserRole)
            for i in range(self.series_entities.count())
            if self.series_entities.item(i).checkState() == Qt.Checked
        ]

    def _selected_series_variant_ids(self) -> list[str]:
        return [
            self.series_variants.item(i).data(Qt.UserRole)
            for i in range(self.series_variants.count())
            if self.series_variants.item(i).checkState() == Qt.Checked
        ]

    def _refresh_series_entities(self, selected: list[str] | None = None):
        selected = selected or []
        session = self.session_getter()
        episode_id = self.series_episode.currentData()
        self.series_entities.blockSignals(True)
        self.series_entities.clear()
        for entity in session.series_entities:
            eligible = not episode_id or not entity.episode_presence or episode_id in entity.episode_presence
            item = QListWidgetItem(f"{entity.display_name} [{entity.entity_type}]")
            item.setData(Qt.UserRole, entity.entity_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if not eligible and entity.entity_id not in selected:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setText(item.text() + " · 이 EP 미등장")
            item.setCheckState(Qt.Checked if entity.entity_id in selected else Qt.Unchecked)
            self.series_entities.addItem(item)
        self.series_entities.blockSignals(False)

    def _refresh_series_variants(self, selected: list[str] | None = None):
        selected = selected if selected is not None else self._selected_series_variant_ids()
        session = self.session_getter()
        episode_id = self.series_episode.currentData()
        entity_ids = set(self._selected_series_entity_ids())
        self.series_variants.blockSignals(True)
        self.series_variants.clear()
        for entity in session.series_entities:
            if entity.entity_id not in entity_ids:
                continue
            for variant in entity.variants:
                if variant.episode_id and episode_id and variant.episode_id != episode_id:
                    continue
                label = f"{entity.display_name} · {variant.variant_id} · {variant.kind}"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, variant.variant_id)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if variant.variant_id in selected else Qt.Unchecked)
                self.series_variants.addItem(item)
        self.series_variants.blockSignals(False)

    def _on_series_episode_changed(self, *_):
        if self._building:
            return
        selected_entities = self._selected_series_entity_ids()
        selected_variants = self._selected_series_variant_ids()
        self._refresh_series_entities(selected_entities)
        self._refresh_series_variants(selected_variants)

    def _refresh_reference_choices(self, selected: list[str] | None = None):
        session = self.session_getter()
        if selected is None:
            shot = self._selected_shot()
            selected = shot.reference_ids if shot else []
        self.references.blockSignals(True)
        self.references.clear()
        for asset in session.references:
            scope_text = f"{asset.applies_to.value}" + (f":{asset.scope_id}" if asset.scope_id else "")
            item = QListWidgetItem(f"{asset.reference_id} · {asset.role.value} · {scope_text}")
            item.setData(Qt.UserRole, asset.reference_id)
            shot = self._selected_shot()
            eligible = shot is None or reference_is_eligible(asset, shot)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if eligible:
                item.setFlags(item.flags() | Qt.ItemIsEnabled)
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setText(item.text() + " · INELIGIBLE")
            item.setCheckState(Qt.Checked if asset.reference_id in selected else Qt.Unchecked)
            self.references.addItem(item)
        self.references.blockSignals(False)

    def _selected_shot(self):
        beat = self._active_beat()
        item = self.shot_list.currentItem()
        shot_id = item.data(Qt.UserRole) if item else None
        return next((shot for shot in self.session_getter().shots if beat and shot.beat_id == beat.beat_id and shot.shot_id == shot_id), None)

    def _load_selected(self, row: int):
        shot = self._selected_shot()
        active = shot is not None
        for widget in (self.start, self.end, self.narrative, self.line_ids, self.cue_ids, self.intent, self.strategy, self.subject, self.action, self.environment, self.composition, self.framing, self.lens, self.angle, self.movement, self.movement_strength, self.lighting, self.emotion, self.motif, self.series_entities, self.series_variants, self.continuity_in, self.continuity_out, self.world_refs, self.references, self.generation_mode, self.negative, self.save_button, self.delete_button, self.split_button, self.duplicate_button):
            widget.setEnabled(active)
        self.series_episode.setEnabled(bool(self.session_getter().series_bible))
        self.add_button.setEnabled(self._active_beat() is not None)
        if not active:
            self.warning_label.setText("Beat를 선택하고 Shot을 추가하세요.")
            return
        self.start.setValue(shot.start_sec)
        self.end.setValue(shot.end_sec)
        self._loaded_times = (shot.shot_id, self.start.value(), self.end.value())
        self.narrative.setText(shot.narrative_function)
        self.line_ids.setText(", ".join(shot.lyric_line_ids))
        self.cue_ids.setText(", ".join(shot.music_cue_ids))
        self.intent.setPlainText(shot.lyric_intent)
        self.strategy.setCurrentIndex(max(0, self.strategy.findData(shot.lyric_visual_strategy)))
        self.subject.setPlainText(shot.subject)
        self.action.setPlainText(shot.action)
        self.environment.setPlainText(shot.environment)
        self.composition.setPlainText(shot.composition)
        self.framing.setText(shot.camera.framing)
        self.lens.setText(shot.camera.lens)
        self.angle.setText(shot.camera.angle)
        self.movement.setText(shot.camera.movement)
        self.movement_strength.setCurrentIndex(max(0, self.movement_strength.findData(shot.camera.movement_strength)))
        self.lighting.setPlainText(shot.lighting)
        self.emotion.setPlainText(shot.emotional_note)
        self.motif.setText(shot.motif or "")
        episode_index = self.series_episode.findData(shot.series_episode_id)
        self.series_episode.blockSignals(True)
        self.series_episode.setCurrentIndex(episode_index if episode_index >= 0 else 0)
        self.series_episode.blockSignals(False)
        self._refresh_series_entities(shot.series_entity_ids)
        self._refresh_series_variants(shot.series_variant_ids)
        self.continuity_in.setPlainText("\n".join(shot.continuity_in))
        self.continuity_out.setPlainText("\n".join(shot.continuity_out))
        self.world_refs.setPlainText("\n".join(shot.world_rule_refs))
        self.generation_mode.setCurrentIndex(max(0, self.generation_mode.findData(shot.generation_mode)))
        self.negative.setPlainText("\n".join(shot.negative_constraints))
        self._refresh_reference_choices(shot.reference_ids)
        bible = self.session_getter().world_bible
        session = self.session_getter()
        known_rules = set()
        if bible:
            for field in ("reality_rules", "weather_rules", "lighting_rules", "camera_rules"):
                known_rules.update(f"{field}:{idx}" for idx, _ in enumerate(getattr(bible, field)))
        warnings = shot_warnings(
            shot, session.story_beats, session.shots, bible.forbidden_elements if bible else [],
            lyric_line_ids={line.line_id for line in session.lines},
            music_cue_ids={cue.cue_id for cue in session.mv_timeline},
            reference_ids={asset.reference_id for asset in session.references},
            world_rule_refs=known_rules,
            references=session.references,
        )
        warnings.extend(item.message for item in shot_timeline_warnings(session.story_beats, session.shots) if shot.shot_id in item.item_ids)
        warnings.extend(item.message for item in duplicate_id_warnings(session.story_beats, session.shots))
        beat_shots = [item for item in session.shots if item.beat_id == shot.beat_id]
        warnings.extend(item.message for item in cinematic_warnings(beat_shots))
        warnings.extend(item.message for item in literalization_warnings(beat_shots, {line.line_id: line.text for line in session.lines}))
        self.warning_label.setText("\n".join(warnings) if warnings else "World Bible / continuity 경고 없음")

    def _add_shot(self):
        session = self.session_getter()
        beat = self._active_beat()
        if not beat:
            return
        shot_id = next_shot_id(beat.beat_id, {item.shot_id for item in session.shots})
        ordinal = int(shot_id.rsplit("S", 1)[1])
        shot = draft_shot(beat, ordinal)
        if self.series_episode.currentData():
            shot = shot.model_copy(update={"series_episode_id": self.series_episode.currentData()})
        session.shots.append(shot)
        self.refresh_shots()
        target = next(i for i in range(self.shot_list.count()) if self.shot_list.item(i).data(Qt.UserRole) == shot_id)
        self.shot_list.setCurrentRow(target)
        self.on_change()

    def _duplicate_shot(self):
        shot = self._selected_shot()
        if not shot:
            return
        session = self.session_getter()
        used = {item.shot_id for item in session.shots}
        shot_id = next_shot_id(shot.beat_id or "B000", used)
        session.shots.append(shot.model_copy(update={"shot_id": shot_id}))
        self.refresh_shots()
        self.on_change()

    def _split_shot(self):
        shot = self._selected_shot()
        if not shot or shot.duration_sec < 0.2:
            return
        session = self.session_getter()
        middle = round((shot.start_sec + shot.end_sec) / 2, 3)
        used = {item.shot_id for item in session.shots}
        shot_id = f"{shot.shot_id}-B"
        n = 2
        while shot_id in used:
            shot_id = f"{shot.shot_id}-B{n}"
            n += 1
        index = session.shots.index(shot)
        session.shots[index] = shot.model_copy(update={"end_sec": middle})
        session.shots.append(shot.model_copy(update={"shot_id": shot_id, "start_sec": middle}))
        self.refresh_shots()
        self.on_change()

    def _delete_shot(self):
        shot = self._selected_shot()
        if not shot:
            return
        session = self.session_getter()
        session.shots.remove(shot)
        self.refresh_shots()
        self.on_change()

    def _save_selected(self):
        shot = self._selected_shot()
        if not shot:
            return
        session = self.session_getter()
        references = [
            self.references.item(i).data(Qt.UserRole)
            for i in range(self.references.count())
            if self.references.item(i).checkState() == Qt.Checked
        ]
        camera = CameraSpec(
            framing=self.framing.text(), lens=self.lens.text(), angle=self.angle.text(),
            movement=self.movement.text(), movement_strength=self.movement_strength.currentData(),
        )
        # Text-only edits must not re-quantize the stored timestamps to the spinbox precision.
        loaded_id, loaded_start, loaded_end = getattr(self, "_loaded_times", (None, None, None))
        same_shot = loaded_id == shot.shot_id
        start = shot.start_sec if same_shot and round(self.start.value(), TIME_DECIMALS) == round(loaded_start, TIME_DECIMALS) else self.start.value()
        end = shot.end_sec if same_shot and round(self.end.value(), TIME_DECIMALS) == round(loaded_end, TIME_DECIMALS) else self.end.value()
        changes = {
            "start_sec": start, "end_sec": end,
            "narrative_function": self.narrative.text(), "lyric_line_ids": StoryRoomPage._tokens(self.line_ids.text()),
            "music_cue_ids": StoryRoomPage._tokens(self.cue_ids.text()), "lyric_intent": self.intent.toPlainText(),
            "lyric_visual_strategy": self.strategy.currentData(), "subject": self.subject.toPlainText(),
            "action": self.action.toPlainText(), "environment": self.environment.toPlainText(),
            "composition": self.composition.toPlainText(), "camera": camera,
            "lighting": self.lighting.toPlainText(), "emotional_note": self.emotion.toPlainText(),
            "motif": self.motif.text().strip() or None,
            "continuity_in": StoryRoomPage._tokens(self.continuity_in.toPlainText()),
            "continuity_out": StoryRoomPage._tokens(self.continuity_out.toPlainText()),
            "world_rule_refs": StoryRoomPage._tokens(self.world_refs.toPlainText()),
            "reference_ids": references, "generation_mode": self.generation_mode.currentData(),
            "negative_constraints": StoryRoomPage._tokens(self.negative.toPlainText()),
            "series_episode_id": self.series_episode.currentData(),
            "series_entity_ids": self._selected_series_entity_ids(),
            "series_variant_ids": self._selected_series_variant_ids(),
        }
        try:
            updated = ShotSpec.model_validate({**shot.model_dump(), **changes})
        except Exception as exc:
            QMessageBox.warning(self, "Shot 값을 확인하세요", str(exc))
            return
        index = session.shots.index(shot)
        session.shots[index] = updated
        self.refresh_shots()
        self.on_change()
