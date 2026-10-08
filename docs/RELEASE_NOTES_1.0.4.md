# MV Director Studio 1.0.4

## G3 dark-theme hotfix

This release fixes a Windows palette regression in **06 STORY ROOM** and **07 SHOT BOARD** where list, scroll and form surfaces could render with the operating-system default white background.

The fix explicitly themes:
- evidence / Story Beat / Shot lists;
- G3 splitter and handles;
- detail scroll viewport;
- form host and pane backgrounds;
- selected rows and scrollbars.

A new `--g3-dark-ui-smoke-test` renders the critical widgets offscreen and fails the release if near-white pixels dominate any target surface.

No Session schema change. G8 Series Studio remains intact. The root executable remains:
`D:\03 musicvideo\MV Director Studio.exe`
