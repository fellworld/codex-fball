"""Simulate football score probabilities with an independent Poisson model."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Poisson score simulations.")
    parser.add_argument("--inputs", default="data/processed/model_match_inputs.csv")
    parser.add_argument("--summary-output", default="data/processed/match_simulation_summary.csv")
    parser.add_argument("--score-output", default="data/processed/match_score_probabilities.csv")
    parser.add_argument("--max-goals", type=int, default=8)
    return parser.parse_args()


def poisson_pmf(lam: float, goals: int) -> float:
    return math.exp(-lam) * (lam ** goals) / math.factorial(goals)


def as_float(value: str) -> float:
    return float(value)


def main() -> int:
    args = parse_args()
    with Path(args.inputs).open(newline="", encoding="utf-8") as handle:
        matches = list(csv.DictReader(handle))

    summary_rows: list[dict[str, str]] = []
    score_rows: list[dict[str, str]] = []

    for match in matches:
        lam_a = as_float(match["team_a_expected_goals"])
        lam_b = as_float(match["team_b_expected_goals"])
        probs_a = [poisson_pmf(lam_a, goals) for goals in range(args.max_goals + 1)]
        probs_b = [poisson_pmf(lam_b, goals) for goals in range(args.max_goals + 1)]

        home_win = draw = away_win = over_25 = under_25 = 0.0
        most_likely_score = ""
        most_likely_probability = -1.0

        for goals_a, prob_a in enumerate(probs_a):
            for goals_b, prob_b in enumerate(probs_b):
                probability = prob_a * prob_b
                if goals_a > goals_b:
                    home_win += probability
                elif goals_a == goals_b:
                    draw += probability
                else:
                    away_win += probability

                if goals_a + goals_b > 2.5:
                    over_25 += probability
                else:
                    under_25 += probability

                if probability > most_likely_probability:
                    most_likely_probability = probability
                    most_likely_score = f"{goals_a}-{goals_b}"

                score_rows.append(
                    {
                        "source_order": match["source_order"],
                        "team_a": match["team_a"],
                        "team_b": match["team_b"],
                        "goals_a": str(goals_a),
                        "goals_b": str(goals_b),
                        "score": f"{goals_a}-{goals_b}",
                        "probability": f"{probability:.8f}",
                    }
                )

        captured_mass = home_win + draw + away_win
        if captured_mass > 0:
            home_win /= captured_mass
            draw /= captured_mass
            away_win /= captured_mass
            over_25 /= captured_mass
            under_25 /= captured_mass
            most_likely_probability /= captured_mass

        summary_rows.append(
            {
                "source_order": match["source_order"],
                "group": match["group"],
                "date_china": match["date_china"],
                "time_china": match["time_china"],
                "team_a": match["team_a"],
                "team_b": match["team_b"],
                "team_a_expected_goals": match["team_a_expected_goals"],
                "team_b_expected_goals": match["team_b_expected_goals"],
                "total_expected_goals": match["total_expected_goals"],
                "team_a_win_probability": f"{home_win:.6f}",
                "draw_probability": f"{draw:.6f}",
                "team_b_win_probability": f"{away_win:.6f}",
                "over_2_5_probability": f"{over_25:.6f}",
                "under_2_5_probability": f"{under_25:.6f}",
                "most_likely_score": most_likely_score,
                "most_likely_score_probability": f"{most_likely_probability:.6f}",
                "captured_probability_mass": f"{captured_mass:.6f}",
            }
        )

    summary_path = Path(args.summary_output)
    score_path = Path(args.score_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    score_path.parent.mkdir(parents=True, exist_ok=True)

    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    with score_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(score_rows[0].keys()))
        writer.writeheader()
        writer.writerows(score_rows)

    print(f"Wrote {len(summary_rows)} match summaries and {len(score_rows)} score rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
