"""Monte Carlo group-stage simulation from scoreline probabilities."""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run group-stage Monte Carlo simulation.")
    parser.add_argument("--matches", default="data/processed/match_prediction_inputs.csv")
    parser.add_argument("--scores", default="data/processed/match_score_probabilities.csv")
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260606)
    parser.add_argument("--output", default="data/processed/group_stage_simulation_summary.csv")
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def weighted_score(score_rows: list[dict[str, str]], rng: random.Random) -> tuple[int, int]:
    draw = rng.random()
    cumulative = 0.0
    fallback = score_rows[-1]
    for row in score_rows:
        cumulative += float(row["probability"])
        if draw <= cumulative:
            return int(row["goals_a"]), int(row["goals_b"])
    return int(fallback["goals_a"]), int(fallback["goals_b"])


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)
    matches = read_csv(args.matches)
    score_rows = read_csv(args.scores)

    scores_by_match: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in score_rows:
        scores_by_match[row["source_order"]].append(row)

    teams_by_group: dict[str, set[str]] = defaultdict(set)
    for match in matches:
        teams_by_group[match["group"]].add(match["team_a"])
        teams_by_group[match["group"]].add(match["team_b"])

    finish_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    advance_counts: dict[str, int] = defaultdict(int)
    group_win_counts: dict[str, int] = defaultdict(int)

    for _ in range(args.iterations):
        table: dict[str, dict[str, dict[str, int]]] = {
            group: {
                team: {"points": 0, "gf": 0, "ga": 0, "wins": 0}
                for team in teams
            }
            for group, teams in teams_by_group.items()
        }

        for match in matches:
            group = match["group"]
            team_a = match["team_a"]
            team_b = match["team_b"]
            goals_a, goals_b = weighted_score(scores_by_match[match["source_order"]], rng)
            table[group][team_a]["gf"] += goals_a
            table[group][team_a]["ga"] += goals_b
            table[group][team_b]["gf"] += goals_b
            table[group][team_b]["ga"] += goals_a
            if goals_a > goals_b:
                table[group][team_a]["points"] += 3
                table[group][team_a]["wins"] += 1
            elif goals_a < goals_b:
                table[group][team_b]["points"] += 3
                table[group][team_b]["wins"] += 1
            else:
                table[group][team_a]["points"] += 1
                table[group][team_b]["points"] += 1

        third_place_pool: list[tuple[tuple[int, int, int, int, float], str]] = []
        for group, group_table in table.items():
            ranked = sorted(
                group_table.items(),
                key=lambda item: (
                    item[1]["points"],
                    item[1]["gf"] - item[1]["ga"],
                    item[1]["gf"],
                    item[1]["wins"],
                    rng.random(),
                ),
                reverse=True,
            )
            for idx, (team, stats) in enumerate(ranked, start=1):
                finish_counts[team][str(idx)] += 1
                if idx <= 2:
                    advance_counts[team] += 1
                if idx == 1:
                    group_win_counts[team] += 1
                if idx == 3:
                    third_place_pool.append(
                        (
                            (
                                stats["points"],
                                stats["gf"] - stats["ga"],
                                stats["gf"],
                                stats["wins"],
                                rng.random(),
                            ),
                            team,
                        )
                    )

        third_place_pool.sort(reverse=True)
        for _, team in third_place_pool[:8]:
            advance_counts[team] += 1

    rows: list[dict[str, str]] = []
    team_group = {
        team: group
        for group, teams in teams_by_group.items()
        for team in teams
    }
    for team in sorted(team_group):
        rows.append(
            {
                "team": team,
                "group": team_group[team],
                "group_win_probability": f"{group_win_counts[team] / args.iterations:.6f}",
                "advance_probability": f"{advance_counts[team] / args.iterations:.6f}",
                "finish_1_probability": f"{finish_counts[team]['1'] / args.iterations:.6f}",
                "finish_2_probability": f"{finish_counts[team]['2'] / args.iterations:.6f}",
                "finish_3_probability": f"{finish_counts[team]['3'] / args.iterations:.6f}",
                "finish_4_probability": f"{finish_counts[team]['4'] / args.iterations:.6f}",
                "iterations": str(args.iterations),
                "notes": "Top two in each group plus best eight third-place teams advance. Tiebreakers are approximated.",
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} group-stage simulation rows from {args.iterations} iterations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
