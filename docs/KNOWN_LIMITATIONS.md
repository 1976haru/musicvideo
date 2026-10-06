# Known Limitations — 1.0.0

- AI 영상 생성 자체는 manual website workflow 중심입니다. Provider API는 현재 기능이 아닙니다.
- OpenCLIP, Beat This, Functional Structure, OpenTimelineIO는 선택 기능입니다.
- Semantic QC는 보조 판단이며 자동 ACCEPT/REJECT를 하지 않습니다.
- OpenCLIP은 정확한 얼굴 identity 확인기가 아닙니다.
- Director Intelligence는 API 없는 외부 AI JSON 교환 방식입니다.
- 외부 package/model API 변경 시 optional adapter 수정이 필요할 수 있습니다.
- 긴 render 속도는 PC 성능과 FFmpeg encoder 성능에 영향을 받습니다.
- OTIO 호환성은 외부 NLE와 plugin 환경에 따라 다릅니다.
- 기본 final renderer는 FFmpeg의 libx264와 AAC encoder가 필요합니다.
