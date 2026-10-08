from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from mvstudio.g9_ui import ProductionControlDialog
from mvstudio.manual_generation import compile_manual_pack
from mvstudio.models import AudioMap, CameraSpec, ShotSpec, StoryBeat
from mvstudio.production_orchestrator import (
    GenerationQueue, build_production_readiness,
    compile_shot_continuity_contract, production_state_fingerprint,
)
from mvstudio.session import LyricsWorldSession
from mvstudio.ui_app import MainWindow
from mvstudio.ui_contract import validate_main_window_contract, validate_production_dialog_contract


def _stress_session(tmp_path: Path, count: int = 200) -> LyricsWorldSession:
    session = LyricsWorldSession(project_dir=tmp_path)
    music = tmp_path / "stress.wav"
    music.write_bytes(b"x")
    session.music_path = str(music)
    session.audio_map = AudioMap(source_path=str(music), duration_sec=float(count), sample_rate=44100, tempo_bpm=100)
    session.duration_sec = float(count)
    session.lyrics_text = "風の中で\n選択を残す\n未来はまだ書かれていない"
    session.source_name = "stress.txt"
    session.analyze()
    session.promote_selected_concept()
    session.initialize_series()

    beats = []
    shots = []
    for i in range(count):
        start = float(i)
        end = float(i + 1)
        beat_id = f"B{i+1:03d}"
        episode_id = f"EP{(i % 5) + 1}"
        beat = StoryBeat(
            beat_id=beat_id, start_sec=start, end_sec=end,
            dramatic_question=f"Q{i}", change=f"C{i}", visual_event=f"V{i}",
            motif="black square STAMP", setup_or_payoff="development" if i else "setup",
        )
        beats.append(beat)
        shots.append(ShotSpec(
            shot_id=f"{beat_id}-S01", beat_id=beat_id, start_sec=start, end_sec=end,
            narrative_function="stress", subject="YOSUMI",
            action="one controlled action", environment="MARGIN CITY",
            composition="readable", camera=CameraSpec(framing="medium", movement="locked", movement_strength="locked"),
            lighting="matte", emotional_note="controlled",
            series_episode_id=episode_id, series_entity_ids=["YOSUMI"],
        ))
    session.story_beats = beats
    session.shots = shots
    return session


def test_g9_stress_200_shots_contract_pack_roundtrip_and_1000_queue_jobs(tmp_path):
    session = _stress_session(tmp_path, 200)
    packs = []
    hashes = []
    for index, shot in enumerate(session.shots):
        contract = compile_shot_continuity_contract(session, shot)
        hashes.append(contract.contract_hash)
        packs.append(compile_manual_pack(
            session, shot,
            pack_id=f"PACK-{index:04d}",
            created_at=f"2026-10-08T00:{index//60:02d}:{index%60:02d}+00:00",
        ))
    session.generation_packs = packs
    assert len(set(hashes)) == 200
    assert all(pack.continuity_contract_hash for pack in packs)

    fingerprint = production_state_fingerprint(session)
    for _ in range(10):
        session = LyricsWorldSession.from_dict(session.to_dict(tmp_path), project_dir=tmp_path)
        assert production_state_fingerprint(session) == fingerprint

    report = build_production_readiness(session)
    assert len(report.shots) == 200
    assert all(not state.stale_pack for state in report.shots)

    queue = GenerationQueue()
    for i in range(1000):
        queue.add(f"S{i:04d}", f"P{i:04d}", "MANUAL")
    assert queue.counts()["PENDING"] == 1000
    for job in queue.jobs[:250]:
        queue.start(job.job_id)
        queue.complete(job.job_id)
    assert queue.counts()["DONE"] == 250
    assert queue.counts()["PENDING"] == 750


def test_g9_ui_contract_at_1100x720(tmp_path, monkeypatch):
    monkeypatch.setenv("MVSTUDIO_APPDATA", str(tmp_path / "appdata"))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(1100, 720)
    main_report = validate_main_window_contract(window)
    assert main_report.passed, main_report.findings

    dialog = ProductionControlDialog(lambda: window.session, lambda: None, window)
    dialog.resize(1100, 720)
    production_report = validate_production_dialog_contract(dialog)
    assert production_report.passed, production_report.findings

    # Exercise each existing page switch and refresh after G9 integration.
    for index in range(window.pages.count()):
        window._switch(index)
        app.processEvents()
    window._refresh_from_session()
    dialog.refresh()
    app.processEvents()

    dialog.close()
    window.close()
    app.processEvents()
