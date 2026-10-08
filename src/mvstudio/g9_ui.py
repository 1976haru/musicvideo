from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from .production_orchestrator import (
    ComfyUIBridge,
    GenerationQueue,
    build_generation_queue,
    build_production_readiness,
    extract_comfyui_output_files,
    materialize_comfyui_workflow,
    verify_final_render,
)


class ProductionControlDialog(QDialog):
    """Beginner-facing control room over the existing G0–G8 pipeline."""

    def __init__(self, session_getter, on_changed=None, parent=None):
        super().__init__(parent)
        self.session_getter = session_getter
        self.on_changed = on_changed or (lambda: None)
        self.queue = GenerationQueue()
        self.settings = QSettings("MVDirectorStudio", "ProductionControl")
        self.workflow_template: dict | None = None
        self.setWindowTitle("PRODUCTION CONTROL · 전체 제작 점검")
        self.resize(1180, 760)
        self.setMinimumSize(1100, 720)
        self._build()
        self.refresh()

    @property
    def session(self):
        return self.session_getter()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        title = QLabel("뮤직비디오 전체 제작을 한 번에 점검합니다")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        subtitle = QLabel(
            "음악 → 세계관 → Series/Reference → Story → Shot → Prompt → Take → QC → Edit/Render를 "
            "하나의 준비 상태로 검사합니다. 빨간 문제부터 해결하면 됩니다."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("muted")
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("productionControlTabs")
        self.tabs.addTab(self._readiness_tab(), "전체 준비 상태")
        self.tabs.addTab(self._generation_tab(), "생성 대기열")
        self.tabs.addTab(self._final_tab(), "최종 영상 검증")
        root.addWidget(self.tabs, 1)

    def _readiness_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        row = QHBoxLayout()
        self.readiness_status = QLabel("검사 전")
        self.readiness_status.setObjectName("metric")
        row.addWidget(self.readiness_status)
        row.addStretch(1)
        refresh = QPushButton("전체 준비 상태 검사")
        refresh.setObjectName("primary")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        layout.addLayout(row)

        self.stage_list = QListWidget()
        self.stage_list.setObjectName("productionStageList")
        self.stage_list.currentRowChanged.connect(self._show_stage)
        layout.addWidget(self.stage_list, 1)

        self.issue_detail = QTextEdit()
        self.issue_detail.setReadOnly(True)
        self.issue_detail.setObjectName("productionIssueDetail")
        self.issue_detail.setMinimumHeight(190)
        layout.addWidget(self.issue_detail)

        self.next_actions = QLabel("다음 작업: -")
        self.next_actions.setWordWrap(True)
        self.next_actions.setObjectName("muted")
        layout.addWidget(self.next_actions)
        return page

    def _generation_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        note = QLabel(
            "외부 유료 API 없이도 사용할 수 있습니다. MANUAL은 기존 웹 생성 흐름이고, "
            "COMFYUI_LOCAL은 사용자가 직접 설치·실행한 localhost ComfyUI만 선택적으로 호출합니다."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("방식"))
        self.adapter = QComboBox()
        self.adapter.addItem("수동 생성", "MANUAL")
        self.adapter.addItem("로컬 ComfyUI", "COMFYUI_LOCAL")
        controls.addWidget(self.adapter)

        queue_btn = QPushButton("현재 필요한 Shot으로 생성 큐 만들기")
        queue_btn.setObjectName("primary")
        queue_btn.clicked.connect(self._build_queue)
        controls.addWidget(queue_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        endpoint_row = QHBoxLayout()
        endpoint_row.addWidget(QLabel("ComfyUI"))
        self.endpoint = QLineEdit(self.settings.value("comfy_endpoint", "http://127.0.0.1:8188"))
        endpoint_row.addWidget(self.endpoint, 1)
        check = QPushButton("연결 확인")
        check.clicked.connect(self._check_comfy)
        endpoint_row.addWidget(check)
        self.comfy_state = QLabel("선택 기능")
        self.comfy_state.setObjectName("muted")
        endpoint_row.addWidget(self.comfy_state)
        layout.addLayout(endpoint_row)

        workflow_row = QHBoxLayout()
        self.workflow_path = QLineEdit(self.settings.value("comfy_workflow", ""))
        self.workflow_path.setPlaceholderText("ComfyUI에서 Export(API format)한 workflow JSON")
        workflow_row.addWidget(self.workflow_path, 1)
        choose_workflow = QPushButton("Workflow JSON 선택")
        choose_workflow.clicked.connect(self._choose_workflow)
        workflow_row.addWidget(choose_workflow)
        layout.addLayout(workflow_row)

        output_row = QHBoxLayout()
        self.comfy_output = QLineEdit(self.settings.value("comfy_output", ""))
        self.comfy_output.setPlaceholderText("선택: ComfyUI/output 폴더 — 완료 영상 candidate 자동 등록용")
        output_row.addWidget(self.comfy_output, 1)
        choose_output = QPushButton("Output 폴더")
        choose_output.clicked.connect(self._choose_output)
        output_row.addWidget(choose_output)
        layout.addLayout(output_row)

        actions = QHBoxLayout()
        send = QPushButton("다음 ComfyUI 작업 보내기")
        send.clicked.connect(self._send_next)
        poll = QPushButton("실행 결과 확인")
        poll.clicked.connect(self._poll_jobs)
        actions.addWidget(send)
        actions.addWidget(poll)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.queue_list = QListWidget()
        self.queue_list.setObjectName("generationQueueList")
        layout.addWidget(self.queue_list, 1)

        self.queue_detail = QTextEdit()
        self.queue_detail.setReadOnly(True)
        self.queue_detail.setMaximumHeight(180)
        layout.addWidget(self.queue_detail)
        return page

    def _final_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        note = QLabel(
            "최종 렌더가 실제 음악 길이·해상도·FPS·오디오와 맞는지 확인하고, "
            "검은 프레임/과도한 정지/비정상적인 컷 수를 추가 검사합니다."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        actions = QHBoxLayout()
        verify = QPushButton("최종 영상 자동 검증")
        verify.setObjectName("primary")
        verify.clicked.connect(self._verify_final)
        actions.addWidget(verify)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.final_result = QTextEdit()
        self.final_result.setReadOnly(True)
        self.final_result.setObjectName("finalVerificationOutput")
        layout.addWidget(self.final_result, 1)
        return page

    def refresh(self):
        report = build_production_readiness(self.session)
        self._readiness_report = report
        icon = {"READY": "✅", "READY_WITH_WARNINGS": "⚠", "BLOCKED": "⛔"}[report.status]
        self.readiness_status.setText(
            f"{icon} {report.status} · blocker {report.blockers} · warning {report.warnings}"
        )
        old = self.stage_list.currentRow()
        self.stage_list.clear()
        for stage in report.stages:
            stage_icon = {
                "READY": "✅", "READY_WITH_WARNINGS": "⚠", "BLOCKED": "⛔", "NOT_STARTED": "○"
            }[stage.status]
            count = f"{stage.ready_count}/{stage.total_count}" if stage.total_count else "-"
            self.stage_list.addItem(f"{stage_icon} {stage.label} · {count} · {stage.status}")
        if self.stage_list.count():
            self.stage_list.setCurrentRow(old if 0 <= old < self.stage_list.count() else 0)
        self.next_actions.setText(
            "다음 작업: " + (" → ".join(report.next_actions) if report.next_actions else "현재 blocker가 없습니다.")
        )
        self._refresh_queue()

    def _show_stage(self, row: int):
        report = getattr(self, "_readiness_report", None)
        if not report or row < 0 or row >= len(report.stages):
            self.issue_detail.clear()
            return
        stage = report.stages[row]
        if not stage.issues:
            self.issue_detail.setPlainText("✅ 이 단계에서 발견된 문제가 없습니다.")
            return
        lines = []
        for issue in stage.issues:
            marker = {"blocker": "⛔", "warning": "⚠", "info": "•"}[issue.severity]
            where = f" [{issue.shot_id}]" if issue.shot_id else ""
            lines.append(f"{marker} {issue.code}{where}\n{issue.message}")
            if issue.action:
                lines.append(f"  → {issue.action}")
        self.issue_detail.setPlainText("\n\n".join(lines))

    def _build_queue(self):
        adapter = self.adapter.currentData()
        created = build_generation_queue(self.session, self.queue, adapter)
        self.queue_detail.setPlainText(
            f"생성 큐 {len(created)}개 준비 · accepted Take가 없고 현재 Prompt Contract가 최신인 Shot만 추가했습니다."
        )
        self._refresh_queue()

    def _refresh_queue(self):
        current = self.queue_list.currentRow()
        self.queue_list.clear()
        for job in self.queue.jobs:
            self.queue_list.addItem(
                f"{job.status:9s} · {job.shot_id} · {job.pack_id} · {job.adapter} · attempt {job.attempts}"
            )
        if self.queue_list.count():
            self.queue_list.setCurrentRow(current if 0 <= current < self.queue_list.count() else 0)

    def _bridge(self):
        endpoint = self.endpoint.text().strip() or "http://127.0.0.1:8188"
        self.settings.setValue("comfy_endpoint", endpoint)
        return ComfyUIBridge(endpoint, timeout_sec=2.5)

    def _check_comfy(self):
        state = self._bridge().status()
        self.comfy_state.setText(f"{state.state} · {state.detail[:100]}")
        if state.state != "AVAILABLE":
            self.queue_detail.setPlainText(
                "ComfyUI는 선택 기능입니다. 실행하지 않아도 MANUAL 제작 흐름은 그대로 사용할 수 있습니다."
            )

    def _choose_workflow(self):
        path, _ = QFileDialog.getOpenFileName(self, "ComfyUI API workflow JSON", self.workflow_path.text(), "JSON (*.json)")
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict):
                raise ValueError("Workflow JSON 최상위 값은 객체여야 합니다.")
        except Exception as exc:
            QMessageBox.warning(self, "Workflow JSON", str(exc))
            return
        self.workflow_template = payload
        self.workflow_path.setText(path)
        self.settings.setValue("comfy_workflow", path)
        self.queue_detail.setPlainText(
            "Workflow API JSON을 불러왔습니다. Prompt 노드 값에 {{MV_MAIN_PROMPT}}, "
            "{{MV_NEGATIVE_PROMPT}}, {{MV_CAMERA_PROMPT}}, {{MV_OUTPUT_PREFIX}} 같은 placeholder를 사용할 수 있습니다."
        )

    def _load_workflow(self):
        if self.workflow_template is not None:
            return self.workflow_template
        path = Path(self.workflow_path.text().strip()).expanduser()
        if not path.is_file():
            raise ValueError("ComfyUI API workflow JSON을 먼저 선택하세요.")
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("Workflow JSON 최상위 값은 객체여야 합니다.")
        self.workflow_template = payload
        return payload

    def _choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "ComfyUI output 폴더", self.comfy_output.text())
        if path:
            self.comfy_output.setText(path)
            self.settings.setValue("comfy_output", path)

    def _send_next(self):
        job = self.queue.next_pending("COMFYUI_LOCAL")
        if not job:
            QMessageBox.information(self, "생성 대기열", "보낼 COMFYUI_LOCAL 대기 작업이 없습니다.")
            return
        pack = next((item for item in self.session.generation_packs if item.pack_id == job.pack_id), None)
        if not pack:
            self.queue.fail(job.job_id, "Prompt Pack을 찾을 수 없습니다.")
            self._refresh_queue()
            return
        try:
            template = self._load_workflow()
            workflow = materialize_comfyui_workflow(template, pack)
            prompt_id = self._bridge().queue_workflow(workflow)
            self.queue.start(job.job_id, prompt_id)
        except Exception as exc:
            self.queue.fail(job.job_id, str(exc))
            self.queue_detail.setPlainText(f"ComfyUI 전송 실패\n{exc}")
        else:
            self.queue_detail.setPlainText(f"ComfyUI에 전송했습니다.\nprompt_id={prompt_id}\nShot={job.shot_id}")
        self._refresh_queue()

    def _poll_jobs(self):
        bridge = self._bridge()
        output_root = Path(self.comfy_output.text()).expanduser().resolve(strict=False) if self.comfy_output.text().strip() else None
        registered = []
        for job in list(self.queue.jobs):
            if job.status != "RUNNING" or not job.provider_job_id:
                continue
            try:
                history = bridge.history(job.provider_job_id)
                filenames = extract_comfyui_output_files(history, job.provider_job_id)
            except Exception as exc:
                self.queue_detail.setPlainText(f"결과 확인 실패\n{exc}")
                continue
            if not filenames:
                continue
            paths = [str((output_root / name).resolve(strict=False)) if output_root else name for name in filenames]
            self.queue.complete(job.job_id, paths)
            if output_root:
                for item in paths:
                    path = Path(item)
                    if path.is_file() and path.suffix.casefold() in {".mp4", ".mov", ".webm", ".mkv", ".m4v"}:
                        try:
                            if not any(Path(t.output_path).name == path.name and t.shot_id == job.shot_id for t in self.session.generation_takes):
                                take = self.session.take_manager.register(path, job.shot_id, job.pack_id)
                                registered.append(take.take_id)
                        except Exception:
                            pass
        if registered:
            self.on_changed()
        self.queue_detail.setPlainText(
            "결과 확인 완료" + (f"\n새 candidate Take: {', '.join(registered)}" if registered else "")
        )
        self._refresh_queue()
        self.refresh()

    def _verify_final(self):
        report = verify_final_render(self.session)
        lines = [
            f"상태: {report.status}",
            f"파일: {report.path or '-'}",
            f"길이: {report.duration_sec:.3f}s / 기대 {report.expected_duration_sec:.3f}s",
            f"검은 프레임 비율: {report.black_frame_ratio if report.black_frame_ratio is not None else 'N/A'}",
            f"정지 비율: {report.freeze_ratio if report.freeze_ratio is not None else 'N/A'}",
            f"감지 컷: {report.scene_cut_count if report.scene_cut_count is not None else 'N/A'} / 편집 경계 {report.expected_boundary_count}",
        ]
        if report.findings:
            lines.append("")
            for finding in report.findings:
                marker = {"blocker": "⛔", "warning": "⚠", "info": "•"}[finding.severity]
                lines.append(f"{marker} {finding.code}: {finding.message}")
        else:
            lines.append("\n✅ 최종 파일에서 추가 문제가 발견되지 않았습니다.")
        self.final_result.setPlainText("\n".join(lines))
