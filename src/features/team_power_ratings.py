"""Blend club quality, Elo, FIFA-rank proxy, and recent form into power ratings."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build blended team power ratings.")
    parser.add_argument("--club", default="data/processed/team_strength_ratings.csv")
    parser.add_argument("--elo", default="data/processed/public_elo_ratings.csv")
    parser.add_argument("--form", default="data/processed/team_form_features.csv")
    parser.add_argument("--output", default="data/processed/team_power_ratings.csv")
    parser.add_argument("--phase-output", default="data/processed/team_phase_ratings.csv")
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize(values: dict[str, float], invert: bool = False) -> dict[str, float]:
    low = min(values.values())
    high = max(values.values())
    if high <= low:
        return {key: 50.0 for key in values}
    output = {}
    for key, value in values.items():
        score = (value - low) / (high - low) * 100.0
        output[key] = 100.0 - score if invert else score
    return output


def main() -> int:
    args = parse_args()
    club_rows = read_csv(args.club)
    elo_rows = read_csv(args.elo)
    form_rows = read_csv(args.form)

    teams = [row["team"] for row in club_rows]
    club = {row["team"]: as_float(row["club_quality_rating"], 50.0) for row in club_rows}
    codes = {row["team"]: row["team_code"] for row in club_rows}
    elo_raw = {row["team"]: as_float(row["elo_rating"], 1500.0) for row in elo_rows}
    elo_rank_raw = {row["team"]: as_float(row["elo_rank"], 100.0) for row in elo_rows}
    form = {row["team"]: as_float(row["form_rating"], 50.0) for row in form_rows}
    avg_gf = {row["team"]: as_float(row["avg_goals_for"], 1.2) for row in form_rows}
    avg_ga = {row["team"]: as_float(row["avg_goals_against"], 1.2) for row in form_rows}

    elo_norm = normalize({team: elo_raw.get(team, 1500.0) for team in teams})
    fifa_rank_norm = normalize({team: elo_rank_raw.get(team, 100.0) for team in teams}, invert=True)
    attack_form_norm = normalize({team: avg_gf.get(team, 1.2) for team in teams})
    defense_form_norm = normalize({team: avg_ga.get(team, 1.2) for team in teams}, invert=True)

    checked_at = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    rows: list[dict[str, str]] = []
    phase_rows: list[dict[str, str]] = []
    for team in teams:
        club_score = club.get(team, 50.0)
        elo_score = elo_norm.get(team, 50.0)
        form_score = form.get(team, 50.0)
        fifa_score = fifa_rank_norm.get(team, 50.0)
        power = 0.40 * elo_score + 0.25 * club_score + 0.25 * form_score + 0.10 * fifa_score
        attack = 0.55 * power + 0.30 * attack_form_norm.get(team, 50.0) + 0.15 * club_score
        defense = 0.55 * power + 0.30 * defense_form_norm.get(team, 50.0) + 0.15 * club_score

        rows.append(
            {
                "team": team,
                "team_code": codes.get(team, ""),
                "power_rating": f"{power:.2f}",
                "club_quality_rating": f"{club_score:.2f}",
                "elo_rating": f"{elo_raw.get(team, 0):.0f}",
                "elo_normalized": f"{elo_score:.2f}",
                "fifa_rank": f"{int(elo_rank_raw.get(team, 0))}" if team in elo_rank_raw else "",
                "fifa_rank_source": "Elo rank proxy; replace with official FIFA rank when full table is available.",
                "fifa_rank_normalized": f"{fifa_score:.2f}",
                "form_rating": f"{form_score:.2f}",
                "attack_rating": f"{attack:.2f}",
                "defense_rating": f"{defense:.2f}",
                "weights": "elo=0.40;club=0.25;form=0.25;fifa_rank=0.10",
                "source_checked_at": checked_at,
            }
        )
        phase_rows.append(
            {
                "team": team,
                "team_code": codes.get(team, ""),
                "attack_rating": f"{attack:.2f}",
                "defense_rating": f"{defense:.2f}",
                "goalkeeper_rating": f"{defense:.2f}",
                "chance_creation_rating": f"{attack:.2f}",
                "finishing_rating": f"{attack:.2f}",
                "set_piece_attack_rating": f"{attack:.2f}",
                "set_piece_defense_rating": f"{defense:.2f}",
                "transition_attack_rating": f"{attack:.2f}",
                "transition_defense_rating": f"{defense:.2f}",
                "phase_notes": "Derived from blended power rating and recent goals until tactical/player data is filled.",
                "source": "team_power_ratings.py",
                "source_checked_at": checked_at,
            }
        )

    rows.sort(key=lambda row: float(row["power_rating"]), reverse=True)
    for path, data, fields in [
        (
            Path(args.output),
            rows,
            [
                "team",
                "team_code",
                "power_rating",
                "club_quality_rating",
                "elo_rating",
                "elo_normalized",
                "fifa_rank",
                "fifa_rank_source",
                "fifa_rank_normalized",
                "form_rating",
                "attack_rating",
                "defense_rating",
                "weights",
                "source_checked_at",
            ],
        ),
        (
            Path(args.phase_output),
            phase_rows,
            [
                "team",
                "team_code",
                "attack_rating",
                "defense_rating",
                "goalkeeper_rating",
                "chance_creation_rating",
                "finishing_rating",
                "set_piece_attack_rating",
                "set_piece_defense_rating",
                "transition_attack_rating",
                "transition_defense_rating",
                "phase_notes",
                "source",
                "source_checked_at",
            ],
        ),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)

    print(f"Wrote {len(rows)} team power ratings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
