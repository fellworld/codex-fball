"""Build team-level club distribution features from squad player rows."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


BIG_FIVE_COUNTRY_CODES = {"ENG", "ESP", "ITA", "GER", "FRA"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build club distribution features.")
    parser.add_argument("--players-input", default="data/processed/squad_players.csv")
    parser.add_argument("--output", default="data/processed/team_club_features.csv")
    return parser.parse_args()


def read_players(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_features(players: list[dict[str, str]]) -> list[dict[str, str]]:
    by_team: dict[str, list[dict[str, str]]] = defaultdict(list)
    for player in players:
        by_team[player["team"]].append(player)

    rows: list[dict[str, str]] = []
    for team, team_players in sorted(by_team.items()):
        club_counts = Counter(player["club"] for player in team_players if player["club"])
        country_counts = Counter(
            player["club_country_code"]
            for player in team_players
            if player["club_country_code"]
        )
        big_five_count = sum(
            1
            for player in team_players
            if player["club_country_code"] in BIG_FIVE_COUNTRY_CODES
        )
        domestic_count = sum(
            1
            for player in team_players
            if player["club_country_code"] == player["team_code"]
        )

        top_clubs = "; ".join(f"{club}:{count}" for club, count in club_counts.most_common(5))
        top_countries = "; ".join(
            f"{country}:{count}" for country, count in country_counts.most_common(5)
        )

        rows.append(
            {
                "team": team,
                "team_code": team_players[0]["team_code"],
                "squad_size": str(len(team_players)),
                "unique_clubs": str(len(club_counts)),
                "unique_club_countries": str(len(country_counts)),
                "domestic_club_players": str(domestic_count),
                "big_five_league_country_players": str(big_five_count),
                "top_clubs": top_clubs,
                "top_club_country_codes": top_countries,
            }
        )
    return rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "team",
        "team_code",
        "squad_size",
        "unique_clubs",
        "unique_club_countries",
        "domestic_club_players",
        "big_five_league_country_players",
        "top_clubs",
        "top_club_country_codes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    players = read_players(Path(args.players_input))
    rows = build_features(players)
    write_rows(Path(args.output), rows)
    print(f"Wrote {len(rows)} team club feature rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
