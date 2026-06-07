# Match simulation model

Last updated: 2026-06-06

## Current model

The first simulator uses an independent Poisson model:

- Estimate expected goals for Team A and Team B.
- Compute scoreline probabilities from 0-0 through `max_goals`.
- Aggregate scorelines into win/draw/loss, over/under, and most likely scores.

## Current inputs

The current version uses:

- `team_strength_ratings.csv`
- `team_power_ratings.csv`
- `team_form_features.csv`
- `match_prediction_inputs.csv`
- optional `team_phase_ratings.csv`
- optional `team_tactical_profiles.csv`
- optional `match_context.csv`

Elo and recent form are now populated from public sources. FIFA rank currently uses an Elo-rank proxy unless a full official FIFA ranking table is supplied. Injuries, starting XI, tactical labels, and odds remain provisional inputs.

## Model formula

Base expected goals:

- Neutral match baseline: 1.35 goals per team.
- Rating gap adjustment: each 10 attack/defense rating points changes expected goals by about 0.18.
- Total-goals adjustment: tactical tags can nudge the total up or down when filled.

Output:

- `match_score_probabilities.csv`
- `match_simulation_summary.csv`

## Next upgrades

1. Replace FIFA-rank proxy with full official FIFA rank.
2. Add expected starting XI adjustments.
3. Add market-implied probabilities from odds.
4. Add Dixon-Coles correction for low-score dependence.
5. Add weather/travel adjustments near match day.
