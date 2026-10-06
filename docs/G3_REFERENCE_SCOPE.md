# G3 Reference scope policy

G3에는 독립 Scene 엔티티가 없으므로 StoryBeat를 임시 scene-scope 단위로 사용한다.

- `PROJECT`: 모든 Shot에 eligible
- `SCENE`: `scope_id == shot.beat_id`일 때만 eligible
- `SHOT`: `scope_id == shot.shot_id`일 때만 eligible

이 판정은 core의 `reference_is_eligible()`을 단일 출처로 사용한다.
기존 Reference metadata와 원본 파일은 변경하지 않는다.
