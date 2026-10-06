# G4A.1 Higgsfield Profile Hardening

## Why this patch is required

The G4A architecture is correct, but the current site-level HIGGSFIELD profile incorrectly behaves as if one set of duration / resolution / first-last-frame capabilities applies to every Higgsfield model.

Higgsfield is a multi-model website. Model capabilities differ.

Examples from current official Higgsfield documentation:
- LTX 2.5 Image-to-Video: 6 / 8 / 10 seconds, first image + optional end image, 720p/1080p (and some variants higher)
- Kling O3 First/Last Frame: duration range 3–15 seconds
- other Higgsfield models expose different duration, resolution, negative-prompt and end-frame capabilities

Therefore the generic HIGGSFIELD site profile must not present fixed model-specific values as authoritative.

## Scope

Keep overall progress at 78%.
Do not start G4B.

## Required changes

### 1. Make HIGGSFIELD explicitly site-level / model-dependent

The profile must say clearly in notes/UI that:
- settings depend on the model selected on Higgsfield
- current website/model options must be checked manually
- camera preset recommendation is site-level guidance, not a guarantee for every model

### 2. Duration choices

Do NOT hard-code [3, 5, 10] as if universally valid.

Preferred safe behavior for the site-level HIGGSFIELD profile:
- duration_options = []
- UI shows Auto / site-model dependent
- compiler generation_duration_hint becomes None unless the user explicitly provides a value from a future model-specific profile

Do not silently recommend an invalid 5s duration to a model that only supports 6/8/10.

### 3. Aspect / resolution choices

Do not pretend one list applies to every model.

Use a safe site-level value such as:
- aspect_ratio_options = ["site / model dependent"]
- resolution_options = ["site / model dependent"]

or equivalent UX that clearly indicates manual verification.

### 4. Generation mode capability

Higgsfield as a site can expose T2V / I2V / First-Last depending on model.

Keep the site-level profile broad, but warnings / notes must make clear that the selected model may not support the Shot generation_mode.

Do not block purely because the site-level profile cannot know the exact model.

### 5. supports_* booleans

If the current boolean model cannot represent model-dependent support, do not redesign all of G4A.

Document their meaning as:
"available on at least some models on this site"

and surface a model-dependent warning where relevant.

A later model-specific profile layer may refine this.

### 6. UI

On HIGGSFIELD selection, visibly show:
"모델별 지원 옵션이 다릅니다. Higgsfield에서 현재 선택한 모델의 duration / aspect / resolution / first-last frame 지원을 확인하세요."

Keep beginner readability.

### 7. Tests

Add/update tests for:
- Higgsfield profile does not hard-code universal 3/5/10 duration choices
- compile_manual_pack with HIGGSFIELD does not mutate Shot duration
- generation_duration_hint is None by default for site-level Higgsfield
- UI can render empty/model-dependent duration options
- camera preset mapping still works
- all existing 38 tests remain PASS
- full suite PASS
- compileall PASS
- git diff --check PASS

## Do not do

- no API
- no browser automation
- no model scraping
- no G4B
- no large refactor

## Completion report

[전체 진행률]
78%

[G4A.1 상태]
PASS / FAIL

[Higgsfield profile hardening]

[테스트]
xx passed / 0 failed

[다음 단계]
WAITING FOR FINAL G4A REVIEW
