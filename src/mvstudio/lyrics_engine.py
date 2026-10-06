from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from .models import LyricLine, LyricAnchor, LyricInterpretation, WorldConcept, LyricVisualBridge

_TS_LRC = re.compile(r"^\[(\d{1,2}):(\d{2}(?:\.\d{1,3})?)\]\s*(.*)$")
_TS_SRT = re.compile(
    r"(?P<sh>\d{2}):(?P<sm>\d{2}):(?P<ss>\d{2}),(?P<sms>\d{3})\s*-->\s*"
    r"(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2}),(?P<ems>\d{3})"
)

LEXICON = {
    "place": ["역","거리","방","창가","카페","바다","강","골목","집","도시","駅","街","部屋","窓","カフェ","海","川","路地","家","町","station","street","room","window","cafe","sea","river","home","city"],
    "weather": ["비","눈","바람","안개","구름","햇빛","노을","雨","雪","風","霧","雲","光","夕焼け","rain","snow","wind","fog","cloud","sunlight","sunset"],
    "object": ["편지","우산","사진","티켓","열쇠","전화","컵","시계","신발","문","手紙","傘","写真","切符","鍵","電話","カップ","時計","靴","扉","letter","umbrella","photo","ticket","key","phone","cup","clock","door"],
    "time": ["오늘","어제","내일","밤","아침","새벽","봄","여름","가을","겨울","今日","昨日","明日","夜","朝","夜明け","春","夏","秋","冬","today","yesterday","tomorrow","night","morning","dawn","spring","summer","autumn","winter"],
    "motion": ["걷","달리","떠나","돌아","기다리","멈추","열","닫","歩","走","去","帰","待","止","開","閉","walk","run","leave","return","wait","stop","open","close"],
    "body_sense": ["손","눈","입술","목소리","숨","향기","온기","차갑","手","目","唇","声","息","香り","温もり","冷た","hand","eye","eyes","lip","voice","breath","scent","warmth","cold"],
    "relationship": ["너","우리","사랑","이별","약속","기억","혼자","함께","君","あなた","僕ら","私たち","恋","愛","別れ","約束","記憶","一人","一緒","you","we","love","goodbye","promise","memory","alone","together"],
    "color_light": ["붉","빨강","파랑","푸른","하얀","검은","빛","그림자","赤","青","白","黒","光","影","red","blue","white","black","light","shadow"],
    "nature": ["꽃","나무","잎","새","달","별","파도","花","木","葉","鳥","月","星","波","flower","tree","leaf","bird","moon","star","wave"],
}

EMOTIONS = {
    "longing": ["그리","보고 싶","기다","恋しい","会いたい","待","miss","long","wait"],
    "sadness": ["슬프","눈물","아프","悲","涙","痛","sad","tear","hurt"],
    "warmth": ["따뜻","웃","온기","温","笑","warm","smile"],
    "anxiety": ["불안","두려","떨","怖","不安","震","fear","anxious"],
    "hope": ["희망","다시","내일","希望","もう一度","明日","hope","again","tomorrow"],
    "acceptance": ["괜찮","놓아","보내","大丈夫","手放","見送","okay","let go","release"],
}

POV_PATTERNS = {
    "first_person": ["나는","내가","나의","난","僕","私","俺"," I ","I'm"," my "," me "],
    "second_person": ["너는","네가","너의","당신","君","あなた"," you "," your "],
    "collective": ["우리","僕ら","私たち"," we "," our "],
}


def _sec(h: int, m: int, s: int, ms: int = 0) -> float:
    return h * 3600 + m * 60 + s + ms / 1000


def parse_lyrics(path: str | Path, song_duration: float | None = None) -> list[LyricLine]:
    path = Path(path)
    raw = path.read_text(encoding="utf-8-sig")
    return parse_lyrics_text(raw, suffix=path.suffix.lower(), song_duration=song_duration)


def parse_lyrics_text(raw: str, suffix: str = ".txt", song_duration: float | None = None) -> list[LyricLine]:
    """Parse pasted lyrics or file contents while preserving line-ID rules."""
    suffix = (suffix or ".txt").lower()
    if suffix == ".srt":
        return _parse_srt(raw)
    if suffix == ".lrc":
        return _parse_lrc(raw, song_duration=song_duration)
    return _parse_txt(raw, song_duration=song_duration)


def _parse_srt(raw: str) -> list[LyricLine]:
    blocks = re.split(r"\n\s*\n", raw.strip())
    out: list[LyricLine] = []
    for block in blocks:
        rows = [r.strip() for r in block.splitlines() if r.strip()]
        time_idx = next((i for i, row in enumerate(rows) if "-->" in row), None)
        if time_idx is None:
            continue
        m = _TS_SRT.search(rows[time_idx])
        if not m:
            continue
        start = _sec(int(m["sh"]), int(m["sm"]), int(m["ss"]), int(m["sms"]))
        end = _sec(int(m["eh"]), int(m["em"]), int(m["es"]), int(m["ems"]))
        text = " ".join(rows[time_idx + 1:]).strip()
        if text:
            out.append(LyricLine(line_id=f"L{len(out)+1:03d}", text=text, start_sec=start, end_sec=end))
    return out


def _parse_lrc(raw: str, song_duration: float | None = None) -> list[LyricLine]:
    temp: list[tuple[float, str]] = []
    for row in raw.splitlines():
        m = _TS_LRC.match(row.strip())
        if not m:
            continue
        start = int(m.group(1)) * 60 + float(m.group(2))
        text = m.group(3).strip()
        if text:
            temp.append((start, text))
    temp.sort(key=lambda x: x[0])
    out = []
    for i, (start, text) in enumerate(temp):
        end = temp[i + 1][0] if i + 1 < len(temp) else (song_duration if song_duration and song_duration >= start else start + 5.0)
        out.append(LyricLine(line_id=f"L{i+1:03d}", text=text, start_sec=start, end_sec=end))
    return out


def _parse_txt(raw: str, song_duration: float | None = None) -> list[LyricLine]:
    rows = [re.sub(r"\s+", " ", r).strip() for r in raw.splitlines() if r.strip()]
    if not rows:
        return []
    per = (song_duration / len(rows)) if song_duration and song_duration > 0 else None
    out = []
    for i, text in enumerate(rows):
        start = round(i * per, 3) if per else None
        end = round((i + 1) * per, 3) if per else None
        out.append(LyricLine(line_id=f"L{i+1:03d}", text=text, start_sec=start, end_sec=end))
    return out


def _norm(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w가-힣ぁ-んァ-ヶ一-龠\s]", "", text)
    return re.sub(r"\s+", " ", text)


def detect_language(lines: list[LyricLine]) -> str:
    joined = " ".join(x.text for x in lines)
    ko = len(re.findall(r"[가-힣]", joined))
    ja_kana = len(re.findall(r"[ぁ-んァ-ヶ]", joined))
    en = len(re.findall(r"[A-Za-z]", joined))
    if ko >= ja_kana and ko >= en:
        return "ko"
    if ja_kana >= ko and ja_kana >= en:
        return "ja"
    if en:
        return "en"
    return "unknown"


def repeated_phrases(lines: list[LyricLine]) -> list[str]:
    counts = Counter(_norm(x.text) for x in lines if len(_norm(x.text)) >= 3)
    return [phrase for phrase, n in counts.most_common(8) if n >= 2]


def _detect_pov(lines: list[LyricLine]) -> str:
    text = " " + " ".join(x.text for x in lines) + " "
    scores = {name: sum(text.count(token) for token in tokens) for name, tokens in POV_PATTERNS.items()}
    if max(scores.values(), default=0) == 0:
        return "observational/implicit"
    return max(scores, key=scores.get)


def extract_anchors(lines: list[LyricLine]) -> list[LyricAnchor]:
    hits: dict[tuple[str, str], list[str]] = defaultdict(list)
    for line in lines:
        lower = line.text.lower()
        for kind, terms in LEXICON.items():
            for term in terms:
                if term.lower() in lower:
                    hits[(kind, term)].append(line.line_id)
    ranked = sorted(hits.items(), key=lambda kv: (len(set(kv[1])), len(kv[0][1])), reverse=True)[:24]
    max_hits = max((len(set(ids)) for _, ids in ranked), default=1)
    return [
        LyricAnchor(
            anchor_id=f"A{idx:02d}", anchor_type=kind, phrase=phrase,
            source_line_ids=list(dict.fromkeys(ids)),
            weight=min(1.0, round(0.45 + 0.55 * len(set(ids)) / max_hits, 2))
        )
        for idx, ((kind, phrase), ids) in enumerate(ranked, 1)
    ]


def _emotion_for_text(text: str) -> str:
    lower = text.lower()
    scores = {emotion: sum(1 for term in terms if term.lower() in lower) for emotion, terms in EMOTIONS.items()}
    if max(scores.values(), default=0) == 0:
        return "neutral/ambiguous"
    return max(scores, key=scores.get)


def emotion_arc(lines: list[LyricLine], bins: int = 5) -> list[str]:
    if not lines:
        return []
    bins = max(1, min(bins, len(lines)))
    result = []
    for b in range(bins):
        start = round(len(lines) * b / bins)
        end = round(len(lines) * (b + 1) / bins)
        chunk = lines[start:end] or [lines[min(start, len(lines)-1)]]
        result.append(_emotion_for_text(" ".join(x.text for x in chunk)))
    return result


def _infer_conflict(lines: list[LyricLine], arc: list[str]) -> str:
    text = " ".join(x.text for x in lines).lower()
    if any(k in text for k in ["이별", "別れ", "goodbye", "떠나", "去", "leave"]):
        return "떠남/이별 이후에도 남아 있는 감정과 앞으로 나아가려는 의지의 충돌"
    if any(k in text for k in ["기억", "記憶", "memory", "사진", "写真", "photo"]):
        return "기억을 붙잡고 싶은 마음과 현재를 살아가야 하는 마음의 충돌"
    if any(k in text for k in ["기다", "待", "wait"]):
        return "기다림을 계속할지 스스로 움직일지의 충돌"
    if arc:
        return f"{arc[0]}에서 {arc[-1]}로 이동하는 내적 변화"
    return "명시적 사건보다 감정 변화가 중심인 내적 갈등"


def analyze_lyrics(lines: list[LyricLine]) -> LyricInterpretation:
    lang = detect_language(lines)
    anchors = extract_anchors(lines)
    repeats = repeated_phrases(lines)
    arc = emotion_arc(lines)
    concrete = [a.phrase for a in anchors[:8] if a.anchor_type in {"place","weather","object","nature","color_light"}][:5]
    relational = [a.phrase for a in anchors if a.anchor_type == "relationship"][:3]
    synopsis = []
    if relational: synopsis.append("관계/기억의 중심어: " + ", ".join(relational))
    if concrete: synopsis.append("시각적으로 강한 가사 앵커: " + ", ".join(concrete))
    if arc: synopsis.append("감정 흐름: " + " → ".join(arc))
    return LyricInterpretation(
        language_hint=lang,
        synopsis=" / ".join(synopsis) if synopsis else "가사 의미를 수동 보강할 필요가 있습니다.",
        pov=_detect_pov(lines),
        central_conflict=_infer_conflict(lines, arc),
        emotional_arc=arc,
        repeated_phrases=repeats,
        anchors=anchors,
        visual_risk_notes=[
            "가사의 모든 명사를 그대로 화면에 옮기지 말 것.",
            "반복되는 후렴은 같은 이미지를 복사하지 말고 모티프의 의미를 발전시킬 것.",
            "추상 감정어는 행동·공간 변화·빛·거리로 번역할 것.",
            "counterpoint는 서사적 이유가 있을 때만 사용할 것.",
        ],
    )


def generate_world_concepts(analysis: LyricInterpretation, lines: list[LyricLine]) -> list[WorldConcept]:
    anchors = analysis.anchors
    def top(kind, n=2): return [a for a in anchors if a.anchor_type == kind][:n]
    def phrase(xs, fallback): return xs[0].phrase if xs else fallback
    place_a, weather_a, object_a, nature_a, color_a = top("place"), top("weather"), top("object",3), top("nature"), top("color_light")
    place = phrase(place_a, "가사 속 반복되는 생활 공간")
    weather = phrase(weather_a, "시간에 따라 변하는 공기")
    obj = phrase(object_a, "반복되는 작은 소지품")
    nature = phrase(nature_a, "계절의 흔적")
    color = phrase(color_a, "절제된 한 가지 포인트 색")
    evidence = []
    for a in place_a + weather_a + object_a + nature_a + color_a:
        evidence.extend(a.source_line_ids)
    evidence = list(dict.fromkeys(evidence))[:12]
    return [
        WorldConcept(
            concept_id="WC03", title="현실 80% + 시적 비현실 20%", interpretation_mode="hybrid",
            one_line=f"현실적인 {place}에서 시작하지만 특정 가사 구절이 반복될 때만 {weather}, {obj}, {nature}가 미세하게 불가능한 방식으로 반응한다.",
            world_rule="대부분은 현실 물리를 따른다. 단 하나의 반복 모티프만 감정의 문턱에서 비현실적으로 변한다.",
            emotional_engine=analysis.central_conflict, recurring_motifs=[obj, weather, nature, color],
            visual_language=["grounded cinematic realism","subtle magical event","motif payoff","visual restraint"],
            ending_image=f"마지막에는 현실만 남고 {obj}의 작은 변화로 서사를 회수한다.", lyric_evidence=evidence,
            lyric_relevance_score=97 if evidence else 76,
        ),
        WorldConcept(
            concept_id="WC01", title="가사에 가장 가까운 현실 세계", interpretation_mode="literal",
            one_line=f"{place}을 중심으로 {weather}와 {obj}가 실제 사건의 흔적이 되는 현실적 세계.",
            world_rule="가사에 나온 장소·사물은 실제로 존재하지만 감정은 표정 설명보다 행동과 거리 변화로 보여준다.",
            emotional_engine=analysis.central_conflict, recurring_motifs=[obj, weather, color],
            visual_language=["observational realism","restrained camera","lyric-grounded props"],
            ending_image=f"처음과 같은 {place}이지만 {obj}의 위치 또는 의미가 달라져 인물의 변화를 보여준다.", lyric_evidence=evidence,
            lyric_relevance_score=94 if evidence else 72,
        ),
        WorldConcept(
            concept_id="WC02", title="가사의 감정을 물리 법칙으로 만든 세계", interpretation_mode="metaphoric",
            one_line=f"{obj}와 {weather}가 인물의 기억 상태에 반응하며 공간 자체가 감정을 보존하는 세계.",
            world_rule=f"감정이 강해질수록 {weather} 또는 빛의 물성이 변하고 {obj}는 기억의 상태를 기록한다. 인물은 현상을 완전히 통제할 수 없다.",
            emotional_engine=analysis.central_conflict, recurring_motifs=[obj,nature,color],
            visual_language=["poetic realism","one impossible rule only","motif transformation","negative space"],
            ending_image=f"{obj}는 남아 있지만 더 이상 비현실적 현상을 일으키지 않는다. 감정이 받아들여졌음을 암시한다.", lyric_evidence=evidence,
            lyric_relevance_score=90 if evidence else 70,
        ),
    ]


def build_lyric_visual_bridges(lines: list[LyricLine], repeated: list[str] | None = None) -> list[LyricVisualBridge]:
    repeated_set = set(repeated or repeated_phrases(lines))
    out = []
    for i, line in enumerate(lines, 1):
        n = _norm(line.text)
        types = {a.anchor_type for a in extract_anchors([line])}
        emotion = _emotion_for_text(line.text)
        if n in repeated_set:
            strategy, literalness = "motif", 0.25
            intent = f"반복 구절을 같은 장면 반복이 아니라 점진적으로 의미가 변하는 모티프로 사용. 감정={emotion}"
        elif types & {"place","object","motion"}:
            strategy, literalness = "literal", 0.60
            intent = f"구체적 행위/사물을 행동 근거로 쓰되 설명적 재연은 피함. 감정={emotion}"
        elif types & {"weather","nature","color_light"}:
            strategy, literalness = "metaphor", 0.35
            intent = f"자연/빛 이미지를 감정 변화의 시각 은유로 번역. 감정={emotion}"
        else:
            strategy, literalness = "metaphor", 0.20
            intent = f"추상 가사를 표정보다 공간, 거리, 행동 변화로 번역. 감정={emotion}"
        out.append(LyricVisualBridge(
            bridge_id=f"LB{i:03d}", source_line_ids=[line.line_id], lyric_intent=intent,
            visual_strategy=strategy, literalness=literalness, must_preserve=[line.text],
            avoid=["가사 문장을 그대로 설명하는 삽화식 연출","근거 없는 새 상징 추가"]
        ))
    return out


def build_director_llm_prompt(lines: list[LyricLine], analysis: LyricInterpretation, concept_count: int = 3) -> str:
    lyric_text = "\n".join(f"{x.line_id}: {x.text}" for x in lines)
    anchors = ", ".join(f"{a.anchor_type}:{a.phrase}({','.join(a.source_line_ids)})" for a in analysis.anchors[:16])
    return f"""You are the story and worldbuilding director for an original music video.

GOAL
Create {concept_count} distinct, original world concepts. Every concept must be grounded in the lyrics but must NOT illustrate every line literally.

LYRIC ANALYSIS
- POV: {analysis.pov}
- Central conflict: {analysis.central_conflict}
- Emotional arc: {' -> '.join(analysis.emotional_arc)}
- Repeated phrases: {analysis.repeated_phrases}
- Semantic anchors: {anchors}

LYRICS
{lyric_text}

REQUIRED CREATIVE RULES
1. Cite supporting lyric line IDs for every world rule, motif, major location, and ending image.
2. Separate literal lyric evidence from visual metaphor.
3. Repeated chorus lines must evolve visually: setup -> transformation -> payoff.
4. Prefer one unforgettable impossible rule over many random fantasy effects.
5. Character identity, geography, weather logic, prop logic, and time must remain continuous.
6. Do not imitate a living artist or copy a copyrighted film universe.
7. Avoid generic 'cinematic masterpiece' wording; describe concrete visual causality.
8. Include grounded realism, restrained magical realism, and a third distinct concept.
9. Return structured JSON only.
""".strip()
