# G2 Codex Handoff — World Bible + Reference Vault

## 현재 기준선

- 버전: v0.4
- 전체 진행률: 45%
- 테스트: 9/9 PASS
- 다음 Gate: G2 완료 시 58%

## Codex에 그대로 전달할 작업지시문

```text
프로젝트: MV Director Studio
현재 버전: v0.4
목표 Gate: G2 World Bible + Reference Vault

먼저 아래 문서를 읽고 임의로 아키텍처를 바꾸지 마라.
- README_KO.md
- docs/ARCHITECTURE.md
- docs/LYRICS_TO_WORLD.md
- docs/MUSIC_INGEST_G1.md
- docs/PROGRESS.md
- docs/G2_CODEX_HANDOFF.md

[핵심 제품 원칙]
이 프로그램은 AI 영상 사이트용 단순 프롬프트 생성기가 아니다.
Music → Lyrics Meaning → World → Reference → Story → Shot → Provider → QC를 연결하는 감독 시스템이다.
기존 lyric_line_ids, MVTimelineCue, WorldConcept의 추적성을 절대 깨지 마라.

[G2 구현 목표]
1. WorldConcept를 WorldBible draft로 승격하는 service를 구현한다.
2. Reference Vault 데이터 모델을 확장한다.
3. reference는 폴더 파일이 아니라 ID + role + lock strength + scope를 가진다.
4. role:
   - CHARACTER_MASTER
   - CHARACTER_WARDROBE
   - LOCATION_MASTER
   - PROP_MASTER
   - COLOR_LIGHT
   - COMPOSITION
   - CAMERA_MOTION
   - TEXTURE_MATERIAL
5. PySide6에 WORLD BIBLE / REFERENCE VAULT 탭을 활성화한다.
6. Reference Vault는 drag & drop과 파일 선택 둘 다 지원한다.
7. 초보자가 쉽게 쓰도록 작은 글씨/밀집 UI를 피한다.
8. reference thumbnail cache 구조를 core와 UI에서 분리한다.
9. 프로젝트 저장 시 상대경로/절대경로 정책을 명시한다.
10. 원본 reference 파일은 절대로 수정/삭제하지 않는다.
11. API key/provider 기능은 G2에서 구현하지 않는다.
12. 이미 있는 Music/Lyrics/World 기능을 회귀시키지 않는다.

[World Bible UI]
- premise
- emotional thesis
- reality rules
- time period
- visual language
- palette
- materials
- weather rules
- lighting rules
- camera rules
- recurring motifs
- forbidden elements
- lyric foundation

선택한 WorldConcept의 lyric evidence를 World Bible에서 확인 가능해야 한다.

[Reference Vault UI]
각 카드에 최소 표시:
- thumbnail
- Reference ID
- role
- lock strength
- file name/path
- notes
- Master 여부

[안전/보존]
- 사용자 파일 삭제 금지
- rename/move 금지
- API key 로그 금지
- git에 개인 reference 이미지 자동 추가 금지
- projects/**/references_local/ 기본 gitignore 고려

[테스트/PASS]
G2 완료 조건:
- 기존 테스트 전부 PASS
- WorldConcept → WorldBible draft unit test
- reference add/remove metadata test (원본 파일은 건드리지 않음)
- duplicate reference ID 방지 test
- missing file 상태 graceful handling test
- 한글/일본어/공백 포함 Windows path test
- session export/import roundtrip test
- UI module Python compile PASS

[완료 보고 형식]
1. 전체 진행률: 58%
2. 변경 파일
3. 구현 내용
4. 테스트 결과
5. 수동 확인이 필요한 UI 항목
6. 남은 위험
7. 다음 G3 진입 가능 여부

한 번에 G3 Story Room까지 진행하지 마라.
G2 PASS에서 멈추고 보고하라.
```

## Claude Code 사용 시점

G2 구현을 Codex로 먼저 진행하고, drag/drop UI 또는 PySide6 다중 화면 수정이 커질 경우 Claude Code를 보조로 사용해도 된다.
하지만 적극적인 Claude Code 병행은 G2 PASS(58%) 이후를 권장한다.
