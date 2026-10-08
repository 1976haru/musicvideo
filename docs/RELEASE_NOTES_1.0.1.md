# MV Director Studio 1.0.1 Hotfix

1.0.1 fixes a Windows packaged-build failure discovered during the first real music-ingest test.

- Fixes missing SciPy Array API compatibility modules in the PyInstaller ONEDIR build.
- Adds a packaged WAV music-analysis smoke test that executes the real librosa → SciPy analysis path.
- A release build now fails if packaged music analysis does not work.

No session-schema change. Existing 1.0 sessions remain compatible.
