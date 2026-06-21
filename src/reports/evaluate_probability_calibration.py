"""Evaluate probability calibration for result and total markets."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate model probability calibration.")
    parser.add_argument("--actuals", default="data/processed/match_actual_results.csv")
    parser.add_argument("--summary", default="data/processed/match_robust_simulation_summary.csv")
    parser.add_argument("--fallback-summary", default="data/processed/match_simulation_summary.csv")
    parser.add_argument("--output", default="data/processed/probability_calibration_report.csv")
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: str, fallback: str) -> tuple[list[dict[str, str]], str]:
    rows = read_csv(path)
    if rows:
        return rows, path
    return read_csv(fallback), fallback


def actual_result(goals_a: int, goals_b: int) -> str:
    if goals_a > goals_b:
        return "team_a"
    if goals_a < goals_b:
        return "team_b"
    return "draw"


def brier_multi(probs: dict[str, float], actual: str) -> float:
    return sum((probs[label] - (1.0 if label == actual else 0.0)) ** 2 for label in probs)


def brier_binary(probability: float, hit: bool) -> float:
    return (probability - (1.0 if hit else 0.0)) ** 2


def log_loss(probability: float) -> float:
    return -math.log(max(probability, 1e-12))


def probability_bin(probability: float) -> str:
    lower = int(min(0.9, max(0.0, probability)) * 10) / 10
    upper = lower + 0.1
    return f"{lower:.1f}-{upper:.1f}"


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def write_csv(path: str, rows: list[dict[str, str]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    actuals = [row for row in read_csv(args.actuals) if row.get("result_status") == "final"]
    summaries, summary_source = read_summary(args.summary, args.fallback_summary)
    summaries_by_match = {row["source_order"]: row for row in summaries}

    match_rows: list[dict[str, str]] = []
    for actual in actuals:
        summary = summaries_by_match.get(actual["source_order"])
        if not summary:
            continue
        goals_a = int(actual["actual_goals_a"])
        goals_b = int(actual["actual_goals_b"])
        result_probs = {
            "team_a": float(summary["team_a_win_probability"]),
            "draw": float(summary["draw_probability"]),
            "team_b": float(summary["team_b_win_probability"]),
        }
        result = actual_result(goals_a, goals_b)
        predicted_result = max(result_probs, key=result_probs.get)
        actual_result_probability = result_probs[result]
        total_over = goals_a + goals_b > 2.5
        over_probability = float(summary["over_2_5_probability"])
        actual_total_probability = (
            over_probability if total_over else float(summary["under_2_5_probability"])
        )
        match_rows.append(
            {
                "row_type": "match",
                "group": "match",
                "source_order": actual["source_order"],
                "team_a": actual["team_a"],
                "team_b": actual["team_b"],
                "actual_score": f"{goals_a}-{goals_b}",
                "predicted_result": predicted_result,
                "actual_result": result,
                "actual_result_probability": f"{actual_result_probability:.6f}",
                "result_brier": f"{brier_multi(result_probs, result):.6f}",
                "result_log_loss": f"{log_loss(actual_result_probability):.6f}",
                "actual_total": "over_2_5" if total_over else "under_2_5",
                "actual_total_probability": f"{actual_total_probability:.6f}",
                "total_brier": f"{brier_binary(over_probability, total_over):.6f}",
                "total_log_loss": f"{log_loss(actual_total_probability):.6f}",
                "summary_source": summary_source,
            }
        )

    summary_row = {
        "row_type": "summary",
        "group": "overall",
        "source_order": "",
        "team_a": "",
        "team_b": "",
        "actual_score": "",
        "predicted_result": "",
        "actual_result": "",
        "actual_result_probability": f"{average([float(row['actual_result_probability']) for row in match_rows]):.6f}",
        "result_brier": f"{average([float(row['result_brier']) for row in match_rows]):.6f}",
        "result_log_loss": f"{average([float(row['result_log_loss']) for row in match_rows]):.6f}",
        "actual_total": "",
        "actual_total_probability": f"{average([float(row['actual_total_probability']) for row in match_rows]):.6f}",
        "total_brier": f"{average([float(row['total_brier']) for row in match_rows]):.6f}",
        "total_log_loss": f"{average([float(row['total_log_loss']) for row in match_rows]):.6f}",
        "summary_source": summary_source,
    }

    bin_rows: list[dict[str, str]] = []
    bins: dict[str, list[dict[str, str]]] = {}
    for row in match_rows:
        bins.setdefault(probability_bin(float(row["actual_result_probability"])), []).append(row)
    for bucket, rows in sorted(bins.items()):
        bin_rows.append(
            {
                **summary_row,
                "row_type": "calibration_bin",
                "group": bucket,
                "actual_result_probability": f"{average([float(row['actual_result_probability']) for row in rows]):.6f}",
                "result_brier": f"{average([float(row['result_brier']) for row in rows]):.6f}",
                "result_log_loss": f"{average([float(row['result_log_loss']) for row in rows]):.6f}",
                "actual_total_probability": "",
                "total_brier": "",
                "total_log_loss": "",
            }
        )

    rows = [summary_row, *bin_rows, *match_rows]
    write_csv(args.output, rows)
    print(f"Evaluated probability calibration for {len(match_rows)} final matches.")
    print(f"Result Brier: {summary_row['result_brier']}")
    print(f"Result log loss: {summary_row['result_log_loss']}")
    print(f"Total Brier: {summary_row['total_brier']}")
    print(f"Total log loss: {summary_row['total_log_loss']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
