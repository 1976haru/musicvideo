# Changelog

## 1.0.1 — 2026-10-08

- Windows ONEDIR 배포본에서 음악 분석 시 누락되던 SciPy Array API compatibility 하위 모듈을 명시적으로 패키징
- `--music-analysis-smoke-test`를 추가해 실제 WAV → librosa → SciPy 분석이 배포본에서 통과해야 빌드 성공
- SciPy를 music dependency에 명시해 release dependency 계약을 분명히 함


## 1.0.0 — 2026-10-07

- Music/Lyrics 분석, World Bible, Reference Vault, Story/Shot Board
- Manual Generation Studio 및 Result/Take Manager
- Technical/Temporal/Visual/Semantic QC와 Director/Music Intelligence
- accepted Take 기반 Rough Cut, Preview, FFmpeg Final Render, Edit Plan/OTIO export
- Windows ONEDIR packaging, First-run Doctor, rotating backup/log, crash recovery, diagnostics
- Session schema 1.0 및 이전 schema 하위호환
