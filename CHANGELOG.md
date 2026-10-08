# Changelog

## 1.0.4 — 2026-10-08

- STORY ROOM / SHOT BOARD에서 Windows 기본 흰색 배경이 노출되던 테마 회귀 수정
- QListWidget/ListView, G3 splitter, scroll viewport, form host를 명시적 dark surface로 고정
- 선택 행과 스크롤바도 다크 테마로 통일
- packaged/root `--g3-dark-ui-smoke-test`가 실제 렌더링의 흰색 픽셀 비율까지 검사
- G8 Series Studio / Session schema 1.0 / 기존 제작 로직은 변경하지 않음


## 1.0.3 — 2026-10-08

- World Bible 전체 초안 생성기를 선택 세계관 + 가사 앵커 + 감정곡선 + 음악 구조 기반으로 확장
- Time period / Palette / Materials / Weather / Lighting / Camera를 포함한 12개 제작 필드를 자동 완성
- BPM과 음악 변화점을 카메라 문법에 반영하되 모든 비트마다 컷하지 않는 원칙 유지
- 기존 World Bible 재생성 시 사용자 수정 내용을 덮어쓰기 전에 확인
- packaged/root World Bible smoke가 12개 제작 필드 완성 여부까지 검사
- Session schema는 계속 1.0으로 유지


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
