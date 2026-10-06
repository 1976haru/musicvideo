from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QListWidget, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)

from .editor import (
    OUTPUT_PRESETS, RenderEngine, RenderFailure, RenderSettings, build_rough_cut,
    check_readiness, export_edit_plan, export_otio, ffmpeg_status, otio_status,
)
from .release_runtime import app_paths


def _label(text: str = "", name: str | None = None) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    if name:
        label.setObjectName(name)
    return label


class RenderWorker(QObject):
    progressed = Signal(str, int, int, float)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, engine, session, output, kind):
        super().__init__()
        self.engine, self.session, self.output, self.kind = engine, session, output, kind
        self.cancel_event = threading.Event()

    @Slot()
    def run(self):
        try:
            record = self.engine.render(
                self.session, self.output, kind=self.kind,
                progress=lambda stage, current, total, value: self.progressed.emit(stage, current, total, value),
                cancel=self.cancel_event,
            )
            self.succeeded.emit(record)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

    def cancel(self):
        self.cancel_event.set()


class EditorRenderPage(QWidget):
    def __init__(self, session_getter, on_change, on_compare_takes):
        super().__init__()
        self.session_getter = session_getter
        self.on_change = on_change
        self.on_compare_takes = on_compare_takes
        self.thread = None
        self.worker = None
        self._build()

    @property
    def session(self):
        return self.session_getter()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(_label("뮤직비디오를 자동으로 편집할까요?", "sectionTitle"))
        layout.addWidget(_label(
            "확정한 Take와 원곡만 사용합니다. 원본 음악과 영상은 변경하지 않습니다.", "muted"
        ))
        self.tool_status = _label()
        layout.addWidget(self.tool_status)
        summary_panel = QFrame()
        summary_panel.setObjectName("panel")
        summary_box = QVBoxLayout(summary_panel)
        self.summary = _label("자동 편집을 만들면 준비 상태를 확인할 수 있습니다.", "smallTitle")
        self.reasons = _label("", "muted")
        summary_box.addWidget(self.summary)
        summary_box.addWidget(self.reasons)
        layout.addWidget(summary_panel)

        actions = QHBoxLayout()
        self.build_button = QPushButton("자동 편집 만들기")
        self.build_button.setObjectName("primary")
        self.build_button.setMinimumHeight(44)
        self.build_button.clicked.connect(self.make_rough_cut)
        self.preview_button = QPushButton("미리보기 만들기")
        self.preview_button.setMinimumHeight(44)
        self.preview_button.clicked.connect(lambda: self.start_render("preview"))
        self.final_button = QPushButton("최종 영상 내보내기")
        self.final_button.setMinimumHeight(44)
        self.final_button.clicked.connect(lambda: self.start_render("final"))
        actions.addWidget(self.build_button)
        actions.addWidget(self.preview_button)
        actions.addWidget(self.final_button)
        layout.addLayout(actions)

        secondary = QHBoxLayout()
        problem = QPushButton("문제 Shot 확인")
        problem.clicked.connect(self.select_first_problem)
        compare = QPushButton("다른 Take 선택")
        compare.clicked.connect(self.on_compare_takes)
        self.open_preview = QPushButton("미리보기 열기")
        self.open_preview.clicked.connect(self._open_preview)
        secondary.addWidget(problem)
        secondary.addWidget(compare)
        secondary.addWidget(self.open_preview)
        layout.addLayout(secondary)

        layout.addWidget(_label("Shot 편집 결정", "smallTitle"))
        self.clip_list = QListWidget()
        self.clip_list.setMinimumHeight(150)
        self.clip_list.currentRowChanged.connect(self._load_selected)
        layout.addWidget(self.clip_list)
        decisions = QFormLayout()
        self.framing = QComboBox()
        self.framing.addItem("화면 채우기", "cover")
        self.framing.addItem("전체 보이기", "contain")
        self.offset = QDoubleSpinBox()
        self.offset.setRange(0, 86400)
        self.offset.setDecimals(3)
        self.short_resolution = QComboBox()
        self.short_resolution.addItem("해결하지 않음", "unresolved_short")
        self.short_resolution.addItem("마지막 프레임 유지", "hold_last")
        apply_clip = QPushButton("선택 Shot 설정 적용")
        apply_clip.clicked.connect(self.apply_clip_decision)
        decisions.addRow("화면 맞춤", self.framing)
        decisions.addRow("소스 시작 위치(초)", self.offset)
        decisions.addRow("길이 부족 해결", self.short_resolution)
        decisions.addRow("", apply_clip)
        layout.addLayout(decisions)

        self.gap_list = QListWidget()
        self.gap_list.setMinimumHeight(90)
        layout.addWidget(_label("Shot 사이 빈 시간", "smallTitle"))
        layout.addWidget(self.gap_list)
        gap_actions = QHBoxLayout()
        black = QPushButton("검은 화면 사용")
        black.clicked.connect(lambda: self.apply_gap("black"))
        hold = QPushButton("이전 화면 유지")
        hold.clicked.connect(lambda: self.apply_gap("hold_previous"))
        gap_actions.addWidget(black)
        gap_actions.addWidget(hold)
        layout.addLayout(gap_actions)

        self.expert_button = QPushButton("전문가 편집 설정")
        self.expert_button.setCheckable(True)
        self.expert_button.toggled.connect(lambda checked: self.expert_panel.setVisible(checked))
        layout.addWidget(self.expert_button)
        self.expert_panel = QFrame()
        self.expert_panel.setObjectName("panel")
        expert = QFormLayout(self.expert_panel)
        self.preset = QComboBox()
        for key, text in [
            ("youtube_1080p", "YouTube 1080p 16:9"), ("youtube_4k", "YouTube 4K 16:9"),
            ("vertical_1080p", "Vertical 1080×1920 9:16"), ("square_1080p", "Square 1080×1080 1:1"),
        ]:
            self.preset.addItem(text, key)
        self.preset.currentIndexChanged.connect(self.apply_preset)
        self.width = QSpinBox(); self.width.setRange(2, 8192)
        self.height = QSpinBox(); self.height.setRange(2, 8192)
        self.fps = QDoubleSpinBox(); self.fps.setRange(1, 120)
        self.quality = QSpinBox(); self.quality.setRange(0, 51)
        save_settings = QPushButton("출력 설정 저장")
        save_settings.clicked.connect(self.save_settings)
        expert.addRow("출력 preset", self.preset)
        expert.addRow("너비", self.width); expert.addRow("높이", self.height)
        expert.addRow("FPS", self.fps); expert.addRow("품질", self.quality)
        expert.addRow("", save_settings)
        self.expert_panel.setVisible(False)
        layout.addWidget(self.expert_panel)

        self.progress_label = _label("", "muted")
        self.progress = QProgressBar()
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.cancel_render)
        self.cancel_button.setEnabled(False)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.cancel_button)
        exports = QHBoxLayout()
        plan = QPushButton("Edit Plan JSON 내보내기")
        plan.clicked.connect(self.export_plan)
        otio = QPushButton("OTIO 내보내기")
        otio.clicked.connect(self.export_otio_file)
        exports.addWidget(plan); exports.addWidget(otio)
        layout.addLayout(exports)
        layout.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll)
        self.refresh()

    def refresh(self):
        session = self.session
        selected_shot = None
        if self.clip_list.currentRow() >= 0 and session.edit_timeline:
            old_clips = sorted(session.edit_timeline.clips, key=lambda item: item.timeline_start)
            if self.clip_list.currentRow() < len(old_clips):
                selected_shot = old_clips[self.clip_list.currentRow()].shot_id
        self.tool_status.setText(
            "영상 내보내기 도구(FFmpeg): " + ffmpeg_status() + "  ·  OTIO: " + otio_status()
            if ffmpeg_status() == "AVAILABLE" else "영상 내보내기 도구(FFmpeg)를 찾을 수 없습니다."
        )
        settings = session.render_settings
        index = self.preset.findData(settings.preset_id)
        self.preset.setCurrentIndex(max(0, index))
        self.width.setValue(settings.width); self.height.setValue(settings.height)
        self.fps.setValue(settings.fps); self.quality.setValue(settings.quality)
        self.clip_list.clear(); self.gap_list.clear()
        if session.edit_timeline:
            for clip in sorted(session.edit_timeline.clips, key=lambda item: item.timeline_start):
                self.clip_list.addItem(
                    f"{clip.shot_id}  {clip.timeline_start:.2f}–{clip.timeline_end:.2f}s  ·  {clip.take_id}\n"
                    f"필요 {clip.target_duration:.2f}s / 실제 {clip.source_span:.2f}s  ·  {clip.fit_status}  ·  QC {clip.qc_status}"
                )
            for gap in session.edit_timeline.gaps:
                self.gap_list.addItem(f"{gap.start_sec:.2f}–{gap.end_sec:.2f}s  ·  {gap.resolution}")
            if selected_shot:
                clips = sorted(session.edit_timeline.clips, key=lambda item: item.timeline_start)
                self.clip_list.setCurrentRow(next((i for i, item in enumerate(clips) if item.shot_id == selected_shot), -1))
        readiness = check_readiness(session, session.edit_timeline, settings)
        blockers = [item for item in readiness.issues if item.severity == "blocker"]
        missing = sum(item.code == "ACCEPTED_FILE_MISSING" for item in blockers)
        short = sum(item.code == "SHORT_CLIP" for item in blockers)
        self.summary.setText(
            f"사용할 영상 {readiness.ready_shots}/{readiness.total_shots} 준비\n"
            f"음악 파일 {'준비됨' if not any(i.code.startswith('MUSIC_') for i in blockers) else '확인 필요'}\n"
            f"길이가 부족한 Shot {short}개\n누락 파일 {missing}개\n상태: {readiness.status}"
        )
        self.reasons.setText("\n".join(f"• {item.message}" for item in readiness.issues[:5]))
        can_render = readiness.status != "BLOCKED" and ffmpeg_status() == "AVAILABLE"
        self.preview_button.setEnabled(can_render and self.thread is None)
        self.final_button.setEnabled(can_render and self.thread is None)
        self.open_preview.setEnabled(bool(session.preview_path and Path(session.preview_path).is_file()))

    def make_rough_cut(self):
        self.session.edit_timeline = build_rough_cut(self.session)
        self.on_change()
        self.refresh()

    def _load_selected(self, row):
        if row < 0 or not self.session.edit_timeline:
            return
        clips = sorted(self.session.edit_timeline.clips, key=lambda item: item.timeline_start)
        if row >= len(clips): return
        clip = clips[row]
        self.framing.setCurrentIndex(max(0, self.framing.findData(clip.framing)))
        self.offset.setValue(clip.source_in)
        self.short_resolution.setCurrentIndex(max(0, self.short_resolution.findData(clip.fit_status)))

    def apply_clip_decision(self):
        row = self.clip_list.currentRow()
        if row < 0 or not self.session.edit_timeline: return
        clips = sorted(self.session.edit_timeline.clips, key=lambda item: item.timeline_start)
        clip = clips[row]
        clip.framing = self.framing.currentData()
        maximum = max(0, clip.source_duration - 0.001)
        clip.source_in = min(self.offset.value(), maximum)
        available = clip.source_duration - clip.source_in
        clip.source_out = min(clip.source_duration, clip.source_in + clip.target_duration)
        clip.fit_status = "trim_end" if available > clip.target_duration + .001 else "exact" if abs(available-clip.target_duration) <= .001 else self.short_resolution.currentData()
        self.on_change(); self.refresh()

    def apply_gap(self, resolution):
        row = self.gap_list.currentRow()
        if row < 0 or not self.session.edit_timeline: return
        self.session.edit_timeline.gaps[row].resolution = resolution
        self.on_change(); self.refresh(); self.gap_list.setCurrentRow(row)

    def apply_preset(self):
        preset = OUTPUT_PRESETS[self.preset.currentData()].model_copy(deep=True)
        self.width.setValue(preset.width); self.height.setValue(preset.height)
        self.fps.setValue(preset.fps); self.quality.setValue(preset.quality)

    def save_settings(self):
        self.session.render_settings = RenderSettings(
            preset_id=self.preset.currentData(), width=self.width.value(), height=self.height.value(),
            fps=self.fps.value(), quality=self.quality.value(), framing=self.session.render_settings.framing,
        )
        self.on_change(); self.refresh()

    def select_first_problem(self):
        readiness = check_readiness(self.session)
        issue = next((item for item in readiness.issues if item.shot_id), None)
        if issue and self.session.edit_timeline:
            clips = sorted(self.session.edit_timeline.clips, key=lambda item: item.timeline_start)
            row = next((i for i, item in enumerate(clips) if item.shot_id == issue.shot_id), -1)
            self.clip_list.setCurrentRow(row)
        elif readiness.issues:
            QMessageBox.information(self, "편집 준비 문제", readiness.issues[0].message)

    def start_render(self, kind):
        suffix = "preview.mp4" if kind == "preview" else "final.mp4"
        start = str(self.session.project_dir or Path.cwd())
        path, _ = QFileDialog.getSaveFileName(self, "미리보기 저장" if kind == "preview" else "최종 영상 저장", str(Path(start) / suffix), "Video (*.mp4)")
        if not path: return
        target = Path(path)
        if target.exists() and QMessageBox.question(self, "파일 덮어쓰기", "기존 파일을 성공한 렌더로 교체할까요?") != QMessageBox.Yes:
            return
        self.thread = QThread(self)
        self.worker = RenderWorker(RenderEngine(cache_dir=app_paths().cache / "render-segments"), self.session, path, kind)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progressed.connect(self._progress)
        self.worker.succeeded.connect(self._render_success)
        self.worker.failed.connect(self._render_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self._render_finished)
        self.thread.start(); self.cancel_button.setEnabled(True); self.refresh()

    def _progress(self, stage, current, total, value):
        overall = int(((current - 1) + value / 100) / max(total, 1) * 100)
        self.progress.setValue(overall)
        self.progress_label.setText(f"{stage}  ·  {overall}%")

    def _render_success(self, record):
        self.session.render_records.append(record)
        if record.kind == "preview": self.session.preview_path = record.output_path
        else: self.session.final_path = record.output_path
        self.on_change()
        QMessageBox.information(self, "완료", "미리보기를 만들었습니다." if record.kind == "preview" else "최종 영상을 만들었습니다.")

    def _render_failed(self, message):
        QMessageBox.warning(self, "영상 내보내기", message or "영상 내보내기에 실패했습니다. 원본 파일은 변경되지 않았습니다.")

    def _render_finished(self):
        if self.thread:
            self.thread.deleteLater()
        self.thread = None; self.worker = None
        self.cancel_button.setEnabled(False); self.refresh()

    def cancel_render(self):
        if self.worker: self.worker.cancel()

    def _open_preview(self):
        if self.session.preview_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.session.preview_path))

    def export_plan(self):
        path, _ = QFileDialog.getSaveFileName(self, "Edit Plan 저장", "mv_edit_plan.json", "JSON (*.json)")
        if path:
            try: export_edit_plan(self.session, path)
            except Exception as exc: QMessageBox.warning(self, "내보내기 실패", str(exc))

    def export_otio_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "OTIO 저장", "mv_timeline.otio", "OpenTimelineIO (*.otio)")
        if path:
            try: export_otio(self.session, path)
            except Exception as exc: QMessageBox.information(self, "OTIO 선택 기능", str(exc))
