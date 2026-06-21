"""Score market lines with calibration-aware strategy rules."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from reports.evaluate_market_recommendations import (
    settle_asian_handicap,
    settle_total,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score market candidates from captured lines.")
    parser.add_argument("--market-lines", default="data/processed/market_lines.csv")
    parser.add_argument("--scores", default="data/processed/match_robust_score_probabilities.csv")
    parser.add_argument("--simulation", default="data/processed/match_robust_simulation_summary.csv")
    parser.add_argument("--output", default="data/processed/market_candidate_scores.csv")
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_csv_with_fallback(path: str, fallback: str) -> tuple[list[dict[str, str]], str]:
    rows = read_csv(path)
    if rows:
        return rows, path
    return read_csv(fallback), fallback


def as_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def raw_implied_from_hk(price: float) -> float:
    return 1.0 / (1.0 + price) if price > 0 else 0.0


def market_group_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    if row["market_type"] == "total":
        line_key = row["line"]
    else:
        line_key = f"{abs(as_float(row['line'])):.2f}"
    return (
        row.get("screenshot_id", ""),
        row["source_order"],
        row["market_type"],
        line_key,
        row.get("captured_at_local", ""),
    )


def no_vig_probabilities(rows: list[dict[str, str]]) -> dict[str, float]:
    raw = {
        row_key(row): raw_implied_from_hk(as_float(row["price"]))
        for row in rows
    }
    total = sum(raw.values())
    if total <= 0:
        return {key: 0.0 for key in raw}
    return {key: value / total for key, value in raw.items()}


def row_key(row: dict[str, str]) -> str:
    return "|".join(
        [
            row.get("screenshot_id", ""),
            row["source_order"],
            row["market_type"],
            row["selection"],
            row["selection_side"],
            row["line"],
        ]
    )


def score_distribution(
    rows: list[dict[str, str]],
    market_type: str,
    selection_side: str,
    line: float,
    price: float,
) -> dict[str, float]:
    buckets = {1.0: 0.0, 0.5: 0.0, 0.0: 0.0, -0.5: 0.0, -1.0: 0.0}
    ev = 0.0
    for row in rows:
        goals_a = int(row["goals_a"])
        goals_b = int(row["goals_b"])
        probability = float(row["probability"])
        if market_type == "asian_handicap":
            if selection_side == "team_a":
                settlement = settle_asian_handicap(goals_a, goals_b, line)
            else:
                settlement = settle_asian_handicap(goals_b, goals_a, line)
        else:
            settlement = settle_total(goals_a + goals_b, line, selection_side)
        buckets[settlement] += probability
        ev += probability * (settlement * price if settlement > 0 else settlement)

    return {
        "full_win_probability": buckets[1.0],
        "half_win_probability": buckets[0.5],
        "push_probability": buckets[0.0],
        "half_loss_probability": buckets[-0.5],
        "full_loss_probability": buckets[-1.0],
        "positive_probability": buckets[1.0] + buckets[0.5],
        "non_loss_probability": buckets[1.0] + buckets[0.5] + buckets[0.0],
        "model_ev": ev,
    }


def total_probability(rows: list[dict[str, str]], predicate) -> float:
    total = 0.0
    for row in rows:
        goals = int(row["goals_a"]) + int(row["goals_b"])
        if predicate(goals):
            total += float(row["probability"])
    return total


def favorite_cover_tail(rows: list[dict[str, str]], selection_side: str, line: float) -> float:
    if selection_side not in {"team_a", "team_b"} or line < 0:
        return 0.0
    tail = 0.0
    for row in rows:
        goals_a = int(row["goals_a"])
        goals_b = int(row["goals_b"])
        probability = float(row["probability"])
        favorite_margin = goals_b - goals_a if selection_side == "team_a" else goals_a - goals_b
        if favorite_margin >= 2:
            tail += probability
    return tail


def tier_and_flags(
    line: dict[str, str],
    distribution: dict[str, float],
    market_probability: float,
    score_rows: list[dict[str, str]],
) -> tuple[str, str, str]:
    market_type = line["market_type"]
    selection_side = line["selection_side"]
    handicap = as_float(line["line"])
    model_ev = distribution["model_ev"]
    non_loss = distribution["non_loss_probability"]
    full_loss = distribution["full_loss_probability"]
    low_score_density = total_probability(score_rows, lambda goals: goals <= 2)
    high_score_density = total_probability(score_rows, lambda goals: goals >= 4)
    blowout_tail = favorite_cover_tail(score_rows, selection_side, handicap)

    flags: list[str] = []
    reasons: list[str] = []

    if market_type == "total" and selection_side == "over" and low_score_density >= 0.40:
        flags.append("over_low_score_density")
    if market_type == "total" and selection_side == "under" and high_score_density >= 0.40:
        flags.append("under_high_score_tail")
    if market_type == "asian_handicap" and handicap > 0:
        flags.append("underdog_handicap_cap")
    if market_type == "asian_handicap" and handicap > 0 and blowout_tail >= 0.28:
        flags.append("underdog_blowout_tail")
    if full_loss >= 0.50:
        flags.append("high_full_loss_probability")
    if market_probability >= 0.58 and model_ev < 0.05:
        flags.append("market_disagreement")
    if distribution["positive_probability"] < market_probability - 0.03:
        flags.append("below_market_probability")

    if model_ev >= 0.12:
        reasons.append("positive_model_ev")
    if non_loss >= 0.62:
        reasons.append("strong_non_loss_profile")
    if market_type == "asian_handicap" and handicap < 0 and distribution["positive_probability"] >= 0.55:
        reasons.append("favorite_direction_supported")
    if market_type == "total" and selection_side == "under" and as_float(line["line"]) >= 3.5:
        reasons.append("high_total_under_buffer")

    if market_type == "total" and selection_side == "over" and flags:
        tier = "C"
    elif market_type == "asian_handicap" and handicap > 0 and "underdog_blowout_tail" in flags:
        tier = "C"
    elif market_type == "asian_handicap" and handicap > 0 and model_ev >= 0.12:
        tier = "B"
    elif model_ev >= 0.12 and not flags and distribution["positive_probability"] >= market_probability:
        tier = "A"
    elif model_ev >= 0.05 and len(flags) <= 1:
        tier = "B"
    elif model_ev >= 0.15 and len(flags) == 1 and "underdog_blowout_tail" not in flags:
        tier = "B"
    else:
        tier = "C"

    return tier, ";".join(flags), ";".join(reasons)


def main() -> int:
    args = parse_args()
    lines = read_csv(args.market_lines)
    simulation_rows, simulation_source = read_csv_with_fallback(
        args.simulation,
        "data/processed/match_simulation_summary.csv",
    )
    score_rows, score_source = read_csv_with_fallback(
        args.scores,
        "data/processed/match_score_probabilities.csv",
    )
    simulations = {row["source_order"]: row for row in simulation_rows}
    scores_by_match: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in score_rows:
        scores_by_match[row["source_order"]].append(row)

    grouped_lines: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for line in lines:
        grouped_lines[market_group_key(line)].append(line)
    no_vig_by_row: dict[str, float] = {}
    for rows in grouped_lines.values():
        no_vig_by_row.update(no_vig_probabilities(rows))

    output_rows: list[dict[str, str]] = []
    for line in lines:
        source_order = line["source_order"]
        score_rows = scores_by_match.get(source_order, [])
        if not score_rows:
            continue
        price = as_float(line["price"])
        distribution = score_distribution(
            rows=score_rows,
            market_type=line["market_type"],
            selection_side=line["selection_side"],
            line=as_float(line["line"]),
            price=price,
        )
        market_probability = no_vig_by_row.get(row_key(line), 0.0)
        tier, risk_flags, strategy_reasons = tier_and_flags(
            line=line,
            distribution=distribution,
            market_probability=market_probability,
            score_rows=score_rows,
        )
        sim = simulations.get(source_order, {})
        output_rows.append(
            {
                "screenshot_id": line.get("screenshot_id", ""),
                "captured_at_local": line.get("captured_at_local", ""),
                "source_order": source_order,
                "team_a": line["team_a"],
                "team_b": line["team_b"],
                "market_type": line["market_type"],
                "selection": line["selection"],
                "selection_side": line["selection_side"],
                "line": line["line"],
                "price": line["price"],
                "probability_source": score_source,
                "market_no_vig_probability": f"{market_probability:.4f}",
                "model_ev": f"{distribution['model_ev']:.4f}",
                "positive_probability": f"{distribution['positive_probability']:.4f}",
                "non_loss_probability": f"{distribution['non_loss_probability']:.4f}",
                "full_loss_probability": f"{distribution['full_loss_probability']:.4f}",
                "low_score_density_le_2": f"{total_probability(score_rows, lambda goals: goals <= 2):.4f}",
                "high_score_density_ge_4": f"{total_probability(score_rows, lambda goals: goals >= 4):.4f}",
                "team_a_win_probability": sim.get("team_a_win_probability", ""),
                "draw_probability": sim.get("draw_probability", ""),
                "team_b_win_probability": sim.get("team_b_win_probability", ""),
                "team_a_rating_std_log_xg": sim.get("team_a_rating_std_log_xg", ""),
                "team_b_rating_std_log_xg": sim.get("team_b_rating_std_log_xg", ""),
                "most_likely_score": sim.get("most_likely_score", ""),
                "strategy_tier": tier,
                "risk_flags": risk_flags,
                "strategy_reasons": strategy_reasons,
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "screenshot_id",
        "captured_at_local",
        "source_order",
        "team_a",
        "team_b",
        "market_type",
        "selection",
        "selection_side",
        "line",
        "price",
        "probability_source",
        "market_no_vig_probability",
        "model_ev",
        "positive_probability",
        "non_loss_probability",
        "full_loss_probability",
        "low_score_density_le_2",
        "high_score_density_ge_4",
        "team_a_win_probability",
        "draw_probability",
        "team_b_win_probability",
        "team_a_rating_std_log_xg",
        "team_b_rating_std_log_xg",
        "most_likely_score",
        "strategy_tier",
        "risk_flags",
        "strategy_reasons",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Scored {len(output_rows)} market candidates.")
    if score_source != args.scores or simulation_source != args.simulation:
        print("Robust probability files were not found; fell back to baseline Poisson outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
