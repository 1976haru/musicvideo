# G1 Music Ingest — 감독용 음악 분석 설계

## 목적

이 모듈은 BPM 측정기가 아니다. 음악에서 **뮤직비디오의 연출 상태를 바꿀 만한 지점**을 찾고, 기존 가사 분석과 합쳐 `MV Director Timeline`을 만드는 것이 목적이다.

```text
AUDIO
  ├─ beat
  ├─ onset
  ├─ RMS energy
  ├─ spectral centroid
  └─ spectral bandwidth
       ↓
AUDIO NOVELTY / CHANGE CANDIDATES
       ↓
LYRICS
  ├─ line timestamps
  ├─ repeated lines
  ├─ emotion arc
  └─ semantic anchors
       ↓
MV DIRECTOR TIMELINE
```

## 1. 자동 분석 항목

- 곡 길이
- Tempo BPM
- Beat time list
- Onset time list
- RMS energy
- Spectral centroid / bandwidth 변화
- 음악 변화점 후보
- 구간 후보
- 4 / 8 / 16 beat 기반 컷 길이 참고값

`4/8/16 beat` 값은 자동 컷 명령이 아니다. 롱테이크, 감정 정지, 후렴 확장 등을 깨뜨리지 않도록 **참고 cadence**로만 사용한다.

## 2. Verse / Chorus를 오디오만으로 확정하지 않는 이유

오디오 특징만으로 Verse/Chorus/Bridge의 의미적 이름을 확정하면 장르에 따라 오판이 많아진다.

따라서 G1에서는:

- `intro_candidate`
- `section_candidate`
- `outro_candidate`

까지만 자동 판정한다.

향후 G2/G3에서 다음 증거를 합쳐 확정한다.

1. 가사 반복/후렴
2. 사용자가 제공한 section label
3. 음악 feature recurrence
4. LLM/music structure 판정
5. 최종 사용자 확인

## 3. MV Director Timeline

Cue마다 다음을 저장한다.

- time_sec
- priority 0~1
- cue_type
- reasons
- lyric_line_ids
- recommended_visual_action

예:

```json
{
  "time_sec": 61.2,
  "priority": 0.91,
  "cue_type": "music+lyrics",
  "reasons": ["energy_rise", "motif_phase=transformation"],
  "lyric_line_ids": ["L018"],
  "recommended_visual_action": "같은 후렴을 반복하지 말고 motif의 transformation 단계로 발전"
}
```

## 4. 중요한 연출 원칙

- 모든 Beat에서 컷하지 않는다.
- 음악이 커졌다고 항상 카메라도 빨라지지 않는다.
- 가사와 음악의 강한 변화가 동시에 일어나는 지점은 높은 우선순위를 갖는다.
- Bridge나 Drop은 오히려 카메라 정지/여백/침묵 같은 counter-direction 연출 후보가 될 수 있다.
- 최종 선택은 Story Room의 서사 목적이 우선한다.

## 5. 현재 한계

- semantic Verse/Chorus 자동 확정은 아직 하지 않음.
- 보컬 분리/화자 인식은 아직 없음.
- plain TXT 가사는 실제 word-level sync가 아니므로 SRT/LRC보다 정확도가 낮음.
- v0.4 GUI 분석은 동기식이므로 긴 곡에서 잠시 UI가 멈출 수 있음. 다음 hardening 단계에서 worker thread로 이동한다.
