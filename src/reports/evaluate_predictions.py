"""Evaluate match predictions against final scores."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate predictions against actual results.")
    parser.add_argument("--actuals", default="data/processed/match_actual_results.csv")
    parser.add_argument("--summary", default="data/processed/match_simulation_summary.csv")
    parser.add_argument("--scores", default="data/processed/match_score_probabilities.csv")
    parser.add_argument("--output", default="data/processed/prediction_backtest_summary.csv")
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def result_label(goals_a: int, goals_b: int) -> str:
    if goals_a > goals_b:
        return "team_a"
    if goals_a < goals_b:
        return "team_b"
    return "draw"


def total_label(goals_a: int, goals_b: int) -> str:
    return "over_2_5" if goals_a + goals_b > 2.5 else "under_2_5"


def predicted_result(row: dict[str, str]) -> str:
    probs = {
        "team_a": float(row["team_a_win_probability"]),
        "draw": float(row["draw_probability"]),
        "team_b": float(row["team_b_win_probability"]),
    }
    return max(probs, key=probs.get)


def predicted_total(row: dict[str, str]) -> str:
    over = float(row["over_2_5_probability"])
    under = float(row["under_2_5_probability"])
    return "over_2_5" if over >= under else "under_2_5"


def score_rank(score_rows: list[dict[str, str]], score: str) -> tuple[int, float, str]:
    ordered = sorted(score_rows, key=lambda row: float(row["probability"]), reverse=True)
    top_scores = "; ".join(
        f"{row['score']}:{float(row['probability']):.3f}" for row in ordered[:5]
    )
    for index, row in enumerate(ordered, start=1):
        if row["score"] == score:
            return index, float(row["probability"]), top_scores
    return 0, 0.0, top_scores


def main() -> int:
    args = parse_args()
    actuals = [row for row in read_csv(args.actuals) if row.get("result_status") == "final"]
    summaries = {row["source_order"]: row for row in read_csv(args.summary)}
    scores_by_match: dict[str, list[dict[str, str]]] = {}
    for row in read_csv(args.scores):
        scores_by_match.setdefault(row["source_order"], []).append(row)

    rows: list[dict[str, str]] = []
    for actual in actuals:
        source_order = actual["source_order"]
        summary = summaries[source_order]
        goals_a = int(actual["actual_goals_a"])
        goals_b = int(actual["actual_goals_b"])
        actual_score = f"{goals_a}-{goals_b}"
        actual_result = result_label(goals_a, goals_b)
        actual_total = total_label(goals_a, goals_b)
        pred_result = predicted_result(summary)
        pred_total = predicted_total(summary)
        rank, prob, top_scores = score_rank(scores_by_match[source_order], actual_score)
        rows.append(
            {
                "source_order": source_order,
                "team_a": actual["team_a"],
                "team_b": actual["team_b"],
                "actual_score": actual_score,
                "most_likely_score": summary["most_likely_score"],
                "exact_score_hit": str(actual_score == summary["most_likely_score"]).lower(),
                "actual_score_rank": str(rank),
                "actual_score_probability": f"{prob:.6f}",
                "actual_score_log_loss": f"{-math.log(max(prob, 1e-12)):.6f}",
                "top5_scores": top_scores,
                "actual_result": actual_result,
                "predicted_result": pred_result,
                "result_hit": str(actual_result == pred_result).lower(),
                "actual_total": actual_total,
                "predicted_total": pred_total,
                "total_hit": str(actual_total == pred_total).lower(),
                "team_a_expected_goals": summary["team_a_expected_goals"],
                "team_b_expected_goals": summary["team_b_expected_goals"],
                "total_expected_goals": summary["total_expected_goals"],
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    result_hits = sum(row["result_hit"] == "true" for row in rows)
    total_hits = sum(row["total_hit"] == "true" for row in rows)
    exact_hits = sum(row["exact_score_hit"] == "true" for row in rows)
    top5_hits = sum(int(row["actual_score_rank"]) <= 5 for row in rows)
    print(f"Evaluated {len(rows)} final matches.")
    print(f"Result hits: {result_hits}/{len(rows)}")
    print(f"Total hits: {total_hits}/{len(rows)}")
    print(f"Exact score hits: {exact_hits}/{len(rows)}")
    print(f"Top-5 score hits: {top5_hits}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
