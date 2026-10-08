# Changelog

## 1.0.2 — 2026-10-08

- World Bible 저장 버튼이 메모리 갱신으로 끝나지 않고 실제 Session JSON에 즉시 저장되도록 수정
- 첫 저장 시 저장 위치를 요청하고, 취소 시 "파일 저장되지 않음"을 명확히 안내
- World Bible QFormLayout의 흰 배경/보이지 않는 라벨 문제를 다크 테마로 수정
- 좌측 Release 버전과 초기 상태 문구를 실제 APP_VERSION과 동기화
- 기존 단일 root EXE / staging / stress / rollback release gate 유지


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
