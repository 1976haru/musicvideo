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


def test_fifth_verdict_seed_has_five_episodes_and_required_registry():
    bible, entities = seed_the_fifth_verdict()
    assert bible.title == "THE FIFTH VERDICT"
    assert len(bible.episode_titles) == len(bible.episodes) == 5
    assert {e.entity_id for e in entities} == {
        "YOSUMI", "SUZUGARA", "TOJI", "THE_ARCHIVE", "HOLLOW",
        "STAMP", "GWAN_SYMBOL", "MARGIN_CITY_LOCATIONS",
    }
    locked = {"YOSUMI", "SUZUGARA", "TOJI", "THE_ARCHIVE", "HOLLOW"}
    assert all(e.shape_grammar.lock_strength == 1.0 and e.text_master for e in entities if e.entity_id in locked)
    assert all(e.shape_grammar.locked_parts for e in entities if e.entity_id in locked)


def test_series_session_round_trip_preserves_schema_1_0():
    session = LyricsWorldSession()
    session.initialize_series()
    payload = session.to_dict()
    assert payload["schema_version"] == "1.0"
    restored = LyricsWorldSession.from_dict(payload)
    assert restored.series_bible.title == "THE FIFTH VERDICT"
    assert len(restored.series_entities) == 8
    # Old sessions remain valid and do not acquire seed data implicitly.
    old = LyricsWorldSession.from_dict({"schema_version": "1.0"})
    assert old.series_bible is None and old.series_entities == []


def test_episode_action_emotion_variants_layer_without_weakening_shape_lock():
    _, entities = seed_the_fifth_verdict()
    yosumi = next(e for e in entities if e.entity_id == "YOSUMI")
    yosumi.variants.extend([
        EntityVariant(variant_id="Y_ACTION_RUN", kind="action", trigger="run", appearance_delta=["coat trails behind"], motion_delta=["controlled sprint"]),
        EntityVariant(variant_id="Y_EMOTION_GRIEF", kind="emotional", trigger="grief", appearance_delta=["lowered chin"]),
    ])
    resolved = resolve_entity_variant(yosumi, "EP5", action="run", emotion="grief")
    assert resolved.applied_variant_ids == ["YOSUMI_EP5", "Y_ACTION_RUN", "Y_EMOTION_GRIEF"]
    assert resolved.shape_grammar == yosumi.shape_grammar
    assert resolved.shape_grammar.lock_strength == 1.0
    assert "four-corner coat" in resolved.shape_grammar.locked_parts


def test_reference_director_and_asset_factory_cover_all_pack_types():
    bible, entities = seed_the_fifth_verdict()
    yosumi = next(e for e in entities if e.entity_id == "YOSUMI")
    yosumi.variants.extend([
        EntityVariant(variant_id="Y_ACTION", kind="action", trigger="stamp", episode_id="EP1"),
        EntityVariant(variant_id="Y_EMOTION", kind="emotional", trigger="doubt", episode_id="EP2"),
    ])
    slots = suggest_reference_slots(bible, entities, [])
    packs = build_asset_prompt_packs(bible, entities, slots)
    roles = {pack.kind for pack in packs}
    assert {"character_sheet", "action_keyart", "emotion_keyart", "environment_keyart", "prop_master", "color_script"}.issubset(roles)
    yosumi_pack = next(p for p in packs if "YOSUMI" in p.pack_id)
    assert "four-corner coat" in yosumi_pack.prompt
    assert "rounded hem" in yosumi_pack.negative_prompt


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
    snapshots = [
        EpisodeContinuitySnapshot(episode_id="EP1", motifs=["margin line"], clues_set_up=[], entities=[
            EntityContinuityState(entity_id="YOSUMI", shape_tokens=["single red cuff"], colors=["hot pink"], prop_states={"STAMP": "intact"}, detected_forbidden=["cape"]),
        ]),
        EpisodeContinuitySnapshot(episode_id="EP5", motifs=["margin line"], payoffs=[], entities=[
            EntityContinuityState(entity_id="YOSUMI", shape_tokens=["four-corner coat", "single red cuff"], colors=["ink black"], prop_states={"STAMP": "broken"}),
        ]),
    ]
    report = run_series_continuity_qc(bible, entities, snapshots)
    categories = {finding.category for finding in report.findings}
    assert not report.passed
    assert {"character_shape", "color", "prop", "forbidden", "clue_payoff"}.issubset(categories)


def test_episode_graph_tracks_clue_payoff_edges():
    bible, _ = seed_the_fifth_verdict()
    graph = build_episode_graph(bible)
    assert [n.node_id for n in graph.nodes] == ["EP1", "EP2", "EP3", "EP4", "EP5"]
    assert {(e.source, e.target) for e in graph.edges} == {("EP1", "EP5"), ("EP2", "EP4")}


def test_series_studio_ui_exposes_beginner_flow_and_seed_entities():
    app = QApplication.instance() or QApplication([])
    session = LyricsWorldSession()
    session.initialize_series()
    dialog = SeriesStudioDialog(session)
    assert dialog.FLOW == ("Series", "Episode", "Character", "Assets", "Continuity", "Episode Graph")
    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == list(dialog.FLOW)
    assert dialog.entity_select.count() == 8
    assert dialog.episode_select.count() == 5
    assert dialog.findChild(QPushButton, "loadSeriesSeed") is not None
    assert "EP1" in dialog.graph_output.toPlainText() and "EP5" in dialog.graph_output.toPlainText()
    dialog.close()
    app.processEvents()
