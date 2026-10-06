# Roadmap

## G0 — 설계 고정
- [x] 핵심 데이터 모델
- [x] Provider-neutral prompt compiler
- [x] 레퍼런스 역할 체계
- [x] QC 개념
- [ ] 실제 사용자의 1곡을 기준으로 데이터 모델 검증

## G0.5 — Lyrics → World Engine
- [x] TXT/SRT/LRC parser
- [x] ko/ja/en 언어 힌트
- [x] POV / 반복구절 / 감정 arc / semantic anchor
- [x] 세계관 후보 3개
- [x] LyricVisualBridge
- [x] Shot별 lyric evidence
- [x] Lyric grounding QC
- [ ] connected LLM structured JSON adapter
- [ ] 실제 사용자 가사 3곡으로 평가/튜닝

## G1 — Music Ingest ✅ v0.4 완료
- [x] WAV/MP3 import
- [x] librosa BPM / beats / onset
- [ ] SRT/LRC import
- [ ] faster-whisper optional transcription
- [x] section editor
- [x] timeline JSON export

## G2 — World Bible / Reference Vault
- [ ] PySide6 UI
- [ ] drag & drop references
- [ ] role + lock strength
- [ ] reference contact sheet
- [ ] character/location master lock

## G3 — Story Room / Shot Board
- [ ] story beat cards
- [ ] timeline assignment
- [ ] shot splitting
- [ ] continuity graph
- [ ] motif tracker
- [ ] shot diversity warning

## G4 — Provider Pack
- [ ] Manual website pack
- [ ] Runway connector
- [ ] Veo connector
- [ ] Luma connector
- [ ] fal/Kling connector
- [ ] ComfyUI workflow connector
- [ ] retry / status / cost log

## G5 — QC
- [ ] OpenCLIP prompt alignment
- [ ] reference similarity
- [ ] palette drift
- [ ] optical-flow jitter
- [ ] scene timing
- [ ] continuity score
- [ ] A/B compare

## G6 — Editor
- [ ] clip bin
- [ ] auto place by ShotSpec time
- [ ] FFmpeg concat/render
- [ ] transition rules
- [ ] proxy generation
- [ ] 1080p master export
- [ ] YouTube export preset

## G7 — Production Hardening
- [ ] SQLite migrations
- [ ] autosave
- [ ] crash recovery
- [ ] portable project package
- [ ] API key vault
- [ ] PyInstaller EXE
- [ ] GitHub Actions test/release
