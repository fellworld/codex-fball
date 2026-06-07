"""Convert decimal odds snapshot rows into no-vig implied probabilities."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build no-vig probabilities from odds CSV.")
    parser.add_argument("--input", default="data/processed/odds_snapshots_latest.csv")
    parser.add_argument("--output", default="data/processed/market_implied_probabilities.csv")
    return parser.parse_args()


def safe_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}. Create it from odds snapshots first.")
        return 0

    with input_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("captured_at_utc", ""),
            row.get("event_id", ""),
            row.get("bookmaker_key", ""),
            row.get("market_key", ""),
        )
        groups[key].append(row)

    output_rows: list[dict[str, str]] = []
    for key, market_rows in groups.items():
        implied_sum = sum(
            1.0 / safe_float(row.get("price_decimal", "0"))
            for row in market_rows
            if safe_float(row.get("price_decimal", "0")) > 1.0
        )
        if implied_sum <= 0:
            continue
        for row in market_rows:
            price = safe_float(row.get("price_decimal", "0"))
            if price <= 1.0:
                continue
            implied_probability = 1.0 / price
            no_vig_probability = implied_probability / implied_sum
            output_rows.append(
                {
                    "captured_at_utc": key[0],
                    "event_id": key[1],
                    "bookmaker_key": key[2],
                    "market_key": key[3],
                    "outcome_name": row.get("outcome_name", ""),
                    "point": row.get("point", ""),
                    "price_decimal": f"{price:.4f}",
                    "implied_probability": f"{implied_probability:.6f}",
                    "no_vig_probability": f"{no_vig_probability:.6f}",
                    "market_overround": f"{implied_sum:.6f}",
                }
            )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "captured_at_utc",
        "event_id",
        "bookmaker_key",
        "market_key",
        "outcome_name",
        "point",
        "price_decimal",
        "implied_probability",
        "no_vig_probability",
        "market_overround",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Wrote {len(output_rows)} no-vig market probability rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
