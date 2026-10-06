# Beginner UI Standard — MV Director Studio

## Product rule

From G5 onward, UI PASS requires that a first-time user can complete the main workflow without reading a manual.

The interface must answer five questions on every active page:

1. 지금 무엇을 해야 하나?
2. 어떤 버튼을 누르면 되나?
3. 결과가 좋은지 나쁜지 어떻게 알 수 있나?
4. 문제가 있으면 어떻게 고치나?
5. 다음 단계는 무엇인가?

## Beginner-first hierarchy

Show information in this order:

### Level 1 — Decision
Plain-language status:
- 사용 가능
- 확인 필요
- 다시 만드는 것을 권장
- 파일 문제 해결 필요

### Level 2 — Action
Primary recommended button:
- 이 Take 사용
- 다른 Take 비교
- 다시 생성하기
- 파일 다시 연결
- 상세 문제 보기

### Level 3 — Reason
Short explanations:
- 인물/레퍼런스 차이가 큼
- 장면이 너무 어두움
- 깜빡임이 감지됨
- Shot 길이보다 결과가 짧음

### Level 4 — Expert details
Collapsed / optional:
- raw metric
- threshold
- sampled frames
- technical warning code
- debug values

Never lead with raw technical metrics.

## Wording

Prefer Korean plain language over internal terms.

Examples:
- "Temporal instability score" → "화면 흔들림/깜빡임"
- "Reference similarity" → "레퍼런스와 비슷한 정도"
- "Duration mismatch" → "필요한 길이와 결과 영상 길이가 다름"

Internal IDs remain available in details.

## Layout

- Main action buttons: minimum 44px height
- Body font: beginner-readable, not dense
- Long Korean/Japanese text must wrap
- Critical status must not rely on color alone
- Each page must have one obvious primary action
- Avoid showing more than 5–7 primary choices at once
- Advanced settings belong under "상세 설정" or "전문가 정보"
- Preserve stable selection after refresh
- Large lists must be scrollable
- 1100×720 minimum layout must remain usable
- Windows high-DPI must be considered

## Error recovery

Every user-facing error should include a recovery action when one exists.

Bad:
"Missing file"

Good:
"결과 영상 파일을 찾을 수 없습니다."
[파일 다시 연결]

Bad:
"Reference mismatch"

Good:
"레퍼런스와 차이가 큽니다."
[다른 Take 비교] [다시 생성하기]

## Progress visibility

Show the user where they are in the workflow.

Example:
1. 음악
2. 세계관
3. Story
4. Shot
5. 생성
6. 결과 비교
7. 품질 확인
8. 편집

Use completed/current/next states.

## Safety against accidental destructive actions

- Metadata-only operations should say "원본 파일은 유지됩니다."
- Destructive operations, if introduced later, require explicit confirmation
- Never hide file deletion behind generic labels

## PASS checklist

A UI stage does not pass if:
- the user must understand internal object IDs to proceed
- the main next action is ambiguous
- warning text has no recovery guidance
- status is only a number
- important buttons are small or crowded
- expert terminology is unavoidable on the main surface
