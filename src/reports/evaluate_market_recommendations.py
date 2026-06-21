"""Settle Asian handicap and goal-total recommendations against actual scores."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


SETTLEMENT_LABELS = {
    1.0: "win",
    0.5: "half_win",
    0.0: "push",
    -0.5: "half_loss",
    -1.0: "loss",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate market recommendations.")
    parser.add_argument("--recommendations", default="data/processed/market_recommendations.csv")
    parser.add_argument("--actuals", default="data/processed/match_actual_results.csv")
    parser.add_argument("--settlement-output", default="data/processed/recommendation_settlement.csv")
    parser.add_argument("--summary-output", default="data/processed/market_backtest_summary.csv")
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def split_quarter_line(line: float) -> list[float]:
    """Return one or two half-goal handicap components."""
    doubled = line * 2
    if abs(doubled - round(doubled)) < 1e-9:
        return [line]
    return [math.floor(doubled) / 2, math.ceil(doubled) / 2]


def settle_margin(margin: float) -> float:
    if margin > 0:
        return 1.0
    if abs(margin) < 1e-9:
        return 0.0
    return -1.0


def settle_asian_handicap(goals_for: int, goals_against: int, line: float) -> float:
    parts = split_quarter_line(line)
    return sum(settle_margin(goals_for + part - goals_against) for part in parts) / len(parts)


def settle_total(total_goals: int, line: float, selection: str) -> float:
    parts = split_quarter_line(line)
    outcomes = []
    for part in parts:
        if selection == "over":
            outcomes.append(settle_margin(total_goals - part))
        elif selection == "under":
            outcomes.append(settle_margin(part - total_goals))
        else:
            raise ValueError(f"Unsupported total selection: {selection}")
    return sum(outcomes) / len(outcomes)


def net_units(settlement: float, price: float, stake: float) -> float:
    if settlement > 0:
        return settlement * price * stake
    return settlement * stake


def recommendation_settlement(
    recommendation: dict[str, str],
    actual: dict[str, str],
) -> dict[str, str]:
    goals_a = int(actual["actual_goals_a"])
    goals_b = int(actual["actual_goals_b"])
    market_type = recommendation["market_type"]
    selection_side = recommendation["selection_side"]
    line = float(recommendation["line"])
    price = float(recommendation["price"])
    stake = float(recommendation.get("stake") or 1.0)

    if market_type == "asian_handicap":
        if selection_side == "team_a":
            settlement = settle_asian_handicap(goals_a, goals_b, line)
        elif selection_side == "team_b":
            settlement = settle_asian_handicap(goals_b, goals_a, line)
        else:
            raise ValueError(f"Unsupported handicap side: {selection_side}")
    elif market_type == "total":
        settlement = settle_total(goals_a + goals_b, line, selection_side)
    else:
        raise ValueError(f"Unsupported market type: {market_type}")

    result_units = net_units(settlement, price, stake)
    return {
        "recommendation_id": recommendation["recommendation_id"],
        "date_discussed": recommendation["date_discussed"],
        "source_order": recommendation["source_order"],
        "team_a": actual["team_a"],
        "team_b": actual["team_b"],
        "market_type": market_type,
        "selection": recommendation["selection"],
        "selection_side": selection_side,
        "line": recommendation["line"],
        "price": recommendation["price"],
        "stake": f"{stake:.2f}",
        "actual_score": f"{goals_a}-{goals_b}",
        "settlement_value": f"{settlement:.1f}",
        "settlement": SETTLEMENT_LABELS[settlement],
        "net_units": f"{result_units:.4f}",
        "rank_in_set": recommendation.get("rank_in_set", ""),
        "set_id": recommendation.get("set_id", ""),
        "model_ev": recommendation.get("model_ev", ""),
        "model_non_loss_probability": recommendation.get("model_non_loss_probability", ""),
        "notes": recommendation.get("notes", ""),
    }


def write_csv(path: str, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[("all", "all")].append(row)
        groups[("market_type", row["market_type"])].append(row)
        groups[("set_id", row["set_id"])].append(row)

    summary_rows: list[dict[str, str]] = []
    for (group_type, group_value), group_rows in sorted(groups.items()):
        count = len(group_rows)
        wins = sum(row["settlement"] in {"win", "half_win"} for row in group_rows)
        non_losses = sum(row["settlement"] in {"win", "half_win", "push"} for row in group_rows)
        losses = sum(row["settlement"] in {"half_loss", "loss"} for row in group_rows)
        net = sum(float(row["net_units"]) for row in group_rows)
        summary_rows.append(
            {
                "group_type": group_type,
                "group_value": group_value,
                "recommendations": str(count),
                "positive_settlements": str(wins),
                "non_loss_settlements": str(non_losses),
                "negative_settlements": str(losses),
                "positive_rate": f"{wins / count:.4f}" if count else "0.0000",
                "non_loss_rate": f"{non_losses / count:.4f}" if count else "0.0000",
                "net_units": f"{net:.4f}",
                "roi_per_unit_stake": f"{net / count:.4f}" if count else "0.0000",
            }
        )
    return summary_rows


def main() -> int:
    args = parse_args()
    recommendations = read_csv(args.recommendations)
    actuals = {
        row["source_order"]: row
        for row in read_csv(args.actuals)
        if row.get("result_status") == "final"
    }

    settled_rows = [
        recommendation_settlement(row, actuals[row["source_order"]])
        for row in recommendations
        if row.get("source_order") in actuals
    ]

    settlement_fields = [
        "recommendation_id",
        "date_discussed",
        "source_order",
        "team_a",
        "team_b",
        "market_type",
        "selection",
        "selection_side",
        "line",
        "price",
        "stake",
        "actual_score",
        "settlement_value",
        "settlement",
        "net_units",
        "rank_in_set",
        "set_id",
        "model_ev",
        "model_non_loss_probability",
        "notes",
    ]
    summary_fields = [
        "group_type",
        "group_value",
        "recommendations",
        "positive_settlements",
        "non_loss_settlements",
        "negative_settlements",
        "positive_rate",
        "non_loss_rate",
        "net_units",
        "roi_per_unit_stake",
    ]
    write_csv(args.settlement_output, settled_rows, settlement_fields)
    write_csv(args.summary_output, summarize(settled_rows), summary_fields)
    print(f"Settled {len(settled_rows)} market recommendations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
