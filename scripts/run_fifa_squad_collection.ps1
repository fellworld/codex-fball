param(
    [string]$ProjectRoot = "H:\iwen-codex\codex-fball",
    [string]$PythonExe = "C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $ProjectRoot

& $PythonExe .\src\collectors\fifa_squad_collector.py --skip-download
& $PythonExe .\src\collectors\public_football_data.py
& $PythonExe .\src\collectors\match_context_collector.py
& $PythonExe .\src\features\team_club_features.py
& $PythonExe .\src\features\team_strength_rating.py
& $PythonExe .\src\features\match_prediction_inputs.py
& $PythonExe .\src\features\team_form_features.py
& $PythonExe .\src\features\team_power_ratings.py
& $PythonExe .\src\features\model_input_builder.py
& $PythonExe .\src\simulation\poisson_match_simulator.py
& $PythonExe .\src\simulation\group_stage_simulator.py
& $PythonExe .\src\reports\generate_prematch_reports.py
