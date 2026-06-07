param(
    [string]$SportKey = "soccer_fifa_world_cup",
    [string]$Markets = "h2h,totals,spreads",
    [string]$Regions = "us,uk,eu,au",
    [string]$ProjectRoot = "H:\iwen-codex\codex-fball",
    [string]$PythonExe = "C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $ProjectRoot

if (-not $env:THE_ODDS_API_KEY) {
    throw "THE_ODDS_API_KEY is not set."
}

& $PythonExe .\src\collectors\odds_collector.py `
    --sport-key $SportKey `
    --markets $Markets `
    --regions $Regions `
    --db-path .\data\raw\odds_snapshots\worldcup_2026_odds.sqlite
