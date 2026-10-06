# G4A Claude Code Handoff — Manual Generation Studio

## 목표

- 현재: 72%
- 목표: 78%
- 작업 브랜치: `g4-manual-generation-studio`
- 범위: Manual Generation Studio only
- G4B Result / Take Manager는 아직 시작하지 않는다.

## 먼저 읽기

1. docs/G4_MANUAL_GENERATION_STUDIO.md
2. README_KO.md
3. PROGRESS.md
4. docs/ARCHITECTURE.md
5. src/mvstudio/models.py
6. src/mvstudio/session.py
7. src/mvstudio/story_engine.py
8. src/mvstudio/g3_ui.py
9. src/mvstudio/prompt_compiler.py
10. src/mvstudio/ui_app.py
11. 전체 tests

먼저 baseline 전체 테스트를 실행하고 현재 구조를 보고한다.

## 구현 우선순위

1. Manual Site Profile core
2. GENERIC + HIGGSFIELD profiles
3. ManualGenerationPack core
4. session 기반 generation context
5. structured prompt compiler
6. readiness validation
7. GENERATE UI 활성화
8. copy buttons
9. single-shot TXT/JSON export
10. session save/open/autosave integration
11. tests

## UI 원칙

초보자가 보자마자 순서를 알 수 있어야 한다.

1. Shot 확인
2. Reference 준비
3. Main Prompt 복사
4. Motion / Camera 복사
5. Negative 복사
6. 사이트에서 생성
7. 결과 등록은 다음 G4B

주요 버튼 42~44px 이상.
긴 한글/일본어 wrap.
작은 글씨와 과밀 배치 금지.

## 매우 중요

API 작업 금지.
브라우저 자동화 금지.
Higgsfield 로그인/클릭 자동화 금지.
G4B 결과 영상 관리 시작 금지.

기존 `compile_shot()` 및 G0-G3 테스트를 깨지 않는다.

## 중간 보고

구현 전에:
[현재 구조]
[Prompt Compiler 재사용 계획]
[Session 연결 방식]
[추가 모델]
[UI 구조]
[수정 예정 파일]
[테스트 계획]

그 후 계속 구현한다.

완료 후 docs/G4_MANUAL_GENERATION_STUDIO.md의 G4A completion report 형식을 사용하고 78%에서 멈춘다.
