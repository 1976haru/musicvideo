from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSpinBox,
    QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from .result_takes import DuplicateTakeIDError, DuplicateTakePathError, VIDEO_EXTENSIONS, resolve_take_path


def _button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(44)
    return button


def _label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    return label


class ResultTakesPage(QWidget):
    def __init__(self, session_getter, on_change):
        super().__init__()
        self.session_getter = session_getter
        self.on_change = on_change
        self._building = False
        self.setAcceptDrops(True)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.addWidget(_label(
            "1. Shot 선택  →  2. 생성에 사용한 Pack 선택  →  3. 결과 영상 등록  →  "
            "4. Take A/B/C 비교  →  5. ACCEPT 또는 REJECT  →  6. FINAL TAKE 확인"
        ))
        selectors = QHBoxLayout()
        self.shot_combo = QComboBox()
        self.pack_combo = QComboBox()
        self.shot_combo.setMinimumHeight(44)
        self.pack_combo.setMinimumHeight(44)
        selectors.addWidget(_label("Shot"))
        selectors.addWidget(self.shot_combo, 1)
        selectors.addWidget(_label("Pack Snapshot"))
        selectors.addWidget(self.pack_combo, 1)
        self.register_button = _button("결과 영상 등록")
        selectors.addWidget(self.register_button)
        outer.addLayout(selectors)
        outer.addWidget(_label("영상 파일을 이 화면에 끌어 놓아도 등록됩니다. 등록과 해제는 metadata-only이며 원본 파일은 그대로 유지됩니다."))

        splitter = QSplitter(Qt.Horizontal)
        self.take_list = QListWidget()
        splitter.addWidget(self.take_list)
        inspector = QWidget()
        inspector_layout = QVBoxLayout(inspector)
        form = QFormLayout()
        self.take_id = QLineEdit(); self.take_id.setReadOnly(True)
        self.filename = QLineEdit(); self.filename.setReadOnly(True)
        self.path = QTextEdit(); self.path.setReadOnly(True); self.path.setMaximumHeight(75)
        self.linkage = _label("-")
        self.status = _label("-")
        self.rating = QSpinBox(); self.rating.setRange(0, 5); self.rating.setSpecialValueText("미평가")
        self.notes = QTextEdit(); self.notes.setMinimumHeight(70)
        self.reject_reason = QTextEdit(); self.reject_reason.setMinimumHeight(60)
        self.missing = _label("-")
        self.warnings = _label("-")
        for name, widget in (
            ("Take ID", self.take_id), ("파일명", self.filename), ("파일 경로", self.path),
            ("Shot / Pack / Profile", self.linkage), ("상태", self.status), ("Rating 1–5", self.rating),
            ("Notes", self.notes), ("Reject reason", self.reject_reason), ("Missing", self.missing),
            ("Warnings", self.warnings),
        ):
            form.addRow(name, widget)
        inspector_layout.addLayout(form)
        actions = QHBoxLayout()
        self.open_button = _button("영상 열기")
        self.relink_button = _button("파일 다시 연결")
        self.accept_button = _button("ACCEPT")
        self.reject_button = _button("REJECT")
        self.restore_button = _button("Candidate로 복원")
        self.save_button = _button("메모 저장")
        self.unregister_button = _button("등록 해제 (원본 유지)")
        for button in (self.open_button, self.relink_button, self.accept_button, self.reject_button, self.restore_button, self.save_button, self.unregister_button):
            actions.addWidget(button)
        inspector_layout.addLayout(actions)
        self.final_take = _label("FINAL TAKE: -")
        self.final_take.setObjectName("smallTitle")
        inspector_layout.addWidget(self.final_take)
        splitter.addWidget(inspector)
        splitter.setSizes([390, 760])
        outer.addWidget(splitter, 1)

        self.shot_combo.currentIndexChanged.connect(self._shot_changed)
        self.take_list.currentRowChanged.connect(self._load_selected)
        self.register_button.clicked.connect(self._pick_results)
        self.open_button.clicked.connect(self._open_result)
        self.relink_button.clicked.connect(self._relink)
        self.accept_button.clicked.connect(self._accept)
        self.reject_button.clicked.connect(self._reject)
        self.restore_button.clicked.connect(self._restore)
        self.save_button.clicked.connect(self._save_notes)
        self.unregister_button.clicked.connect(self._unregister)

    def refresh(self):
        self._building = True
        previous = self.shot_combo.currentData()
        self.shot_combo.clear()
        for shot in sorted(self.session_getter().shots, key=lambda item: (item.start_sec, item.shot_id)):
            self.shot_combo.addItem(f"{shot.shot_id} · {shot.narrative_function}", shot.shot_id)
        index = self.shot_combo.findData(previous)
        self.shot_combo.setCurrentIndex(index if index >= 0 else (0 if self.shot_combo.count() else -1))
        self._building = False
        self._shot_changed()

    def _shot_id(self):
        return self.shot_combo.currentData()

    def _shot_changed(self):
        if self._building:
            return
        previous_pack = self.pack_combo.currentData()
        self.pack_combo.clear()
        self.pack_combo.addItem("No Pack Snapshot", None)
        packs = sorted(
            (pack for pack in self.session_getter().generation_packs if pack.shot_id == self._shot_id()),
            key=lambda pack: (pack.created_at, pack.pack_id), reverse=True,
        )
        for pack in packs:
            self.pack_combo.addItem(f"{pack.pack_id} · {pack.profile_id}", pack.pack_id)
        index = self.pack_combo.findData(previous_pack)
        self.pack_combo.setCurrentIndex(index if index >= 0 else (1 if packs else 0))
        self._refresh_takes()

    def _takes(self):
        return sorted(
            (take for take in self.session_getter().generation_takes if take.shot_id == self._shot_id()),
            key=lambda take: (take.imported_at, take.take_id),
        )

    def _refresh_takes(self, selected_id: str | None = None):
        if selected_id is None and self.take_list.currentItem():
            selected_id = self.take_list.currentItem().data(Qt.UserRole + 1)
        self.take_list.blockSignals(True)
        self.take_list.clear()
        for index, take in enumerate(self._takes()):
            display = chr(ord("A") + index) if index < 26 else str(index + 1)
            available = "MISSING" if take.file_missing(self.session_getter().project_dir) else "available"
            item = QListWidgetItem(f"Take {display} · {take.status.upper()} · {available}\n{take.take_id}\n{take.original_filename}")
            session_index = next(i for i, stored in enumerate(self.session_getter().generation_takes) if stored is take)
            item.setData(Qt.UserRole, session_index)
            item.setData(Qt.UserRole + 1, take.take_id)
            self.take_list.addItem(item)
        row = next((i for i in range(self.take_list.count()) if self.take_list.item(i).data(Qt.UserRole + 1) == selected_id), 0)
        self.take_list.setCurrentRow(row if self.take_list.count() else -1)
        self.take_list.blockSignals(False)
        self._load_selected()
        manager = self.session_getter().take_manager
        final = manager.accepted_take_for_shot(self._shot_id())
        if final:
            self.final_take.setText(f"FINAL TAKE: {final.take_id} · {final.original_filename}")
        elif manager.shot_result_status(self._shot_id()) == "NEEDS_REVIEW":
            self.final_take.setText("FINAL TAKE: NEEDS_REVIEW")
        else:
            self.final_take.setText("FINAL TAKE: -")

    def _selected_take(self):
        item = self.take_list.currentItem()
        index = item.data(Qt.UserRole) if item else None
        takes = self.session_getter().generation_takes
        return takes[index] if isinstance(index, int) and 0 <= index < len(takes) else None

    def _mutation_take(self):
        take = self._selected_take()
        if not take:
            return None
        if sum(item.take_id == take.take_id for item in self.session_getter().generation_takes) != 1:
            QMessageBox.warning(self, "Duplicate Take ID", "중복 take_id가 있어 변경할 수 없습니다. 원본 history는 유지됩니다.")
            return None
        return take

    def _load_selected(self, *_):
        take = self._selected_take()
        active = take is not None
        unique = active and sum(item.take_id == take.take_id for item in self.session_getter().generation_takes) == 1
        self.open_button.setEnabled(active)
        for widget in (self.relink_button, self.accept_button, self.reject_button, self.restore_button, self.save_button, self.unregister_button, self.rating, self.notes, self.reject_reason):
            widget.setEnabled(unique)
        if not take:
            return
        resolved = resolve_take_path(take, self.session_getter().project_dir)
        self.take_id.setText(take.take_id)
        self.filename.setText(take.original_filename)
        self.path.setPlainText(str(resolved))
        self.linkage.setText(f"Shot: {take.shot_id}\nPack: {take.pack_id or 'No Pack Snapshot'}\nProfile: {take.source_profile_id or '-'}")
        self.status.setText(take.status.upper())
        self.rating.setValue(take.rating or 0)
        self.notes.setPlainText(take.notes)
        self.reject_reason.setPlainText(take.reject_reason)
        self.missing.setText("MISSING" if take.file_missing(self.session_getter().project_dir) else "Available")
        warnings = self.session_getter().take_manager.warnings_for_take(take)
        self.warnings.setText("\n".join(f"{warning.code}: {warning.message}" for warning in warnings) or "None")

    def _pick_results(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "결과 영상 등록", "", "Video (*.mp4 *.mov *.webm *.mkv *.m4v)")
        self._register_paths(paths)

    def _register_paths(self, paths):
        if not self._shot_id():
            QMessageBox.information(self, "Shot 선택", "먼저 Shot을 선택하세요.")
            return
        selected_id = None
        failures = []
        for path in paths:
            if Path(path).suffix.casefold() not in VIDEO_EXTENSIONS:
                failures.append(f"{Path(path).name}: unsupported file type")
                continue
            try:
                take = self.session_getter().take_manager.register(path, self._shot_id(), self.pack_combo.currentData())
            except (OSError, ValueError, DuplicateTakePathError) as exc:
                failures.append(f"{Path(path).name}: {exc}")
                continue
            selected_id = take.take_id
        if selected_id:
            self._refresh_takes(selected_id)
            self.on_change()
        if failures:
            QMessageBox.warning(self, "일부 결과 등록 실패", "\n".join(failures))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(Path(url.toLocalFile()).suffix.casefold() in VIDEO_EXTENSIONS for url in event.mimeData().urls() if url.isLocalFile()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self._register_paths(paths)
        event.acceptProposedAction()

    def _open_result(self):
        take = self._selected_take()
        if not take:
            return
        path = resolve_take_path(take, self.session_getter().project_dir)
        if not path.is_file():
            QMessageBox.warning(self, "영상 열기", f"파일을 찾을 수 없습니다:\n{path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _relink(self):
        take = self._mutation_take()
        if not take:
            return
        path, _ = QFileDialog.getOpenFileName(self, "파일 다시 연결", "", "Video (*.mp4 *.mov *.webm *.mkv *.m4v)")
        if not path:
            return
        try:
            self.session_getter().take_manager.relink(take.take_id, path)
        except (OSError, ValueError, DuplicateTakeIDError, DuplicateTakePathError) as exc:
            QMessageBox.warning(self, "파일 다시 연결 실패", str(exc))
            return
        self._refresh_takes(take.take_id); self.on_change()

    def _accept(self):
        take = self._mutation_take()
        if take:
            self.session_getter().take_manager.accept(take.take_id)
            self._refresh_takes(take.take_id); self.on_change()

    def _reject(self):
        take = self._mutation_take()
        if take:
            reason = self.reject_reason.toPlainText().strip()
            if not reason:
                answer = QMessageBox.question(self, "Reject reason 없음", "Reject reason이 비어 있습니다. 그대로 REJECT할까요?")
                if answer != QMessageBox.Yes:
                    return
            self.session_getter().take_manager.reject(take.take_id, reason)
            self._refresh_takes(take.take_id); self.on_change()

    def _restore(self):
        take = self._mutation_take()
        if take:
            self.session_getter().take_manager.restore_candidate(take.take_id)
            self._refresh_takes(take.take_id); self.on_change()

    def _save_notes(self):
        take = self._mutation_take()
        if take:
            updated = self.session_getter().take_manager.update_notes(
                take.take_id, rating=self.rating.value() or None, notes=self.notes.toPlainText(),
                reject_reason=self.reject_reason.toPlainText(),
            )
            self._refresh_takes(updated.take_id); self.on_change()

    def _unregister(self):
        take = self._mutation_take()
        if not take:
            return
        answer = QMessageBox.question(self, "등록 해제", "Take metadata만 제거합니다. 원본 영상 파일은 그대로 유지됩니다. 계속할까요?")
        if answer != QMessageBox.Yes:
            return
        self.session_getter().take_manager.unregister(take.take_id)
        self._refresh_takes(); self.on_change()
