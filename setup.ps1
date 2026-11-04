# One-time setup on Windows. In PowerShell, in this folder:
#   powershell -ExecutionPolicy Bypass -File setup.ps1
# Installs the tools, downloads the two AI models (~10 GB, once), installs the app and checks it works.
# Safe to run again: anything already done is skipped. Your data\profile.yaml is never overwritten.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$AiModel = "gemma3:12b"  # same as DEFAULT_MODEL in src/vff/extract.py
$OllamaUrl = "http://localhost:11434/api/version"

function Step($message) { Write-Host "`n==> $message" }
function Have($command) { [bool](Get-Command $command -ErrorAction SilentlyContinue) }
function Run {
    & $args[0] $args[1..($args.Count - 1)]
    if ($LASTEXITCODE) { throw "Stopped: '$($args -join ' ')' failed." }
}
function RefreshPath {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}
function OllamaUp {
    try { Invoke-RestMethod $OllamaUrl -TimeoutSec 2 | Out-Null; $true } catch { $false }
}

function InstallWithWinget($id) {
    # $true if winget installed it. Only winget's own source: the Microsoft Store source often fails or asks questions.
    if (-not (Have winget)) { Write-Host "  (winget is not available)"; return $false }
    & winget install --id $id -e --source winget --accept-source-agreements --accept-package-agreements
    return ($LASTEXITCODE -eq 0)
}

if ($PSScriptRoot -match "OneDrive|iCloud|Dropbox") {
    Write-Host "`nNOTE: this folder is inside a synced folder (OneDrive). The app installs about 2 GB of files here;"
    Write-Host "      syncing them is slow and can break the install. If it fails, move the folder to C:\Users\<you>\ and run again."
}

if (-not (Have uv)) {
    Step "Installing uv (the Python tool)"
    if (-not (InstallWithWinget "astral-sh.uv")) {
        Write-Host "  winget could not install uv - using uv's own installer instead."
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    }
    RefreshPath
    if (-not (Have uv)) { throw "uv did not install. Install it from https://docs.astral.sh/uv/getting-started/installation/ then run setup.ps1 again." }
}

if (-not (Have ollama)) {
    Step "Installing Ollama (the local AI)"
    if (-not (InstallWithWinget "Ollama.Ollama")) {
        Write-Host "  winget could not install Ollama - downloading its installer instead (about 1 GB)."
        $installer = Join-Path $env:TEMP "OllamaSetup.exe"
        Invoke-WebRequest https://ollama.com/download/OllamaSetup.exe -OutFile $installer
        Start-Process $installer -ArgumentList "/VERYSILENT" -Wait
    }
    RefreshPath
    if (-not (Have ollama)) { throw "Ollama did not install. Install it from https://ollama.com/download then run setup.ps1 again." }
}

if (-not (Have ffmpeg)) {
    Step "Installing ffmpeg (only needed to read voice-memo and video files)"
    if (-not (InstallWithWinget "Gyan.FFmpeg")) {
        Write-Host "  Could not install ffmpeg. Live recording works without it; to use voice-memo files later, install it from https://ffmpeg.org/download.html"
    }
    RefreshPath
}

Step "Starting the local AI"
if (-not (OllamaUp)) {
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    foreach ($i in 1..20) { if (OllamaUp) { break }; Start-Sleep 1 }
}
if (-not (OllamaUp)) { throw "The local AI (Ollama) did not start. Open the Ollama app, then run setup.ps1 again." }

if (-not (ollama list | Select-String -Pattern "^$([regex]::Escape($AiModel)) ")) {
    Step "Downloading the local AI ($AiModel, about 8 GB, once)"
    Run ollama pull $AiModel
}

Step "Installing the app"
Run uv sync

Step "Downloading the speech-to-text model (about 1.5 GB, once)"
Run uv run make-report --setup

$madeProfile = $false
if (-not (Test-Path "data\profile.yaml")) {
    New-Item -ItemType Directory -Force "data" | Out-Null
    Copy-Item "templates\examples\company_profile.yaml" "data\profile.yaml"
    $madeProfile = $true
}

Step "Checking it works (one test story, typed - no microphone; about 3 minutes)"
$null | uv run live-test --typed --script 3 --no-open
if ($LASTEXITCODE) { throw "Stopped: the check failed." }

Write-Host "`nSet up."
Write-Host "  Full check of every test story, any time: uv run live-test --typed"
if ($madeProfile) {
    Write-Host "  Next: open data\profile.yaml and type your company's details (it holds a sample company now)."
}
Write-Host '  Then: uv run record   (press Enter, tell what happened, say "stop recording")'
