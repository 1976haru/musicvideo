from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .models import LyricInterpretation, StoryBeat, WorldConcept


class EvidenceClaim(BaseModel):
    text: str
    lyric_line_ids: list[str] = Field(default_factory=list)


class MotifProgression(BaseModel):
    motif: str
    phase: Literal["setup", "development", "payoff"]
    description: str
    lyric_line_ids: list[str] = Field(default_factory=list)


class SectionInterpretation(BaseModel):
    section: str
    interpretation: str
    lyric_line_ids: list[str] = Field(default_factory=list)


class DirectorIntelligenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    created_at: str
    source_label: str
    language: str
    synopsis: str
    pov: str
    central_conflict: str
    emotional_arc: list[str] = Field(default_factory=list)
    narrative_thesis: EvidenceClaim
    recurring_motifs: list[EvidenceClaim] = Field(default_factory=list)
    motif_progression: list[MotifProgression] = Field(default_factory=list)
    section_interpretations: list[SectionInterpretation] = Field(default_factory=list)
    world_concepts: list[WorldConcept] = Field(default_factory=list)
    story_beat_suggestions: list[StoryBeat] = Field(default_factory=list)
    ending_image: EvidenceClaim
    lyric_evidence_map: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    schema_version: Literal["1.0"] = "1.0"


class DirectorImportError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def build_director_intelligence_prompt(lines, current_analysis: LyricInterpretation | None = None) -> str:
    lyric_rows = "\n".join(
        f"{line.line_id} [{line.start_sec}-{line.end_sec}] {line.text}" for line in lines
    )
    current = current_analysis.model_dump(mode="json") if current_analysis else None
    return (
        "You are a music-video director. Return JSON only. Do not invent lyric line IDs.\n"
        "Treat this as a proposal; never claim that it has already changed the project.\n"
        "Every motif, world concept, ending image, and story beat must cite lyric_line_ids.\n"
        "Allowed interpretation_mode: literal, metaphoric, hybrid, counterpoint.\n"
        "Allowed setup_or_payoff: setup, development, payoff, none.\n"
        "Top-level fields: result_id, created_at, source_label, language, synopsis, pov, "
        "central_conflict, emotional_arc, narrative_thesis{text,lyric_line_ids}, "
        "recurring_motifs[{text,lyric_line_ids}], motif_progression[{motif,phase,description,lyric_line_ids}], "
        "section_interpretations[{section,interpretation,lyric_line_ids}], world_concepts, "
        "story_beat_suggestions, ending_image{text,lyric_line_ids}, lyric_evidence_map, warnings, schema_version='1.0'.\n"
        f"CURRENT DETERMINISTIC ANALYSIS:\n{json.dumps(current, ensure_ascii=False)}\n"
        f"LYRICS WITH AUTHORITATIVE IDS:\n{lyric_rows}"
    )


def import_director_result(payload: str | bytes | dict[str, Any], valid_line_ids: set[str]) -> DirectorIntelligenceResult:
    try:
        data = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise DirectorImportError([f"JSON을 읽을 수 없습니다: {exc}"]) from exc
    if not isinstance(data, dict):
        raise DirectorImportError(["JSON 최상위 값은 객체여야 합니다."])
    try:
        result = DirectorIntelligenceResult.model_validate(data)
    except ValidationError as exc:
        raise DirectorImportError([error["msg"] for error in exc.errors()]) from exc

    issues: list[str] = []
    evidence_sets = [result.narrative_thesis.lyric_line_ids, result.ending_image.lyric_line_ids]
    evidence_sets += [item.lyric_line_ids for item in result.recurring_motifs]
    evidence_sets += [item.lyric_line_ids for item in result.motif_progression]
    evidence_sets += [item.lyric_line_ids for item in result.section_interpretations]
    evidence_sets += [item.lyric_evidence for item in result.world_concepts]
    evidence_sets += [item.lyric_line_ids for item in result.story_beat_suggestions]
    evidence_sets += list(result.lyric_evidence_map.values())
    unknown = sorted({line_id for group in evidence_sets for line_id in group if line_id not in valid_line_ids})
    if unknown:
        issues.append("존재하지 않는 lyric line ID: " + ", ".join(unknown))
    beat_ids = [beat.beat_id for beat in result.story_beat_suggestions]
    duplicates = sorted({beat_id for beat_id in beat_ids if beat_ids.count(beat_id) > 1})
    if duplicates:
        issues.append("중복 Story Beat ID: " + ", ".join(duplicates))
    if any(not motif.lyric_line_ids for motif in result.recurring_motifs):
        issues.append("주요 모티프에는 lyric evidence가 필요합니다.")
    if any(not concept.lyric_evidence for concept in result.world_concepts):
        issues.append("World Concept에는 lyric evidence가 필요합니다.")
    if not result.ending_image.lyric_line_ids:
        issues.append("결말 이미지에는 lyric evidence가 필요합니다.")
    if issues:
        raise DirectorImportError(issues)
    return result


def new_result_id() -> str:
    return "DIR-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def compare_with_current(result: DirectorIntelligenceResult, current: LyricInterpretation | None) -> list[str]:
    if current is None:
        return ["현재 기본 분석이 없어 AI 감독 제안만 표시합니다."]
    rows = []
    for label, before, after in (
        ("Synopsis", current.synopsis, result.synopsis),
        ("POV", current.pov, result.pov),
        ("중심 갈등", current.central_conflict, result.central_conflict),
    ):
        rows.append(f"{label}: {'같음' if before == after else '제안이 다름'}")
    rows.append(f"감정 단계: 기본 {len(current.emotional_arc)} / 제안 {len(result.emotional_arc)}")
    return rows


def apply_director_proposal(session, result: DirectorIntelligenceResult, scope: Literal["interpretation", "world_concepts", "story_beats"]):
    if scope == "interpretation":
        current = session.analysis or LyricInterpretation()
        session.analysis = current.model_copy(update={
            "language_hint": result.language, "synopsis": result.synopsis, "pov": result.pov,
            "central_conflict": result.central_conflict, "emotional_arc": list(result.emotional_arc),
            "repeated_phrases": [item.text for item in result.recurring_motifs],
        })
    elif scope == "world_concepts":
        session.concepts = [item.model_copy(deep=True) for item in result.world_concepts]
        session.selected_concept_id = None
    elif scope == "story_beats":
        session.story_beats = [item.model_copy(deep=True) for item in result.story_beat_suggestions]
    else:
        raise ValueError(f"Unknown apply scope: {scope}")
