from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from .result_takes import resolve_take_path
from .technical_qc import DEFAULT_OPTIONS, TakeQCReport, analyze_take, report_is_fresh


def _label(text: str = "") -> QLabel:
    widget = QLabel(text)
    widget.setWordWrap(True)
    return widget


def _button(text: str) -> QPushButton:
    widget = QPushButton(text)
    widget.setMinimumHeight(44)
    return widget


class TechnicalQCPage(QWidget):
    STATUS_TEXT = {
        "PASS": "✅ 사용 가능",
        "REVIEW": "⚠ 확인 필요",
        "REGENERATE": "❌ 다시 생성 권장",
        "BLOCKED": "⛔ 파일 문제 해결 필요",
    }

    def __init__(self, session_getter, on_change, show_results):
        super().__init__()
        self.session_getter = session_getter
        self.on_change = on_change
        self.show_results = show_results
        self._building = False
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 18, 24, 18)
        outer.setSpacing(12)
        outer.addWidget(_label("7. 품질 확인 · 결과를 이해하고 다음 행동을 선택하세요."))
        self.question = _label("이 영상은 사용해도 될까요?")
        self.question.setObjectName("sectionTitle")
        outer.addWidget(self.question)

        selectors = QHBoxLayout()
        self.shot_combo = QComboBox(); self.shot_combo.setMinimumHeight(44)
        self.take_combo = QComboBox(); self.take_combo.setMinimumHeight(44)
        self.analyze_button = _button("품질 검사 시작")
        self.analyze_button.setObjectName("primary")
        selectors.addWidget(_label("Shot")); selectors.addWidget(self.shot_combo, 1)
        selectors.addWidget(_label("Take")); selectors.addWidget(self.take_combo, 1)
        selectors.addWidget(self.analyze_button)
        outer.addLayout(selectors)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        host = QWidget(); body = QVBoxLayout(host); body.setSpacing(12)
        self.status = _label("검사할 Take를 선택하세요.")
        self.status.setObjectName("sectionTitle")
        body.addWidget(self.status)
        self.reasons = _label("품질 검사를 시작하면 쉬운 설명으로 결과를 알려드립니다.")
        body.addWidget(self.reasons)

        actions = QHBoxLayout()
        self.primary_action = _button("이 Take 사용")
        self.primary_action.setObjectName("primary")
        self.compare_action = _button("다른 Take 비교")
        actions.addWidget(self.primary_action)
        actions.addWidget(self.compare_action)
        actions.addStretch(1)
        body.addLayout(actions)

        self.expert = QGroupBox("전문가 정보 보기")
        self.expert.setCheckable(True); self.expert.setChecked(False)
        expert_layout = QVBoxLayout(self.expert)
        self.expert_text = QTextEdit(); self.expert_text.setReadOnly(True); self.expert_text.setMinimumHeight(180)
        expert_layout.addWidget(self.expert_text)
        body.addWidget(self.expert)
        body.addStretch(1)
        scroll.setWidget(host)
        outer.addWidget(scroll, 1)

        self.expert.toggled.connect(self.expert_text.setVisible)
        self.expert_text.setVisible(False)
        self.shot_combo.currentIndexChanged.connect(self._shot_changed)
        self.take_combo.currentIndexChanged.connect(self._show_saved_report)
        self.analyze_button.clicked.connect(self._analyze)
        self.primary_action.clicked.connect(self._primary_action)
        self.compare_action.clicked.connect(self.show_results)

    def refresh(self):
        selected_shot = self.shot_combo.currentData()
        selected_take = self.take_combo.currentData()
        self._building = True
        self.shot_combo.clear()
        for shot in sorted(self.session_getter().shots, key=lambda item: (item.start_sec, item.shot_id)):
            self.shot_combo.addItem(f"{shot.narrative_function} · {shot.start_sec:.1f}–{shot.end_sec:.1f}s", shot.shot_id)
        index = self.shot_combo.findData(selected_shot)
        self.shot_combo.setCurrentIndex(index if index >= 0 else (0 if self.shot_combo.count() else -1))
        self._building = False
        self._shot_changed(selected_take)

    def _shot_changed(self, selected_take=None):
        if self._building:
            return
        if isinstance(selected_take, int):
            selected_take = None
        selected_take = selected_take or self.take_combo.currentData()
        self.take_combo.blockSignals(True)
        self.take_combo.clear()
        for take in self.session_getter().generation_takes:
            if take.shot_id == self.shot_combo.currentData():
                self.take_combo.addItem(f"{take.original_filename} · {take.status}", take.take_id)
        index = self.take_combo.findData(selected_take)
        self.take_combo.setCurrentIndex(index if index >= 0 else (0 if self.take_combo.count() else -1))
        self.take_combo.blockSignals(False)
        self._show_saved_report()

    def _take(self):
        take_id = self.take_combo.currentData()
        matches = [take for take in self.session_getter().generation_takes if take.take_id == take_id]
        return matches[0] if len(matches) == 1 else None

    def _latest_report(self):
        take = self._take()
        reports = [report for report in self.session_getter().qc_reports if take and report.take_id == take.take_id]
        return reports[-1] if reports else None

    def _show_saved_report(self, *_):
        report = self._latest_report()
        if report:
            take = self._take()
            path = resolve_take_path(take, self.session_getter().project_dir)
            if report_is_fresh(report, path, dict(DEFAULT_OPTIONS)):
                self._render(report)
            else:
                self.status.setText("⚠ 다시 검사 필요")
                self.reasons.setText("• 영상 파일 또는 검사 설정이 바뀌었습니다.\n• 이전 결과를 그대로 사용하지 않습니다.\n• [품질 검사 시작]을 다시 눌러 주세요.")
                self.expert_text.setPlainText("저장된 QC 결과의 source fingerprint가 현재 파일과 다릅니다.")
                self.primary_action.setText("품질 검사 시작")
        else:
            self.status.setText("검사 전")
            self.reasons.setText("[품질 검사 시작]을 누르면 결과와 다음 행동을 알려드립니다.")
            self.expert_text.clear()
            self.primary_action.setText("다른 Take 비교")

    def _analyze(self):
        take = self._take()
        if not take:
            QMessageBox.information(self, "Take 선택", "검사할 Take를 선택하세요. 중복 Take ID가 있으면 먼저 안전하게 정리해야 합니다.")
            return
        shot = next((item for item in self.session_getter().shots if item.shot_id == take.shot_id), None)
        self.status.setText("검사 중… 원본 영상은 변경하지 않습니다.")
        QApplication.processEvents()
        report, cache_hit = analyze_take(
            take, shot, self.session_getter().project_dir,
            cached_reports=self.session_getter().qc_reports,
        )
        if not cache_hit:
            self.session_getter().qc_reports.append(report)
            self.on_change()
        self._render(report)

    def _render(self, report: TakeQCReport):
        self.status.setText(self.STATUS_TEXT[report.status])
        self.reasons.setText("\n".join(f"• {reason}" for reason in report.beginner_summary[:5]))
        self.primary_action.setText(report.recommended_action)
        details = [
            f"Report: {report.report_id}", f"Analyzer: {report.analyzer_version}",
            f"Status: {report.status}", f"Score: {report.overall_score if report.overall_score is not None else '-'}",
        ]
        details.extend(f"\n[{metric.metric_id}] {metric.technical_detail}\nraw={metric.raw_value}" for metric in report.metrics)
        self.expert_text.setPlainText("\n".join(details))

    def _primary_action(self):
        if self.primary_action.text() == "품질 검사 시작":
            self._analyze()
            return
        report = self._latest_report()
        take = self._take()
        if not report or not take:
            self.show_results()
            return
        if report.status == "PASS":
            self.session_getter().take_manager.accept(take.take_id)
            self.on_change()
            self.status.setText("✅ 사용 가능 · 이 Take를 사용하도록 선택했습니다.")
        else:
            self.show_results()
