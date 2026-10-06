from __future__ import annotations

import json
import importlib.machinery
import os
import subprocess
import sys
import types
from pathlib import Path

import cv2
import numpy as np
import pytest

from mvstudio.director_intelligence import (
    DirectorImportError, apply_director_proposal, build_director_intelligence_prompt,
    import_director_result,
)
from mvstudio.manual_generation import compile_manual_pack
from mvstudio.models import (
    AudioMap, AudioTransition, CameraSpec, LyricLine, ReferenceAsset, ReferenceRole,
    ReferenceScope, ShotSpec,
)
from mvstudio.music_intelligence import (
    BeatThisBackend, EnhancedMusicStructure, FunctionalStructureBackend,
    MusicStructureSegment, analyze_music_intelligence, fuse_music_structure_timeline,
    get_music_backend, normalize_section_label,
)
from mvstudio.optional_backends import clear_backend_load_failure, openclip_availability
from mvstudio.result_takes import GenerationTake
from mvstudio.semantic_qc import (
    adjacent_visual_findings, analyze_visual_semantic, eligible_visual_references,
    palette_drift_score,
)
from mvstudio.session import LyricsWorldSession


def _shot(shot_id="B001-S01", start=0, narrative="setup", environment="station"):
    return ShotSpec(
        shot_id=shot_id, beat_id="B001", start_sec=start, end_sec=start + 2,
        narrative_function=narrative, subject="person", action="walk", environment=environment,
        composition="center", camera=CameraSpec(framing="medium", movement="locked"),
        lighting="soft", emotional_note="quiet", continuity_in=["red ticket"], continuity_out=["red ticket"],
    )


def _video(path: Path, colors: list[tuple[int, int, int]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (80, 60))
    assert writer.isOpened()
    for color in colors:
        for _ in range(10):
            writer.write(np.full((60, 80, 3), color, dtype=np.uint8))
    writer.release()
    return path


def _take(path: Path, take_id: str, shot_id: str, status="accepted", pack_id=None):
    return GenerationTake(
        take_id=take_id, shot_id=shot_id, pack_id=pack_id, output_path=str(path),
        created_at="2026-01-01", imported_at="2026-01-01", status=status,
        original_filename=path.name,
    )


def _director_payload():
    concept = {
        "concept_id": "AI-W1", "title": "Memory Station", "interpretation_mode": "hybrid",
        "one_line": "Rain reveals memory", "world_rule": "rain reflects memory", "emotional_engine": "departure",
        "recurring_motifs": ["ticket"], "visual_language": ["restrained"], "ending_image": "ticket floats",
        "lyric_evidence": ["L001"], "lyric_relevance_score": 95,
    }
    beat = {
        "beat_id": "AI-B001", "start_sec": 0, "end_sec": 5, "dramatic_question": "leave?",
        "change": "accepts departure", "visual_event": "ticket released", "motif": "ticket",
        "setup_or_payoff": "setup", "lyric_line_ids": ["L001"],
    }
    return {
        "result_id": "DIR-1", "created_at": "2026-01-01", "source_label": "Manual AI", "language": "ko",
        "synopsis": "A departure", "pov": "first_person", "central_conflict": "stay or leave",
        "emotional_arc": ["waiting", "release"],
        "narrative_thesis": {"text": "leaving preserves memory", "lyric_line_ids": ["L001"]},
        "recurring_motifs": [{"text": "ticket", "lyric_line_ids": ["L001"]}],
        "motif_progression": [{"motif": "ticket", "phase": "setup", "description": "held", "lyric_line_ids": ["L001"]}],
        "section_interpretations": [{"section": "verse", "interpretation": "waiting", "lyric_line_ids": ["L001"]}],
        "world_concepts": [concept], "story_beat_suggestions": [beat],
        "ending_image": {"text": "ticket floats", "lyric_line_ids": ["L001"]},
        "lyric_evidence_map": {"ending": ["L001"]}, "warnings": [], "schema_version": "1.0",
    }


def test_optional_openclip_and_no_pack_are_safe(tmp_path):
    state = openclip_availability()
    assert state.state in {"AVAILABLE", "NOT_INSTALLED", "LOAD_FAILED"}
    shot = _shot()
    video = _video(tmp_path / "한글 日本語 clip.mp4", [(20, 30, 40), (25, 35, 45)])
    take = _take(video, "T1", shot.shot_id)
    session = LyricsWorldSession(shots=[shot], generation_takes=[take], project_dir=tmp_path)
    report = analyze_visual_semantic(session, take)
    finding = next(item for item in report.findings if item.finding_id == "semantic_optional")
    assert finding.status == "N/A"


def test_reference_scope_eligibility_and_palette_drift(tmp_path):
    shot = _shot()
    image = tmp_path / "ref.png"; cv2.imwrite(str(image), np.full((20, 20, 3), 100, dtype=np.uint8))
    refs = [
        ReferenceAsset(reference_id="P", role=ReferenceRole.COLOR_LIGHT, path=str(image), applies_to=ReferenceScope.PROJECT),
        ReferenceAsset(reference_id="S", role=ReferenceRole.CHARACTER_MASTER, path=str(image), applies_to=ReferenceScope.SHOT, scope_id=shot.shot_id),
        ReferenceAsset(reference_id="X", role=ReferenceRole.LOCATION_MASTER, path=str(image), applies_to=ReferenceScope.SHOT, scope_id="OTHER"),
        ReferenceAsset(reference_id="C", role=ReferenceRole.COMPOSITION, path=str(image), applies_to=ReferenceScope.PROJECT),
    ]
    session = LyricsWorldSession(shots=[shot], references=refs, project_dir=tmp_path)
    assert {item.reference_id for item in eligible_visual_references(session, shot)} == {"P", "S"}
    stable = _video(tmp_path / "stable.mp4", [(0, 0, 255)] * 3)
    drift = _video(tmp_path / "drift.mp4", [(0, 0, 255), (0, 255, 0), (255, 0, 0)])
    assert palette_drift_score(drift) > palette_drift_score(stable)


def test_adjacent_continuity_accepted_only_and_redundancy_never_rejects(tmp_path):
    shots = [_shot("S1", 0, "setup"), _shot("S2", 2, "middle"), _shot("S3", 4, "payoff")]
    same_a = _video(tmp_path / "a.mp4", [(60, 70, 80)] * 2)
    ignored = _video(tmp_path / "ignored.mp4", [(0, 0, 255)] * 2)
    same_b = _video(tmp_path / "b.mp4", [(60, 70, 80)] * 2)
    takes = [_take(same_a, "T1", "S1"), _take(ignored, "T2", "S2", "candidate"), _take(same_b, "T3", "S3")]
    session = LyricsWorldSession(shots=shots, generation_takes=takes, project_dir=tmp_path)
    findings = adjacent_visual_findings(session)
    assert any(item.finding_id.startswith("redundancy:S1:S3") for item in findings)
    assert all("S2" not in item.finding_id for item in findings)
    assert [take.status for take in takes] == ["accepted", "candidate", "accepted"]


def test_director_prompt_import_validation_and_no_automatic_overwrite(tmp_path):
    lines = [LyricLine(line_id="L001", text="붉은 표를 놓는다", start_sec=0, end_sec=5)]
    session = LyricsWorldSession(lines=lines, shots=[_shot()], story_beats=[])
    before = (session.world_bible, list(session.story_beats), list(session.shots))
    prompt = build_director_intelligence_prompt(lines, None)
    assert "L001" in prompt and "Return JSON only" in prompt
    result = import_director_result(json.dumps(_director_payload(), ensure_ascii=False), {"L001"})
    session.director_intelligence_results.append(result)
    assert (session.world_bible, session.story_beats, session.shots) == before
    bad = _director_payload(); bad["ending_image"]["lyric_line_ids"] = ["UNKNOWN"]
    with pytest.raises(DirectorImportError, match="UNKNOWN"):
        import_director_result(bad, {"L001"})
    duplicate = _director_payload(); duplicate["story_beat_suggestions"].append(dict(duplicate["story_beat_suggestions"][0]))
    with pytest.raises(DirectorImportError, match="중복"):
        import_director_result(duplicate, {"L001"})


def test_director_selective_apply_preserves_unselected_domains():
    session = LyricsWorldSession(lines=[LyricLine(line_id="L001", text="line")], shots=[_shot()])
    result = import_director_result(_director_payload(), {"L001"})
    shots = list(session.shots)
    apply_director_proposal(session, result, "interpretation")
    assert session.analysis.synopsis == "A departure" and session.shots == shots
    apply_director_proposal(session, result, "world_concepts")
    assert session.concepts[0].concept_id == "AI-W1" and session.shots == shots
    apply_director_proposal(session, result, "story_beats")
    assert session.story_beats[0].beat_id == "AI-B001" and session.shots == shots


def test_music_optional_fallback_structure_fusion_and_no_beat_explosion(tmp_path):
    audio = AudioMap(
        source_path=str(tmp_path / "song.wav"), duration_sec=20, sample_rate=22050, tempo_bpm=120,
        beat_times_sec=[x * 0.5 for x in range(40)],
        transitions=[AudioTransition(transition_id="AT1", time_sec=5, strength=.8, character="energy_rise")],
    )
    Path(audio.source_path).write_bytes(b"placeholder")
    fallback = analyze_music_intelligence(audio.source_path, "BEAT_THIS", audio_map=audio)
    assert fallback.backend == "LIBROSA_BASIC" and fallback.warnings
    structure = EnhancedMusicStructure(
        backend="TEST_FUNCTIONAL", tempo_bpm=120, beats=audio.beat_times_sec, downbeats=[0, 2, 4],
        segments=[
            MusicStructureSegment(segment_id="S1", label="verse", start_sec=0, end_sec=5, confidence=.8, source_backend="TEST"),
            MusicStructureSegment(segment_id="S2", label="chorus", start_sec=5, end_sec=10, confidence=.9, source_backend="TEST"),
            MusicStructureSegment(segment_id="S3", label="chorus", start_sec=10, end_sec=15, confidence=.9, source_backend="TEST"),
            MusicStructureSegment(segment_id="S4", label="outro", start_sec=15, end_sec=20, confidence=.8, source_backend="TEST"),
        ],
    )
    lines = [LyricLine(line_id="L1", text="return", start_sec=4.5, end_sec=5.5)]
    cues = fuse_music_structure_timeline(audio, lines, None, structure)
    assert any("functional_section=chorus" in cue.reasons for cue in cues)
    assert len(cues) <= len(audio.transitions) + len(structure.segments) + 2
    assert len(cues) < len(audio.beat_times_sec)


def test_schema_09_roundtrip_and_08_backward_compatibility(tmp_path):
    result = import_director_result(_director_payload(), {"L001"})
    structure = EnhancedMusicStructure(backend="TEST", tempo_bpm=100)
    session = LyricsWorldSession(
        lines=[LyricLine(line_id="L001", text="line")], director_intelligence_results=[result],
        enhanced_music_structure=structure,
    )
    path = tmp_path / "통합 세션 日本語.json"
    session.export(path)
    restored = LyricsWorldSession.import_file(path)
    assert restored.to_dict()["schema_version"] == "1.0"
    assert restored.director_intelligence_results[0].result_id == "DIR-1"
    assert restored.enhanced_music_structure.backend == "TEST"
    old = LyricsWorldSession.from_dict({"schema_version": "0.8"})
    assert old.director_intelligence_results == [] and old.enhanced_music_structure is None


def test_megagate_beginner_ui_hides_backend_details(tmp_path):
    from PySide6.QtWidgets import QApplication
    from mvstudio.ui_app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    page = window.technical_qc_page
    assert page.question.text() == "이 영상은 사용해도 될까요?"
    assert page.expert_text.isHidden()
    assert page.director_copy.minimumHeight() >= 44 and page.music_basic.minimumHeight() >= 44
    assert "API 없이도" in page.api_notice.text()
    assert any(text in page.music_backend_status.text() for text in (
        "사용 가능", "설치되어 있지 않습니다", "불러오지 못했습니다",
    ))
    window.close()


def _fake_package(monkeypatch, name, **attributes):
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    for key, value in attributes.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _audio_map(path: Path):
    return AudioMap(source_path=str(path), duration_sec=4, sample_rate=22050, tempo_bpm=100)


def test_builtin_beat_this_adapter_selection_and_normalization(tmp_path, monkeypatch):
    source = tmp_path / "beat source.wav"; source.write_bytes(b"audio")
    checkpoint = tmp_path / "manual model.ckpt"; checkpoint.write_bytes(b"weights")
    calls = []

    class File2Beats:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def __call__(self, path):
            return [0.5, 1.0, 1.5], [0.5, 1.5]

    package = _fake_package(monkeypatch, "beat_this", __version__="fake-1")
    package.__path__ = []
    _fake_package(monkeypatch, "beat_this.inference", File2Beats=File2Beats)
    clear_backend_load_failure("BEAT_THIS")
    result = analyze_music_intelligence(
        source, "BEAT_THIS", audio_map=_audio_map(source),
        backend_options={"checkpoint_path": str(checkpoint)},
    )
    assert isinstance(get_music_backend("BEAT_THIS", options={"checkpoint_path": checkpoint}), BeatThisBackend)
    assert result.backend == "BEAT_THIS"
    assert result.beats == [0.5, 1.0, 1.5] and result.downbeats == [0.5, 1.5]
    assert result.tempo_bpm == 120 and result.backend_version
    assert calls == [{"checkpoint_path": str(checkpoint.resolve()), "device": "cpu", "float16": False}]


def test_builtin_functional_adapter_and_label_normalization(tmp_path, monkeypatch):
    source = tmp_path / "structure 日本語.wav"; source.write_bytes(b"audio")
    calls = []

    def analyze(path, device=None):
        calls.append((path, device))
        return {
            "bpm": 98, "beats": [0.6, 1.2], "downbeats": [0.6],
            "segments": [
                {"start": 0, "end": 2, "label": "Introduction", "confidence": .8},
                {"start": 2, "end": 3, "label": "Pre-Chorus 2"},
                {"start": 3, "end": 4, "label": "Instrumental Solo"},
            ],
        }

    _fake_package(monkeypatch, "allin1", analyze=analyze, __version__="fake-2")
    clear_backend_load_failure("FUNCTIONAL_STRUCTURE")
    result = analyze_music_intelligence(
        source, "FUNCTIONAL_STRUCTURE", audio_map=_audio_map(source),
        backend_options={"allow_model_load": True},
    )
    assert isinstance(get_music_backend("FUNCTIONAL_STRUCTURE", options={"allow_model_load": True}), FunctionalStructureBackend)
    assert result.backend == "FUNCTIONAL_STRUCTURE" and result.backend_version
    assert [segment.label for segment in result.segments] == ["intro", "pre_chorus", "other"]
    assert normalize_section_label("FINAL CHORUS") == "chorus"
    assert calls == [(str(source.resolve()), "cpu")]


def test_builtin_api_mismatch_gracefully_falls_back_without_download(tmp_path, monkeypatch):
    source = tmp_path / "fallback.wav"; source.write_bytes(b"audio")
    checkpoint = tmp_path / "local.ckpt"; checkpoint.write_bytes(b"local only")
    package = _fake_package(monkeypatch, "beat_this", __version__="broken")
    package.__path__ = []
    _fake_package(monkeypatch, "beat_this.inference", UnexpectedAPI=object)
    clear_backend_load_failure("BEAT_THIS")
    result = analyze_music_intelligence(
        source, "BEAT_THIS", audio_map=_audio_map(source),
        backend_options={"checkpoint_path": checkpoint},
    )
    assert result.backend == "LIBROSA_BASIC"
    assert any("불러오지 못했습니다" in warning for warning in result.warnings)
    assert checkpoint.read_bytes() == b"local only"


def test_app_startup_does_not_import_heavy_music_backends():
    code = (
        "import sys; import mvstudio.ui_app; "
        "assert 'beat_this' not in sys.modules; assert 'allin1' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=Path.cwd(), capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")},
    )
    assert completed.returncode == 0, completed.stderr


def test_existing_music_adapter_injection_is_preserved(tmp_path):
    source = tmp_path / "injected.wav"; source.write_bytes(b"audio")

    class Injected:
        backend_id = "INJECTED"
        version = "test"
        def analyze(self, path):
            return EnhancedMusicStructure(backend=self.backend_id, backend_version=self.version, beats=[1.0])

    result = analyze_music_intelligence(source, "BEAT_THIS", adapter=Injected())
    assert result.backend == "INJECTED" and result.beats == [1.0]
