from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .lyrics_engine import (
    analyze_lyrics,
    build_director_llm_prompt,
    build_lyric_visual_bridges,
    generate_world_concepts,
    parse_lyrics_text,
)
from .models import (
    AudioMap, LyricInterpretation, LyricLine, LyricVisualBridge, MVTimelineCue,
    ReferenceAsset, ReferenceRole, WorldBible, WorldConcept,
)
from .reference_vault import ReferenceVault, portable_path, resolve_reference_path
from .world_bible import promote_world_concept


@dataclass
class LyricsWorldSession:
    music_path: str = ""
    audio_map: AudioMap | None = None
    mv_timeline: list[MVTimelineCue] = field(default_factory=list)
    lyrics_text: str = ""
    source_name: str = "pasted_lyrics.txt"
    duration_sec: float | None = None
    lines: list[LyricLine] = field(default_factory=list)
    analysis: LyricInterpretation | None = None
    concepts: list[WorldConcept] = field(default_factory=list)
    bridges: list[LyricVisualBridge] = field(default_factory=list)
    selected_concept_id: str | None = None
    world_bible: WorldBible | None = None
    references: list[ReferenceAsset] = field(default_factory=list)
    project_dir: Path | None = None

    def analyze(self, suffix: str | None = None) -> None:
        if not self.lyrics_text.strip():
            raise ValueError("가사를 입력하거나 파일을 불러오세요.")
        if suffix is None:
            suffix = Path(self.source_name).suffix or ".txt"
        self.lines = parse_lyrics_text(self.lyrics_text, suffix=suffix, song_duration=self.duration_sec)
        if not self.lines:
            raise ValueError("분석 가능한 가사 행을 찾지 못했습니다.")
        self.analysis = analyze_lyrics(self.lines)
        self.concepts = generate_world_concepts(self.analysis, self.lines)
        self.bridges = build_lyric_visual_bridges(self.lines, self.analysis.repeated_phrases)
        self.selected_concept_id = self.concepts[0].concept_id if self.concepts else None


    def analyze_music(self, music_path: str | Path | None = None) -> None:
        from .music_engine import analyze_audio, build_mv_timeline

        if music_path is not None:
            self.music_path = str(music_path)
        if not self.music_path:
            raise ValueError("음악 파일을 먼저 선택하세요.")
        self.audio_map = analyze_audio(self.music_path)
        # If plain TXT lyrics were analyzed with a guessed duration, real audio duration wins.
        if self.lyrics_text.strip() and (self.duration_sec is None or abs(self.duration_sec - self.audio_map.duration_sec) > 0.25):
            self.duration_sec = self.audio_map.duration_sec
            self.analyze()
        if self.lines:
            self.mv_timeline = build_mv_timeline(self.audio_map, self.lines, self.analysis)
        else:
            self.mv_timeline = build_mv_timeline(self.audio_map, [], None)

    def rebuild_mv_timeline(self) -> None:
        if not self.audio_map:
            self.mv_timeline = []
            return
        from .music_engine import build_mv_timeline
        self.mv_timeline = build_mv_timeline(self.audio_map, self.lines, self.analysis)

    def select_concept(self, concept_id: str) -> None:
        if concept_id not in {c.concept_id for c in self.concepts}:
            raise ValueError(f"Unknown concept_id: {concept_id}")
        self.selected_concept_id = concept_id

    def promote_selected_concept(self) -> WorldBible:
        if not self.selected_concept:
            raise ValueError("먼저 World Lab에서 세계관을 선택하세요.")
        self.world_bible = promote_world_concept(self.selected_concept)
        return self.world_bible

    @property
    def reference_vault(self) -> ReferenceVault:
        return ReferenceVault(self.references, self.project_dir)

    def add_reference(self, source: str | Path, role: ReferenceRole = ReferenceRole.COMPOSITION, **kwargs) -> ReferenceAsset:
        return self.reference_vault.add(source, role, **kwargs)

    def remove_reference(self, reference_id: str) -> ReferenceAsset:
        return self.reference_vault.remove(reference_id)

    @property
    def selected_concept(self) -> WorldConcept | None:
        return next((c for c in self.concepts if c.concept_id == self.selected_concept_id), None)

    def to_dict(self, project_dir: str | Path | None = None) -> dict:
        target_dir = Path(project_dir).resolve(strict=False) if project_dir else self.project_dir
        references = []
        for asset in self.references:
            data = asset.model_dump(mode="json")
            resolved = resolve_reference_path(asset, self.project_dir)
            data["path"] = portable_path(resolved, target_dir)
            references.append(data)
        return {
            "schema_version": "0.4",
            "music_path": self.music_path,
            "audio_map": self.audio_map.model_dump() if self.audio_map else None,
            "mv_timeline": [x.model_dump() for x in self.mv_timeline],
            "source_name": self.source_name,
            "duration_sec": self.duration_sec,
            "lyrics_text": self.lyrics_text,
            "lyric_lines": [x.model_dump() for x in self.lines],
            "lyric_interpretation": self.analysis.model_dump() if self.analysis else None,
            "world_concepts": [x.model_dump() for x in self.concepts],
            "lyric_visual_bridges": [x.model_dump() for x in self.bridges],
            "selected_concept_id": self.selected_concept_id,
            "world_bible": self.world_bible.model_dump() if self.world_bible else None,
            "references": references,
            "director_llm_prompt": build_director_llm_prompt(self.lines, self.analysis) if self.analysis and self.lines else "",
        }

    @classmethod
    def from_dict(cls, data: dict, project_dir: str | Path | None = None) -> "LyricsWorldSession":
        session = cls(
            music_path=data.get("music_path", ""),
            audio_map=AudioMap.model_validate(data["audio_map"]) if data.get("audio_map") else None,
            mv_timeline=[MVTimelineCue.model_validate(x) for x in data.get("mv_timeline", [])],
            lyrics_text=data.get("lyrics_text", ""),
            source_name=data.get("source_name", "pasted_lyrics.txt"),
            duration_sec=data.get("duration_sec"),
            lines=[LyricLine.model_validate(x) for x in data.get("lyric_lines", [])],
            analysis=LyricInterpretation.model_validate(data["lyric_interpretation"]) if data.get("lyric_interpretation") else None,
            concepts=[WorldConcept.model_validate(x) for x in data.get("world_concepts", [])],
            bridges=[LyricVisualBridge.model_validate(x) for x in data.get("lyric_visual_bridges", [])],
            selected_concept_id=data.get("selected_concept_id"),
            world_bible=WorldBible.model_validate(data["world_bible"]) if data.get("world_bible") else None,
            references=[ReferenceAsset.model_validate(x) for x in data.get("references", [])],
            project_dir=Path(project_dir).resolve(strict=False) if project_dir else None,
        )
        ReferenceVault(session.references, session.project_dir)
        return session

    @classmethod
    def import_file(cls, path: str | Path) -> "LyricsWorldSession":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return cls.from_dict(data, project_dir=path.parent)

    def export(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(path.parent), ensure_ascii=False, indent=2), encoding="utf-8")
        self.project_dir = path.parent.resolve(strict=False)
        return path
