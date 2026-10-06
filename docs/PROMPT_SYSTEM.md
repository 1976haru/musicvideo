# Prompt System v0.1

## 중요한 원칙

**스토리 프롬프트와 영상 생성 프롬프트를 분리합니다.**

스토리 프롬프트는 “무슨 이야기를 왜 보여주는가”를 결정하고,
영상 생성 프롬프트는 “이 샷 안에서 카메라와 피사체가 어떻게 움직이는가”를 결정합니다.

두 개를 한 프롬프트로 섞으면:
- 매 샷의 문장이 길어짐
- 캐릭터가 변함
- 카메라 지시가 묻힘
- 모델별 최적화가 불가능해짐

---

## 1. Story Architect Input

- song summary
- lyrics
- music sections
- creative thesis
- world bible
- available references

## 2. Story Architect Output

각 beat는 아래만 작성:

```json
{
  "beat_id": "B05",
  "time_range": "01:02-01:21",
  "dramatic_question": "그녀는 떠난 사람의 흔적을 붙잡을 것인가?",
  "change": "기억을 회피하던 상태에서 처음으로 마주 본다.",
  "visual_event": "닫혀 있던 역 대합실 창이 바람에 열린다.",
  "motif": "red_ticket",
  "setup_or_payoff": "payoff"
}
```

---

## 3. Shot Director Output

한 beat를 여러 shot으로 분해.

금지:
- “beautiful cinematic masterpiece” 같은 의미 없는 품질 주문 반복
- 한 샷에 4개 이상의 주 행동
- 카메라 무브를 동시에 여러 개 지시
- 인물 외형을 샷마다 새로 묘사

권장:
- 하나의 primary action
- 하나의 camera intent
- 하나의 emotional purpose
- 명시적 continuity in/out

---

## 4. Prompt Layer

### Immutable
변하면 안 됨.
- 캐릭터 identity
- 대표 의상
- 장소 구조
- 핵심 소품
- 세계 색/재질 규칙

### Shot Variable
샷마다 변함.
- action
- framing
- lens
- camera motion
- weather intensity
- emotion
- transition

### Provider Variable
모델별로 바꿈.
- 문장 길이
- negative prompt 지원 여부
- first/last frame
- keyframe
- duration
- aspect ratio
