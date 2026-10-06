from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from .manual_generation import (
    MANUAL_SITE_PROFILES, ManualGenerationPack, compile_manual_pack,
    export_manual_pack, get_manual_site_profile, safe_shot_filename,
)


def _button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(44)
    return button


def _read_only() -> QTextEdit:
    editor = QTextEdit()
    editor.setReadOnly(True)
    editor.setMinimumHeight(105)
    return editor


def _wrapped(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    return label


class ManualGenerationStudioPage(QWidget):
    def __init__(self, session_getter, on_change):
        super().__init__()
        self.session_getter = session_getter
        self.on_change = on_change
        self.current_pack: ManualGenerationPack | None = None
        self._building = False
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(12)
        title = QLabel("MANUAL GENERATION STUDIO")
        title.setObjectName("sectionTitle")
        outer.addWidget(title)
        outer.addWidget(_wrapped(
            "1. Shot 확인  →  2. Reference 준비  →  3. Main Prompt 복사  →  "
            "4. Motion / Camera 복사  →  5. Negative 복사  →  6. 사이트에서 생성  →  "
            "7. 결과 등록은 다음 G4B"
        ))

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._selector_panel())
        splitter.addWidget(self._prompt_panel())
        splitter.addWidget(self._settings_panel())
        splitter.setSizes([300, 660, 390])
        outer.addWidget(splitter, 1)

    def _selector_panel(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.addWidget(_wrapped("1. Shot 확인",))
        self.beat_combo = QComboBox()
        self.shot_list = QListWidget()
        self.beat_combo.setMinimumHeight(44)
        layout.addWidget(self.beat_combo)
        layout.addWidget(self.shot_list, 1)
        layout.addWidget(_wrapped("Shot readiness"))
        self.readiness = _wrapped("Shot을 선택하세요.")
        self.readiness.setObjectName("smallTitle")
        layout.addWidget(self.readiness)
        self.traceability = _wrapped("Traceability: -")
        layout.addWidget(self.traceability)
        self.copy_shot_id = _button("Shot ID 복사")
        layout.addWidget(self.copy_shot_id)
        self.beat_combo.currentIndexChanged.connect(self._refresh_shots)
        self.shot_list.currentRowChanged.connect(self._compile)
        self.copy_shot_id.clicked.connect(lambda: self._copy(self._selected_shot().shot_id if self._selected_shot() else ""))
        return host

    def _prompt_section(self, layout: QVBoxLayout, title: str, copy_label: str):
        row = QHBoxLayout()
        row.addWidget(_wrapped(title), 1)
        button = _button(copy_label)
        row.addWidget(button)
        layout.addLayout(row)
        editor = _read_only()
        layout.addWidget(editor)
        return editor, button

    def _prompt_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.addWidget(_wrapped("2. Reference 준비 / 3–5. Prompt 복사"))
        self.reference_text, self.copy_references = self._prompt_section(layout, "Reference instructions", "Reference 경로 복사")
        self.main_prompt, self.copy_main = self._prompt_section(layout, "Main Prompt", "Main Prompt 복사")
        self.motion_prompt, self.copy_motion = self._prompt_section(layout, "Motion Prompt", "Motion 복사")
        self.camera_prompt, self.copy_camera = self._prompt_section(layout, "Camera Prompt", "Camera 복사")
        self.negative_prompt, self.copy_negative = self._prompt_section(layout, "Negative Prompt", "Negative 복사")
        scroll.setWidget(host)
        self.copy_references.clicked.connect(lambda: self._copy(self.reference_text.toPlainText()))
        self.copy_main.clicked.connect(lambda: self._copy(self.main_prompt.toPlainText()))
        self.copy_motion.clicked.connect(lambda: self._copy(self.motion_prompt.toPlainText()))
        self.copy_camera.clicked.connect(lambda: self._copy(self.camera_prompt.toPlainText()))
        self.copy_negative.clicked.connect(lambda: self._copy(self.negative_prompt.toPlainText()))
        return scroll

    def _settings_panel(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.addWidget(_wrapped("6. 사이트에서 직접 생성"))
        form = QFormLayout()
        self.profile_combo = QComboBox()
        for profile in MANUAL_SITE_PROFILES.values():
            self.profile_combo.addItem(profile.display_name, profile.profile_id)
        self.duration_combo = QComboBox()
        self.aspect_combo = QComboBox()
        self.resolution_combo = QComboBox()
        for widget in (self.profile_combo, self.duration_combo, self.aspect_combo, self.resolution_combo):
            widget.setMinimumHeight(42)
        form.addRow("Site Profile", self.profile_combo)
        form.addRow("Website duration", self.duration_combo)
        form.addRow("Aspect", self.aspect_combo)
        form.addRow("Resolution", self.resolution_combo)
        layout.addLayout(form)
        self.settings = _wrapped("Settings: -")
        self.frames = _wrapped("First Frame: -\nLast Frame: -")
        self.preset = _wrapped("Camera preset: -")
        self.warnings = _wrapped("Warnings: -")
        layout.addWidget(self.settings)
        layout.addWidget(self.frames)
        layout.addWidget(self.preset)
        layout.addWidget(self.warnings)
        self.feedback = _wrapped("")
        self.feedback.setObjectName("smallTitle")
        layout.addWidget(self.feedback)
        self.copy_full = _button("Full Pack 복사")
        self.save_snapshot = _button("Pack Snapshot 저장")
        self.export_txt = _button("Selected Shot TXT export")
        self.export_json = _button("Selected Shot JSON export")
        for button in (self.copy_full, self.save_snapshot, self.export_txt, self.export_json):
            layout.addWidget(button)
        layout.addStretch(1)
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        self.duration_combo.currentIndexChanged.connect(self._compile)
        self.aspect_combo.currentIndexChanged.connect(self._compile)
        self.resolution_combo.currentIndexChanged.connect(self._compile)
        self.copy_full.clicked.connect(lambda: self._copy(self.current_pack.full_clipboard_text if self.current_pack else ""))
        self.save_snapshot.clicked.connect(self._save_snapshot)
        self.export_txt.clicked.connect(lambda: self._export("txt"))
        self.export_json.clicked.connect(lambda: self._export("json"))
        self._profile_changed()
        return host

    def refresh(self):
        self._building = True
        session = self.session_getter()
        previous = self.beat_combo.currentData()
        self.beat_combo.clear()
        for beat in sorted(session.story_beats, key=lambda item: (item.start_sec, item.beat_id)):
            self.beat_combo.addItem(f"{beat.beat_id} · {beat.start_sec:.2f}–{beat.end_sec:.2f}s", beat.beat_id)
        index = self.beat_combo.findData(previous)
        self.beat_combo.setCurrentIndex(index if index >= 0 else (0 if self.beat_combo.count() else -1))
        self._building = False
        self._refresh_shots()

    def _active_beat_id(self):
        return self.beat_combo.currentData()

    def _refresh_shots(self):
        if self._building:
            return
        previous = self.shot_list.currentItem().data(Qt.UserRole) if self.shot_list.currentItem() else None
        self.shot_list.blockSignals(True)
        self.shot_list.clear()
        shots = sorted((shot for shot in self.session_getter().shots if shot.beat_id == self._active_beat_id()), key=lambda item: (item.start_sec, item.shot_id))
        for shot in shots:
            item = QListWidgetItem(f"{shot.shot_id}\n{shot.start_sec:.2f}–{shot.end_sec:.2f}s · {shot.narrative_function}")
            item.setData(Qt.UserRole, shot.shot_id)
            self.shot_list.addItem(item)
        restored = next((i for i in range(self.shot_list.count()) if self.shot_list.item(i).data(Qt.UserRole) == previous), 0)
        self.shot_list.setCurrentRow(restored if shots else -1)
        self.shot_list.blockSignals(False)
        self._compile()

    def _selected_shot(self):
        item = self.shot_list.currentItem()
        shot_id = item.data(Qt.UserRole) if item else None
        return next((shot for shot in self.session_getter().shots if shot.shot_id == shot_id), None)

    def _profile_changed(self):
        profile = get_manual_site_profile(self.profile_combo.currentData() or "GENERIC_MANUAL")
        self._building = True
        self.duration_combo.clear()
        self.duration_combo.addItem("Auto / nearest", None)
        for value in profile.duration_options:
            self.duration_combo.addItem(f"{value:g}s", float(value))
        self.aspect_combo.clear()
        self.aspect_combo.addItems(profile.aspect_ratio_options)
        self.resolution_combo.clear()
        self.resolution_combo.addItems(profile.resolution_options)
        self._building = False
        self._compile()

    def _compile(self):
        if self._building:
            return
        shot = self._selected_shot()
        if not shot:
            self.current_pack = None
            self.readiness.setText("Shot을 선택하세요.")
            return
        self.current_pack = compile_manual_pack(
            self.session_getter(), shot, self.profile_combo.currentData(),
            generation_duration_hint=self.duration_combo.currentData(),
            aspect_ratio=self.aspect_combo.currentText() or None,
            resolution_hint=self.resolution_combo.currentText() or None,
        )
        pack = self.current_pack
        self.readiness.setText(pack.readiness)
        self.traceability.setText(
            f"Beat: {pack.beat_id or '-'}\nLyrics: {', '.join(pack.lyric_line_ids) or '-'}\n"
            f"Music: {', '.join(pack.music_cue_ids) or '-'}\nWorld rules: {', '.join(pack.world_rule_refs) or '-'}"
        )
        self.reference_text.setPlainText("\n\n".join(
            f"{item.reference_id} · {item.role} · {item.scope} · eligible={item.eligible} · missing={item.missing}\n{item.path}\n{item.instruction}"
            for item in pack.reference_instructions
        ) or "No reference files linked")
        self.main_prompt.setPlainText(pack.main_prompt)
        self.motion_prompt.setPlainText(pack.motion_prompt)
        self.camera_prompt.setPlainText(pack.camera_prompt)
        self.negative_prompt.setPlainText(pack.negative_prompt)
        self.settings.setText("\n".join(pack.settings_checklist))
        self.frames.setText(f"First Frame: {pack.first_frame_ref or '-'}\nLast Frame: {pack.last_frame_ref or '-'}")
        self.preset.setText(f"Camera preset recommendation: {pack.camera_preset_recommendation}")
        self.warnings.setText("Warnings:\n" + ("\n".join(f"• {value}" for value in pack.warnings) or "• None"))

    def _copy(self, text: str):
        if not text:
            self.feedback.setText("복사할 내용이 없습니다.")
            return
        QApplication.clipboard().setText(text)
        self.feedback.setText("복사 완료")

    def _save_snapshot(self):
        self._compile()
        if not self.current_pack:
            return
        session = self.session_getter()
        session.generation_packs.append(self.current_pack.model_copy(deep=True))
        self.feedback.setText(f"Snapshot 저장 완료 · {self.current_pack.pack_id}")
        self.on_change()

    def _export(self, suffix: str):
        if not self.current_pack:
            return
        filename = f"{safe_shot_filename(self.current_pack.shot_id)}_manual_pack.{suffix}"
        path, _ = QFileDialog.getSaveFileName(self, "Manual Generation Pack export", filename, f"{suffix.upper()} (*.{suffix})")
        if not path:
            return
        try:
            export_manual_pack(self.current_pack, path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Export 실패", str(exc))
            return
        self.feedback.setText(f"Export 완료 · {Path(path).name}")
