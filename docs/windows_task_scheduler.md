# Windows task scheduler setup for odds snapshots

This project needs two scheduled runs:

- Daily full snapshot.
- Match-day snapshot every 2 hours before kickoff.

The collector requires `THE_ODDS_API_KEY` and a working Python installation.

## Daily snapshot

Run once per day at 12:00 Asia/Shanghai:

```powershell
schtasks /Create /TN "CodexFball Odds Daily" /SC DAILY /ST 12:00 /TR "powershell.exe -ExecutionPolicy Bypass -File H:\iwen-codex\codex-fball\scripts\run_odds_snapshot.ps1"
```

## Match-day 2-hour snapshot

For the tournament period, run every 2 hours:

```powershell
schtasks /Create /TN "CodexFball Odds Matchday 2h" /SC HOURLY /MO 2 /TR "powershell.exe -ExecutionPolicy Bypass -File H:\iwen-codex\codex-fball\scripts\run_odds_snapshot.ps1"
```

Before enabling this, add date gating if you only want it active on exact match days. The simplest operational approach is:

1. Enable the 2-hour task on the first match day.
2. Disable it after the final match day.
3. Keep the daily task active for long-range trend collection.

## Environment variable

Set the API key for the user account that runs the scheduled task:

```powershell
setx THE_ODDS_API_KEY "your_api_key_here"
```

Open a new terminal after running `setx`.

