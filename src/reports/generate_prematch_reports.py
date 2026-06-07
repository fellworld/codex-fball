"""Generate lightweight pre-match Markdown reports for group-stage fixtures."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate pre-match reports.")
    parser.add_argument("--matches", default="data/processed/match_prediction_inputs.csv")
    parser.add_argument("--club-features", default="data/processed/team_club_features.csv")
    parser.add_argument("--coaches", default="data/processed/team_coaches.csv")
    parser.add_argument("--ratings", default="data/processed/team_strength_ratings.csv")
    parser.add_argument("--power-ratings", default="data/processed/team_power_ratings.csv")
    parser.add_argument("--form", default="data/processed/team_form_features.csv")
    parser.add_argument("--simulation", default="data/processed/match_simulation_summary.csv")
    parser.add_argument("--output-dir", default="outputs/reports/prematch")
    return parser.parse_args()


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def team_line(
    team_display: str,
    canonical: str,
    ratings: dict[str, dict[str, str]],
    powers: dict[str, dict[str, str]],
    forms: dict[str, dict[str, str]],
    clubs: dict[str, dict[str, str]],
    coaches: dict[str, dict[str, str]],
) -> str:
    rating = ratings.get(canonical, {})
    power = powers.get(canonical, {})
    form = forms.get(canonical, {})
    club = clubs.get(canonical, {})
    coach = coaches.get(canonical, {})
    return (
        f"| {team_display} | {rating.get('club_quality_rating', '')} | "
        f"{power.get('power_rating', '')} | {power.get('elo_rating', '')} | "
        f"{form.get('recent_wins', '')}-{form.get('recent_draws', '')}-{form.get('recent_losses', '')} | "
        f"{form.get('avg_goals_for', '')}/{form.get('avg_goals_against', '')} | "
        f"{rating.get('club_quality_tier', '')} | {coach.get('head_coach', '')} | "
        f"{club.get('big_five_league_country_players', '')} | "
        f"{club.get('domestic_club_players', '')} | {club.get('top_clubs', '')} |"
    )


def report_body(
    match: dict[str, str],
    ratings: dict[str, dict[str, str]],
    powers: dict[str, dict[str, str]],
    forms: dict[str, dict[str, str]],
    clubs: dict[str, dict[str, str]],
    coaches: dict[str, dict[str, str]],
    simulations: dict[str, dict[str, str]],
) -> str:
    team_a = match["team_a"]
    team_b = match["team_b"]
    team_a_canonical = match["team_a_canonical"]
    team_b_canonical = match["team_b_canonical"]
    sim = simulations.get(match["source_order"], {})

    return "\n".join(
        [
            f"# {team_a} vs {team_b}",
            "",
            f"- Group: {match['group']}",
            f"- China time: {match['date_china']} {match['time_china']}",
            f"- Initial favorite: {match['initial_favorite']}",
            f"- Initial total-goals lean: {match['initial_total_goals_lean']}",
            f"- Club-quality rating gap: {match['rating_diff_a_minus_b']}",
            f"- Simulated win/draw/loss: {sim.get('team_a_win_probability', '')} / {sim.get('draw_probability', '')} / {sim.get('team_b_win_probability', '')}",
            f"- Simulated over 2.5: {sim.get('over_2_5_probability', '')}",
            f"- Most likely score: {sim.get('most_likely_score', '')}",
            "",
            "## Team Snapshot",
            "",
            "| Team | Club rating | Power | Elo | Recent W-D-L | GF/GA | Tier | Head coach | Big-five players | Domestic players | Top clubs |",
            "| --- | ---: | ---: | ---: | --- | --- | --- | --- | ---: | ---: | --- |",
            team_line(team_a, team_a_canonical, ratings, powers, forms, clubs, coaches),
            team_line(team_b, team_b_canonical, ratings, powers, forms, clubs, coaches),
            "",
            "## Current Read",
            "",
            "This is a model preview using public Elo, recent results, and official squad club affiliations. Treat it as a structured preview until odds, lineups, and injuries are complete.",
            "",
            "## Data Still Needed",
            "",
            "- Expected starting XI",
            "- Injuries and suspensions",
            "- Tactical style labels",
            "- Opening and latest bookmaker odds",
            "- Market-implied probabilities after removing overround",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    matches = read_csv(args.matches)
    ratings = {row["team"]: row for row in read_csv(args.ratings)}
    powers = {row["team"]: row for row in read_csv(args.power_ratings)}
    forms = {row["team"]: row for row in read_csv(args.form)}
    clubs = {row["team"]: row for row in read_csv(args.club_features)}
    coaches = {row["team"]: row for row in read_csv(args.coaches)}
    simulations = {row["source_order"]: row for row in read_csv(args.simulation)}

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_rows = ["# Prematch Report Index", ""]
    for match in matches:
        filename = (
            f"{int(match['source_order']):02d}-"
            f"{slugify(match['team_a'])}-vs-{slugify(match['team_b'])}.md"
        )
        path = output_dir / filename
        path.write_text(report_body(match, ratings, powers, forms, clubs, coaches, simulations), encoding="utf-8")
        index_rows.append(
            f"- [{match['source_order']}. {match['team_a']} vs {match['team_b']}]({filename})"
        )

    (output_dir / "index.md").write_text("\n".join(index_rows) + "\n", encoding="utf-8")
    print(f"Wrote {len(matches)} pre-match reports to {output_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
