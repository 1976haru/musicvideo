from __future__ import annotations

import json
from pathlib import Path
import typer
from rich import print

from .models import MusicVideoProject
from .prompt_compiler import compile_shot
from .qc import evaluate_project
from .lyrics_engine import (
    parse_lyrics,
    analyze_lyrics,
    generate_world_concepts,
    build_lyric_visual_bridges,
    build_director_llm_prompt,
)
from .music_engine import analyze_audio, build_mv_timeline, format_timeline_text

app = typer.Typer(help="MV Director Studio 1.0.1 — Music + Lyrics Director Timeline")


def load_project(path: Path) -> MusicVideoProject:
    return MusicVideoProject.model_validate_json(path.read_text(encoding="utf-8"))


@app.command()
def demo():
    print("[bold]MV Director Studio 1.0.0[/bold]")
    print("Music + Lyrics → director timeline → world concepts → shots → provider prompts.")
    print("Try: mvstudio music-pack song.wav")
    print("Try: mvstudio timeline-pack song.wav --lyrics lyrics.srt")


@app.command("music-pack")
def music_pack(
    audio_file: Path,
    out_dir: Path = typer.Option(Path("music_pack")),
):
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_map = analyze_audio(audio_file)
    (out_dir / "01_audio_map.json").write_text(audio_map.model_dump_json(indent=2), encoding="utf-8")
    print(f"[green]Music Pack created[/green] → {out_dir}")
    print(
        f"duration={audio_map.duration_sec:.1f}s tempo={audio_map.tempo_bpm:.1f} "
        f"beats={len(audio_map.beat_times_sec)} transitions={len(audio_map.transitions)}"
    )


@app.command("timeline-pack")
def timeline_pack(
    audio_file: Path,
    lyrics: Path | None = typer.Option(None, help="Optional TXT/SRT/LRC lyrics."),
    out_dir: Path = typer.Option(Path("mv_timeline_pack")),
):
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_map = analyze_audio(audio_file)
    lines = []
    analysis = None
    if lyrics:
        lines = parse_lyrics(lyrics, song_duration=audio_map.duration_sec)
        analysis = analyze_lyrics(lines)
    cues = build_mv_timeline(audio_map, lines, analysis)
    (out_dir / "01_audio_map.json").write_text(audio_map.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / "02_mv_timeline.json").write_text(
        json.dumps([x.model_dump() for x in cues], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "03_mv_timeline.txt").write_text(format_timeline_text(cues), encoding="utf-8")
    print(f"[green]MV Timeline Pack created[/green] → {out_dir}")
    print(f"timeline_cues={len(cues)} lyrics_lines={len(lines)}")


@app.command("lyrics-pack")
def lyrics_pack(
    lyrics_file: Path,
    duration: float | None = typer.Option(None, help="Song duration in seconds; useful for plain TXT."),
    out_dir: Path = typer.Option(Path("lyrics_pack")),
):
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = parse_lyrics(lyrics_file, song_duration=duration)
    analysis = analyze_lyrics(lines)
    concepts = generate_world_concepts(analysis, lines)
    bridges = build_lyric_visual_bridges(lines, analysis.repeated_phrases)
    llm_prompt = build_director_llm_prompt(lines, analysis)
    (out_dir / "01_lyric_lines.json").write_text(
        json.dumps([x.model_dump() for x in lines], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "02_interpretation.json").write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / "03_world_concepts.json").write_text(
        json.dumps([x.model_dump() for x in concepts], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "04_lyric_visual_bridges.json").write_text(
        json.dumps([x.model_dump() for x in bridges], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "05_director_llm_prompt.txt").write_text(llm_prompt, encoding="utf-8")
    print(f"[green]Lyrics Pack created[/green] → {out_dir}")
    print(f"lines={len(lines)} anchors={len(analysis.anchors)} world_concepts={len(concepts)} bridges={len(bridges)}")


@app.command("qc")
def qc_cmd(project_file: Path):
    project = load_project(project_file)
    print(json.dumps(evaluate_project(project).as_dict(), ensure_ascii=False, indent=2))


@app.command("compile")
def compile_cmd(
    project_file: Path,
    provider: str = typer.Option("generic"),
    out_dir: Path = typer.Option(Path("generation_packs")),
):
    project = load_project(project_file)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for shot in project.shots:
        pack = compile_shot(project, shot, provider)
        target = out_dir / f"{shot.shot_id}_{provider}.json"
        target.write_text(json.dumps(pack.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.append(target.name)
    (out_dir / "manifest.json").write_text(
        json.dumps({"project": project.title, "provider": provider, "files": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[green]Created {len(manifest)} generation packs[/green] → {out_dir}")


if __name__ == "__main__":
    app()
