from __future__ import annotations

from .models import WorldBible, WorldConcept


def promote_world_concept(concept: WorldConcept) -> WorldBible:
    """Create an editable G2 draft while preserving the selected concept's evidence."""
    visual_language = list(dict.fromkeys(concept.visual_language))
    motifs = list(dict.fromkeys(concept.recurring_motifs))
    evidence = list(dict.fromkeys(concept.lyric_evidence))
    return WorldBible(
        premise=concept.one_line,
        emotional_thesis=concept.emotional_engine,
        reality_rules=[concept.world_rule] if concept.world_rule else [],
        visual_language=visual_language,
        recurring_motifs=motifs,
        forbidden_elements=[
            "가사의 모든 명사를 설명적으로 재연하지 않는다.",
            "선택한 세계 법칙과 충돌하는 임의의 판타지 효과를 추가하지 않는다.",
        ],
        lyric_foundation=evidence,
        source_concept_id=concept.concept_id,
    )
