"""Build provisional team strength ratings from squad club features."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build provisional team strength ratings.")
    parser.add_argument("--club-features", default="data/processed/team_club_features.csv")
    parser.add_argument("--output", default="data/processed/team_strength_ratings.csv")
    return parser.parse_args()


def to_float(value: str) -> float:
    return float(value or 0)


def score_row(row: dict[str, str]) -> dict[str, str]:
    squad_size = max(to_float(row["squad_size"]), 1.0)
    big_five_share = to_float(row["big_five_league_country_players"]) / squad_size
    domestic_share = to_float(row["domestic_club_players"]) / squad_size
    unique_club_share = to_float(row["unique_clubs"]) / squad_size
    unique_country_share = to_float(row["unique_club_countries"]) / squad_size

    top_club_counts = []
    for item in row["top_clubs"].split("; "):
        if ":" in item:
            top_club_counts.append(to_float(item.rsplit(":", 1)[1]))
    top5_club_share = sum(top_club_counts[:5]) / squad_size

    raw_score = (
        50.0
        + 35.0 * big_five_share
        + 8.0 * domestic_share
        + 8.0 * top5_club_share
        - 8.0 * unique_club_share
        - 4.0 * unique_country_share
    )
    rating = max(1.0, min(99.0, raw_score))

    tier = "elite" if rating >= 72 else "strong" if rating >= 64 else "middle" if rating >= 56 else "outsider"

    return {
        "team": row["team"],
        "team_code": row["team_code"],
        "club_quality_rating": f"{rating:.2f}",
        "club_quality_tier": tier,
        "big_five_share": f"{big_five_share:.3f}",
        "domestic_share": f"{domestic_share:.3f}",
        "top5_club_share": f"{top5_club_share:.3f}",
        "unique_club_share": f"{unique_club_share:.3f}",
        "unique_club_country_share": f"{unique_country_share:.3f}",
        "rating_notes": "Provisional club-affiliation rating; blend with Elo/FIFA/form before final prediction.",
    }


def main() -> int:
    args = parse_args()
    with Path(args.club_features).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    scored = [score_row(row) for row in rows]
    scored.sort(key=lambda row: float(row["club_quality_rating"]), reverse=True)

    fieldnames = [
        "team",
        "team_code",
        "club_quality_rating",
        "club_quality_tier",
        "big_five_share",
        "domestic_share",
        "top5_club_share",
        "unique_club_share",
        "unique_club_country_share",
        "rating_notes",
    ]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scored)

    print(f"Wrote {len(scored)} team strength ratings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
