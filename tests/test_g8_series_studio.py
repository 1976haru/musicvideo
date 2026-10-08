from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from mvstudio.g8_ui import SeriesStudioDialog
from mvstudio.manual_generation import compile_manual_pack
from mvstudio.models import CameraSpec, ShotSpec, StoryBeat
from mvstudio.series_studio import (
    DownloadWatcher, EntityContinuityState, EntityVariant,
    EpisodeContinuitySnapshot, SeriesAsset, build_asset_prompt_packs, build_episode_graph,
    resolve_entity_variant, run_series_continuity_qc, seed_the_fifth_verdict,
    suggest_reference_slots,
)
from mvstudio.session import LyricsWorldSession


EXPECTED_TITLES = [
    "MUTE BELL",
    "DOORLESS ROAD",
    "SILENT WITNESS",
    "MUTINY OF THE UNWRITTEN",
    "GWAN: THE UNWRITTEN VERDICT",
]


def _entity(entities, entity_id):
    return next(entity for entity in entities if entity.entity_id == entity_id)


def test_fifth_verdict_seed_matches_final_project_bible():
    bible, entities = seed_the_fifth_verdict()
    assert bible.title == "THE FIFTH VERDICT"
    assert bible.episode_titles == EXPECTED_TITLES
    assert [ep.title for ep in sorted(bible.episodes, key=lambda ep: ep.order)] == EXPECTED_TITLES
    assert len(bible.common_world_rules) == 7
    assert "deep ink navy #162432" in bible.color_system["base"]
    assert "dark teal #0B7D80" in bible.color_system["base"]
    assert "aged paper #E9E5DA" in bible.color_system["base"]
    assert {e.entity_id for e in entities} == {
        "YOSUMI", "SUZUGARA", "TOJI", "THE_ARCHIVE", "HOLLOW",
        "STAMP", "GWAN_SYMBOL", "MARGIN_CITY_LOCATIONS",
    }


def test_required_shape_grammar_locks_match_final_bible():
    _, entities = seed_the_fifth_verdict()

    yosumi = _entity(entities, "YOSUMI")
    assert yosumi.shape_grammar.lock_strength == 1.0
    assert yosumi.shape_grammar.locked_parts == [
        "three black ink ribbons",
        "centered rectangular hollow chest",
        "matte white left hand only",
    ]
    assert "EXACTLY THREE" in yosumi.text_master
    assert "ONLY the anatomical LEFT hand" in yosumi.text_master
    assert "fourth ribbon" in yosumi.shape_grammar.forbidden_mutations

    suzugara = _entity(entities, "SUZUGARA")
    assert "no clapper" in suzugara.shape_grammar.locked_parts
    assert "two short legs" in suzugara.shape_grammar.locked_parts

    toji = _entity(entities, "TOJI")
    assert "two facing closed brackets" in toji.shape_grammar.locked_parts
    assert "single golden gap" in toji.shape_grammar.locked_parts

    archive = _entity(entities, "THE_ARCHIVE")
    assert archive.entity_type == "system"
    assert "rotating window-frame system" in archive.shape_grammar.locked_parts
    assert "black square STAMP interface" in archive.shape_grammar.locked_parts

    hollow = _entity(entities, "HOLLOW")
    assert "hollow-centered geometric bodies" in hollow.shape_grammar.locked_parts
    assert "shared ring motif" in hollow.shape_grammar.locked_parts


def test_series_session_round_trip_preserves_schema_1_0():
    session = LyricsWorldSession()
    session.initialize_series()
    payload = session.to_dict()
    assert payload["schema_version"] == "1.0"
    restored = LyricsWorldSession.from_dict(payload)
    assert restored.series_bible.title == "THE FIFTH VERDICT"
    assert restored.series_bible.episode_titles == EXPECTED_TITLES
    assert len(restored.series_entities) == 8
    old = LyricsWorldSession.from_dict({"schema_version": "1.0"})
    assert old.series_bible is None and old.series_entities == []


def test_episode_action_emotion_variants_layer_without_weakening_shape_lock():
    _, entities = seed_the_fifth_verdict()
    yosumi = _entity(entities, "YOSUMI")
    yosumi.variants.extend([
        EntityVariant(
            variant_id="Y_ACTION_INTERCEPT", kind="action", trigger="intercept",
            appearance_delta=["topology unchanged"], motion_delta=["controlled interception"],
        ),
        EntityVariant(
            variant_id="Y_EMOTION_RESOLVE", kind="emotional", trigger="resolve",
            appearance_delta=["open protective posture"],
        ),
    ])
    resolved = resolve_entity_variant(yosumi, "EP5", action="intercept", emotion="resolve")
    assert resolved.applied_variant_ids == [
        "YOSUMI_EP5_GWAN", "Y_ACTION_INTERCEPT", "Y_EMOTION_RESOLVE"
    ]
    assert resolved.shape_grammar == yosumi.shape_grammar
    assert resolved.shape_grammar.lock_strength == 1.0
    assert "three black ink ribbons" in resolved.shape_grammar.locked_parts
    assert "centered rectangular hollow chest" in resolved.shape_grammar.locked_parts
    assert "matte white left hand only" in resolved.shape_grammar.locked_parts


def test_reference_director_and_asset_factory_preserve_real_yosumi_identity():
    bible, entities = seed_the_fifth_verdict()
    yosumi = _entity(entities, "YOSUMI")
    yosumi.variants.extend([
        EntityVariant(variant_id="Y_ACTION", kind="action", trigger="intercept", episode_id="EP1"),
        EntityVariant(variant_id="Y_EMOTION", kind="emotional", trigger="protective realization", episode_id="EP1"),
    ])
    slots = suggest_reference_slots(bible, entities, [])
    packs = build_asset_prompt_packs(bible, entities, slots)
    roles = {pack.kind for pack in packs}
    assert {
        "character_sheet", "action_keyart", "emotion_keyart",
        "environment_keyart", "prop_master", "color_script",
    }.issubset(roles)

    yosumi_pack = next(pack for pack in packs if "YOSUMI" in pack.pack_id)
    assert "EXACTLY THREE" in yosumi_pack.prompt
    assert "rectangular" in yosumi_pack.prompt
    assert "LEFT hand" in yosumi_pack.prompt
    assert "fourth ribbon" in yosumi_pack.negative_prompt
    assert "realistic fingers" in yosumi_pack.negative_prompt


def test_download_watcher_auto_ingest_is_non_destructive(tmp_path):
    _, entities = seed_the_fifth_verdict()
    watcher = DownloadWatcher(tmp_path)
    image = tmp_path / "YOSUMI__EP2__action_keyart__日本語.png"
    original = b"not-a-real-image-but-a-downloaded-file"
    image.write_bytes(original)
    detected = watcher.detect_new()
    assets = []
    added = watcher.ingest(detected, entities, assets)
    assert len(added) == 1
    assert added[0].entity_id == "YOSUMI"
    assert added[0].episode_id == "EP2"
    assert added[0].role == "action_keyart"
    assert image.read_bytes() == original
    assert watcher.ingest([image], entities, assets) == []


def test_series_continuity_qc_detects_shape_color_prop_forbidden_and_clue_drift():
    bible, entities = seed_the_fifth_verdict()
    yosumi = _entity(entities, "YOSUMI")
    snapshots = [
        EpisodeContinuitySnapshot(
            episode_id="EP1",
            motifs=["black square STAMP"],
            clues_set_up=[],
            entities=[
                EntityContinuityState(
                    entity_id="YOSUMI",
                    shape_tokens=["matte white left hand only"],
                    colors=["hot pink"],
                    prop_states={"STAMP": "intact"},
                    detected_forbidden=["fourth ribbon"],
                ),
            ],
        ),
        EpisodeContinuitySnapshot(
            episode_id="EP5",
            motifs=["black square STAMP"],
            payoffs=[],
            entities=[
                EntityContinuityState(
                    entity_id="YOSUMI",
                    shape_tokens=list(yosumi.shape_grammar.locked_parts),
                    colors=["deep ink navy #162432"],
                    prop_states={"STAMP": "broken"},
                ),
            ],
        ),
    ]
    report = run_series_continuity_qc(bible, entities, snapshots)
    categories = {finding.category for finding in report.findings}
    assert not report.passed
    assert {
        "character_shape", "color", "prop", "forbidden", "clue_payoff"
    }.issubset(categories)


def test_episode_graph_tracks_final_bible_clue_payoff_chains():
    bible, _ = seed_the_fifth_verdict()
    graph = build_episode_graph(bible)
    assert [node.node_id for node in graph.nodes] == ["EP1", "EP2", "EP3", "EP4", "EP5"]
    assert [node.label for node in graph.nodes] == EXPECTED_TITLES
    chain_ids = {edge.chain_id for edge in graph.edges}
    assert chain_ids == {
        "CHAIN_BELL_SILENCE",
        "CHAIN_STAMP_CAUSALITY",
        "CHAIN_LULLABY_MEMORY",
        "CHAIN_TOJI_ALLY",
        "CHAIN_GWAN_NAME",
        "CHAIN_DOORLESS_PATH",
    }
    assert sum(edge.source == "EP1" and edge.target == "EP5" for edge in graph.edges) == 3
    assert any(edge.source == "EP4" and edge.target == "EP5" for edge in graph.edges)


def test_series_studio_ui_exposes_beginner_flow_and_final_seed():
    app = QApplication.instance() or QApplication([])
    session = LyricsWorldSession()
    session.initialize_series()
    dialog = SeriesStudioDialog(session)
    assert dialog.FLOW == ("Series", "Episode", "Character", "Assets", "Continuity", "Episode Graph")
    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == list(dialog.FLOW)
    assert dialog.entity_select.count() == 8
    assert dialog.episode_select.count() == 5
    assert dialog.findChild(QPushButton, "loadSeriesSeed") is not None
    assert "MUTE BELL" in dialog.graph_output.toPlainText()
    assert "GWAN: THE UNWRITTEN VERDICT" in dialog.graph_output.toPlainText()
    dialog.close()
    app.processEvents()



def test_shot_to_generate_injects_series_hard_locks_and_approved_assets(tmp_path):
    session = LyricsWorldSession(project_dir=tmp_path)
    session.initialize_series()

    keyart = tmp_path / "YOSUMI_EP1_character_sheet.png"
    keyart.write_bytes(b"approved-reference")
    session.series_assets.append(
        SeriesAsset(
            asset_id="ASSET_YOSUMI_MASTER",
            path=str(keyart),
            role="character_sheet",
            entity_id="YOSUMI",
            episode_id=None,
            source="manual",
            review_status="approved",
        )
    )
    beat = StoryBeat(
        beat_id="B001", start_sec=0, end_sec=5,
        dramatic_question="Is the silent bell dangerous?",
        change="YOSUMI hesitates before striking",
        visual_event="YOSUMI faces SUZUGARA",
    )
    shot = ShotSpec(
        shot_id="B001-S01", beat_id="B001", start_sec=0, end_sec=5,
        narrative_function="protective realization",
        subject="YOSUMI", action="opens the white left palm instead of striking",
        environment="Margin City folded alley", composition="three-quarter full body",
        camera=CameraSpec(framing="full body", movement="subtle push-in"),
        lighting="matte teal haze", emotional_note="protective realization",
        series_episode_id="EP1",
        series_entity_ids=["YOSUMI"],
        series_variant_ids=["YOSUMI_PROTECTIVE_REALIZATION"],
    )
    session.story_beats = [beat]
    session.shots = [shot]

    pack = compile_manual_pack(
        session, shot, "GENERIC_MANUAL",
        pack_id="PACK-TEST", created_at="test",
    )

    assert pack.series_episode_id == "EP1"
    assert pack.series_entity_ids == ["YOSUMI"]
    assert "YOSUMI_PROTECTIVE_REALIZATION" in pack.series_variant_ids
    assert "EXACTLY THREE" in pack.main_prompt
    assert "centered rectangular" in pack.main_prompt
    assert "LEFT hand" in pack.main_prompt
    assert "fourth ribbon" in pack.negative_prompt
    assert pack.series_asset_ids == ["ASSET_YOSUMI_MASTER"]
    assert str(keyart.resolve()) in pack.series_asset_paths
    assert any("three black ink ribbons" in item for item in pack.continuity_summary)


def test_character_registry_ui_edits_real_hard_locks_and_asset_review(tmp_path):
    app = QApplication.instance() or QApplication([])
    session = LyricsWorldSession(project_dir=tmp_path)
    session.initialize_series()
    dialog = SeriesStudioDialog(session)

    yosumi_index = dialog.entity_select.findData("YOSUMI")
    dialog.entity_select.setCurrentIndex(yosumi_index)
    dialog._load_entity()
    assert "three black ink ribbons" in dialog.entity_locked_parts.toPlainText()
    assert "fourth ribbon" in dialog.entity_forbidden_mutations.toPlainText()

    dialog.entity_locked_parts.setPlainText(
        "three black ink ribbons\ncentered rectangular hollow chest\nmatte white left hand only"
    )
    dialog._apply_entity()
    yosumi = _entity(session.series_entities, "YOSUMI")
    assert yosumi.shape_grammar.locked_parts == [
        "three black ink ribbons",
        "centered rectangular hollow chest",
        "matte white left hand only",
    ]

    image = tmp_path / "YOSUMI__EP1__character_sheet.png"
    image.write_bytes(b"asset")
    asset = SeriesAsset(
        asset_id="ASSET_UI",
        path=str(image),
        role="character_sheet",
        entity_id="YOSUMI",
        episode_id="EP1",
        review_status="candidate",
    )
    session.series_assets.append(asset)
    dialog._refresh_assets("ASSET_UI")
    dialog._set_asset_status("approved")
    assert asset.review_status == "approved"
    assert image.read_bytes() == b"asset"

    dialog.close()
    app.processEvents()


def test_series_asset_path_is_portable_and_resolves_after_session_reopen(tmp_path):
    project = tmp_path / "portable series project"
    assets_dir = project / "assets"
    assets_dir.mkdir(parents=True)
    image = assets_dir / "YOSUMI EP1 approved.png"
    image.write_bytes(b"portable-approved-reference")

    session = LyricsWorldSession(project_dir=project)
    session.initialize_series()
    session.series_assets.append(SeriesAsset(
        asset_id="ASSET_PORTABLE",
        path=str(image),
        role="character_sheet",
        entity_id="YOSUMI",
        episode_id="EP1",
        review_status="approved",
    ))
    target = project / "series_session.json"
    session.export(target)

    reopened = LyricsWorldSession.import_file(target)
    assert reopened.series_assets[0].path == "assets/YOSUMI EP1 approved.png"

    shot = ShotSpec(
        shot_id="PORTABLE-S01", start_sec=0, end_sec=5,
        narrative_function="portable reference validation",
        subject="YOSUMI", action="protects the silent bell",
        environment="Margin City", composition="full body",
        camera=CameraSpec(framing="full body"), lighting="dark teal",
        emotional_note="protective realization", series_episode_id="EP1",
        series_entity_ids=["YOSUMI"],
        series_variant_ids=["YOSUMI_PROTECTIVE_REALIZATION"],
    )
    pack = compile_manual_pack(reopened, shot, pack_id="PACK-PORTABLE", created_at="test")
    assert pack.series_asset_ids == ["ASSET_PORTABLE"]
    assert pack.series_asset_paths == [str(image.resolve())]
