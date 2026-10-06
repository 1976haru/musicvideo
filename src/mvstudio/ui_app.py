from __future__ import annotations

import sys
from pathlib import Path

try:
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
        QMessageBox, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
        QStatusBar, QTextEdit, QVBoxLayout, QWidget,
    )
except ImportError as exc:
    raise RuntimeError(
        "PySide6가 필요합니다. `pip install -e .[ui,music]` 실행 후 다시 시작하세요."
    ) from exc

from .music_engine import format_timeline_text
from .session import LyricsWorldSession

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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session = LyricsWorldSession()
        self.concept_cards = {}
        self.setWindowTitle("MV Director Studio v0.4 — Music + Lyrics Timeline")
        self.resize(1420, 900)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(APP_STYLE)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("전체 개발 진행률 45% · G1 Music Ingest 완료 · Codex 병행 준비")
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

        self.nav_buttons = []
        steps = [
            ("01  MUSIC", True),
            ("02  LYRICS & MEANING", True),
            ("03  WORLD LAB", True),
            ("04  WORLD BIBLE", False),
            ("05  REFERENCE VAULT", False),
            ("06  STORY ROOM", False),
            ("07  SHOT BOARD", False),
            ("08  GENERATE", False),
            ("09  QC / EDIT", False),
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
        side.addStretch(1)
        side.addWidget(_label("전체 45% · G1 완료\n이 버전부터 GitHub + Codex 병행 권장", "muted"))

        self.pages = QStackedWidget()
        self.pages.addWidget(self._music_page())
        self.pages.addWidget(self._lyrics_page())
        self.pages.addWidget(self._world_page())
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
        self.summary.setText(a.synopsis)
        self.pov.setText(f"POV · {a.pov}")
        self.conflict.setText(f"중심 갈등 · {a.central_conflict}")
        self.arc.setText("감정곡선 · " + " → ".join(a.emotional_arc or ["분석 보강 필요"]))
        self.repeat.setText("반복구절 · " + (" / ".join(a.repeated_phrases) if a.repeated_phrases else "명시적 반복 없음"))
        self.anchors.setText("시각 앵커 · " + (
            " / ".join(f"{x.anchor_type}:{x.phrase}" for x in a.anchors[:12]) if a.anchors else "추가 해석 필요"
        ))
        if self.session.audio_map:
            self.timeline_summary.setPlainText(format_timeline_text(self.session.mv_timeline))
        self._render_concepts()
        self.statusBar().showMessage(
            f"가사 {len(self.session.lines)}행 분석 완료 · 세계관 {len(self.session.concepts)}안 · MV cue {len(self.session.mv_timeline)}개"
        )
        self._switch(2)

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

    def _lock(self):
        c = self.session.selected_concept
        if not c:
            QMessageBox.information(self, "세계관 선택", "먼저 세계관을 선택하세요.")
            return
        QMessageBox.information(
            self,
            "세계관 잠금",
            f"'{c.title}'을 현재 방향으로 잠갔습니다.\n\n다음 G2에서 WORLD BIBLE로 승격하고 Reference Vault와 연결합니다.",
        )
        self.statusBar().showMessage(f"WORLD LOCK · {c.title} · 다음 G2 Reference Vault")

    def _export(self):
        if not self.session.analysis and not self.session.audio_map:
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
        self.statusBar().showMessage(f"저장 완료 · {saved}")


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
