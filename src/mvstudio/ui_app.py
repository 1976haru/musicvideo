from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from PySide6.QtCore import QStandardPaths, QTimer, Qt
    from PySide6.QtGui import QFont, QPixmap
    from PySide6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
        QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
        QPushButton, QScrollArea, QSpinBox, QStackedWidget, QStatusBar, QTabWidget,
        QTextEdit, QVBoxLayout, QWidget,
    )
except ImportError as exc:
    raise RuntimeError(
        "PySide6가 필요합니다. `pip install -e .[ui,music]` 실행 후 다시 시작하세요."
    ) from exc

from .music_engine import format_timeline_text
from .models import ReferenceRole
from .g3_ui import ShotBoardPage, StoryRoomPage
from .g4_ui import ManualGenerationStudioPage
from .g4b_ui import ResultTakesPage
from .g5a_ui import TechnicalQCPage
from .reference_vault import resolve_reference_path
from .session import LyricsWorldSession
from .thumbnail_cache import ThumbnailCache

APP_STYLE = r"""
QMainWindow { background: #12151a; color: #eef2f7; }
QWidget { color: #eef2f7; font-size: 15px; }
QFrame#sidebar { background: #171b22; border-right: 1px solid #2d333d; }
QFrame#panel { background: #191e26; border: 1px solid #303744; border-radius: 12px; }
QFrame#conceptCard { background: #191e26; border: 1px solid #343c49; border-radius: 14px; }
QFrame#conceptCard[selected="true"] { border: 2px solid #7da6ff; background: #1b2230; }
QPushButton { min-height: 44px; border: 1px solid #384150; border-radius: 9px; padding: 0 14px; background: #232a34; }
QPushButton:hover { background: #2b3440; }
QPushButton:disabled { color: #647080; background: #171b21; border-color: #262d36; }
QPushButton#primary { background: #3764c7; border: 1px solid #4d78d7; font-weight: 700; }
QPushButton#nav { text-align: left; padding-left: 14px; background: transparent; border: none; }
QPushButton#nav[active="true"] { background: #242c38; border: 1px solid #364154; }
QTextEdit { background: #101319; border: 1px solid #313946; border-radius: 10px; padding: 10px; selection-background-color: #3764c7; }
QSpinBox { min-height: 40px; background: #101319; border: 1px solid #313946; border-radius: 8px; padding: 0 8px; }
QLineEdit, QComboBox, QDoubleSpinBox { min-height: 42px; background: #101319; border: 1px solid #313946; border-radius: 8px; padding: 0 10px; }
QLabel#muted { color: #9aa6b5; }
QLabel#score { font-size: 24px; font-weight: 800; color: #a9c2ff; }
QLabel#metric { font-size: 21px; font-weight: 800; color: #dce7ff; }
QLabel#sectionTitle { font-size: 22px; font-weight: 800; }
QLabel#smallTitle { font-size: 16px; font-weight: 750; }
QScrollArea { border: none; background: transparent; }
QStatusBar { background: #15191f; color: #aab3c0; }
"""


def _label(text="", name=None):
    w = QLabel(text)
    w.setWordWrap(True)
    if name:
        w.setObjectName(name)
    return w


class ConceptCard(QFrame):
    def __init__(self, concept, on_select):
        super().__init__()
        self.concept = concept
        self.setObjectName("conceptCard")
        self.setProperty("selected", False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        items = [
            _label(concept.title, "smallTitle"),
            _label(f"{concept.interpretation_mode.upper()} · 가사 연관도", "muted"),
            _label(str(concept.lyric_relevance_score), "score"),
            _label(concept.one_line),
            _label("세계 법칙 · " + concept.world_rule, "muted"),
            _label("모티프 · " + " / ".join(concept.recurring_motifs), "muted"),
            _label("마지막 이미지 · " + concept.ending_image, "muted"),
            _label("가사 근거 · " + ", ".join(concept.lyric_evidence or ["분석 보강 필요"]), "muted"),
        ]
        for item in items:
            lay.addWidget(item)
        btn = QPushButton("이 세계관 선택")
        btn.clicked.connect(lambda: on_select(self.concept.concept_id))
        lay.addWidget(btn)

    def set_selected(self, value: bool):
        self.setProperty("selected", value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class ReferenceDropArea(QFrame):
    def __init__(self, on_files):
        super().__init__()
        self.on_files = on_files
        self.setAcceptDrops(True)
        self.setObjectName("panel")
        box = QVBoxLayout(self)
        box.setContentsMargins(22, 22, 22, 22)
        box.addWidget(_label("이미지/영상 파일을 여기에 놓으세요", "smallTitle"), alignment=Qt.AlignCenter)
        box.addWidget(_label("원본은 이동·변경·삭제하지 않고 메타데이터만 등록합니다.", "muted"), alignment=Qt.AlignCenter)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.on_files(paths)
            event.acceptProposedAction()


class ReferenceCard(QFrame):
    def __init__(self, asset, source_path: Path, status: str, on_remove):
        super().__init__()
        self.setObjectName("panel")
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 16, 16, 16)
        thumb = QLabel("미리보기 없음")
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setFixedSize(150, 100)
        pixmap = QPixmap(str(source_path)) if status == "available" else QPixmap()
        if not pixmap.isNull():
            thumb.setPixmap(pixmap.scaled(150, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        row.addWidget(thumb)
        details = QVBoxLayout()
        master = "MASTER" if asset.is_master else "SECONDARY"
        details.addWidget(_label(f"{asset.reference_id} · {master}", "smallTitle"))
        details.addWidget(_label(f"역할: {asset.role.value} · 잠금 {asset.lock_strength:.2f}"))
        details.addWidget(_label(f"범위: {asset.applies_to.value} · 상태: {status}", "muted"))
        details.addWidget(_label(f"파일: {source_path}", "muted"))
        details.addWidget(_label(f"메모: {asset.notes or '-'}", "muted"))
        row.addLayout(details, 1)
        remove = QPushButton("등록 해제")
        remove.clicked.connect(lambda: on_remove(asset.reference_id))
        row.addWidget(remove)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session = LyricsWorldSession()
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(1000)
        self.autosave_timer.timeout.connect(self._autosave)
        self.concept_cards = {}
        self.setWindowTitle("MV Director Studio — G4B Result / Take Manager")
        self.resize(1420, 900)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(APP_STYLE)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("G2 작업 중 · World Bible + Reference Vault")
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(255)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 20, 16, 20)
        side.setSpacing(8)
        side.addWidget(_label("MV DIRECTOR\nSTUDIO", "sectionTitle"))
        side.addWidget(_label("음악과 가사를 먼저 읽고\n그 뒤에 세계를 설계합니다.", "muted"))
        side.addSpacing(18)
        session_actions = QHBoxLayout()
        open_session = QPushButton("세션 열기")
        open_session.clicked.connect(self._open_session)
        save_session = QPushButton("세션 저장")
        save_session.clicked.connect(self._export)
        session_actions.addWidget(open_session)
        session_actions.addWidget(save_session)
        side.addLayout(session_actions)

        self.nav_buttons = []
        steps = [
            ("01  MUSIC", True),
            ("02  LYRICS & MEANING", True),
            ("03  WORLD LAB", True),
            ("04  WORLD BIBLE", True),
            ("05  REFERENCE VAULT", True),
            ("06  STORY ROOM", True),
            ("07  SHOT BOARD", True),
            ("08  GENERATE", True),
            ("09  QC", True),
        ]
        for i, (txt, enabled) in enumerate(steps):
            b = QPushButton(txt)
            b.setObjectName("nav")
            b.setEnabled(enabled)
            b.setProperty("active", i == 0)
            side.addWidget(b)
            self.nav_buttons.append(b)
        self.nav_buttons[0].clicked.connect(lambda: self._switch(0))
        self.nav_buttons[1].clicked.connect(lambda: self._switch(1))
        self.nav_buttons[2].clicked.connect(lambda: self._switch(2))
        self.nav_buttons[3].clicked.connect(lambda: self._switch(3))
        self.nav_buttons[4].clicked.connect(lambda: self._switch(4))
        side.addStretch(1)
        side.addWidget(_label("전체 약 87% · G5A\nTechnical / Temporal QC", "muted"))

        self.pages = QStackedWidget()
        self.pages.addWidget(self._music_page())
        self.pages.addWidget(self._lyrics_page())
        self.pages.addWidget(self._world_page())
        self.pages.addWidget(self._world_bible_page())
        self.pages.addWidget(self._reference_page())
        self.story_room_page = StoryRoomPage(lambda: self.session, self._schedule_autosave)
        self.shot_board_page = ShotBoardPage(lambda: self.session, self._schedule_autosave)
        self.pages.addWidget(self.story_room_page)
        self.pages.addWidget(self.shot_board_page)
        self.manual_generation_page = ManualGenerationStudioPage(lambda: self.session, self._schedule_autosave)
        self.result_takes_page = ResultTakesPage(lambda: self.session, self._schedule_autosave)
        self.generation_tabs = QTabWidget()
        self.generation_tabs.addTab(self.manual_generation_page, "PROMPT PACK")
        self.generation_tabs.addTab(self.result_takes_page, "RESULT / TAKES")
        self.pages.addWidget(self.generation_tabs)
        self.technical_qc_page = TechnicalQCPage(
            lambda: self.session, self._schedule_autosave,
            lambda: (self.generation_tabs.setCurrentIndex(1), self._switch(7)),
        )
        self.pages.addWidget(self.technical_qc_page)
        self.nav_buttons[5].clicked.connect(lambda: self._switch(5))
        self.nav_buttons[6].clicked.connect(lambda: self._switch(6))
        self.nav_buttons[7].clicked.connect(lambda: self._switch(7))
        self.nav_buttons[8].clicked.connect(lambda: self._switch(8))
        outer.addWidget(sidebar)
        outer.addWidget(self.pages, 1)
        self.setCentralWidget(root)

    def _switch(self, index):
        self.pages.setCurrentIndex(index)
        for i, b in enumerate(self.nav_buttons):
            b.setProperty("active", i == index)
            b.style().unpolish(b)
            b.style().polish(b)

    def _music_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(_label("음악의 변화점을 먼저 찾습니다", "sectionTitle"))
        lay.addWidget(_label(
            "BPM만 보는 것이 아니라 비트·온셋·에너지·스펙트럼 변화를 합쳐 장면 전환 후보를 찾고, "
            "가사 타임라인과 겹쳐 감독용 MV Timeline을 만듭니다.", "muted"
        ))

        tools = QHBoxLayout()
        load = QPushButton("음악 파일 선택")
        load.clicked.connect(self._load_music)
        tools.addWidget(load)
        self.music_source = _label("선택된 음악: -", "muted")
        tools.addWidget(self.music_source, 1)
        analyze = QPushButton("음악 분석 + MV Timeline 생성")
        analyze.setObjectName("primary")
        analyze.clicked.connect(self._analyze_music)
        tools.addWidget(analyze)
        lay.addLayout(tools)

        metrics = QHBoxLayout()
        for title, attr in [("길이", "music_duration"), ("Tempo", "music_tempo"), ("Beat", "music_beats"), ("변화점", "music_transitions")]:
            panel = QFrame()
            panel.setObjectName("panel")
            box = QVBoxLayout(panel)
            box.setContentsMargins(16, 14, 16, 14)
            box.addWidget(_label(title, "muted"))
            value = _label("-", "metric")
            setattr(self, attr, value)
            box.addWidget(value)
            metrics.addWidget(panel, 1)
        lay.addLayout(metrics)

        body = QHBoxLayout()
        body.setSpacing(14)
        left = QFrame()
        left.setObjectName("panel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 16, 16, 16)
        ll.addWidget(_label("AUDIO MAP", "smallTitle"))
        self.audio_summary = QTextEdit()
        self.audio_summary.setReadOnly(True)
        self.audio_summary.setPlaceholderText("음악을 분석하면 섹션 후보와 변화점이 표시됩니다.")
        ll.addWidget(self.audio_summary, 1)

        right = QFrame()
        right.setObjectName("panel")
        rr = QVBoxLayout(right)
        rr.setContentsMargins(16, 16, 16, 16)
        rr.addWidget(_label("MV DIRECTOR TIMELINE", "smallTitle"))
        self.timeline_summary = QTextEdit()
        self.timeline_summary.setReadOnly(True)
        self.timeline_summary.setPlaceholderText("음악 + 가사 근거가 합쳐진 장면 전환 우선순위가 표시됩니다.")
        rr.addWidget(self.timeline_summary, 1)
        rr.addWidget(_label("P 값은 컷 강제값이 아니라 연출 우선순위입니다. 모든 비트마다 화면을 바꾸지 않습니다.", "muted"))
        body.addWidget(left, 1)
        body.addWidget(right, 1)
        lay.addLayout(body, 1)
        return page

    def _lyrics_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(_label("가사에서 세계관의 씨앗을 찾습니다", "sectionTitle"))
        lay.addWidget(_label(
            "반복 구절·감정곡선·장소·사물·빛·행동을 분해하고, 무엇을 현실로 보여주고 무엇을 은유로 바꿀지 결정합니다.",
            "muted"
        ))
        tools = QHBoxLayout()
        load = QPushButton("가사 파일 불러오기")
        load.clicked.connect(self._load_lyrics)
        tools.addWidget(load)
        tools.addWidget(QLabel("곡 길이(초)"))
        self.duration = QSpinBox()
        self.duration.setRange(0, 3600)
        self.duration.setValue(180)
        self.duration.setSpecialValueText("미지정")
        tools.addWidget(self.duration)
        tools.addStretch(1)
        analyze = QPushButton("가사 분석 + 세계관 생성")
        analyze.setObjectName("primary")
        analyze.clicked.connect(self._analyze_lyrics)
        tools.addWidget(analyze)
        lay.addLayout(tools)

        body = QHBoxLayout()
        body.setSpacing(14)
        left = QFrame()
        left.setObjectName("panel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 16, 16, 16)
        ll.addWidget(_label("가사 원문", "smallTitle"))
        self.lyrics = QTextEdit()
        self.lyrics.setPlaceholderText("여기에 가사를 붙여넣거나 TXT / SRT / LRC 파일을 불러오세요.")
        ll.addWidget(self.lyrics, 1)
        self.source = _label("입력: 직접 붙여넣기", "muted")
        ll.addWidget(self.source)

        right = QFrame()
        right.setObjectName("panel")
        rr = QVBoxLayout(right)
        rr.setContentsMargins(16, 16, 16, 16)
        rr.setSpacing(9)
        rr.addWidget(_label("MEANING MAP", "smallTitle"))
        self.summary = _label("분석 전입니다.", "muted")
        rr.addWidget(self.summary)
        self.pov = _label("POV · -")
        self.conflict = _label("중심 갈등 · -")
        self.arc = _label("감정곡선 · -")
        self.repeat = _label("반복구절 · -")
        self.anchors = _label("시각 앵커 · -")
        for item in [self.pov, self.conflict, self.arc, self.repeat, self.anchors]:
            rr.addWidget(item)
        rr.addStretch(1)
        rr.addWidget(_label("음악이 먼저 분석되어 있으면 실제 곡 길이를 TXT 가사 시간 배치에 사용합니다.", "muted"))
        body.addWidget(left, 3)
        body.addWidget(right, 2)
        lay.addLayout(body, 1)
        return page

    def _world_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)
        lay.addWidget(_label("WORLD LAB", "sectionTitle"))
        lay.addWidget(_label("현실형, 은유형, 현실 80% + 시적 비현실 20% Hybrid를 가사 근거와 함께 비교합니다.", "muted"))
        self.empty = _label("먼저 가사를 분석하세요.", "muted")
        lay.addWidget(self.empty)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.card_host = QWidget()
        self.card_layout = QHBoxLayout(self.card_host)
        self.card_layout.setContentsMargins(0, 4, 0, 4)
        self.card_layout.setSpacing(12)
        scroll.setWidget(self.card_host)
        lay.addWidget(scroll, 1)
        actions = QHBoxLayout()
        self.selected = _label("선택된 세계관: -", "muted")
        actions.addWidget(self.selected, 1)
        export = QPushButton("현재 세션 JSON 저장")
        export.clicked.connect(self._export)
        lock = QPushButton("선택 세계관 잠금")
        lock.setObjectName("primary")
        lock.clicked.connect(self._lock)
        actions.addWidget(export)
        actions.addWidget(lock)
        lay.addLayout(actions)
        return page

    def _world_bible_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)
        outer.addWidget(_label("WORLD BIBLE", "sectionTitle"))
        outer.addWidget(_label("선택한 세계관을 변하면 안 되는 제작 규칙으로 정리합니다. 가사 근거 Line ID는 계속 보존됩니다.", "muted"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(13)
        self.bible_fields = {}
        labels = [
            ("premise", "Premise"), ("emotional_thesis", "Emotional thesis"),
            ("reality_rules", "Reality rules"), ("time_period", "Time period"),
            ("visual_language", "Visual language"), ("palette", "Palette"),
            ("material_language", "Materials"), ("weather_rules", "Weather rules"),
            ("lighting_rules", "Lighting rules"), ("camera_rules", "Camera rules"),
            ("recurring_motifs", "Recurring motifs"), ("forbidden_elements", "Forbidden elements"),
            ("lyric_foundation", "Lyric foundation (읽기 전용)"),
        ]
        for key, title in labels:
            editor = QTextEdit()
            editor.setMinimumHeight(76)
            if key == "lyric_foundation":
                editor.setReadOnly(True)
            self.bible_fields[key] = editor
            form.addRow(title, editor)
        scroll.setWidget(host)
        outer.addWidget(scroll, 1)
        actions = QHBoxLayout()
        promote = QPushButton("선택 세계관에서 초안 만들기")
        promote.clicked.connect(self._promote_world_bible)
        save = QPushButton("World Bible 변경 저장")
        save.setObjectName("primary")
        save.clicked.connect(self._save_world_bible)
        actions.addStretch(1)
        actions.addWidget(promote)
        actions.addWidget(save)
        outer.addLayout(actions)
        return page

    def _reference_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)
        outer.addWidget(_label("REFERENCE VAULT", "sectionTitle"))
        outer.addWidget(_label("Reference ID, 역할, 잠금 강도와 적용 범위를 관리합니다. 등록 해제는 원본 파일을 삭제하지 않습니다.", "muted"))
        controls = QHBoxLayout()
        self.reference_role = QComboBox()
        for role in ReferenceRole:
            self.reference_role.addItem(role.name, role)
        self.reference_lock = QDoubleSpinBox()
        self.reference_lock.setRange(0.0, 1.0)
        self.reference_lock.setSingleStep(0.05)
        self.reference_lock.setValue(0.8)
        self.reference_master = QCheckBox("Master")
        self.reference_master.setMinimumHeight(42)
        self.reference_notes = QLineEdit()
        self.reference_notes.setPlaceholderText("메모 (선택)")
        choose = QPushButton("파일 선택")
        choose.clicked.connect(self._choose_references)
        controls.addWidget(_label("역할"))
        controls.addWidget(self.reference_role)
        controls.addWidget(_label("잠금"))
        controls.addWidget(self.reference_lock)
        controls.addWidget(self.reference_master)
        controls.addWidget(self.reference_notes, 1)
        controls.addWidget(choose)
        outer.addLayout(controls)
        outer.addWidget(_label("현재 G2는 Project scope를 사용합니다. Scene / Shot scope assignment는 G3 Story Room / Shot Board에서 활성화됩니다.", "muted"))
        outer.addWidget(ReferenceDropArea(self._add_reference_paths))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.reference_host = QWidget()
        self.reference_layout = QVBoxLayout(self.reference_host)
        self.reference_layout.setContentsMargins(0, 4, 0, 4)
        self.reference_layout.setSpacing(12)
        self.reference_layout.addStretch(1)
        scroll.setWidget(self.reference_host)
        outer.addWidget(scroll, 1)
        return page

    def _promote_world_bible(self):
        try:
            bible = self.session.promote_selected_concept()
        except ValueError as exc:
            QMessageBox.information(self, "World Bible", str(exc))
            return
        for key, editor in self.bible_fields.items():
            value = getattr(bible, key)
            editor.setPlainText("\n".join(value) if isinstance(value, list) else value)
        self.statusBar().showMessage(f"World Bible 초안 생성 · {bible.source_concept_id}")
        self._schedule_autosave()

    def _save_world_bible(self):
        if not self.session.world_bible:
            QMessageBox.information(self, "World Bible", "먼저 선택 세계관에서 초안을 만드세요.")
            return
        list_fields = {
            "reality_rules", "visual_language", "palette", "material_language", "weather_rules",
            "lighting_rules", "camera_rules", "recurring_motifs", "forbidden_elements", "lyric_foundation",
        }
        changes = {}
        for key, editor in self.bible_fields.items():
            text = editor.toPlainText().strip()
            changes[key] = [line.strip() for line in text.splitlines() if line.strip()] if key in list_fields else text
        self.session.world_bible = self.session.world_bible.model_copy(update=changes)
        self.statusBar().showMessage("World Bible 변경 저장 완료")
        self._schedule_autosave()

    def _choose_references(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Reference 파일 선택", "", "Media (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.mp4 *.mov);;All Files (*)")
        self._add_reference_paths(paths)

    def _add_reference_paths(self, paths):
        added = False
        for path in paths:
            try:
                self.session.add_reference(
                    path,
                    self.reference_role.currentData(),
                    lock_strength=self.reference_lock.value(),
                    notes=self.reference_notes.text().strip(),
                    is_master=self.reference_master.isChecked(),
                )
                added = True
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "Reference 등록 실패", f"{path}\n\n{exc}")
        self._render_references()
        if added:
            self._schedule_autosave()

    def _render_references(self):
        while self.reference_layout.count() > 1:
            item = self.reference_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        vault = self.session.reference_vault
        cache_root = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation)) / "reference_thumbnails"
        cache = ThumbnailCache(cache_root)
        for asset in self.session.references:
            source = resolve_reference_path(asset, self.session.project_dir)
            status = vault.status(asset)
            preview = source
            if status == "available":
                pixmap = QPixmap(str(source))
                if not pixmap.isNull():
                    target = cache.target_for(source)
                    if not target.exists():
                        cache.prepare()
                        pixmap.scaled(320, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(str(target), "PNG")
                    preview = target
            self.reference_layout.insertWidget(
                self.reference_layout.count() - 1,
                ReferenceCard(asset, preview, status, self._remove_reference),
            )

    def _remove_reference(self, reference_id):
        self.session.remove_reference(reference_id)
        self._render_references()
        self.statusBar().showMessage(f"{reference_id} 메타데이터 등록 해제 · 원본 파일 유지")
        self._schedule_autosave()

    def _schedule_autosave(self):
        if self.session.session_path is not None:
            self.autosave_timer.start()

    def _autosave(self):
        if self.session.session_path is None:
            return
        try:
            saved = self.session.export()
        except Exception as exc:
            self.statusBar().showMessage(f"자동 저장 실패 · 기존 파일은 유지됨 · {exc}", 10000)
            return
        self.statusBar().showMessage(f"자동 저장 완료 · {saved}", 5000)

    def _open_session(self):
        path, _ = QFileDialog.getOpenFileName(self, "세션 JSON 열기", "", "MV Director Session (*.json);;JSON (*.json)")
        if not path:
            return
        try:
            loaded = LyricsWorldSession.import_file(path)
        except (OSError, json.JSONDecodeError, UnicodeError, ValueError, TypeError) as exc:
            QMessageBox.warning(
                self,
                "세션을 열 수 없습니다",
                f"선택한 JSON 세션을 읽지 못했습니다. 파일이 있는지와 JSON 형식을 확인하세요.\n\n{exc}",
            )
            self.statusBar().showMessage("세션 열기 실패 · 현재 작업은 유지됩니다", 8000)
            return
        self.autosave_timer.stop()
        self.session = loaded
        self._refresh_from_session()
        self._switch(0)
        self.statusBar().showMessage(f"세션 열기 완료 · 자동 저장 사용 · {loaded.session_path}")

    def _refresh_from_session(self):
        session = self.session
        self.music_source.setText(f"선택된 음악: {Path(session.music_path).name if session.music_path else '-'}")
        if session.audio_map:
            audio = session.audio_map
            self.music_duration.setText(f"{audio.duration_sec:.1f}s")
            self.music_tempo.setText(f"{audio.tempo_bpm:.1f} BPM")
            self.music_beats.setText(str(len(audio.beat_times_sec)))
            self.music_transitions.setText(str(len(audio.transitions)))
            sections = [
                f"{sec.section_id}  {sec.start_sec:6.2f}–{sec.end_sec:6.2f}s  {sec.label}  energy={sec.mean_energy:.4f}"
                for sec in audio.sections
            ]
            transitions = [
                f"{tr.time_sec:6.2f}s  {tr.character:26s}  strength={tr.strength:.2f}"
                for tr in audio.transitions
            ]
            cadence = " / ".join(f"{k}={v}s" for k, v in audio.cut_cadence_hints.items()) or "tempo 불명"
            self.audio_summary.setPlainText(
                "[CUT CADENCE HINT]\n" + cadence + "\n\n[SECTION CANDIDATES]\n" +
                ("\n".join(sections) or "-") + "\n\n[MUSIC TRANSITIONS]\n" + ("\n".join(transitions) or "-")
            )
        else:
            for name in ("music_duration", "music_tempo", "music_beats", "music_transitions"):
                getattr(self, name).setText("-")
            self.audio_summary.clear()
        self.timeline_summary.setPlainText(format_timeline_text(session.mv_timeline))
        self.lyrics.setPlainText(session.lyrics_text)
        self.source.setText(f"입력: {session.source_name if session.lyrics_text else '직접 붙여넣기'}")
        if session.duration_sec is not None:
            self.duration.setValue(max(0, min(3600, round(session.duration_sec))))
        if session.analysis:
            analysis = session.analysis
            self.summary.setText(analysis.synopsis)
            self.pov.setText(f"POV · {analysis.pov}")
            self.conflict.setText(f"중심 갈등 · {analysis.central_conflict}")
            self.arc.setText("감정곡선 · " + " → ".join(analysis.emotional_arc or ["분석 보강 필요"]))
            self.repeat.setText("반복구절 · " + (" / ".join(analysis.repeated_phrases) if analysis.repeated_phrases else "명시적 반복 없음"))
            self.anchors.setText("시각 앵커 · " + (" / ".join(f"{x.anchor_type}:{x.phrase}" for x in analysis.anchors[:12]) if analysis.anchors else "추가 해석 필요"))
        else:
            self.summary.setText("분석 전입니다.")
            self.pov.setText("POV · -")
            self.conflict.setText("중심 갈등 · -")
            self.arc.setText("감정곡선 · -")
            self.repeat.setText("반복구절 · -")
            self.anchors.setText("시각 앵커 · -")
        self._render_concepts()
        if session.world_bible:
            for key, editor in self.bible_fields.items():
                value = getattr(session.world_bible, key)
                editor.setPlainText("\n".join(value) if isinstance(value, list) else value or "")
        else:
            for editor in self.bible_fields.values():
                editor.clear()
        self._render_references()
        self.story_room_page.refresh()
        self.shot_board_page.refresh()
        self.manual_generation_page.refresh()
        self.result_takes_page.refresh()
        self.technical_qc_page.refresh()

    def _load_music(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "음악 파일 선택",
            "",
            "Audio (*.wav *.mp3 *.flac *.ogg *.m4a);;All Files (*)",
        )
        if not path:
            return
        self.session.music_path = path
        self.music_source.setText(f"선택된 음악: {Path(path).name}")

    def _analyze_music(self):
        if not self.session.music_path:
            QMessageBox.information(self, "음악 파일", "먼저 음악 파일을 선택하세요.")
            return
        # Keep any edited lyrics in session so music+lyrics fusion can happen in one click.
        self.session.lyrics_text = self.lyrics.toPlainText() if hasattr(self, "lyrics") else self.session.lyrics_text
        if self.session.lyrics_text.strip():
            self.session.duration_sec = None  # real audio duration should become authoritative
        self.statusBar().showMessage("음악 분석 중 · 비트/온셋/에너지/스펙트럼 변화 계산")
        QApplication.processEvents()
        try:
            self.session.analyze_music()
        except Exception as exc:
            QMessageBox.warning(self, "음악 분석 실패", str(exc))
            self.statusBar().showMessage("음악 분석 실패")
            return

        a = self.session.audio_map
        self.music_duration.setText(f"{a.duration_sec:.1f}s")
        self.music_tempo.setText(f"{a.tempo_bpm:.1f} BPM")
        self.music_beats.setText(str(len(a.beat_times_sec)))
        self.music_transitions.setText(str(len(a.transitions)))

        section_rows = []
        for sec in a.sections:
            section_rows.append(
                f"{sec.section_id}  {sec.start_sec:6.2f}–{sec.end_sec:6.2f}s  "
                f"{sec.label}  energy={sec.mean_energy:.4f}"
            )
        trans_rows = []
        for tr in a.transitions:
            trans_rows.append(
                f"{tr.time_sec:6.2f}s  {tr.character:26s}  strength={tr.strength:.2f}"
            )
        cadence = " / ".join(f"{k}={v}s" for k, v in a.cut_cadence_hints.items()) or "tempo 불명"
        self.audio_summary.setPlainText(
            "[CUT CADENCE HINT]\n" + cadence +
            "\n\n[SECTION CANDIDATES]\n" + ("\n".join(section_rows) or "-") +
            "\n\n[MUSIC TRANSITIONS]\n" + ("\n".join(trans_rows) or "-")
        )
        self.timeline_summary.setPlainText(format_timeline_text(self.session.mv_timeline) or "가사 없이 음악 변화점만 생성되었습니다.")
        if hasattr(self, "duration"):
            self.duration.setValue(max(0, min(3600, round(a.duration_sec))))
        self.statusBar().showMessage(
            f"G1 완료 · {a.tempo_bpm:.1f} BPM · 변화점 {len(a.transitions)}개 · MV cue {len(self.session.mv_timeline)}개"
        )
        self._refresh_from_session()
        self._schedule_autosave()

    def _load_lyrics(self):
        path, _ = QFileDialog.getOpenFileName(self, "가사 파일 선택", "", "Lyrics (*.txt *.srt *.lrc);;All Files (*)")
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except Exception as exc:
            QMessageBox.critical(self, "불러오기 실패", str(exc))
            return
        self.lyrics.setPlainText(text)
        self.session.source_name = Path(path).name
        self.source.setText(f"입력: {Path(path).name}")

    def _analyze_lyrics(self):
        self.session.lyrics_text = self.lyrics.toPlainText()
        if self.session.audio_map:
            self.session.duration_sec = self.session.audio_map.duration_sec
        else:
            self.session.duration_sec = float(self.duration.value()) if self.duration.value() else None
        try:
            self.session.analyze()
            self.session.rebuild_mv_timeline()
        except Exception as exc:
            QMessageBox.warning(self, "분석할 수 없습니다", str(exc))
            return
        a = self.session.analysis
        self._refresh_from_session()
        self.statusBar().showMessage(
            f"가사 {len(self.session.lines)}행 분석 완료 · 세계관 {len(self.session.concepts)}안 · MV cue {len(self.session.mv_timeline)}개"
        )
        self._switch(2)
        self._schedule_autosave()

    def _clear_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.concept_cards.clear()

    def _render_concepts(self):
        self._clear_cards()
        self.empty.setVisible(not bool(self.session.concepts))
        for c in self.session.concepts:
            card = ConceptCard(c, self._select)
            self.concept_cards[c.concept_id] = card
            self.card_layout.addWidget(card, 1)
        if self.session.selected_concept_id:
            self._select(self.session.selected_concept_id)

    def _select(self, cid):
        self.session.select_concept(cid)
        for key, card in self.concept_cards.items():
            card.set_selected(key == cid)
        c = self.session.selected_concept
        if c:
            self.selected.setText(f"선택된 세계관: {c.title} · 가사 연관도 {c.lyric_relevance_score}")
            self._schedule_autosave()

    def _lock(self):
        c = self.session.selected_concept
        if not c:
            QMessageBox.information(self, "세계관 선택", "먼저 세계관을 선택하세요.")
            return
        self._promote_world_bible()
        self._switch(3)
        self.statusBar().showMessage(f"WORLD LOCK · {c.title} · World Bible 초안 생성")

    def _export(self):
        if not self.session.analysis and not self.session.audio_map and not self.session.world_bible and not self.session.references and not self.session.story_beats and not self.session.shots:
            QMessageBox.information(self, "저장할 내용 없음", "먼저 음악 또는 가사를 분석하세요.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Music/Lyrics/World 세션 저장", "mv_director_session.json", "JSON (*.json)")
        if not path:
            return
        try:
            saved = self.session.export(path)
        except Exception as exc:
            QMessageBox.critical(self, "저장 실패", str(exc))
            return
        self.autosave_timer.stop()
        self._refresh_from_session()
        self.statusBar().showMessage(f"저장 완료 · 자동 저장 활성 · {saved}")


def run_gui() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("MV Director Studio")
    font = QFont()
    font.setPointSize(11)
    app.setFont(font)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_gui())
