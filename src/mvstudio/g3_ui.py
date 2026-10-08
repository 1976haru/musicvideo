from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .models import CameraSpec, ShotSpec, StoryBeat
from .story_engine import (
    beat_traceability_warnings, cinematic_warnings, draft_shot, draft_story_beats,
    duplicate_id_warnings, literalization_warnings, motif_progression_warnings,
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


def _time(value: float = 0.0) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setRange(0, 86400)
    widget.setDecimals(2)
    widget.setSingleStep(0.5)
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
        actions = QHBoxLayout()
        self.auto_button = QPushButton("자동 초안 만들기")
        self.add_button = QPushButton("Beat 추가")
        self.save_button = QPushButton("Beat 변경 저장")
        self.delete_button = QPushButton("Beat 삭제")
        self.save_button.setObjectName("primary")
        for button in (self.auto_button, self.add_button, self.save_button, self.delete_button):
            button.setMinimumHeight(44)
            actions.addWidget(button)
        detail_outer.addLayout(actions)
        splitter.addWidget(_pane("선택 Beat 편집", detail_host))
        splitter.setSizes([300, 420, 560])
        outer.addWidget(splitter, 1)
        self.beat_list.currentRowChanged.connect(self._load_selected)
        self.auto_button.clicked.connect(self._auto_draft)
        self.add_button.clicked.connect(self._add_beat)
        self.save_button.clicked.connect(self._save_selected)
        self.delete_button.clicked.connect(self._delete_selected)
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
        current = self.beat_list.currentItem()
        previous_id = current.data(Qt.UserRole) if current else None
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
                f"{beat.start_sec:6.2f}–{beat.end_sec:6.2f}s  {beat.beat_id} · {beat.setup_or_payoff.upper()} · {beat.motif or 'motif 없음'}\n{beat.dramatic_question}"
            )
            item.setData(Qt.UserRole, beat.beat_id)
            self.beat_list.addItem(item)
        if self.beat_list.count():
            restored = next((i for i in range(self.beat_list.count()) if self.beat_list.item(i).data(Qt.UserRole) == previous_id), 0)
            self.beat_list.setCurrentRow(restored)
        self.beat_list.blockSignals(False)
        self._load_selected(self.beat_list.currentRow())
        warnings = timeline_warnings(session.story_beats, session.audio_map.duration_sec if session.audio_map else session.duration_sec)
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

    def _selected_beat(self):
        row = self.beat_list.currentRow()
        if row < 0:
            return None
        beat_id = self.beat_list.item(row).data(Qt.UserRole)
        return next((beat for beat in self.session_getter().story_beats if beat.beat_id == beat_id), None)

    def _load_selected(self, row: int):
        beat = self._selected_beat()
        active = beat is not None
        for widget in (self.start, self.end, self.question, self.change, self.visual, self.motif, self.phase, self.lyric_ids, self.cue_ids, self.lyric_intent, self.emotion, self.world_refs, self.reference_ids, self.notes, self.save_button, self.delete_button):
            widget.setEnabled(active)
        if not active:
            return
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

    def _auto_draft(self):
        session = self.session_getter()
        bible = session.world_bible
        rules = []
        if bible:
            for field in ("reality_rules", "weather_rules", "lighting_rules", "camera_rules"):
                rules.extend(f"{field}:{idx}" for idx, _ in enumerate(getattr(bible, field)))
        session.story_beats = draft_story_beats(
            session.lines, session.mv_timeline,
            session.audio_map.duration_sec if session.audio_map else session.duration_sec,
            motif_pool=bible.recurring_motifs if bible else [],
            emotional_arc=session.analysis.emotional_arc if session.analysis else [],
            world_rule_refs=rules,
            bridges=session.bridges,
        )
        self.refresh()
        self.on_change()

    def _add_beat(self):
        beats = self.session_getter().story_beats
        end = self.session_getter().audio_map.duration_sec if self.session_getter().audio_map else self.session_getter().duration_sec or 10
        beat_id = next_beat_id({beat.beat_id for beat in beats})
        beat = StoryBeat(beat_id=beat_id, start_sec=0, end_sec=max(0.1, end), dramatic_question="이 구간의 질문은 무엇인가?", change="", visual_event="")
        beats.append(beat)
        self.refresh()
        target_row = next(i for i in range(self.beat_list.count()) if self.beat_list.item(i).data(Qt.UserRole) == beat_id)
        self.beat_list.setCurrentRow(target_row)
        self.on_change()

    def _save_selected(self):
        session = self.session_getter()
        selected = self._selected_beat()
        if selected is None:
            return
        beat = selected
        row = session.story_beats.index(beat)
        changes = {
            "start_sec": self.start.value(), "end_sec": self.end.value(),
            "dramatic_question": self.question.text(), "change": self.change.toPlainText(),
            "visual_event": self.visual.toPlainText(), "motif": self.motif.text().strip() or None,
            "setup_or_payoff": self.phase.currentData(), "lyric_line_ids": self._tokens(self.lyric_ids.text()),
            "music_cue_ids": self._tokens(self.cue_ids.text()), "lyric_intent": self.lyric_intent.toPlainText(),
            "emotional_state": self.emotion.text(), "world_rule_refs": self._tokens(self.world_refs.toPlainText()),
            "reference_ids": self._tokens(self.reference_ids.text()), "notes": self.notes.toPlainText(),
        }
        try:
            session.story_beats[row] = StoryBeat.model_validate({**beat.model_dump(), **changes})
        except Exception as exc:
            QMessageBox.warning(self, "Beat 값을 확인하세요", str(exc))
            return
        beat_id = beat.beat_id
        self.refresh()
        target_row = next((i for i in range(self.beat_list.count()) if self.beat_list.item(i).data(Qt.UserRole) == beat_id), -1)
        self.beat_list.setCurrentRow(target_row)
        self.on_change()

    def _delete_selected(self):
        row = self.beat_list.currentRow()
        beat = self._selected_beat()
        if beat is None:
            return
        session = self.session_getter()
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
            self.beat_combo.addItem(f"{beat.beat_id} · {beat.start_sec:.2f}–{beat.end_sec:.2f}s · {beat.motif or 'motif 없음'}", beat.beat_id)
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
        changes = {
            "start_sec": self.start.value(), "end_sec": self.end.value(),
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
