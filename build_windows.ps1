param([string]$OutputRoot = "release", [switch]$SkipTests, [switch]$NoBundleFFmpeg)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo
if (-not $SkipTests) {
    $env:QT_QPA_PLATFORM = "offscreen"
    python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
}
python -m compileall -q src
if ($LASTEXITCODE -ne 0) { throw "compileall failed." }
$dist = Join-Path $repo "$OutputRoot\dist"
$work = Join-Path $repo "$OutputRoot\build"
python -m PyInstaller --noconfirm --clean --distpath $dist --workpath $work MV_Director_Studio.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
$artifact = Join-Path $dist "MV_Director_Studio"
New-Item -ItemType Directory -Force -Path (Join-Path $artifact "tools\ffmpeg\bin") | Out-Null
Copy-Item README_FIRST.txt, CHANGELOG.md -Destination $artifact -Force
Copy-Item docs\RELEASE_NOTES_1.0.0.md, docs\KNOWN_LIMITATIONS.md -Destination $artifact -Force
$ffmpegStrategy = "app-local tools/ffmpeg/bin, then PATH"
if (-not $NoBundleFFmpeg) {
    $ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
    $ffprobe = (Get-Command ffprobe -ErrorAction SilentlyContinue).Source
    if ($ffmpeg -and $ffprobe) {
        Copy-Item $ffmpeg, $ffprobe -Destination (Join-Path $artifact "tools\ffmpeg\bin") -Force
        @(
            "FFmpeg source: https://ffmpeg.org/",
            "Windows build provider detected at release build time: https://www.gyan.dev/ffmpeg/builds/",
            "This distribution must comply with the license of the copied FFmpeg build (LGPL/GPL depending on configuration).",
            "Run tools/ffmpeg/bin/ffmpeg.exe -L to view the complete license notice.",
            "The MV Director Studio source repository does not store the FFmpeg binaries."
        ) |
            Set-Content -Encoding UTF8 (Join-Path $artifact "FFMPEG_LICENSE_AND_SOURCE.txt")
        $ffmpegStrategy = "bundled app-local FFmpeg/FFprobe; source/license documented"
    } else { throw "FFmpeg/FFprobe not found. Use -NoBundleFFmpeg only for a diagnostic build." }
}
$commit = (git rev-parse HEAD 2>$null)
if (-not $commit) { $commit = "unknown" }
$manifest = [ordered]@{
    app_version = "1.0.0"; session_schema = "1.0"; git_commit = $commit.Trim()
    build_time_utc = [DateTime]::UtcNow.ToString("o")
    python = (python --version 2>&1 | Out-String).Trim(); platform = [Environment]::OSVersion.VersionString
    packaging = "PyInstaller ONEDIR"; ffmpeg_strategy = $ffmpegStrategy
    optional_components = @("OpenCLIP:not bundled", "Beat This:not bundled", "Functional Structure:not bundled", "OpenTimelineIO:optional")
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $artifact "release_manifest.json")
$env:PYTHONPATH = $null
$env:MVSTUDIO_APPDATA = (Join-Path $repo "$OutputRoot\smoke-appdata")
& (Join-Path $artifact "MV Director Studio.exe") --smoke-test
if ($LASTEXITCODE -ne 0) { throw "Packaged smoke test failed." }
& (Join-Path $artifact "MV Director Studio.exe") --render-smoke-test
if ($LASTEXITCODE -ne 0) { throw "Packaged FFmpeg render smoke test failed." }
Write-Host "RELEASE ARTIFACT: $artifact"
