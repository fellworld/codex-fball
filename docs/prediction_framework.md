# Prediction framework

Last updated: 2026-06-06

## First working model

The first prediction layer uses data already available in the project:

- FIFA official squad list.
- Player club affiliations.
- Team club-distribution features.
- Group-stage schedule.
- Tactical profile placeholders.

It deliberately avoids pretending that subjective tactical labels, likely starters, injury status, and odds signals are complete before those feeds are actually collected.

## Current outputs

- `data/processed/team_strength_ratings.csv`
- `data/processed/match_prediction_inputs.csv`
- `data/processed/team_form_features.csv`
- `data/processed/team_power_ratings.csv`
- `data/processed/team_phase_ratings.csv`

## Team strength rating

The current rating is a provisional club-quality score, not a full football power rating.

Components:

- Big-five league country player share.
- Domestic club player share.
- Club concentration from the top five clubs.
- Squad dispersion across many clubs and club countries.

Interpretation:

- Higher score usually means stronger club-level pedigree.
- Higher domestic concentration can indicate tactical familiarity, but can also indicate lower external club quality for some teams.
- High dispersion can reduce familiarity, so it receives a small penalty.

This score should later be blended with:

- FIFA Ranking.
- Elo rating.
- Recent match form.
- Expected starting XI quality.
- Injuries/suspensions.
- Tactical style.
- Market-implied probabilities from odds.

## Match input table

`match_prediction_inputs.csv` contains one row per group-stage fixture. It joins:

- Match schedule.
- Team A strength score.
- Team B strength score.
- Score difference.
- Initial favorite.
- Initial total-goals lean.

The initial total-goals lean is intentionally conservative. It is based on strength gap only until tactical and odds data are complete.

## Next modeling steps

1. Replace the current FIFA-rank proxy with a full official FIFA table when available.
2. Fill tactical tags in `team_tactical_profiles.csv`.
3. Add likely starters to `squad_players.csv` or `expected_lineups.csv`.
4. Convert odds snapshots into no-vig probabilities.
5. Blend model probability and market probability.
