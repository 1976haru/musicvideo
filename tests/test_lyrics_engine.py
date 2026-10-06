from pathlib import Path
from mvstudio.lyrics_engine import parse_lyrics, analyze_lyrics, generate_world_concepts, build_lyric_visual_bridges, build_director_llm_prompt
from mvstudio.models import MusicVideoProject
from mvstudio.qc import evaluate_project

ROOT = Path(__file__).resolve().parents[1]


def test_txt_lyrics_pack():
    lines = parse_lyrics(ROOT / "examples" / "lyrics_original_ja.txt", song_duration=180)
    assert len(lines) == 12
    assert lines[0].start_sec == 0
    assert lines[-1].end_sec == 180
    analysis = analyze_lyrics(lines)
    assert analysis.language_hint == "ja"
    assert len(analysis.anchors) > 0
    concepts = generate_world_concepts(analysis, lines)
    assert len(concepts) == 3
    assert concepts[0].interpretation_mode == "hybrid"
    assert concepts[0].lyric_relevance_score >= 90
    bridges = build_lyric_visual_bridges(lines, analysis.repeated_phrases)
    assert len(bridges) == 12
    assert all(x.source_line_ids for x in bridges)
    prompt = build_director_llm_prompt(lines, analysis)
    assert "line IDs" in prompt


def test_lyrics_project_qc():
    project = MusicVideoProject.model_validate_json(
        (ROOT / "examples" / "project.lyrics.example.json").read_text(encoding="utf-8")
    )
    qc = evaluate_project(project)
    assert qc.lyric_grounding >= 14
    assert qc.score >= 80
