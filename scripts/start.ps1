[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$SkipPrepare,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "未找到 .venv。请先运行: python -m venv .venv"
}

$npmCommand = Get-Command npm.exe -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    throw "未找到 npm，请先安装 Node.js 24+。"
}
$npm = $npmCommand.Path

if ($Install) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
    & $python -m pip install -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }

    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    & $npm --prefix web ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
}

if (-not $SkipPrepare) {
    Write-Host "Preparing local PDF samples..." -ForegroundColor Cyan
    & $python scripts/prepare_samples.py
    if ($LASTEXITCODE -ne 0) { throw "Sample preparation failed." }
}

$shell = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Path
if (-not $shell) {
    $shell = (Get-Command powershell.exe -ErrorAction SilentlyContinue).Path
}
if (-not $shell) {
    throw "未找到 PowerShell，无法打开独立服务窗口。"
}

$backendCommand = "Set-Location -LiteralPath '$root'; & '$python' -m uvicorn paperx.api:app --app-dir backend --host 127.0.0.1 --port 8000"
$frontendCommand = "Set-Location -LiteralPath '$root'; & '$npm' --prefix web run dev"

Start-Process -FilePath $shell -WorkingDirectory $root -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $backendCommand
) | Out-Null

Start-Process -FilePath $shell -WorkingDirectory $root -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $frontendCommand
) | Out-Null

Write-Host "Backend:  http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "Close the two service windows to stop the project." -ForegroundColor DarkGray

if ($OpenBrowser) {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:5173"
}
