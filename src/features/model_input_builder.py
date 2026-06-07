"""Build model-ready match rows from schedule, ratings, and optional data."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build model-ready match inputs.")
    parser.add_argument("--matches", default="data/processed/match_prediction_inputs.csv")
    parser.add_argument("--power-ratings", default="data/processed/team_power_ratings.csv")
    parser.add_argument("--phase-ratings", default="data/processed/team_phase_ratings.csv")
    parser.add_argument("--tactics", default="data/processed/team_tactical_profiles.csv")
    parser.add_argument("--context", default="data/processed/match_context.csv")
    parser.add_argument("--output", default="data/processed/model_match_inputs.csv")
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def tactical_total_adjustment(row: dict[str, str]) -> float:
    adjustment = 0.0
    if row.get("tempo") == "fast":
        adjustment += 0.08
    if row.get("tempo") == "slow":
        adjustment -= 0.08
    if row.get("pressing_height") == "high":
        adjustment += 0.06
    if row.get("defensive_line") == "high":
        adjustment += 0.05
    if row.get("defensive_line") == "low":
        adjustment -= 0.06
    if row.get("goal_expectation_bias") == "over":
        adjustment += 0.10
    if row.get("goal_expectation_bias") == "under":
        adjustment -= 0.10
    return adjustment


def main() -> int:
    args = parse_args()
    matches = read_csv(args.matches)
    powers = {row["team"]: row for row in read_csv(args.power_ratings)}
    phases = {row["team"]: row for row in read_csv(args.phase_ratings)}
    tactics = {row["team"]: row for row in read_csv(args.tactics)}
    context = {row["source_order"]: row for row in read_csv(args.context)}

    rows: list[dict[str, str]] = []
    for match in matches:
        team_a = match["team_a_canonical"]
        team_b = match["team_b_canonical"]
        phase_a = phases.get(team_a, {})
        phase_b = phases.get(team_b, {})
        tactic_a = tactics.get(team_a, {})
        tactic_b = tactics.get(team_b, {})
        ctx = context.get(match["source_order"], {})

        rating_a = as_float(match["team_a_rating"], 50.0)
        rating_b = as_float(match["team_b_rating"], 50.0)
        power_a = powers.get(team_a, {})
        power_b = powers.get(team_b, {})
        power_rating_a = as_float(power_a.get("power_rating"), rating_a)
        power_rating_b = as_float(power_b.get("power_rating"), rating_b)
        attack_a = as_float(phase_a.get("attack_rating"), as_float(power_a.get("attack_rating"), power_rating_a))
        defense_a = as_float(phase_a.get("defense_rating"), as_float(power_a.get("defense_rating"), power_rating_a))
        attack_b = as_float(phase_b.get("attack_rating"), as_float(power_b.get("attack_rating"), power_rating_b))
        defense_b = as_float(phase_b.get("defense_rating"), as_float(power_b.get("defense_rating"), power_rating_b))

        base_lambda = 1.35
        team_a_xg = base_lambda + ((attack_a - defense_b) / 10.0) * 0.18
        team_b_xg = base_lambda + ((attack_b - defense_a) / 10.0) * 0.18

        total_adjustment = tactical_total_adjustment(tactic_a) + tactical_total_adjustment(tactic_b)
        if ctx.get("home_advantage_team") == match["team_a"]:
            team_a_xg += 0.10
        elif ctx.get("home_advantage_team") == match["team_b"]:
            team_b_xg += 0.10

        team_a_xg = max(0.20, team_a_xg + total_adjustment / 2.0)
        team_b_xg = max(0.20, team_b_xg + total_adjustment / 2.0)

        rows.append(
            {
                "source_order": match["source_order"],
                "group": match["group"],
                "date_china": match["date_china"],
                "time_china": match["time_china"],
                "team_a": match["team_a"],
                "team_b": match["team_b"],
                "team_a_canonical": team_a,
                "team_b_canonical": team_b,
                "team_a_attack_rating": f"{attack_a:.2f}",
                "team_a_defense_rating": f"{defense_a:.2f}",
                "team_b_attack_rating": f"{attack_b:.2f}",
                "team_b_defense_rating": f"{defense_b:.2f}",
                "team_a_power_rating": f"{power_rating_a:.2f}",
                "team_b_power_rating": f"{power_rating_b:.2f}",
                "team_a_expected_goals": f"{team_a_xg:.3f}",
                "team_b_expected_goals": f"{team_b_xg:.3f}",
                "total_expected_goals": f"{team_a_xg + team_b_xg:.3f}",
                "input_notes": "xG from blended power/phase ratings; tactical/context data can further adjust totals.",
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} model match input rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
