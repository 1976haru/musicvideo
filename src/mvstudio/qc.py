from __future__ import annotations
from dataclasses import dataclass, asdict
from .models import MusicVideoProject


@dataclass
class ProjectQC:
    score: int
    world_rules: int
    reference_coverage: int
    continuity: int
    motif_design: int
    shot_specificity: int
    lyric_grounding: int
    warnings: list[str]

    def as_dict(self):
        return asdict(self)


def evaluate_project(project: MusicVideoProject) -> ProjectQC:
    warnings: list[str] = []
    w = project.world_bible
    rule_count = sum(bool(x) for x in [w.reality_rules, w.visual_language, w.lighting_rules, w.camera_rules, w.forbidden_elements, w.lyric_foundation])
    world_rules = round(16 * rule_count / 6)
    if world_rules < 13:
        warnings.append("World Bible 규칙 또는 lyric_foundation이 약합니다.")
    if not project.shots:
        return ProjectQC(0, world_rules, 0, 0, 0, 0, 0, warnings + ["Shot이 없습니다."])

    n = len(project.shots)
    reference_coverage = round(16 * sum(bool(s.reference_ids) for s in project.shots) / n)
    continuity = round(16 * sum(bool(s.continuity_in or s.continuity_out) for s in project.shots) / n)
    motifs = [s.motif for s in project.shots if s.motif]
    motif_design = 16 if len(motifs) >= 3 and len(set(motifs)) < len(motifs) else 8 if motifs else 0
    shot_specificity = round(16 * sum(bool(s.action.strip() and s.camera.framing.strip() and s.camera.movement.strip() and s.emotional_note.strip()) for s in project.shots) / n)
    lyric_grounding = round(20 * sum(bool(s.lyric_line_ids and s.lyric_intent.strip() and s.lyric_visual_strategy) for s in project.shots) / n)

    if reference_coverage < 11: warnings.append("Master/reference가 연결되지 않은 샷이 많아 identity drift 위험이 있습니다.")
    if continuity < 11: warnings.append("continuity_in/out이 부족합니다.")
    if motif_design < 16: warnings.append("가사 핵심 모티프를 setup→development→payoff로 3회 이상 발전시키세요.")
    if lyric_grounding < 14: warnings.append("가사 근거(line IDs + lyric_intent + visual strategy)가 약한 샷이 많습니다.")

    score = world_rules + reference_coverage + continuity + motif_design + shot_specificity + lyric_grounding
    return ProjectQC(score, world_rules, reference_coverage, continuity, motif_design, shot_specificity, lyric_grounding, warnings)
