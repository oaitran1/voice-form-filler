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

if (-not (Have winget)) {
    throw "winget is missing. Install 'App Installer' from the Microsoft Store, then run setup.ps1 again."
}
foreach ($tool in @(@{ Name = "uv"; Id = "astral-sh.uv" }, @{ Name = "ollama"; Id = "Ollama.Ollama" })) {
    if (-not (Have $tool.Name)) {
        Step "Installing $($tool.Name)"
        Run winget install --id $tool.Id -e --accept-source-agreements --accept-package-agreements
        RefreshPath
    }
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

Step "Checking it works (the 3 test stories, typed - no microphone; a few minutes)"
$null | uv run live-test --typed --no-open
if ($LASTEXITCODE) { throw "Stopped: the check failed." }

Write-Host "`nSet up."
if ($madeProfile) {
    Write-Host "  Next: open data\profile.yaml and type your company's details (it holds a sample company now)."
}
Write-Host '  Then: uv run record   (press Enter, tell what happened, say "stop recording")'
