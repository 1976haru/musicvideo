# CHANGELOG v0.4 — Music Ingest

## 신규

- 실제 WAV/MP3/FLAC/OGG 음악 분석 엔진
- Tempo / Beat / Onset 분석
- RMS + spectral centroid + bandwidth 기반 변화점 후보
- AudioSection / AudioTransition / AudioMap 모델
- 4/8/16 beat 컷 cadence 참고값
- 음악 변화 + 가사 반복/경계 결합 `MV Director Timeline`
- 각 timeline cue에 lyric line IDs 보존
- MUSIC UI 탭 활성화
- 음악 파일 선택 → 분석 → Audio Map / MV Timeline 표시
- CLI `music-pack`
- CLI `timeline-pack`
- synthetic beat regression test

## 의도적으로 하지 않은 것

- 오디오만으로 Verse/Chorus를 확정하지 않음
- 모든 Beat에 자동 컷하지 않음
- 아직 외부 AI 영상 API를 호출하지 않음

## 개발 단계

G1 완료. 전체 45%.
이 버전부터 GitHub + Codex 1차 병행 시점.
다음 G2는 World Bible + Reference Vault.
