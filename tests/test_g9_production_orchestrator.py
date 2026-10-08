from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from mvstudio.editor import MediaInfo
from mvstudio.manual_generation import ManualGenerationPack, compile_manual_pack
from mvstudio.models import AudioMap, CameraSpec, ShotSpec, StoryBeat
from mvstudio.production_orchestrator import (
    ComfyUIBridge,
    GenerationQueue,
    audit_creative_coverage,
    build_generation_queue,
    build_production_readiness,
    compile_shot_continuity_contract,
    extract_comfyui_output_files,
    materialize_comfyui_workflow,
    production_state_fingerprint,
    verify_final_render,
)
from mvstudio.session import LyricsWorldSession


def _base_session(tmp_path: Path) -> LyricsWorldSession:
    tmp_path.mkdir(parents=True, exist_ok=True)
    session = LyricsWorldSession(project_dir=tmp_path)
    music = tmp_path / "05 - 寒くないって笑った.wav"
    music.write_bytes(b"synthetic-audio-placeholder")
    session.music_path = str(music)
    session.audio_map = AudioMap(
        source_path=str(music),
        duration_sec=20.0,
        sample_rate=44100,
        tempo_bpm=92.0,
        beat_times_sec=[0.5, 1.2, 1.9],
    )
    session.duration_sec = 20.0
    session.lyrics_text = "夜明けの海で\n寒くないって笑った\n風の中で少し近づいた"
    session.source_name = "05_寒くないって笑った.txt"
    session.analyze()
    session.rebuild_mv_timeline()
    session.promote_selected_concept()
    session.initialize_series()

    beat = StoryBeat(
        beat_id="B001", start_sec=0.0, end_sec=5.0,
        dramatic_question="Will YOSUMI protect without deciding guilt?",
        change="hesitation becomes protection",
        visual_event="YOSUMI opens the white left palm",
        motif="open palm", setup_or_payoff="setup",
        lyric_line_ids=[session.lines[0].line_id],
        emotional_state="protective realization",
    )
    shot = ShotSpec(
        shot_id="B001-S01", beat_id="B001", start_sec=0.0, end_sec=5.0,
        narrative_function="protective realization",
        lyric_line_ids=list(beat.lyric_line_ids),
        lyric_intent="hesitation becomes protection",
        subject="YOSUMI", action="opens the white left palm",
        environment="MARGIN CITY folded alley",
        composition="readable full body",
        camera=CameraSpec(framing="full body", lens="50mm", angle="eye-level", movement="subtle push-in"),
        lighting="dark teal matte light",
        emotional_note="protective realization",
        continuity_in=["three ribbons separate", "chest hollow visible"],
        continuity_out=["white left palm open"],
        series_episode_id="EP1",
        series_entity_ids=["YOSUMI"],
        series_variant_ids=["YOSUMI_PROTECTIVE_REALIZATION"],
    )
    session.story_beats = [beat]
    session.shots = [shot]
    return session


def test_continuity_contract_is_stable_and_tracks_identity_changes(tmp_path):
    session = _base_session(tmp_path)
    shot = session.shots[0]
    first = compile_shot_continuity_contract(session, shot)
    second = compile_shot_continuity_contract(session, shot)
    assert first.contract_hash == second.contract_hash
    assert "three black ink ribbons" in first.prompt_block
    assert "rectangular hollow" in first.prompt_block
    assert "left hand" in first.prompt_block.casefold()

    yosumi = next(entity for entity in session.series_entities if entity.entity_id == "YOSUMI")
    yosumi.shape_grammar.locked_parts.append("new deliberate test lock")
    changed = compile_shot_continuity_contract(session, shot)
    assert changed.contract_hash != first.contract_hash
    assert "new deliberate test lock" in changed.prompt_block


def test_generation_pack_binds_contract_and_readiness_detects_stale_pack(tmp_path):
    session = _base_session(tmp_path)
    shot = session.shots[0]
    pack = compile_manual_pack(session, shot, pack_id="PACK-G9", created_at="2026-10-08T00:00:00+00:00")
    session.generation_packs = [pack]
    assert pack.continuity_contract_id == "CONTRACT-B001-S01"
    assert pack.continuity_contract_hash
    assert pack.continuity_contract_block in pack.main_prompt

    report = build_production_readiness(session)
    state = report.shots[0]
    assert state.pack_id == "PACK-G9"
    assert state.pack_ready
    assert not state.stale_pack

    yosumi = next(entity for entity in session.series_entities if entity.entity_id == "YOSUMI")
    yosumi.shape_grammar.forbidden_mutations.append("test forbidden mutation")
    report2 = build_production_readiness(session)
    state2 = report2.shots[0]
    assert state2.stale_pack
    assert any(issue.code == "STALE_PROMPT_PACK" for issue in state2.issues)


def test_old_generation_pack_schema_still_loads_without_contract_fields(tmp_path):
    session = _base_session(tmp_path)
    pack = compile_manual_pack(session, session.shots[0], pack_id="PACK-OLD", created_at="old")
    payload = pack.model_dump(mode="json")
    payload.pop("continuity_contract_id")
    payload.pop("continuity_contract_hash")
    payload.pop("continuity_contract_block")
    restored = ManualGenerationPack.model_validate(payload)
    assert restored.continuity_contract_hash == ""
    session.generation_packs = [restored]
    report = build_production_readiness(session)
    assert report.shots[0].stale_pack


def test_generation_queue_is_deduplicated_stateful_and_persistent(tmp_path):
    session = _base_session(tmp_path)
    pack = compile_manual_pack(session, session.shots[0], pack_id="PACK-Q", created_at="q")
    session.generation_packs = [pack]
    queue = GenerationQueue(session.generation_jobs)
    jobs = build_generation_queue(session, queue, "COMFYUI_LOCAL")
    assert len(jobs) == 1
    assert build_generation_queue(session, queue, "COMFYUI_LOCAL")[0].job_id == jobs[0].job_id
    job = queue.start(jobs[0].job_id, "prompt-1")
    assert job.status == "RUNNING" and job.attempts == 1
    queue.fail(job.job_id, "temporary")
    assert queue.requeue(job.job_id).status == "PENDING"
    queue.start(job.job_id, "prompt-2")
    queue.complete(job.job_id, ["output/test.mp4"])
    assert queue.counts()["DONE"] == 1
    with pytest.raises(ValueError):
        queue.cancel(job.job_id)

    target = tmp_path / "queue_session.json"
    session.export(target)
    reopened = LyricsWorldSession.import_file(target)
    assert len(reopened.generation_jobs) == 1
    assert reopened.generation_jobs[0].status == "DONE"
    assert reopened.generation_jobs[0].provider_job_id == "prompt-2"
    assert reopened.generation_jobs[0].output_paths == ["output/test.mp4"]


def test_comfyui_workflow_materialization_and_local_endpoint_safety(tmp_path):
    session = _base_session(tmp_path)
    pack = compile_manual_pack(session, session.shots[0], pack_id="PACK-C", created_at="c")
    template = {
        "1": {"inputs": {"text": "{{MV_MAIN_PROMPT}}"}},
        "2": {"inputs": {"negative": "{{MV_NEGATIVE_PROMPT}}", "prefix": "{{MV_OUTPUT_PREFIX}}"}},
        "3": {"inputs": {"shot": "{{MV_SHOT_ID}}", "duration": "{{MV_DURATION}}"}},
    }
    template["4"] = {"inputs": {"image": "{{MV_REFERENCE_1}}", "second": "{{MV_REFERENCE_2}}"}}
    result = materialize_comfyui_workflow(
        template, pack, reference_names=["mvstudio/ref1.png", "mvstudio/ref2.png"]
    )
    assert "{{MV_" not in str(result)
    assert "YOSUMI" in result["1"]["inputs"]["text"]
    assert result["3"]["inputs"]["shot"] == "B001-S01"
    assert "B001-S01" in result["2"]["inputs"]["prefix"]
    assert result["4"]["inputs"]["image"] == "mvstudio/ref1.png"
    assert result["4"]["inputs"]["second"] == "mvstudio/ref2.png"

    bridge = ComfyUIBridge("http://example.com:8188")
    status = bridge.status()
    assert status.state == "INVALID_ENDPOINT"

    payload = {
        "abc": {
            "outputs": {
                "10": {
                    "images": [{"filename": "shot.png", "subfolder": "mvstudio"}],
                    "videos": [{"filename": "shot.mp4", "subfolder": "mvstudio"}],
                }
            }
        }
    }
    assert extract_comfyui_output_files(payload, "abc") == [
        "mvstudio/shot.png", "mvstudio/shot.mp4"
    ]


def test_production_state_fingerprint_roundtrip_and_change_detection(tmp_path):
    session = _base_session(tmp_path)
    pack = compile_manual_pack(session, session.shots[0], pack_id="PACK-F", created_at="f")
    session.generation_packs = [pack]
    first = production_state_fingerprint(session)
    restored = LyricsWorldSession.from_dict(session.to_dict(tmp_path), project_dir=tmp_path)
    assert production_state_fingerprint(restored) == first
    restored.shots[0].action = "different action"
    assert production_state_fingerprint(restored) != first


def test_final_render_verification_checks_delivery_contract(tmp_path, monkeypatch):
    session = _base_session(tmp_path)
    final = tmp_path / "final.mp4"
    final.write_bytes(b"fake")
    session.final_path = str(final)

    monkeypatch.setattr(
        "mvstudio.editor.probe_media",
        lambda path: MediaInfo(
            path=str(path), duration_sec=20.0,
            width=session.render_settings.width, height=session.render_settings.height,
            fps=session.render_settings.fps, codec="h264", has_audio=True, backend="test",
        ),
    )
    monkeypatch.setattr("mvstudio.production_orchestrator._sample_render_health", lambda path: (0.0, 0.0))
    monkeypatch.setattr("mvstudio.production_orchestrator._scene_cut_count", lambda path: 0)
    report = verify_final_render(session)
    assert report.status == "PASS"
    assert report.duration_sec == 20.0

    monkeypatch.setattr(
        "mvstudio.editor.probe_media",
        lambda path: MediaInfo(
            path=str(path), duration_sec=18.0,
            width=1280, height=720, fps=24, codec="h264", has_audio=False, backend="test",
        ),
    )
    failed = verify_final_render(session)
    assert failed.status == "FAIL"
    codes = {finding.code for finding in failed.findings}
    assert {"DURATION_MISMATCH", "NO_AUDIO", "OUTPUT_SIZE_MISMATCH"}.issubset(codes)



def test_comfyui_upload_image_uses_local_official_route(tmp_path, monkeypatch):
    image = tmp_path / "YOSUMI 日本語.png"
    image.write_bytes(b"png-bytes")
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return b'{"name":"YOSUMI.png","subfolder":"mvstudio","type":"input"}'

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["content_type"] = request.headers.get("Content-type") or request.headers.get("Content-Type")
        captured["body"] = request.data
        return Response()

    monkeypatch.setattr("mvstudio.production_orchestrator.urllib.request.urlopen", fake_urlopen)
    bridge = ComfyUIBridge("http://127.0.0.1:8188")
    returned = bridge.upload_image(image)
    assert captured["url"].endswith("/upload/image")
    assert "multipart/form-data" in captured["content_type"]
    assert b"png-bytes" in captured["body"]
    assert b'name="type"' in captured["body"]
    assert b"input" in captured["body"]
    assert returned == "mvstudio/YOSUMI.png"



def test_episode_specific_approved_assets_do_not_leak_to_other_shots(tmp_path):
    from mvstudio.series_studio import SeriesAsset

    session = _base_session(tmp_path)
    ep1 = tmp_path / "ep1.png"
    ep1.write_bytes(b"ep1")
    session.series_assets.append(SeriesAsset(
        asset_id="ASSET_EP1",
        path=str(ep1),
        role="character_sheet",
        entity_id="YOSUMI",
        episode_id="EP1",
        review_status="approved",
    ))

    shot_ep1 = session.shots[0]
    assert "ASSET_EP1" in compile_shot_continuity_contract(session, shot_ep1).series_asset_ids

    shot_ep2 = shot_ep1.model_copy(update={"shot_id": "B001-S02", "series_episode_id": "EP2"})
    assert "ASSET_EP1" not in compile_shot_continuity_contract(session, shot_ep2).series_asset_ids

    shot_no_ep = shot_ep1.model_copy(update={"shot_id": "B001-S03", "series_episode_id": None})
    assert "ASSET_EP1" not in compile_shot_continuity_contract(session, shot_no_ep).series_asset_ids


def test_director_coverage_warns_without_auto_rewriting_creative_choices(tmp_path):
    session = _base_session(tmp_path)
    base = session.shots[0]
    session.shots = [
        base.model_copy(update={
            "shot_id": f"B001-S{i+1:02d}",
            "start_sec": i * 0.5,
            "end_sec": (i + 1) * 0.5,
            "action": "same repeated protective action",
            "lyric_line_ids": [],
            "series_episode_id": None,
            "series_entity_ids": [],
            "lyric_visual_strategy": "literal",
        })
        for i in range(8)
    ]
    before = [shot.model_dump(mode="json") for shot in session.shots]
    report = audit_creative_coverage(session)
    codes = {finding.code for finding in report.findings}
    assert "LOW_LYRIC_EVIDENCE_COVERAGE" in codes
    assert "LOW_SERIES_CONTEXT_COVERAGE" in codes
    assert "LOW_VISUAL_STRATEGY_VARIETY" in codes
    assert "REPEATED_ACTION_RUN" in codes
    assert "VERY_FAST_SHOT_RHYTHM" in codes
    assert [shot.model_dump(mode="json") for shot in session.shots] == before



def test_continuity_contract_hash_does_not_depend_on_project_root(tmp_path):
    project_a = tmp_path / "project_a"
    project_a.mkdir(parents=True, exist_ok=True)
    session = _base_session(project_a)
    shot = session.shots[0]
    first = compile_shot_continuity_contract(session, shot)

    # Move the logical project root without changing creative IDs/rules. Absolute path
    # transport details must not invalidate every Prompt Pack.
    session.project_dir = tmp_path / "project_b"
    session.project_dir.mkdir(parents=True, exist_ok=True)
    second = compile_shot_continuity_contract(session, shot)
    assert first.contract_hash == second.contract_hash
