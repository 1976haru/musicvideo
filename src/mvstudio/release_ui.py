from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget, QInputDialog,
)

from .release_runtime import (
    APP_VERSION, app_paths, cache_size, clear_owned_cache, create_diagnostic_bundle,
    inspect_project, run_startup_doctor, valid_recovery_sessions,
    mark_startup_doctor_seen,
)


def _label(text: str, name: str | None = None) -> QLabel:
    label = QLabel(text); label.setWordWrap(True)
    if name: label.setObjectName(name)
    return label


class ReleaseDoctorDialog(QDialog):
    recovery_selected = Signal(str)
    def __init__(self, session_getter, previous_unclean: bool = False, parent=None):
        super().__init__(parent)
        self.session_getter = session_getter
        self.previous_unclean = previous_unclean
        self.setWindowTitle(f"MV Director Studio {APP_VERSION} · 준비 확인")
        self.resize(760, 650)
        self.setMinimumSize(700, 560)
        outer = QVBoxLayout(self)
        outer.addWidget(_label("뮤직비디오 제작 준비가 되었나요?", "sectionTitle"))
        outer.addWidget(_label("필수 도구와 선택 기능을 나누어 확인합니다. 선택 기능이 없어도 프로그램은 시작할 수 있습니다.", "muted"))
        if previous_unclean:
            warning = _label("이전 실행이 정상적으로 종료되지 않았습니다. 자동으로 프로젝트를 덮어쓰지 않습니다.")
            warning.setStyleSheet("color:#ffd27d;font-weight:700")
            outer.addWidget(warning)
            recovery = QHBoxLayout()
            recent = QPushButton("최근 정상 세션 열기")
            recent.clicked.connect(self.open_recent_recovery)
            show = QPushButton("복구본 보기")
            show.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_paths().recovery))))
            recovery.addWidget(recent); recovery.addWidget(show)
            outer.addLayout(recovery)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        self.checks_widget = QWidget(); self.checks_layout = QVBoxLayout(self.checks_widget)
        scroll.setWidget(self.checks_widget); outer.addWidget(scroll, 1)
        actions = QHBoxLayout()
        diagnostic = QPushButton("진단 보고서 만들기")
        diagnostic.clicked.connect(self.create_diagnostics)
        cache = QPushButton("캐시 정리")
        cache.clicked.connect(self.clear_cache)
        integrity = QPushButton("프로젝트 상태 확인")
        integrity.clicked.connect(self.project_integrity)
        close = QPushButton("그냥 시작")
        close.setObjectName("primary"); close.clicked.connect(self.accept)
        for button in (diagnostic, cache, integrity, close):
            button.setMinimumHeight(44); actions.addWidget(button)
        outer.addLayout(actions)
        self.refresh()

    def refresh(self):
        while self.checks_layout.count():
            item = self.checks_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for check in run_startup_doctor():
            if check.state == "READY": icon = "✓ 준비됨"
            elif check.state == "OPTIONAL_MISSING": icon = "– 선택 기능 없음"
            else: icon = "! 필수 도구 확인 필요"
            kind = "필수" if check.required else "선택"
            text = f"{icon} · {kind} · {check.label}\n{check.reason}"
            if check.action: text += f"\n해결: {check.action}"
            self.checks_layout.addWidget(_label(text))
        self.checks_layout.addStretch(1)
        mark_startup_doctor_seen()

    def open_recent_recovery(self):
        candidates = valid_recovery_sessions()
        if not candidates:
            QMessageBox.information(self, "복구", "검증을 통과한 복구본이 없습니다.")
            return
        selected, ok = QInputDialog.getItem(
            self, "검증된 복구본", "열 복구본을 선택하세요.",
            [str(item) for item in candidates], 0, False,
        )
        if ok and selected:
            self.recovery_selected.emit(selected)
            self.accept()

    def create_diagnostics(self):
        path, _ = QFileDialog.getSaveFileName(self, "진단 보고서 저장", "mvstudio-diagnostics.zip", "ZIP (*.zip)")
        if path:
            try:
                create_diagnostic_bundle(path)
                QMessageBox.information(self, "진단 보고서", "미디어와 비밀정보를 제외한 진단 보고서를 만들었습니다.")
            except Exception as exc:
                QMessageBox.warning(self, "진단 보고서", str(exc))

    def clear_cache(self):
        size = cache_size()
        if QMessageBox.question(self, "캐시 정리", f"프로그램 소유 캐시 {size / 1024 / 1024:.1f} MB를 정리할까요?\n원본과 session/final은 삭제하지 않습니다.") == QMessageBox.Yes:
            clear_owned_cache(); QMessageBox.information(self, "캐시 정리", "캐시를 정리했습니다. 필요하면 자동으로 다시 생성됩니다.")

    def project_integrity(self):
        findings = inspect_project(self.session_getter())
        text = "프로젝트 상태를 확인했습니다.\n\n" + "\n".join(f"• {item.state}: {item.message}" for item in findings)
        QMessageBox.information(self, "프로젝트 상태", text)
