"""Generate uncertainty-aware score probabilities from baseline xG inputs."""

from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path

from simulation.poisson_match_simulator import poisson_pmf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run uncertainty-aware Poisson simulations.")
    parser.add_argument("--inputs", default="data/processed/model_match_inputs.csv")
    parser.add_argument("--ratings", default="data/processed/team_power_ratings.csv")
    parser.add_argument(
        "--summary-output",
        default="data/processed/match_robust_simulation_summary.csv",
    )
    parser.add_argument(
        "--score-output",
        default="data/processed/match_robust_score_probabilities.csv",
    )
    parser.add_argument(
        "--uncertainty-output",
        default="data/processed/team_rating_uncertainty.csv",
    )
    parser.add_argument(
        "--metadata-output",
        default="data/processed/model_run_metadata.csv",
    )
    parser.add_argument("--max-goals", type=int, default=8)
    parser.add_argument("--draws", type=int, default=2500)
    parser.add_argument("--seed", type=int, default=20260620)
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def team_uncertainty(row: dict[str, str]) -> dict[str, str]:
    power = as_float(row.get("power_rating"))
    club = as_float(row.get("club_quality_rating"))
    form = as_float(row.get("form_rating"))
    elo = as_float(row.get("elo_normalized"))
    data_floor = min(value for value in [club, form, elo] if value > 0)
    data_gap = max(0.0, 1.0 - data_floor / 100.0)
    strength_sd = min(0.28, max(0.10, 0.10 + 0.10 * data_gap + 0.06 * (1.0 - power / 100.0)))
    if club < 45:
        strength_sd = min(0.32, strength_sd + 0.03)
    return {
        "team": row["team"],
        "power_rating": f"{power:.2f}",
        "club_quality_rating": f"{club:.2f}",
        "form_rating": f"{form:.2f}",
        "elo_normalized": f"{elo:.2f}",
        "rating_std_log_xg": f"{strength_sd:.4f}",
        "uncertainty_reason": "partial-pooling proxy from power, club, form, and Elo coverage",
    }


def uncertainty_by_team(ratings: list[dict[str, str]]) -> dict[str, float]:
    output = {}
    for row in ratings:
        team = row["team"]
        output[team] = as_float(team_uncertainty(row)["rating_std_log_xg"], 0.16)
    return output


def poisson_grid(lam_a: float, lam_b: float, max_goals: int) -> list[list[float]]:
    probs_a = [poisson_pmf(lam_a, goals) for goals in range(max_goals + 1)]
    probs_b = [poisson_pmf(lam_b, goals) for goals in range(max_goals + 1)]
    return [[prob_a * prob_b for prob_b in probs_b] for prob_a in probs_a]


def draw_lambda(base: float, sigma: float, rng: random.Random, tempo_shift: float) -> float:
    sigma = max(0.01, sigma)
    centered_log_base = math.log(max(base, 0.05)) - 0.5 * sigma * sigma
    return max(0.05, math.exp(centered_log_base + rng.gauss(0.0, sigma) + tempo_shift))


def summarize_score_grid(
    match: dict[str, str],
    grid: list[list[float]],
    max_goals: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    home_win = draw = away_win = over_25 = under_25 = 0.0
    most_likely_score = ""
    most_likely_probability = -1.0
    score_rows: list[dict[str, str]] = []

    captured_mass = sum(sum(row) for row in grid)
    normalizer = captured_mass if captured_mass > 0 else 1.0
    for goals_a in range(max_goals + 1):
        for goals_b in range(max_goals + 1):
            probability = grid[goals_a][goals_b] / normalizer
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

    summary = {
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
    return summary, score_rows


def write_csv(path: str, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    matches = read_csv(args.inputs)
    ratings = read_csv(args.ratings)
    uncertainty_rows = [team_uncertainty(row) for row in ratings]
    uncertainty = uncertainty_by_team(ratings)

    summary_rows: list[dict[str, str]] = []
    score_rows: list[dict[str, str]] = []
    default_sigma = 0.18
    tempo_sigma = 0.10

    for match in matches:
        rng = random.Random(args.seed + int(match["source_order"]))
        lam_a = as_float(match["team_a_expected_goals"])
        lam_b = as_float(match["team_b_expected_goals"])
        sigma_a = uncertainty.get(match["team_a_canonical"], default_sigma)
        sigma_b = uncertainty.get(match["team_b_canonical"], default_sigma)
        grid = [[0.0 for _ in range(args.max_goals + 1)] for _ in range(args.max_goals + 1)]

        for _ in range(args.draws):
            tempo_shift = rng.gauss(0.0, tempo_sigma)
            draw_lam_a = draw_lambda(lam_a, sigma_a, rng, tempo_shift)
            draw_lam_b = draw_lambda(lam_b, sigma_b, rng, tempo_shift)
            draw_grid = poisson_grid(draw_lam_a, draw_lam_b, args.max_goals)
            for goals_a in range(args.max_goals + 1):
                for goals_b in range(args.max_goals + 1):
                    grid[goals_a][goals_b] += draw_grid[goals_a][goals_b] / args.draws

        summary, scores = summarize_score_grid(match, grid, args.max_goals)
        summary["team_a_rating_std_log_xg"] = f"{sigma_a:.4f}"
        summary["team_b_rating_std_log_xg"] = f"{sigma_b:.4f}"
        summary["simulation_draws"] = str(args.draws)
        summary["simulation_seed"] = str(args.seed)
        summary_rows.append(summary)
        score_rows.extend(scores)

    write_csv(args.uncertainty_output, uncertainty_rows)
    write_csv(args.summary_output, summary_rows)
    write_csv(args.score_output, score_rows)
    write_csv(
        args.metadata_output,
        [
            {
                "run_name": "robust_match_simulator",
                "seed": str(args.seed),
                "draws": str(args.draws),
                "max_goals": str(args.max_goals),
                "tempo_std_log_xg": f"{tempo_sigma:.4f}",
                "model_note": "Uncertainty-aware Poisson mixture; market lines remain validation inputs only.",
            }
        ],
    )
    print(
        f"Wrote {len(summary_rows)} robust match summaries, "
        f"{len(score_rows)} score rows, and {len(uncertainty_rows)} team uncertainty rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
