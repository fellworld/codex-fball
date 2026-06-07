"""Build basic 2026 World Cup match context from public schedule data."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import urllib.request
from pathlib import Path


WORLDCUP_JSON_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

HOST_TEAMS = {
    "Mexico": "Mexico",
    "Canada": "Canada",
    "United States": "United States",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect match context from public World Cup schedule.")
    parser.add_argument("--schedule", default="data/processed/group_stage_schedule_cst.csv")
    parser.add_argument("--raw-output", default="data/raw/public/worldcup_2026_openfootball.json")
    parser.add_argument("--output", default="data/processed/match_context.csv")
    return parser.parse_args()


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "codex-fball/0.1"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def norm_name(value: str) -> str:
    return (
        value.replace("USA", "United States")
        .replace("Korea Republic", "South Korea")
        .replace("Czech Republic", "Czechia")
        .replace("Turkey", "Turkiye")
        .replace("Côte d'Ivoire", "Ivory Coast")
        .replace("DR Congo", "DR Congo")
        .replace("Congo DR", "DR Congo")
        .replace("Curaçao", "Curacao")
        .replace("Cape Verde", "Cape Verde")
        .replace("IR Iran", "Iran")
    )


def main() -> int:
    args = parse_args()
    schedule = read_csv(args.schedule)
    data = fetch_json(WORLDCUP_JSON_URL)
    checked_at = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    raw_path = Path(args.raw_output)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    public_matches = []
    for item in data.get("matches", []):
        team1 = item.get("team1") or ""
        team2 = item.get("team2") or ""
        if isinstance(team1, dict):
            team1 = team1.get("name", "")
        if isinstance(team2, dict):
            team2 = team2.get("name", "")
        public_matches.append(
            {
                "date": item.get("date", ""),
                "team_a": norm_name(team1),
                "team_b": norm_name(team2),
                "city": item.get("city", "") or item.get("ground", ""),
                "stadium": item.get("stadium", ""),
            }
        )

    rows = []
    for match in schedule:
        found = next(
            (
                item
                for item in public_matches
                if item["team_a"] == match["team_a"] and item["team_b"] == match["team_b"]
            ),
            {},
        )
        home_advantage = ""
        if match["team_a"] in HOST_TEAMS:
            home_advantage = match["team_a"]
        elif match["team_b"] in HOST_TEAMS:
            home_advantage = match["team_b"]
        rows.append(
            {
                "source_order": match["source_order"],
                "match_id": match["source_order"],
                "city": found.get("city", ""),
                "stadium": found.get("stadium", ""),
                "altitude_m": "",
                "temperature_c": "",
                "humidity_pct": "",
                "rest_days_team_a": "",
                "rest_days_team_b": "",
                "travel_distance_team_a_km": "",
                "travel_distance_team_b_km": "",
                "home_advantage_team": home_advantage,
                "context_notes": "City/stadium from openfootball worldcup.json when matched; weather/travel reserved for later.",
                "source": WORLDCUP_JSON_URL,
                "source_checked_at": checked_at,
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} match context rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
