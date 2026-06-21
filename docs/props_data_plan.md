# Corner and card prop data plan

Last updated: 2026-06-16

## Current status

The project now has placeholder-ready tables for corner and card markets:

- `data/processed/team_discipline_setpiece_features.csv`
- `data/processed/match_event_stats.csv`
- `data/processed/match_prop_prediction_inputs.csv`

The current rows are model priors, not verified historical event statistics. They should be treated as low-confidence inputs until recent match event data and referee tendencies are collected.

## Target markets

- Total corners
- Team corners
- Corner handicap
- Total yellow cards
- Total red cards or red-card risk
- Team cards

## Required future inputs

- Recent corners for and against
- Recent yellow and red cards for and against
- Fouls for and against
- Referee cards per match
- Referee fouls called per match
- Match state context: favorite, expected possession, and knockout/group urgency

## Modeling approach

For corners, start with attacking pressure, wide play, set-piece attack rating, opponent defensive pressure, and expected goal share.

For cards, start with team foul tendency, underdog defensive load, transition mismatch, referee card rate, rivalry/urgency, and red-card history.

The first production upgrade should replace `model_prior` rows with at least 10 recent matches per team from a verified event-stat source.
