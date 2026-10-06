# G5B FINAL HARDENING — Concrete Music Intelligence Adapters

## Goal
Keep this inside the current G5B major step.
Current branch: g5-automated-qc
Target after this patch: 92% FINAL PASS.

Do NOT start Editor/Render.

## Review finding
The architecture for optional music backends is correct, but current code only:
- detects Beat This / Functional Structure availability;
- accepts an externally injected adapter;
- otherwise falls back to LIBROSA_BASIC.

That means installing the optional packages does not yet make the built-in "고급 음악 구조 분석" actually call them.

This must be closed before claiming Music Intelligence complete.

## Required changes

### 1. Concrete Beat This adapter
Implement a built-in adapter behind the existing protocol.

Requirements:
- lazy import only when selected;
- detect package/version;
- CPU by default;
- no forced GPU;
- no auto-download initiated silently;
- convert backend output into EnhancedMusicStructure;
- fill beat times;
- fill tempo where derivable;
- preserve backend provenance/version;
- on API mismatch or model unavailability: return LOAD_FAILED/fallback with a beginner-readable warning, not crash.

Important:
Beat This package APIs may vary. Keep all package-specific code in one adapter module/function so future maintenance is isolated.

### 2. Concrete functional structure adapter
Implement a built-in adapter for the currently supported All-In-One-compatible package/module available in the environment.

Requirements:
- lazy import;
- no default-install dependency;
- no app startup failure;
- map functional labels to:
  intro / verse / pre_chorus / chorus / bridge / outro / other
- convert boundaries/labels to MusicStructureSegment;
- tempo/beats/downbeats if exposed;
- record backend/version;
- if package API differs or dependencies are missing, graceful fallback with a clear warning.

Keep package-specific code isolated.

### 3. Backend registry
Provide one deterministic entry point, e.g.
- get_music_backend("BEAT_THIS")
- get_music_backend("FUNCTIONAL_STRUCTURE")

analyze_music_intelligence() should use built-in adapters when available instead of requiring callers to inject an adapter manually.

Injection may remain for tests.

### 4. Optional dependency metadata
Do not make heavy packages mandatory.

But music-intelligence extra must not remain misleadingly empty.

Either:
A. add verified installable optional packages with safe version ranges, OR
B. if Windows/package compatibility is not reliable enough, keep extra intentionally non-installing but document exact manual install commands and why.

Do not put a package into pyproject if it is known to break the default Windows install.

### 5. Beginner UI
When high-level backend is:
- AVAILABLE → enable high-level analysis action
- NOT_INSTALLED → show "고급 분석 구성요소가 설치되어 있지 않습니다."
- LOAD_FAILED → show "고급 분석을 불러오지 못했습니다. 기본 분석을 사용할 수 있습니다."

Do not expose stack traces in beginner surface.

### 6. Tests
Add tests for:
- built-in Beat This adapter selected when a fake/mock installed module is available
- backend API output normalization into EnhancedMusicStructure
- built-in functional adapter selected similarly
- label normalization
- package API mismatch gracefully falls back
- no heavy import at app startup
- no auto-download call
- existing injection path still works
- all 67+ tests stay green
- compileall
- git diff --check

## Completion
[전체 진행률]
92%

[G5B FINAL 상태]
PASS / FAIL

[Concrete Music Backends]

[Optional dependency safety]

[Beginner UI]

[전체 테스트]
xx passed / 0 failed

[다음 단계]
Editor / Render는 시작하지 말고 WAITING FOR REVIEW
