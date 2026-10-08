from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from .series_studio import (
    DownloadWatcher, SeriesAsset, build_asset_prompt_packs, build_episode_graph,
    run_series_continuity_qc, suggest_reference_slots,
)


def _lines(value: list[str]) -> str:
    return "\n".join(value)


def _parse_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


class SeriesStudioDialog(QDialog):
    """Beginner-facing G8 workspace without changing the legacy G0–G7 page order."""

    FLOW = ("Series", "Episode", "Character", "Assets", "Continuity", "Episode Graph")

    def __init__(self, session, on_changed=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.on_changed = on_changed or (lambda: None)
        self.watcher: DownloadWatcher | None = None
        self.watch_timer = QTimer(self)
        self.watch_timer.setInterval(1500)
        self.watch_timer.timeout.connect(self._scan_downloads)
        self.setWindowTitle("SERIES STUDIO — Series → Episode → Character → Assets → Story → Shot → Generate")
        self.resize(1080, 760)
        self.setMinimumSize(900, 640)
        root = QVBoxLayout(self)
        title = QLabel("SERIES → EPISODE → CHARACTER → ASSETS → STORY → SHOT → GENERATE")
        title.setObjectName("seriesWorkflow")
        root.addWidget(title)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("seriesStudioTabs")
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._series_tab(), "Series")
        self.tabs.addTab(self._episode_tab(), "Episode")
        self.tabs.addTab(self._character_tab(), "Character")
        self.tabs.addTab(self._assets_tab(), "Assets")
        self.tabs.addTab(self._continuity_tab(), "Continuity")
        self.tabs.addTab(self._graph_tab(), "Episode Graph")
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        root.addWidget(close)
        self.refresh()

    def _series_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.series_title = QLineEdit()
        self.series_logline = QTextEdit()
        self.series_world = QTextEdit()
        self.series_visual = QTextEdit()
        self.series_motifs = QTextEdit()
        self.series_forbidden = QTextEdit()
        form.addRow("Series title", self.series_title)
        form.addRow("Series logline", self.series_logline)
        form.addRow("Common world rules", self.series_world)
        form.addRow("Common visual rules", self.series_visual)
        form.addRow("Recurring motifs", self.series_motifs)
        form.addRow("Forbidden elements", self.series_forbidden)
        buttons = QHBoxLayout()
        seed = QPushButton("Load THE FIFTH VERDICT seed")
        seed.setObjectName("loadSeriesSeed")
        seed.clicked.connect(self._seed)
        save = QPushButton("Apply Series Bible")
        save.clicked.connect(self._apply_series)
        buttons.addWidget(seed)
        buttons.addWidget(save)
        form.addRow(buttons)
        return page

    def _episode_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.episode_select = QComboBox()
        self.episode_select.currentIndexChanged.connect(self._load_episode)
        self.episode_title = QLineEdit()
        self.episode_logline = QTextEdit()
        self.episode_world = QTextEdit()
        self.episode_visual = QTextEdit()
        self.episode_color = QTextEdit()
        form.addRow("Episode", self.episode_select)
        form.addRow("Title", self.episode_title)
        form.addRow("Logline", self.episode_logline)
        form.addRow("World overrides", self.episode_world)
        form.addRow("Visual overrides", self.episode_visual)
        form.addRow("Color arc", self.episode_color)
        save = QPushButton("Apply Episode Bible")
        save.clicked.connect(self._apply_episode)
        form.addRow(save)
        return page

    def _character_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.entity_select = QComboBox()
        self.entity_select.currentIndexChanged.connect(self._load_entity)
        self.entity_role = QLineEdit()
        self.entity_text_master = QTextEdit()
        self.entity_shape = QTextEdit()
        self.entity_locked_parts = QTextEdit()
        self.entity_palette = QTextEdit()
        self.entity_motion = QTextEdit()
        self.entity_forbidden = QTextEdit()
        self.entity_forbidden_mutations = QTextEdit()
        self.entity_presence = QLineEdit()
        self.entity_variants = QTextEdit()
        self.entity_variants.setReadOnly(True)
        form.addRow("Entity", self.entity_select)
        form.addRow("Role", self.entity_role)
        form.addRow("TEXT MASTER", self.entity_text_master)
        form.addRow("Silhouette rules", self.entity_shape)
        form.addRow("HARD LOCKED PARTS", self.entity_locked_parts)
        form.addRow("Palette rules", self.entity_palette)
        form.addRow("Motion rules", self.entity_motion)
        form.addRow("Forbidden rules", self.entity_forbidden)
        form.addRow("HARD FORBIDDEN MUTATIONS", self.entity_forbidden_mutations)
        form.addRow("Episode presence", self.entity_presence)
        form.addRow("Episode / action / emotion variants", self.entity_variants)
        save = QPushButton("Apply Entity Master")
        save.clicked.connect(self._apply_entity)
        form.addRow(save)
        return page

    def _assets_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        controls = QHBoxLayout()
        suggest = QPushButton("Reference Director — Suggest slots")
        suggest.clicked.connect(self._suggest_assets)
        prompts = QPushButton("Asset Factory — Build prompt pack")
        prompts.clicked.connect(self._build_prompts)
        watch = QPushButton("Watch download folder")
        watch.clicked.connect(self._choose_watch_folder)
        add_file = QPushButton("기존 이미지 추가")
        add_file.clicked.connect(self._add_asset_file)
        controls.addWidget(suggest)
        controls.addWidget(prompts)
        controls.addWidget(watch)
        controls.addWidget(add_file)
        layout.addLayout(controls)

        layout.addWidget(QLabel("등록된 Series Assets · candidate를 확인한 뒤 Approve하면 Shot/Generate에서 사용할 수 있습니다."))
        self.asset_list = QListWidget()
        self.asset_list.setMinimumHeight(150)
        self.asset_list.currentRowChanged.connect(self._load_asset)
        layout.addWidget(self.asset_list)

        meta_host = QWidget()
        meta = QFormLayout(meta_host)
        self.asset_role = QComboBox()
        for role in (
            "character_sheet", "action_keyart", "emotion_keyart", "environment_keyart",
            "prop_master", "color_script", "shape_reference", "unassigned",
        ):
            self.asset_role.addItem(role, role)
        self.asset_entity = QComboBox()
        self.asset_episode = QComboBox()
        meta.addRow("Role", self.asset_role)
        meta.addRow("Entity", self.asset_entity)
        meta.addRow("Episode", self.asset_episode)
        layout.addWidget(meta_host)

        review = QHBoxLayout()
        apply_meta = QPushButton("메타데이터 적용")
        apply_meta.clicked.connect(self._apply_asset_metadata)
        approve = QPushButton("Approve")
        approve.clicked.connect(lambda: self._set_asset_status("approved"))
        reject = QPushButton("Reject")
        reject.clicked.connect(lambda: self._set_asset_status("rejected"))
        unregister = QPushButton("등록 해제")
        unregister.clicked.connect(self._unregister_asset)
        for button in (apply_meta, approve, reject, unregister):
            review.addWidget(button)
        layout.addLayout(review)

        self.asset_output = QTextEdit()
        self.asset_output.setReadOnly(True)
        self.asset_output.setObjectName("assetFactoryOutput")
        layout.addWidget(self.asset_output, 1)
        return page

    def _continuity_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        run = QPushButton("Run Series Continuity QC")
        run.clicked.connect(self._run_qc)
        layout.addWidget(run)
        self.qc_output = QTextEdit()
        self.qc_output.setReadOnly(True)
        self.qc_output.setObjectName("seriesContinuityReport")
        layout.addWidget(self.qc_output)
        return page

    def _graph_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.graph_output = QTextEdit()
        self.graph_output.setReadOnly(True)
        self.graph_output.setObjectName("episodeGraph")
        layout.addWidget(self.graph_output)
        return page

    def _seed(self):
        if self.session.series_bible is not None:
            answer = QMessageBox.question(self, "Replace series data?", "Existing series data will be replaced. Continue?")
            if answer != QMessageBox.Yes:
                return
        self.session.initialize_series(replace=True)
        self.on_changed()
        self.refresh()

    def refresh(self):
        bible = self.session.series_bible
        self.episode_select.blockSignals(True)
        self.entity_select.blockSignals(True)
        self.episode_select.clear()
        self.entity_select.clear()
        if bible:
            self.series_title.setText(bible.title)
            self.series_logline.setPlainText(bible.series_logline)
            self.series_world.setPlainText(_lines(bible.common_world_rules))
            self.series_visual.setPlainText(_lines(bible.common_visual_rules))
            self.series_motifs.setPlainText(_lines(bible.recurring_motifs))
            self.series_forbidden.setPlainText(_lines(bible.forbidden_elements))
            for episode in sorted(bible.episodes, key=lambda x: x.order):
                self.episode_select.addItem(f"{episode.episode_id} — {episode.title}", episode.episode_id)
        for entity in self.session.series_entities:
            self.entity_select.addItem(f"{entity.display_name} [{entity.entity_type}]", entity.entity_id)
        self.episode_select.blockSignals(False)
        self.entity_select.blockSignals(False)
        self._load_episode()
        self._load_entity()
        self._refresh_assets()
        self._refresh_graph()

    def _apply_series(self):
        bible = self.session.series_bible
        if not bible:
            QMessageBox.information(self, "Series Bible", "Load the seed or create a series first.")
            return
        bible.title = self.series_title.text().strip() or bible.title
        bible.series_logline = self.series_logline.toPlainText().strip()
        bible.common_world_rules = _parse_lines(self.series_world.toPlainText())
        bible.common_visual_rules = _parse_lines(self.series_visual.toPlainText())
        bible.recurring_motifs = _parse_lines(self.series_motifs.toPlainText())
        bible.forbidden_elements = _parse_lines(self.series_forbidden.toPlainText())
        self.on_changed()
        self._refresh_graph()

    def _current_episode(self):
        if not self.session.series_bible:
            return None
        eid = self.episode_select.currentData()
        return next((e for e in self.session.series_bible.episodes if e.episode_id == eid), None)

    def _load_episode(self, *_):
        episode = self._current_episode()
        if not episode:
            return
        self.episode_title.setText(episode.title)
        self.episode_logline.setPlainText(episode.logline)
        self.episode_world.setPlainText(_lines(episode.world_overrides))
        self.episode_visual.setPlainText(_lines(episode.visual_overrides))
        self.episode_color.setPlainText(_lines(episode.color_arc))

    def _apply_episode(self):
        episode = self._current_episode()
        if not episode:
            return
        episode.title = self.episode_title.text().strip() or episode.title
        episode.logline = self.episode_logline.toPlainText().strip()
        episode.world_overrides = _parse_lines(self.episode_world.toPlainText())
        episode.visual_overrides = _parse_lines(self.episode_visual.toPlainText())
        episode.color_arc = _parse_lines(self.episode_color.toPlainText())
        self.session.series_bible.episode_titles = [e.title for e in sorted(self.session.series_bible.episodes, key=lambda x: x.order)]
        self.on_changed()
        self._refresh_graph()

    def _current_entity(self):
        eid = self.entity_select.currentData()
        return next((e for e in self.session.series_entities if e.entity_id == eid), None)

    def _load_entity(self, *_):
        entity = self._current_entity()
        if not entity:
            return
        self.entity_role.setText(entity.role)
        self.entity_text_master.setPlainText(entity.text_master)
        self.entity_shape.setPlainText(_lines(entity.silhouette_rules))
        self.entity_locked_parts.setPlainText(_lines(entity.shape_grammar.locked_parts))
        self.entity_palette.setPlainText(_lines(entity.palette_rules))
        self.entity_motion.setPlainText(_lines(entity.motion_rules))
        self.entity_forbidden.setPlainText(_lines(entity.forbidden_rules))
        self.entity_forbidden_mutations.setPlainText(_lines(entity.shape_grammar.forbidden_mutations))
        self.entity_presence.setText(", ".join(entity.episode_presence))
        self.entity_variants.setPlainText("\n".join(f"{v.variant_id}: {v.kind} / {v.episode_id or v.trigger}" for v in entity.variants) or "Base form only")

    def _apply_entity(self):
        entity = self._current_entity()
        if not entity:
            return
        entity.role = self.entity_role.text().strip()
        entity.text_master = self.entity_text_master.toPlainText().strip()
        entity.silhouette_rules = _parse_lines(self.entity_shape.toPlainText())
        entity.shape_grammar.locked_parts = _parse_lines(self.entity_locked_parts.toPlainText())
        entity.palette_rules = _parse_lines(self.entity_palette.toPlainText())
        entity.motion_rules = _parse_lines(self.entity_motion.toPlainText())
        entity.forbidden_rules = _parse_lines(self.entity_forbidden.toPlainText())
        entity.shape_grammar.forbidden_mutations = _parse_lines(self.entity_forbidden_mutations.toPlainText())
        entity.episode_presence = [x.strip().upper() for x in self.entity_presence.text().split(",") if x.strip()]
        self.on_changed()

    def _refresh_assets(self, select_asset_id: str | None = None):
        if not hasattr(self, "asset_list"):
            return
        current = select_asset_id
        if current is None and self.asset_list.currentItem():
            current = self.asset_list.currentItem().data(Qt.UserRole)

        self.asset_entity.blockSignals(True)
        self.asset_episode.blockSignals(True)
        self.asset_entity.clear()
        self.asset_entity.addItem("미지정", None)
        for entity in self.session.series_entities:
            self.asset_entity.addItem(f"{entity.display_name} [{entity.entity_type}]", entity.entity_id)
        self.asset_episode.clear()
        self.asset_episode.addItem("SERIES / 공통", None)
        if self.session.series_bible:
            for episode in sorted(self.session.series_bible.episodes, key=lambda item: item.order):
                self.asset_episode.addItem(f"{episode.episode_id} · {episode.title}", episode.episode_id)
        self.asset_entity.blockSignals(False)
        self.asset_episode.blockSignals(False)

        self.asset_list.blockSignals(True)
        self.asset_list.clear()
        restore = -1
        for index, asset in enumerate(self.session.series_assets):
            label = (
                f"{asset.asset_id} · {asset.review_status.upper()} · {asset.role} · "
                f"{asset.entity_id or 'UNASSIGNED'} · {asset.episode_id or 'SERIES'}\n{Path(asset.path).name}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, asset.asset_id)
            self.asset_list.addItem(item)
            if asset.asset_id == current:
                restore = index
        self.asset_list.blockSignals(False)
        if self.asset_list.count():
            self.asset_list.setCurrentRow(restore if restore >= 0 else 0)
        else:
            self._load_asset(-1)

    def _current_asset(self):
        item = self.asset_list.currentItem() if hasattr(self, "asset_list") else None
        asset_id = item.data(Qt.UserRole) if item else None
        return next((asset for asset in self.session.series_assets if asset.asset_id == asset_id), None)

    def _load_asset(self, *_):
        asset = self._current_asset()
        enabled = asset is not None
        for widget in (self.asset_role, self.asset_entity, self.asset_episode):
            widget.setEnabled(enabled)
        if not asset:
            return
        self.asset_role.setCurrentIndex(max(0, self.asset_role.findData(asset.role)))
        self.asset_entity.setCurrentIndex(max(0, self.asset_entity.findData(asset.entity_id)))
        self.asset_episode.setCurrentIndex(max(0, self.asset_episode.findData(asset.episode_id)))

    def _add_asset_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Series reference image",
            str(Path.home() / "Downloads"),
            "Images (*.png *.jpg *.jpeg *.webp *.tif *.tiff)",
        )
        if not path:
            return
        resolved = Path(path).expanduser().resolve(strict=False)
        existing = next(
            (asset for asset in self.session.series_assets if Path(asset.path).resolve(strict=False) == resolved),
            None,
        )
        if existing:
            self._refresh_assets(existing.asset_id)
            self.asset_output.setPlainText("이미 등록된 파일입니다. 원본 파일은 변경하지 않았습니다.")
            return
        asset = SeriesAsset(
            asset_id=f"ASSET_{uuid4().hex[:12].upper()}",
            path=str(resolved),
            source="manual",
            review_status="candidate",
        )
        self.session.series_assets.append(asset)
        self.on_changed()
        self._refresh_assets(asset.asset_id)
        self.asset_output.setPlainText("candidate로 등록했습니다. Entity / Episode / Role을 지정한 뒤 Approve하세요.")

    def _apply_asset_metadata(self):
        asset = self._current_asset()
        if not asset:
            return
        asset.role = self.asset_role.currentData()
        asset.entity_id = self.asset_entity.currentData()
        asset.episode_id = self.asset_episode.currentData()
        self.on_changed()
        self._refresh_assets(asset.asset_id)
        self.asset_output.setPlainText("메타데이터를 적용했습니다. 실제 생성 기준으로 사용할 파일이면 Approve하세요.")

    def _set_asset_status(self, status: str):
        asset = self._current_asset()
        if not asset:
            return
        if status == "approved" and asset.role == "unassigned":
            QMessageBox.information(self, "Asset 승인", "Approve 전에 Role을 지정하세요.")
            return
        asset.review_status = status
        self.on_changed()
        self._refresh_assets(asset.asset_id)
        self.asset_output.setPlainText(
            f"{asset.asset_id} → {status.upper()}\n"
            "원본 파일은 이동·변경·삭제하지 않았습니다."
        )

    def _unregister_asset(self):
        asset = self._current_asset()
        if not asset:
            return
        answer = QMessageBox.question(
            self,
            "등록 해제",
            "Series Studio 등록 정보만 제거합니다. 원본 이미지 파일은 삭제하지 않습니다. 계속할까요?",
        )
        if answer != QMessageBox.Yes:
            return
        self.session.series_assets.remove(asset)
        self.on_changed()
        self._refresh_assets()
        self.asset_output.setPlainText("등록 정보만 제거했습니다. 원본 파일은 그대로 유지됩니다.")

    def _suggest_assets(self):
        if not self.session.series_bible:
            self.asset_output.setPlainText("Load a Series Bible first.")
            return
        slots = suggest_reference_slots(self.session.series_bible, self.session.series_entities, self.session.series_assets)
        self.asset_output.setPlainText("\n".join(f"{s.slot_id} | {s.role} | {s.entity_id or s.episode_id} | {s.reason}" for s in slots))

    def _build_prompts(self):
        if not self.session.series_bible:
            self.asset_output.setPlainText("Load a Series Bible first.")
            return
        slots = suggest_reference_slots(self.session.series_bible, self.session.series_entities, self.session.series_assets)
        packs = build_asset_prompt_packs(self.session.series_bible, self.session.series_entities, slots)
        self.asset_output.setPlainText("\n\n".join(f"[{p.kind}] {p.pack_id}\n{p.prompt}\nNEGATIVE: {p.negative_prompt}" for p in packs))

    def _choose_watch_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Download folder to watch", str(Path.home() / "Downloads"))
        if not folder:
            return
        self.watcher = DownloadWatcher(folder)
        self.watch_timer.start()
        self.asset_output.setPlainText(f"Watching: {folder}\nFiles are registered in place and are never moved or deleted.")

    def _scan_downloads(self):
        if not self.watcher:
            return
        new_paths = self.watcher.detect_new()
        if not new_paths:
            return
        added = self.watcher.ingest(new_paths, self.session.series_entities, self.session.series_assets)
        if added:
            self.on_changed()
            self._refresh_assets(added[-1].asset_id)
            self.asset_output.append("\nAUTO-INGEST (candidate):\n" + "\n".join(
                f"{a.asset_id} → {a.entity_id or 'UNASSIGNED'} / {a.episode_id or 'SERIES'} / {a.role}"
                for a in added
            ) + "\n검토 후 Approve하세요. 원본 파일은 이동·변경·삭제하지 않습니다.")

    def _run_qc(self):
        if not self.session.series_bible:
            self.qc_output.setPlainText("Load a Series Bible first.")
            return
        report = run_series_continuity_qc(self.session.series_bible, self.session.series_entities, self.session.episode_continuity)
        header = "PASS" if report.passed else "FAIL"
        lines = [f"SERIES CONTINUITY QC: {header}"]
        lines.extend(f"[{f.severity.upper()}] {f.episode_id} {f.entity_id or ''} — {f.category}: {f.message}" for f in report.findings)
        if not report.findings:
            lines.append("No continuity violations in registered snapshots.")
        self.qc_output.setPlainText("\n".join(lines))

    def _refresh_graph(self):
        if not self.session.series_bible:
            self.graph_output.setPlainText("Load a Series Bible first.")
            return
        graph = build_episode_graph(self.session.series_bible)
        lines = ["EPISODES"] + [f"{n.order}. {n.node_id} — {n.label}" for n in graph.nodes]
        lines += ["", "CLUE → PAYOFF"] + [f"{e.source} ── {e.label} ──▶ {e.target} [{e.chain_id}]" for e in graph.edges]
        self.graph_output.setPlainText("\n".join(lines))
