param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$projectDirectory = $PSScriptRoot
$buildPython = Join-Path $projectDirectory ".venv-build\Scripts\python.exe"

Set-Location -LiteralPath $projectDirectory

if (-not (Test-Path -LiteralPath $buildPython)) {
    python -m venv (Join-Path $projectDirectory ".venv-build")
}

if (-not $SkipInstall) {
    & $buildPython -m pip install --upgrade pip
    & $buildPython -m pip install -r (Join-Path $projectDirectory "requirements-build.txt")
}

& $buildPython -m unittest discover -s tests -v
& $buildPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "SZU-Network-Guardian-v1.1.1" `
    (Join-Path $projectDirectory "main.py")

Write-Host ""
Write-Host "Build complete: $projectDirectory\dist\SZU-Network-Guardian-v1.1.1.exe"
