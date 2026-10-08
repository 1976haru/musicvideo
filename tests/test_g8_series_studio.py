from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from mvstudio.g8_ui import SeriesStudioDialog
from mvstudio.series_studio import (
    DownloadWatcher, EntityContinuityState, EntityVariant,
    EpisodeContinuitySnapshot, build_asset_prompt_packs, build_episode_graph,
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
