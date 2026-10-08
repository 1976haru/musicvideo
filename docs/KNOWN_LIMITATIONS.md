# Known Limitations — 1.1.0

- 생성 모델 자체의 미학적 품질은 사용하는 외부 웹 도구 또는 로컬 ComfyUI workflow/model에 영향을 받습니다.
- ComfyUI 연결은 선택 기능이며 자동 설치, checkpoint 다운로드, workflow 자동 제작을 수행하지 않습니다.
- 기본 ComfyUI bridge는 안전을 위해 localhost/127.0.0.1/::1만 허용합니다.
- 최대 4개의 이미지 Reference를 workflow placeholder로 전달합니다. workflow가 해당 placeholder를 사용하도록 사용자가 준비해야 합니다.
- OpenCLIP, Beat This, Functional Structure, OpenTimelineIO는 선택 기능입니다.
- OpenCLIP/semantic QC는 보조 판단이며 얼굴 identity나 캐릭터 동일성을 절대적으로 보증하지 않습니다.
- Production Readiness/Director Coverage는 규칙 기반 진단이며 창작 판단을 자동으로 대체하지 않습니다.
- PySceneDetect의 실제 cut 수는 최종 렌더 이상 징후를 찾기 위한 보조 경고이며, 의도한 카메라 내부 변화도 cut처럼 감지될 수 있습니다.
- 긴 Final Render와 PySceneDetect 분석 속도는 PC/codec/해상도에 영향을 받습니다.
- SAM2/DINOv2 같은 무거운 시각 모델은 Windows core release에 포함하지 않습니다. 향후 선택 plugin 후보입니다.
- OTIO 호환성은 외부 NLE와 plugin 환경에 따라 다릅니다.
- 기본 final renderer는 FFmpeg의 libx264와 AAC encoder가 필요합니다.
