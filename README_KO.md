# MV Director Studio 1.1.0

Windows에서 음악과 가사를 분석하고, 세계관·시리즈·캐릭터·Story Beat·Shot을 설계한 뒤 생성 결과를 QC하고 최종 MP4까지 만드는 로컬 뮤직비디오 제작 스튜디오입니다.

실행 파일은 항상:

`D:\03 musicvideo\MV Director Studio.exe`

하나만 사용합니다.

## 기본 제작 흐름

1. **01 MUSIC** — 음악 분석과 MV Director Timeline
2. **02 LYRICS & MEANING** — 가사 Line ID, 의미, 감정, 시각 앵커
3. **03 WORLD LAB** — 가사 기반 세계관 후보
4. **04 WORLD BIBLE** — 12개 제작 규칙 전체 초안/잠금
5. **05 REFERENCE VAULT** — 캐릭터·장소·색/빛·소품 Reference
6. **06 STORY ROOM** — Story Beat와 가사/음악 근거
7. **07 SHOT BOARD** — Shot, 카메라, continuity, Series Entity/Variant
8. **08 GENERATE** — Continuity Contract가 포함된 Prompt Pack
9. **RESULT / TAKES** — 생성 결과 등록 및 Shot당 accepted Take 1개
10. **09 QC** — 기술 QC와 선택형 시각/의미 QC
11. **10 EDIT / RENDER** — Rough Cut, Preview, Final MP4, Edit Plan/OTIO

5부작 프로젝트는 별도 **SERIES STUDIO**에서 Series Bible, Episode, Entity/Shape Grammar, Asset, Continuity, Episode Graph를 관리합니다.

## 1.1.0 Production Control

사이드바의 **PRODUCTION CONTROL**은 기존 페이지 번호를 바꾸지 않고 전체 제작 상태를 한 번에 검사합니다.

- 음악/가사/World/Series/Story/Shot/Prompt/Take/QC/Edit 상태
- Shot별 deterministic Continuity Contract
- World/Character/Reference 변경 뒤 오래된 Prompt Pack 자동 감지
- Director Coverage: 가사 근거, 주요 음악 변화점, Series context, 반복 action/visual strategy, Shot 호흡
- 생성 Queue 상태 저장/재열기
- Final Render의 길이·오디오·해상도·FPS·검은 프레임·Freeze·컷 구조 검증

## THE FIFTH VERDICT

내장 Series seed는 다섯 편을 사용합니다.

1. MUTE BELL
2. DOORLESS ROAD
3. SILENT WITNESS
4. MUTINY OF THE UNWRITTEN
5. GWAN: THE UNWRITTEN VERDICT

YOSUMI, SUZUGARA, TOJI, THE ARCHIVE, HOLLOW, STAMP, GWAN_SYMBOL, MARGIN_CITY_LOCATIONS를 Series Entity로 관리합니다. Hard Shape Grammar는 Asset Factory, Shot Board, Generate Continuity Contract까지 이어집니다.

## 생성 방법

### Manual
기존 방식입니다. Prompt Pack을 복사해 외부 웹 생성 도구에 사용하고 결과를 Take로 등록합니다.

### Local ComfyUI — 선택 기능
외부 유료 API 없이 사용자가 직접 실행한 **localhost ComfyUI**에 연결할 수 있습니다.

- ComfyUI 자동 설치/모델 다운로드 없음
- 기본적으로 localhost/127.0.0.1만 허용
- API-format workflow JSON은 사용자가 준비
- Prompt placeholder 자동 치환
- 최대 4개의 승인 Reference 이미지를 ComfyUI input으로 업로드
- 실행 결과를 확인해 video output을 candidate Take로 등록 가능
- Queue/PROMPT ID 상태는 Session JSON에 저장

지원 placeholder 예:

```text
{{MV_MAIN_PROMPT}}
{{MV_MOTION_PROMPT}}
{{MV_CAMERA_PROMPT}}
{{MV_NEGATIVE_PROMPT}}
{{MV_SHOT_ID}}
{{MV_DURATION}}
{{MV_ASPECT_RATIO}}
{{MV_OUTPUT_PREFIX}}
{{MV_FIRST_REFERENCE}}
{{MV_REFERENCE_1}}
{{MV_REFERENCE_2}}
{{MV_REFERENCE_3}}
{{MV_REFERENCE_4}}
```

## 파일 안전성

- Music, Take, Reference, Series Asset 원본은 프로그램이 임의 이동·삭제·변경하지 않습니다.
- Session JSON은 atomic 저장하고 정상본을 recovery에 회전 백업합니다.
- 프로그램 cache 정리는 AppData의 프로그램 소유 cache만 대상으로 합니다.
- Final Render는 임시 파일을 완성한 뒤 성공했을 때만 교체합니다.

## Final Render

H.264(libx264)와 AAC를 지원하는 FFmpeg/FFprobe가 필요합니다. 탐지 순서는 앱 설정 → `tools/ffmpeg/bin` → PATH입니다.

1.1.0 Final Verification은 media probe와 샘플 프레임 검사에 더해 PySceneDetect가 설치된 경우 실제 장면 전환 수를 보조 검사합니다. Scene cut 결과는 창작 판단을 대신하지 않고 경고로만 사용합니다.

## 선택 기능

기본 제작/렌더는 아래 기능이 없어도 동작해야 합니다.

- OpenCLIP — prompt/reference semantic QC
- Beat This — beat/downbeat 보조 분석
- Functional Structure — 음악 구조 보조 분석
- OpenTimelineIO — NLE 교환
- ComfyUI — 로컬 생성 자동화

선택 기능이 없거나 실패해도 앱 전체가 시작 불가 상태가 되어서는 안 됩니다.

## Release Gate

Windows root 실행본은 기존 모든 packaged/root gate와 함께 **G9 Production Megagate**를 통과해야 교체됩니다.

Production Megagate는 합성 5부작 프로젝트에서 Continuity Contract, 50 Shot Prompt Pack, stale detection, 500-job Queue, Session round-trip, 1100×720 UI contract, ComfyUI workflow materialization, 실제 FFmpeg final media verification을 검사합니다.

더 자세한 내용:
- `docs/G8_SERIES_STUDIO.md`
- `docs/G9_PRODUCTION_ORCHESTRATOR_MEGAGATE.md`
- `docs/KNOWN_LIMITATIONS.md`
