"""Build recent national-team form features from public international results."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path


TEAM_ALIASES = {
    "United States": "USA",
    "US Virgin Islands": "US Virgin Islands",
    "South Korea": "Korea Republic",
    "Korea Republic": "Korea Republic",
    "Czech Republic": "Czechia",
    "Côte d'Ivoire": "Côte D'Ivoire",
    "Ivory Coast": "Côte D'Ivoire",
    "DR Congo": "Congo DR",
    "Democratic Republic of the Congo": "Congo DR",
    "Cape Verde": "Cabo Verde",
    "Curaçao": "Curaçao",
    "Curacao": "Curaçao",
    "Iran": "IR Iran",
    "Turkey": "Türkiye",
    "Turkiye": "Türkiye",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build recent form features.")
    parser.add_argument("--results", default="data/raw/public/international_results.csv")
    parser.add_argument("--elo", default="data/processed/public_elo_ratings.csv")
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--output", default="data/processed/team_form_features.csv")
    parser.add_argument("--team-form-output", default="data/processed/team_form_ratings.csv")
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def canonical(name: str) -> str:
    return TEAM_ALIASES.get(name, name)


def norm_rating(value: float, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    return max(0.0, min(100.0, (value - low) / (high - low) * 100.0))


def main() -> int:
    args = parse_args()
    elo_rows = read_csv(args.elo)
    team_names = [row["team"] for row in elo_rows]
    elo_by_team = {row["team"]: float(row["elo_rating"]) for row in elo_rows if row.get("elo_rating")}
    elo_rank_by_team = {row["team"]: int(row["elo_rank"]) for row in elo_rows if row.get("elo_rank")}
    code_by_team = {row["team"]: row["team_code"] for row in elo_rows if row.get("team_code")}

    matches_by_team: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in read_csv(args.results):
        home = canonical(row["home_team"])
        away = canonical(row["away_team"])
        if home not in team_names and away not in team_names:
            continue
        try:
            match_date = dt.date.fromisoformat(row["date"])
            home_score = int(row["home_score"])
            away_score = int(row["away_score"])
        except ValueError:
            continue

        for team, opponent, gf, ga, is_home in [
            (home, away, home_score, away_score, True),
            (away, home, away_score, home_score, False),
        ]:
            if team not in team_names:
                continue
            result = "W" if gf > ga else "D" if gf == ga else "L"
            matches_by_team[team].append(
                {
                    "date": match_date,
                    "opponent": opponent,
                    "gf": gf,
                    "ga": ga,
                    "result": result,
                    "opponent_elo": elo_by_team.get(opponent, 1500.0),
                    "tournament": row["tournament"],
                    "neutral": row["neutral"],
                }
            )

    rows: list[dict[str, str]] = []
    form_rating_values: dict[str, float] = {}
    for team in team_names:
        recent = sorted(matches_by_team.get(team, []), key=lambda item: item["date"], reverse=True)[: args.window]
        played = len(recent)
        wins = sum(1 for m in recent if m["result"] == "W")
        draws = sum(1 for m in recent if m["result"] == "D")
        losses = sum(1 for m in recent if m["result"] == "L")
        gf = sum(int(m["gf"]) for m in recent)
        ga = sum(int(m["ga"]) for m in recent)
        avg_gf = gf / played if played else 0.0
        avg_ga = ga / played if played else 0.0
        points_per_match = (wins * 3 + draws) / played if played else 0.0
        strength_of_schedule = sum(float(m["opponent_elo"]) for m in recent) / played if played else 1500.0
        raw_form = points_per_match * 18.0 + avg_gf * 10.0 - avg_ga * 7.0 + (strength_of_schedule - 1500.0) / 20.0
        form_rating_values[team] = raw_form
        rows.append(
            {
                "team": team,
                "team_code": code_by_team.get(team, ""),
                "recent_matches": str(played),
                "recent_wins": str(wins),
                "recent_draws": str(draws),
                "recent_losses": str(losses),
                "recent_goals_for": str(gf),
                "recent_goals_against": str(ga),
                "avg_goals_for": f"{avg_gf:.3f}",
                "avg_goals_against": f"{avg_ga:.3f}",
                "points_per_match": f"{points_per_match:.3f}",
                "strength_of_schedule": f"{strength_of_schedule:.1f}",
                "raw_form_score": f"{raw_form:.3f}",
                "latest_match_date": recent[0]["date"].isoformat() if recent else "",
                "source": "https://raw.githubusercontent.com/martj42/international_results/master/results.csv",
                "source_checked_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
            }
        )

    lows, highs = min(form_rating_values.values()), max(form_rating_values.values())
    for row in rows:
        row["form_rating"] = f"{norm_rating(float(row['raw_form_score']), lows, highs):.2f}"

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "team",
        "team_code",
        "recent_matches",
        "recent_wins",
        "recent_draws",
        "recent_losses",
        "recent_goals_for",
        "recent_goals_against",
        "avg_goals_for",
        "avg_goals_against",
        "points_per_match",
        "strength_of_schedule",
        "raw_form_score",
        "form_rating",
        "latest_match_date",
        "source",
        "source_checked_at",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    form_output = Path(args.team_form_output)
    with form_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "team",
                "team_code",
                "fifa_rank",
                "elo_rating",
                "recent_matches",
                "recent_wins",
                "recent_draws",
                "recent_losses",
                "recent_goals_for",
                "recent_goals_against",
                "avg_goals_for",
                "avg_goals_against",
                "strength_of_schedule",
                "form_notes",
                "source",
                "source_checked_at",
            ],
        )
        writer.writeheader()
        for row in rows:
            team = row["team"]
            writer.writerow(
                {
                    "team": team,
                    "team_code": row["team_code"],
                    "fifa_rank": elo_rank_by_team.get(team, ""),
                    "elo_rating": f"{elo_by_team.get(team, 0):.0f}" if team in elo_by_team else "",
                    "recent_matches": row["recent_matches"],
                    "recent_wins": row["recent_wins"],
                    "recent_draws": row["recent_draws"],
                    "recent_losses": row["recent_losses"],
                    "recent_goals_for": row["recent_goals_for"],
                    "recent_goals_against": row["recent_goals_against"],
                    "avg_goals_for": row["avg_goals_for"],
                    "avg_goals_against": row["avg_goals_against"],
                    "strength_of_schedule": row["strength_of_schedule"],
                    "form_notes": "fifa_rank currently uses Elo rank proxy until full FIFA table is exposed/filled.",
                    "source": row["source"],
                    "source_checked_at": row["source_checked_at"],
                }
            )

    print(f"Wrote {len(rows)} team form feature rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
