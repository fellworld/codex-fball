param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8765,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $projectRoot "src\web_console.py"

if (!(Test-Path -LiteralPath $scriptPath)) {
    throw "Web console script not found: $scriptPath"
}

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($existing) {
    Write-Host "Web console is already running. PID: $($existing.OwningProcess)"
    Write-Host "Open: http://$HostAddress`:$Port/"
    return
}

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (!$python) {
    throw "Python command not found. Install Python or add it to PATH."
}

if ($Foreground) {
    Write-Host "Starting web console in foreground mode..."
    Write-Host "Open: http://$HostAddress`:$Port/"
    Push-Location $projectRoot
    try {
        & $python $scriptPath --host $HostAddress --port $Port
    }
    finally {
        Pop-Location
    }
    return
}

$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (!(Test-Path -LiteralPath $pythonw)) {
    $pythonw = $python
}

$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = $pythonw
$processInfo.Arguments = "`"$scriptPath`" --host $HostAddress --port $Port"
$processInfo.WorkingDirectory = $projectRoot
$processInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$processInfo.UseShellExecute = $true

$process = [System.Diagnostics.Process]::Start($processInfo)
Start-Sleep -Seconds 2

$started = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.OwningProcess -eq $process.Id } |
    Select-Object -First 1

if (!$started) {
    throw "Web console failed to start. Try: powershell -ExecutionPolicy Bypass -File scripts\start_web_console.ps1 -Foreground"
}

Write-Host "Web console started. PID: $($process.Id)"
Write-Host "Open: http://$HostAddress`:$Port/"
