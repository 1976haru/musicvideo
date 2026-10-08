from __future__ import annotations

from .models import AudioMap, LyricInterpretation, WorldBible, WorldConcept


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in items if item and item.strip()))


def _anchors(analysis: LyricInterpretation | None, kind: str, limit: int = 4) -> list[str]:
    if not analysis:
        return []
    return _unique([anchor.phrase for anchor in analysis.anchors if anchor.anchor_type == kind])[:limit]


def _contains(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(word.casefold() in lowered for word in words)


def _time_profile(analysis: LyricInterpretation | None) -> tuple[str, list[str], list[str]]:
    time_phrases = _anchors(analysis, "time", 3)
    source = " ".join(time_phrases)
    profiles = [
        (
            ("새벽", "아침", "朝", "夜明け", "dawn", "morning"),
            "새벽에서 아침으로 넘어가는 시간대",
            ["blue gray", "pale dawn peach", "natural warm skin tone"],
            [
                "초반은 차가운 blue-hour 자연광을 기본으로 한다.",
                "후반으로 갈수록 새벽의 옅은 따뜻한 빛이 아주 천천히 증가한다.",
            ],
        ),
        (
            ("밤", "夜", "midnight", "night"),
            "밤",
            ["deep navy", "blue gray", "restrained warm practical light"],
            [
                "밤의 낮은 주변광과 실제 practical light를 기본으로 한다.",
                "얼굴을 과도하게 밝히지 않고 어두운 공간 속 시선과 실루엣을 보존한다.",
            ],
        ),
        (
            ("저녁", "夕", "夕方", "夕暮", "sunset", "evening", "dusk"),
            "해질녘에서 저녁으로 넘어가는 시간대",
            ["muted amber", "dusty rose", "deep blue"],
            [
                "낮은 각도의 따뜻한 자연광에서 푸른 저녁빛으로 점진적으로 이동한다.",
                "색온도 변화는 장면 전환보다 감정 변화에 맞춰 연속적으로 유지한다.",
            ],
        ),
        (
            ("낮", "昼", "day", "afternoon", "오후"),
            "낮",
            ["soft neutral daylight", "desaturated earth tone", "natural skin tone"],
            [
                "부드러운 자연광을 우선하고 과도한 하이라이트를 피한다.",
                "시간 연속성이 깨지지 않도록 태양 방향과 명암비를 Shot 간 유지한다.",
            ],
        ),
    ]
    for words, label, palette, lighting in profiles:
        if _contains(source, words):
            detail = f"시대 미지정 · {label}"
            if time_phrases:
                detail += f" · 가사 시간 앵커: {' / '.join(time_phrases)}"
            return detail, palette, lighting
    if time_phrases:
        return (
            f"시대 미지정 · 가사 시간 앵커 {' / '.join(time_phrases)}를 기준으로 하나의 연속된 시간대 유지",
            ["natural neutral base", "restrained warm/cool contrast", "natural skin tone"],
            [
                f"가사 시간 앵커({' / '.join(time_phrases)})에 맞는 자연광 방향과 색온도를 유지한다.",
                "시간이 진행되더라도 광원 방향과 노출은 갑자기 점프하지 않는다.",
            ],
        )
    return (
        "시대 미지정 · 현대적 중립 배경을 사용하되 시대를 강하게 특정하는 소품은 피한다.",
        ["natural neutral base", "one restrained accent color", "natural skin tone"],
        [
            "현실적인 동기광과 자연광을 우선한다.",
            "감정 변화를 표현하기 위해 노출이나 색온도를 갑자기 바꾸지 않는다.",
        ],
    )


def _palette_rules(concept: WorldConcept, analysis: LyricInterpretation | None, base: list[str]) -> list[str]:
    color_anchors = _anchors(analysis, "color_light", 4)
    result = list(base)
    result.extend(f"가사 색/빛 앵커 '{phrase}'를 반복 포인트로 일관되게 유지" for phrase in color_anchors)
    if concept.interpretation_mode in {"hybrid", "metaphoric"}:
        result.append("비현실 순간에도 전체 채도를 올리지 말고 한 가지 포인트 색만 미세하게 변화")
    else:
        result.append("색보정은 현실적인 피부톤과 장소 고유색을 우선")
    return _unique(result)


def _material_rules(analysis: LyricInterpretation | None) -> list[str]:
    objects = _anchors(analysis, "object", 4)
    places = _anchors(analysis, "place", 3)
    nature = _anchors(analysis, "nature", 3)
    result: list[str] = []
    result.extend(f"반복 소품 '{phrase}'는 Shot마다 형태·재질·사용 흔적을 동일하게 유지" for phrase in objects)
    result.extend(f"장소 '{phrase}'는 과도한 CG 광택보다 실제 사용감이 있는 표면과 재질을 우선" for phrase in places)
    result.extend(f"자연 앵커 '{phrase}'는 합성 티보다 실제 광학·대기·표면 질감을 우선" for phrase in nature)
    if not result:
        result = [
            "피부·천·유리·금속·바닥 등 주요 표면은 실제 촬영 가능한 물성과 미세한 사용감을 유지",
            "과도하게 매끈한 생성형 CG 질감과 Shot마다 바뀌는 재질을 피한다.",
        ]
    return _unique(result)[:6]


def _weather_rules(concept: WorldConcept, analysis: LyricInterpretation | None) -> list[str]:
    weather = _anchors(analysis, "weather", 4)
    nature = _anchors(analysis, "nature", 3)
    result: list[str] = []
    if weather:
        result.extend(f"가사 날씨 앵커 '{phrase}'를 기본 기상 연속성으로 유지" for phrase in weather)
    else:
        result.append("가사에 명시적 날씨 근거가 없으면 하나의 안정된 기상 상태를 유지한다.")
    if nature:
        result.append(f"자연 앵커({' / '.join(nature)})의 움직임은 Shot 사이에서 방향과 강도가 연속되어야 한다.")
    result.append("감정을 설명하기 위해 Shot마다 비·눈·안개·바람을 임의로 급변시키지 않는다.")
    if concept.interpretation_mode in {"hybrid", "metaphoric"}:
        result.append("비현실적 날씨 반응은 선택 세계관의 단 하나의 반복 모티프가 감정의 문턱에 도달할 때만 허용한다.")
    return _unique(result)


def _lighting_rules(
    concept: WorldConcept,
    analysis: LyricInterpretation | None,
    base: list[str],
) -> list[str]:
    result = list(base)
    arc = analysis.emotional_arc if analysis else []
    if arc:
        result.append(
            f"감정곡선({' → '.join(arc)})은 광원의 개수를 늘리기보다 명암비·색온도·배경 밝기의 미세한 이동으로 표현"
        )
    color_anchors = _anchors(analysis, "color_light", 3)
    if color_anchors:
        result.append(f"빛/색 앵커({' / '.join(color_anchors)})는 반복될수록 의미가 발전하되 광원 논리는 유지")
    if concept.interpretation_mode in {"hybrid", "metaphoric"}:
        result.append("시적 비현실 효과는 발광 VFX보다 반사·굴절·노출 변화처럼 실제 광학에 가까운 방식으로 제한")
    return _unique(result)


def _camera_rules(concept: WorldConcept, audio_map: AudioMap | None) -> list[str]:
    tempo = audio_map.tempo_bpm if audio_map and audio_map.tempo_bpm else 0.0
    transitions = len(audio_map.transitions) if audio_map else 0
    if tempo and tempo < 90:
        movement = "기본은 locked-off 또는 아주 느린 dolly/push. 긴 호흡의 medium/close shot을 우선"
    elif tempo and tempo <= 125:
        movement = "기본은 안정된 dolly·slider·restrained handheld. medium과 close-up을 감정 변화에 맞춰 점진적으로 전환"
    elif tempo:
        movement = "리듬 에너지는 통제된 tracking과 짧아진 Shot 호흡으로 반영하되 모든 비트마다 컷하지 않는다"
    else:
        movement = "기본은 안정된 카메라와 절제된 이동. 가사 전환과 인물 행동이 있을 때만 카메라 문법을 바꾼다"

    result = [
        movement,
        "한 Shot에는 하나의 주된 행동과 하나의 명확한 카메라 의도를 둔다.",
        "모든 비트마다 화면을 바꾸지 않고 가사 의미 전환·감정 변화·음악 변화점에서만 구도나 이동을 단계적으로 바꾼다.",
        "인물 정체성과 공간 방향을 보존하고 이유 없는 축 변경·과도한 whip pan·무작위 drone movement를 피한다.",
    ]
    if transitions:
        result.append(f"분석된 음악 변화점 {transitions}개는 컷 명령이 아니라 카메라/구도 변화를 검토할 우선 지점으로만 사용")
    if concept.interpretation_mode == "metaphoric":
        result.append("은유 장면은 과한 카메라 트릭보다 negative space와 통제된 프레이밍으로 비현실성을 느끼게 한다.")
    elif concept.interpretation_mode == "hybrid":
        result.append("현실 장면의 카메라 문법을 유지하고 시적 순간에만 이동 강도나 framing을 한 단계 변화시킨다.")
    return _unique(result)


def promote_world_concept(
    concept: WorldConcept,
    analysis: LyricInterpretation | None = None,
    audio_map: AudioMap | None = None,
) -> WorldBible:
    """Create a complete editable World Bible draft from grounded project evidence.

    The function deliberately stays deterministic and API-free. It uses the selected
    WorldConcept, lyric anchors/emotional arc and basic music structure to populate all
    production-facing fields while preserving lyric evidence and continuity rules.
    """
    visual_language = _unique(
        list(concept.visual_language)
        + ["lyric-grounded visual causality", "continuity-first worldbuilding"]
    )
    motifs = _unique(list(concept.recurring_motifs))
    evidence = _unique(list(concept.lyric_evidence))
    time_period, base_palette, base_lighting = _time_profile(analysis)

    emotional = concept.emotional_engine.strip() or "가사의 감정 변화가 행동·거리·공간의 변화로 축적된다."
    if analysis and analysis.emotional_arc:
        emotional += f" · 감정곡선: {' → '.join(analysis.emotional_arc)}"

    reality_rules = _unique(
        ([concept.world_rule] if concept.world_rule else [])
        + [
            "인물 정체성·장소 지리·의상·소품·날씨·시간의 연속성을 Shot 사이에서 유지한다.",
            "가사 근거가 없는 새 장소·상징·판타지 규칙을 장식 목적으로 추가하지 않는다.",
        ]
    )

    forbidden = _unique(
        [
            "가사의 모든 명사를 설명적으로 재연하지 않는다.",
            "선택한 세계 법칙과 충돌하는 임의의 판타지 효과를 추가하지 않는다.",
            "Shot마다 인물 얼굴·헤어·의상·주요 소품·장소 구조를 임의로 바꾸지 않는다.",
            "감정 강화를 이유로 근거 없는 날씨 급변·과도한 네온·무작위 슬로모션·과장된 VFX를 추가하지 않는다.",
        ]
        + (analysis.visual_risk_notes if analysis else [])
    )

    return WorldBible(
        premise=concept.one_line or "선택 세계관의 가사 근거를 중심으로 하나의 연속된 현실을 만든다.",
        emotional_thesis=emotional,
        reality_rules=reality_rules,
        time_period=time_period,
        visual_language=visual_language,
        palette=_palette_rules(concept, analysis, base_palette),
        material_language=_material_rules(analysis),
        weather_rules=_weather_rules(concept, analysis),
        lighting_rules=_lighting_rules(concept, analysis, base_lighting),
        camera_rules=_camera_rules(concept, audio_map),
        recurring_motifs=motifs or ["반복 가사 구절에서 의미가 발전하는 단 하나의 시각 모티프"],
        forbidden_elements=forbidden,
        lyric_foundation=evidence or ["가사 근거 Line ID 보강 필요"],
        source_concept_id=concept.concept_id,
    )
