from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from pydantic import ValidationError

from .lyrics_engine import (
    analyze_lyrics,
    build_director_llm_prompt,
    build_lyric_visual_bridges,
    generate_world_concepts,
    parse_lyrics_text,
)
from .models import (
    AudioMap, LyricInterpretation, LyricLine, LyricVisualBridge, MVTimelineCue,
    ReferenceAsset, ReferenceRole, ShotSpec, StoryBeat, WorldBible, WorldConcept,
)
from .manual_generation import ManualGenerationPack
from .result_takes import (
    GenerationTake, TakeManager, portable_take_path, reconcile_take_counters,
    resolve_take_path,
)
from .reference_vault import ReferenceVault, portable_path, resolve_reference_path
from .world_bible import promote_world_concept
from .technical_qc import TakeQCReport
from .semantic_qc import SemanticQCReport
from .director_intelligence import DirectorIntelligenceResult
from .music_intelligence import EnhancedMusicStructure
from .editor import EditTimeline, RenderRecord, RenderSettings
from .release_runtime import backup_session, configure_logging


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
    story_beats: list[StoryBeat] = field(default_factory=list)
    shots: list[ShotSpec] = field(default_factory=list)
    generation_packs: list[ManualGenerationPack] = field(default_factory=list)
    generation_takes: list[GenerationTake] = field(default_factory=list)
    take_id_counters: dict[str, int] = field(default_factory=dict)
    qc_reports: list[TakeQCReport] = field(default_factory=list)
    semantic_qc_reports: list[SemanticQCReport] = field(default_factory=list)
    director_intelligence_results: list[DirectorIntelligenceResult] = field(default_factory=list)
    enhanced_music_structure: EnhancedMusicStructure | None = None
    edit_timeline: EditTimeline | None = None
    render_settings: RenderSettings = field(default_factory=RenderSettings)
    render_records: list[RenderRecord] = field(default_factory=list)
    preview_path: str = ""
    final_path: str = ""
    project_dir: Path | None = None
    session_path: Path | None = None

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

    def promote_selected_concept(self, fill_missing_only: bool = False) -> WorldBible:
        if not self.selected_concept:
            raise ValueError("먼저 World Lab에서 세계관을 선택하세요.")
        generated = promote_world_concept(self.selected_concept, self.analysis, self.audio_map)
        if fill_missing_only and self.world_bible is not None:
            updates = {}
            for key in WorldBible.model_fields:
                if key == "source_concept_id":
                    continue
                current = getattr(self.world_bible, key)
                if not current:
                    updates[key] = getattr(generated, key)
            updates["source_concept_id"] = generated.source_concept_id
            self.world_bible = self.world_bible.model_copy(update=updates)
        else:
            self.world_bible = generated
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

    @property
    def take_manager(self) -> TakeManager:
        return TakeManager(
            self.generation_takes, self.shots, self.generation_packs,
            self.project_dir, self.take_id_counters,
        )

    def to_dict(self, project_dir: str | Path | None = None) -> dict:
        target_dir = Path(project_dir).resolve(strict=False) if project_dir else self.project_dir
        references = []
        for asset in self.references:
            data = asset.model_dump(mode="json")
            resolved = resolve_reference_path(asset, self.project_dir)
            data["path"] = portable_path(resolved, target_dir)
            references.append(data)
        takes = []
        for take in self.generation_takes:
            data = take.model_dump(mode="json")
            data["output_path"] = portable_take_path(resolve_take_path(take, self.project_dir), target_dir)
            takes.append(data)
        return {
            "schema_version": "1.0",
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
            "story_beats": [beat.model_dump(mode="json") for beat in self.story_beats],
            "shots": [shot.model_dump(mode="json") for shot in self.shots],
            "generation_packs": [pack.model_dump(mode="json") for pack in self.generation_packs],
            "generation_takes": takes,
            "take_id_counters": dict(self.take_id_counters),
            "qc_reports": [report.model_dump(mode="json") for report in self.qc_reports],
            "semantic_qc_reports": [report.model_dump(mode="json") for report in self.semantic_qc_reports],
            "director_intelligence_results": [result.model_dump(mode="json") for result in self.director_intelligence_results],
            "enhanced_music_structure": self.enhanced_music_structure.model_dump(mode="json") if self.enhanced_music_structure else None,
            "edit_timeline": self.edit_timeline.model_dump(mode="json") if self.edit_timeline else None,
            "render_settings": self.render_settings.model_dump(mode="json"),
            "render_records": [record.model_dump(mode="json") for record in self.render_records],
            "preview_path": self.preview_path,
            "final_path": self.final_path,
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
            story_beats=[StoryBeat.model_validate(x) for x in data.get("story_beats", [])],
            shots=[ShotSpec.model_validate(x) for x in data.get("shots", [])],
            generation_packs=[ManualGenerationPack.model_validate(x) for x in data.get("generation_packs", [])],
            generation_takes=[GenerationTake.model_validate(x) for x in data.get("generation_takes", [])],
            take_id_counters={str(key): int(value) for key, value in data.get("take_id_counters", {}).items()},
            qc_reports=[TakeQCReport.model_validate(x) for x in data.get("qc_reports", [])],
            semantic_qc_reports=[SemanticQCReport.model_validate(x) for x in data.get("semantic_qc_reports", [])],
            director_intelligence_results=[DirectorIntelligenceResult.model_validate(x) for x in data.get("director_intelligence_results", [])],
            enhanced_music_structure=EnhancedMusicStructure.model_validate(data["enhanced_music_structure"]) if data.get("enhanced_music_structure") else None,
            edit_timeline=EditTimeline.model_validate(data["edit_timeline"]) if data.get("edit_timeline") else None,
            render_settings=RenderSettings.model_validate(data.get("render_settings", {})),
            render_records=[RenderRecord.model_validate(x) for x in data.get("render_records", [])],
            preview_path=data.get("preview_path", ""),
            final_path=data.get("final_path", ""),
            project_dir=Path(project_dir).resolve(strict=False) if project_dir else None,
        )
        reconcile_take_counters(session.generation_takes, session.take_id_counters)
        ReferenceVault(session.references, session.project_dir)
        return session

    @classmethod
    def import_file(cls, path: str | Path) -> "LyricsWorldSession":
        path = Path(path).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ValueError(f"세션 파일이 아닙니다: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError("세션 JSON의 최상위 값은 객체여야 합니다.")
            session = cls.from_dict(data, project_dir=path.parent)
        except (json.JSONDecodeError, UnicodeError, ValidationError, TypeError, AttributeError) as exc:
            raise ValueError(f"세션 JSON이 손상되었거나 형식이 올바르지 않습니다: {exc}") from exc
        session.session_path = path
        return session

    def export(self, path: str | Path | None = None) -> Path:
        path = Path(path or self.session_path).expanduser().resolve(strict=False) if (path or self.session_path) else None
        if path is None:
            raise ValueError("저장할 세션 JSON 경로를 지정하세요.")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(path.parent), ensure_ascii=False, indent=2).encode("utf-8")
        temp_path: Path | None = None
        try:
            backup_session(path)
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(payload)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, path)
        except Exception:
            configure_logging().exception("session save failed: %s", path)
            raise
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
        self.project_dir = path.parent.resolve(strict=False)
        self.session_path = path
        return path
