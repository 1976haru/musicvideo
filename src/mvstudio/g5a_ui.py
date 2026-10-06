from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from .result_takes import resolve_take_path
from .technical_qc import DEFAULT_OPTIONS, TakeQCReport, analyze_take, report_is_fresh
from .semantic_qc import adjacent_visual_findings, analyze_visual_semantic, semantic_report_is_fresh
from .director_intelligence import (
    DirectorImportError, apply_director_proposal, build_director_intelligence_prompt,
    compare_with_current, import_director_result,
)
from .music_intelligence import analyze_music_intelligence, fuse_music_structure_timeline
from .optional_backends import functional_structure_availability


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

        director = QGroupBox("더 깊은 AI 감독 분석이 필요하신가요?")
        director_layout = QVBoxLayout(director)
        self.api_notice = _label("API 없이도 사용할 수 있습니다. 프롬프트를 외부 AI에 붙여넣고 JSON 제안만 가져옵니다.")
        director_layout.addWidget(self.api_notice)
        director_actions = QHBoxLayout()
        self.director_copy = _button("감독 분석 프롬프트 복사")
        self.director_import = _button("AI 결과 JSON 불러오기")
        self.director_compare = _button("현재 분석과 비교")
        director_actions.addWidget(self.director_copy); director_actions.addWidget(self.director_import); director_actions.addWidget(self.director_compare)
        director_layout.addLayout(director_actions)
        self.director_json = QTextEdit(); self.director_json.setPlaceholderText("AI가 만든 JSON을 여기에 붙여넣거나 파일을 불러오세요."); self.director_json.setMaximumHeight(90)
        director_layout.addWidget(self.director_json)
        apply_row = QHBoxLayout()
        self.apply_scope = QComboBox(); self.apply_scope.setMinimumHeight(44)
        self.apply_scope.addItem("Interpretation만", "interpretation")
        self.apply_scope.addItem("World Concept 후보만", "world_concepts")
        self.apply_scope.addItem("Story Beat 제안만", "story_beats")
        self.director_apply = _button("선택한 제안 반영")
        apply_row.addWidget(self.apply_scope, 1); apply_row.addWidget(self.director_apply)
        director_layout.addLayout(apply_row)
        self.director_status = _label("현재 프로젝트는 바뀌지 않습니다. 제안을 불러온 뒤 명시적으로 반영하세요.")
        director_layout.addWidget(self.director_status)
        body.addWidget(director)

        music = QGroupBox("음악 구조를 더 정확하게 분석할까요?")
        music_layout = QVBoxLayout(music)
        music_actions = QHBoxLayout()
        self.music_basic = _button("기본 분석")
        self.music_advanced = _button("고급 음악 구조 분석")
        self.music_advanced.setVisible(functional_structure_availability().state == "AVAILABLE")
        music_actions.addWidget(self.music_basic); music_actions.addWidget(self.music_advanced); music_actions.addStretch(1)
        music_layout.addLayout(music_actions)
        self.music_summary = _label("기본 분석은 빠르고 오프라인으로 동작합니다.")
        music_layout.addWidget(self.music_summary)
        body.addWidget(music)
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
        self.director_copy.clicked.connect(self._copy_director_prompt)
        self.director_import.clicked.connect(self._import_director_json)
        self.director_compare.clicked.connect(self._compare_director)
        self.director_apply.clicked.connect(self._apply_director)
        self.music_basic.clicked.connect(lambda: self._analyze_music_intelligence("LIBROSA_BASIC"))
        self.music_advanced.clicked.connect(lambda: self._analyze_music_intelligence("FUNCTIONAL_STRUCTURE"))

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
        if report.status != "BLOCKED":
            try:
                session = self.session_getter()
                semantic = next((item for item in reversed(session.semantic_qc_reports)
                                 if item.take_id == take.take_id and semantic_report_is_fresh(session, take, item)), None)
                if semantic is None:
                    semantic = analyze_visual_semantic(session, take)
                    session.semantic_qc_reports.append(semantic)
                    self.on_change()
            except (OSError, ValueError):
                pass
        self._render(report)

    def _render(self, report: TakeQCReport):
        semantic = next((item for item in reversed(self.session_getter().semantic_qc_reports) if item.take_id == report.take_id), None)
        visual_findings = semantic.findings if semantic else []
        try:
            visual_findings = [*visual_findings, *[item for item in adjacent_visual_findings(self.session_getter()) if report.shot_id in item.finding_id]]
        except (OSError, ValueError):
            pass
        visual_review = any(item.status == "REVIEW" for item in visual_findings)
        display_status = "REVIEW" if report.status == "PASS" and visual_review else report.status
        self.status.setText(self.STATUS_TEXT[display_status])
        reasons = list(report.beginner_summary)
        reasons.extend(item.summary_ko for item in visual_findings if item.status in {"REVIEW", "N/A"})
        self.reasons.setText("\n".join(f"• {reason}" for reason in reasons[:5]))
        self.primary_action.setText("문제 장면 확인" if display_status == "REVIEW" else report.recommended_action)
        details = [
            f"Report: {report.report_id}", f"Analyzer: {report.analyzer_version}",
            f"Status: {report.status}", f"Score: {report.overall_score if report.overall_score is not None else '-'}",
        ]
        details.extend(f"\n[{metric.metric_id}] {metric.technical_detail}\nraw={metric.raw_value}" for metric in report.metrics)
        details.extend(f"\n[{finding.finding_id}] {finding.technical_detail}\nstatus={finding.status}" for finding in visual_findings)
        self.expert_text.setPlainText("\n".join(details))

    def _copy_director_prompt(self):
        session = self.session_getter()
        QApplication.clipboard().setText(build_director_intelligence_prompt(session.lines, session.analysis))
        self.director_status.setText("감독 분석 프롬프트를 복사했습니다. ChatGPT / Claude 등에 붙여넣으세요.")

    def _import_director_json(self):
        payload = self.director_json.toPlainText().strip()
        if not payload:
            path, _ = QFileDialog.getOpenFileName(self, "AI 감독 JSON 불러오기", "", "JSON (*.json)")
            if not path:
                return
            try:
                payload = Path(path).read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError) as exc:
                QMessageBox.warning(self, "JSON 불러오기 실패", str(exc)); return
        try:
            result = import_director_result(payload, {line.line_id for line in self.session_getter().lines})
        except DirectorImportError as exc:
            QMessageBox.warning(self, "AI 감독 제안 검증 실패", "\n".join(exc.issues)); return
        self.session_getter().director_intelligence_results.append(result)
        self.director_status.setText("제안 Snapshot을 불러왔습니다. 기존 World / Story / Shot은 변경되지 않았습니다.")
        self.on_change()

    def _compare_director(self):
        results = self.session_getter().director_intelligence_results
        if not results:
            QMessageBox.information(self, "비교할 제안 없음", "먼저 AI 결과 JSON을 불러오세요."); return
        QMessageBox.information(self, "현재 분석과 비교", "\n".join(compare_with_current(results[-1], self.session_getter().analysis)))

    def _apply_director(self):
        results = self.session_getter().director_intelligence_results
        if not results:
            QMessageBox.information(self, "반영할 제안 없음", "먼저 AI 결과 JSON을 불러오세요."); return
        apply_director_proposal(self.session_getter(), results[-1], self.apply_scope.currentData())
        self.director_status.setText("선택한 범위만 반영했습니다. 기존 Shot은 자동 재생성하지 않았습니다.")
        self.on_change()

    def _analyze_music_intelligence(self, backend):
        session = self.session_getter()
        if not session.music_path:
            QMessageBox.information(self, "음악 파일", "먼저 MUSIC 화면에서 음악 파일을 선택하세요."); return
        try:
            structure = analyze_music_intelligence(session.music_path, backend, audio_map=session.audio_map)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "음악 구조 분석 실패", str(exc)); return
        session.enhanced_music_structure = structure
        if session.audio_map:
            session.mv_timeline = fuse_music_structure_timeline(session.audio_map, session.lines, session.analysis, structure)
        labels = [segment.label.replace("_", " ").title() for segment in structure.segments]
        self.music_summary.setText(" → ".join(labels) if labels else "기본 음악 분석을 유지합니다. 고급 기능 구간은 확정하지 않았습니다.")
        self.on_change()

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
