"""Build group-stage match input rows for the prediction model."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build match prediction input table.")
    parser.add_argument("--schedule", default="data/processed/group_stage_schedule_cst.csv")
    parser.add_argument("--ratings", default="data/processed/team_strength_ratings.csv")
    parser.add_argument("--tactics", default="data/processed/team_tactical_profiles.csv")
    parser.add_argument("--aliases", default="config/team_aliases.csv")
    parser.add_argument("--output", default="data/processed/match_prediction_inputs.csv")
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_aliases(path: str) -> dict[str, str]:
    alias_path = Path(path)
    if not alias_path.exists():
        return {}
    with alias_path.open(newline="", encoding="utf-8") as handle:
        return {
            row["display_name"]: row["canonical_name"]
            for row in csv.DictReader(handle)
            if row.get("display_name") and row.get("canonical_name")
        }


def lean_from_gap(gap: float) -> str:
    abs_gap = abs(gap)
    if abs_gap >= 16:
        return "over_watch"
    if abs_gap <= 4:
        return "draw_or_under_watch"
    return "neutral"


def main() -> int:
    args = parse_args()
    schedule = read_csv(args.schedule)
    ratings = {row["team"]: row for row in read_csv(args.ratings)}
    tactics = {row["team"]: row for row in read_csv(args.tactics)}
    aliases = read_aliases(args.aliases)

    rows: list[dict[str, str]] = []
    for match in schedule:
        team_a = match["team_a"]
        team_b = match["team_b"]
        team_a_canonical = aliases.get(team_a, team_a)
        team_b_canonical = aliases.get(team_b, team_b)
        rating_a = float(ratings.get(team_a_canonical, {}).get("club_quality_rating", 50))
        rating_b = float(ratings.get(team_b_canonical, {}).get("club_quality_rating", 50))
        diff = rating_a - rating_b
        favorite = team_a if diff > 1.5 else team_b if diff < -1.5 else "even"

        team_a_tactics = tactics.get(team_a_canonical, {})
        team_b_tactics = tactics.get(team_b_canonical, {})

        rows.append(
            {
                "source_order": match["source_order"],
                "group": match["group"],
                "date_china": match["date_china"],
                "time_china": match["time_china"],
                "team_a": team_a,
                "team_b": team_b,
                "team_a_canonical": team_a_canonical,
                "team_b_canonical": team_b_canonical,
                "team_a_rating": f"{rating_a:.2f}",
                "team_b_rating": f"{rating_b:.2f}",
                "rating_diff_a_minus_b": f"{diff:.2f}",
                "initial_favorite": favorite,
                "initial_total_goals_lean": lean_from_gap(diff),
                "team_a_style": team_a_tactics.get("style_tag_primary", ""),
                "team_b_style": team_b_tactics.get("style_tag_primary", ""),
                "team_a_goal_expectation_bias": team_a_tactics.get("goal_expectation_bias", ""),
                "team_b_goal_expectation_bias": team_b_tactics.get("goal_expectation_bias", ""),
                "notes": "Initial model input; update after Elo/FIFA/odds/tactical data are complete.",
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} match prediction input rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
