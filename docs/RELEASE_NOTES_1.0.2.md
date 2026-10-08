# MV Director Studio 1.0.2 Hotfix

This hotfix addresses issues found during the first real World Bible workflow test.

- **World Bible save is now a real disk save.** If no Session JSON exists yet, the first save asks where to create it. Later saves write directly to that same file.
- If the user cancels the first file dialog, the app explicitly says the change is only in memory and does not claim that it was saved.
- The World Bible form now uses the dark application background and explicit visible field labels instead of the white/invisible-label layout.
- Sidebar release text and the initial status message use the current application version.
- Session schema remains 1.0.
- Existing single-root EXE, packaged/root smoke, music-analysis, render, stress and rollback release gates remain in force.
