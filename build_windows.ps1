param([switch]$NoBundleFFmpeg, [switch]$ArtifactOnly)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$staging = Join-Path $repo ".build_staging"
$dist = Join-Path $staging "dist"
$work = Join-Path $staging "build"
$artifact = Join-Path $dist "MV_Director_Studio"
$rootExe = Join-Path $repo "MV Director Studio.exe"
$backup = Join-Path $repo ".previous_release"
$runtimeNames = @("MV Director Studio.exe", "_internal", "tools", "release_manifest.json")

function Invoke-Gate([string]$Name, [scriptblock]$Action) {
    Write-Host "[GATE] $Name"
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "$Name failed (exit $LASTEXITCODE)." }
}
function Invoke-ExeGate([string]$Name, [string]$ExePath, [string[]]$Arguments) {
    Write-Host "[GATE] $Name"
    $process = Start-Process -FilePath $ExePath -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw "$Name failed (exit $($process.ExitCode))." }
}
function Assert-AppNotRunning {
    if (-not (Test-Path -LiteralPath $rootExe)) { return }
    $resolved = [IO.Path]::GetFullPath($rootExe)
    $running = Get-Process -Name "MV Director Studio" -ErrorAction SilentlyContinue | Where-Object {
        try { [IO.Path]::GetFullPath($_.Path) -eq $resolved } catch { $false }
    }
    if ($running) { throw "Close MV Director Studio before updating." }
}
function Resolve-RealTool([string]$Name) {
    $candidates = New-Object System.Collections.Generic.List[string]
    $repoTool = Join-Path $repo ("tools\ffmpeg\bin\" + $Name + ".exe")
    if (Test-Path -LiteralPath $repoTool) { $candidates.Add($repoTool) }

    $command = Get-Command ($Name + ".exe") -ErrorAction SilentlyContinue
    if ($command -and $command.Source) { $candidates.Add($command.Source) }

    $chocoRoot = $env:ChocolateyInstall
    if (-not $chocoRoot) { $chocoRoot = "C:\ProgramData\chocolatey" }
    $chocoTools = Join-Path $chocoRoot "lib\ffmpeg\tools"
    if (Test-Path -LiteralPath $chocoTools) {
        Get-ChildItem -LiteralPath $chocoTools -Recurse -File -Filter ($Name + ".exe") -ErrorAction SilentlyContinue |
            Sort-Object Length -Descending |
            ForEach-Object { $candidates.Add($_.FullName) }
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $item = Get-Item -LiteralPath $candidate
        # Chocolatey shims are tiny wrappers; real FFmpeg/FFprobe binaries are much larger.
        if ($item.Length -lt 1048576) { continue }
        try {
            $process = Start-Process -FilePath $candidate -ArgumentList @("-version") -Wait -PassThru -WindowStyle Hidden
            if ($process.ExitCode -eq 0) { return $candidate }
        } catch {}
    }
    return $null
}

function Copy-Runtime([string]$From, [string]$To) {
    foreach ($name in $runtimeNames) {
        $source = Join-Path $From $name
        if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $To -Recurse -Force }
    }
}
function Remove-RootRuntime {
    foreach ($name in $runtimeNames) {
        $target = Join-Path $repo $name
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
    }
}

# Nothing in the active root runtime is changed before all packaged gates pass.
if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
New-Item -ItemType Directory -Force -Path $staging | Out-Null
$env:QT_QPA_PLATFORM = "offscreen"
Invoke-Gate "pytest" { python tests\run_pytest_release.py }
Invoke-Gate "compileall" { python -m compileall -q src }
Invoke-Gate "git diff --check" { git diff --check }
Invoke-Gate "PyInstaller staging build" { python -m PyInstaller --noconfirm --clean --distpath $dist --workpath $work MV_Director_Studio.spec }

New-Item -ItemType Directory -Force -Path (Join-Path $artifact "tools\ffmpeg\bin") | Out-Null
$ffmpegStrategy = "app-local tools/ffmpeg/bin, then PATH"
if (-not $NoBundleFFmpeg) {
    $ffmpeg = Resolve-RealTool "ffmpeg"
    $ffprobe = Resolve-RealTool "ffprobe"
    if (-not $ffmpeg -or -not $ffprobe) { throw "Real FFmpeg/FFprobe binaries not found." }
    Copy-Item -LiteralPath $ffmpeg -Destination (Join-Path $artifact "tools\ffmpeg\bin\ffmpeg.exe") -Force
    Copy-Item -LiteralPath $ffprobe -Destination (Join-Path $artifact "tools\ffmpeg\bin\ffprobe.exe") -Force
    $ffmpegStrategy = "bundled app-local FFmpeg/FFprobe"
}
$commit = (git rev-parse HEAD 2>$null)
if (-not $commit) { $commit = "unknown" }
[ordered]@{
    app_version = "1.1.0"; session_schema = "1.0"; git_commit = $commit.Trim()
    build_time_utc = [DateTime]::UtcNow.ToString("o")
    python = (python --version 2>&1 | Out-String).Trim(); platform = [Environment]::OSVersion.VersionString
    packaging = "PyInstaller ONEDIR"; ffmpeg_strategy = $ffmpegStrategy; entrypoint = "MV Director Studio.exe"
} | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $artifact "release_manifest.json")

$env:PYTHONPATH = $null
$env:MVSTUDIO_APPDATA = Join-Path $staging "packaged-appdata"
$stagedExe = Join-Path $artifact "MV Director Studio.exe"
Invoke-ExeGate "packaged smoke" $stagedExe @("--smoke-test")
Invoke-ExeGate "packaged music analysis" $stagedExe @("--music-analysis-smoke-test")
Invoke-ExeGate "packaged render" $stagedExe @("--render-smoke-test")
Invoke-ExeGate "release stress" $stagedExe @("--release-stress-test")
Invoke-ExeGate "packaged World Bible save/UI" $stagedExe @("--world-bible-smoke-test")
Invoke-ExeGate "packaged Series Studio" $stagedExe @("--series-studio-smoke-test")
Invoke-ExeGate "packaged G3 dark UI" $stagedExe @("--g3-dark-ui-smoke-test")
Invoke-ExeGate "packaged Production Megagate" $stagedExe @("--production-megagate-test")
if ($ArtifactOnly) { Write-Host "ARTIFACT READY (root deploy skipped): $artifact"; exit 0 }

Assert-AppNotRunning
$deployed = $false
try {
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    Copy-Runtime $repo $backup
    Remove-RootRuntime
    Copy-Runtime $artifact $repo
    $deployed = $true

    $env:MVSTUDIO_APPDATA = Join-Path $staging "root-appdata"
    Invoke-ExeGate "root smoke" $rootExe @("--smoke-test")
    Invoke-ExeGate "root music analysis" $rootExe @("--music-analysis-smoke-test")
    Invoke-ExeGate "root render" $rootExe @("--render-smoke-test")
    Invoke-ExeGate "root release stress" $rootExe @("--release-stress-test")
    Invoke-ExeGate "root GUI music action" $rootExe @("--gui-music-test")
    Invoke-ExeGate "root World Bible save/UI" $rootExe @("--world-bible-smoke-test")
    Invoke-ExeGate "root Series Studio" $rootExe @("--series-studio-smoke-test")
    Invoke-ExeGate "root G3 dark UI" $rootExe @("--g3-dark-ui-smoke-test")
    Invoke-ExeGate "root Production Megagate" $rootExe @("--production-megagate-test")

    foreach ($path in @((Join-Path $repo "dist"), (Join-Path $repo "build"), (Join-Path $repo "release"))) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    }
    Get-ChildItem -LiteralPath $repo -Directory -Filter "release_*" -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.FullName.StartsWith($repo + [IO.Path]::DirectorySeparatorChar)) { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
    }
    Remove-Item -LiteralPath $staging -Recurse -Force
    $failedRelease = Join-Path $repo ".failed_release"
    if (Test-Path -LiteralPath $failedRelease) { Remove-Item -LiteralPath $failedRelease -Recurse -Force }
    Write-Host "LOCAL RELEASE READY: $rootExe"
} catch {
    if ($deployed) {
        Write-Warning "Root verification/deploy failed; restoring the previous runtime."
        Remove-RootRuntime
        Copy-Runtime $backup $repo
    }
    throw
}
