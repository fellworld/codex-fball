"""Backtest strategy-tiered market candidates against final scores."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from reports.evaluate_market_recommendations import (
    SETTLEMENT_LABELS,
    net_units,
    settle_asian_handicap,
    settle_total,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest A/B/C market strategy tiers.")
    parser.add_argument("--candidates", default="data/processed/market_candidate_scores.csv")
    parser.add_argument("--actuals", default="data/processed/match_actual_results.csv")
    parser.add_argument("--output", default="data/processed/strategy_tier_backtest.csv")
    parser.add_argument("--summary-output", default="data/processed/strategy_tier_backtest_summary.csv")
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


def settle_candidate(row: dict[str, str], actual: dict[str, str]) -> dict[str, str]:
    goals_a = int(actual["actual_goals_a"])
    goals_b = int(actual["actual_goals_b"])
    line = as_float(row["line"])
    price = as_float(row["price"])
    if row["market_type"] == "asian_handicap":
        if row["selection_side"] == "team_a":
            settlement = settle_asian_handicap(goals_a, goals_b, line)
        else:
            settlement = settle_asian_handicap(goals_b, goals_a, line)
    else:
        settlement = settle_total(goals_a + goals_b, line, row["selection_side"])
    return {
        "source_order": row["source_order"],
        "team_a": row["team_a"],
        "team_b": row["team_b"],
        "market_type": row["market_type"],
        "selection": row["selection"],
        "selection_side": row["selection_side"],
        "line": row["line"],
        "price": row["price"],
        "strategy_tier": row["strategy_tier"],
        "risk_flags": row["risk_flags"],
        "strategy_reasons": row["strategy_reasons"],
        "model_ev": row["model_ev"],
        "non_loss_probability": row["non_loss_probability"],
        "actual_score": f"{goals_a}-{goals_b}",
        "settlement": SETTLEMENT_LABELS[settlement],
        "settlement_value": f"{settlement:.1f}",
        "net_units": f"{net_units(settlement, price, 1.0):.4f}",
    }


def summarize(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[("all", "all")].append(row)
        groups[("strategy_tier", row["strategy_tier"])].append(row)
        groups[("market_type", row["market_type"])].append(row)
        groups[(f"tier_market", f"{row['strategy_tier']}|{row['market_type']}")].append(row)

    summary_rows: list[dict[str, str]] = []
    for (group_type, group_value), group_rows in sorted(groups.items()):
        count = len(group_rows)
        positive = sum(row["settlement"] in {"win", "half_win"} for row in group_rows)
        non_loss = sum(row["settlement"] in {"win", "half_win", "push"} for row in group_rows)
        net = sum(float(row["net_units"]) for row in group_rows)
        summary_rows.append(
            {
                "group_type": group_type,
                "group_value": group_value,
                "candidates": str(count),
                "positive_settlements": str(positive),
                "non_loss_settlements": str(non_loss),
                "positive_rate": f"{positive / count:.4f}" if count else "0.0000",
                "non_loss_rate": f"{non_loss / count:.4f}" if count else "0.0000",
                "net_units": f"{net:.4f}",
                "roi_per_unit_stake": f"{net / count:.4f}" if count else "0.0000",
            }
        )
    return summary_rows


def write_csv(path: str, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    candidates = read_csv(args.candidates)
    actuals = {
        row["source_order"]: row
        for row in read_csv(args.actuals)
        if row.get("result_status") == "final"
    }
    rows = [
        settle_candidate(candidate, actuals[candidate["source_order"]])
        for candidate in candidates
        if candidate.get("source_order") in actuals
    ]
    fields = [
        "source_order",
        "team_a",
        "team_b",
        "market_type",
        "selection",
        "selection_side",
        "line",
        "price",
        "strategy_tier",
        "risk_flags",
        "strategy_reasons",
        "model_ev",
        "non_loss_probability",
        "actual_score",
        "settlement",
        "settlement_value",
        "net_units",
    ]
    summary_fields = [
        "group_type",
        "group_value",
        "candidates",
        "positive_settlements",
        "non_loss_settlements",
        "positive_rate",
        "non_loss_rate",
        "net_units",
        "roi_per_unit_stake",
    ]
    write_csv(args.output, rows, fields)
    write_csv(args.summary_output, summarize(rows), summary_fields)
    print(f"Backtested {len(rows)} strategy-tiered candidates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
