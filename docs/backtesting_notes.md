# Backtesting notes

Last updated: 2026-06-20

## First 32 matches

The first 32 final scores are stored in:

- `data/processed/match_actual_results.csv`

Backtest output:

- `data/processed/prediction_backtest_summary.csv`

Current result:

- Match result direction: 17/32
- Over/under 2.5: 18/32
- Exact most-likely score: 4/32
- Actual score inside top 5 scorelines: 14/32

## Interpretation

Exact score is a low-probability target. Even the most likely football scoreline is often only around 10-16% likely in this model. For match previews, use the top scoreline cluster instead of a single score prediction.

The first 32 matches show two recurring issues: the model underweights some high-margin/high-total tails, and it has over-favored several nominal stronger teams in result direction. Result direction improved from matches 17-32, but high-tail scores such as 4-2, 4-1, and 6-0 remain underweighted. Totals are no longer clearly stronger than result direction after several 1-0 and 2-0 outcomes punished broad over leans.

## Next model improvements

- Report top 5 scorelines in every pre-match report.
- Add a calibration table for actual score rank and probability.
- Consider a tail-risk adjustment for high-tempo or strong-favorite matches after more results are available.
- Keep exact score as a secondary signal; use totals, result direction, and score clusters for decision-making.

## Market recommendation backtesting

The project now has a separate workflow for user-provided market screenshots and chat recommendations:

- `data/processed/market_lines.csv`: captured Asian handicap and goal-total lines from screenshots.
- `data/processed/market_recommendations.csv`: recommended candidates selected from those markets.
- `src/reports/evaluate_market_recommendations.py`: settles Asian handicap and total recommendations, including quarter lines.
- `data/processed/recommendation_settlement.csv`: one settled row per recommendation.
- `data/processed/market_backtest_summary.csv`: grouped settlement summary by market type and recommendation set.
- `data/processed/market_candidate_scores.csv`: A/B/C strategy scoring for all captured screenshot lines.
- `src/reports/score_market_candidates.py`: applies the revised selection layer before any recommendation is promoted.

Current seeded sample:

- Matches 21-24 stable candidates: 2 positive settlements from 4, net -0.1300 units.
- Matches 25-28 stable candidates: 0 positive settlements from 4, net -4.0000 units.
- Matches 29-32 stable candidates: 2 positive settlements from 4, net -0.5200 units.
- Total seeded market candidates: 4 positive settlements from 12, net -4.6500 units.

Interpretation:

- The candidate selector overvalued underdog protection in matches where favorites had blowout risk.
- The total-goals selector overvalued 2/2.5 over positions in low-score tactical spots.
- Future candidate ranking should penalize favorite blowout risk, low-score density, and large disagreement against a strongly directional market.
- The 29-32 set improved because Morocco -0.5/1 aligned model and market direction, and Brazil vs Haiti under 3.5 respected blowout-tail caution. The remaining misses were both over positions, reinforcing that broad over leans need stricter low-score-density checks.

## Revised selection strategy

The project now separates model pricing from recommendation selection:

1. The baseline Poisson score matrix estimates initial score probabilities.
2. `src/simulation/robust_match_simulator.py` adds an uncertainty-aware Poisson mixture.
3. The strategy layer uses the robust score matrix to price settlement probabilities and expected value.
4. Candidates are assigned tiers instead of forcing four picks.

Tier interpretation:

- `A`: playable candidate. Requires positive model EV and no current structural red flags.
- `B`: watch-only candidate. Has some model value but violates a known risk rule; do not promote into the main recommendation set unless later evidence supports that pattern.
- `C`: avoid. Either negative model value or a structural risk that has recently performed poorly.

Current risk rules:

- Ordinary over positions are downgraded when the model still has high `<=2 goals` density.
- Underdog handicap positions are capped at `B` because recent results show the model overvalued protection and underweighted blowouts.
- Underdog handicap positions are downgraded to `C` when favorite blowout-tail risk is high.
- `A` candidates must also clear the market baseline: model positive probability cannot sit below the market no-vig probability.
- High-total unders can reach `A` when the line gives enough buffer and the model does not show excessive 4+ goal density.
- Favorite Asian handicap positions can reach `A` when model direction and market direction align and the handicap is not too deep.

On the current captured 21-32 market lines, the revised strategy would only mark these as `A`:

- Scotland vs Morocco: Morocco -0.5/1.
- Brazil vs Haiti: Under 3.5.

This is intentionally stricter than the previous "top four" workflow. If a screenshot only has one or two `A` candidates, the correct output is one or two candidates, not a forced four-pick list.

## Strategy-tier backtest

`src/reports/backtest_strategy_tiers.py` replays the revised A/B/C strategy against completed market lines. It uses every captured line, not just the chat-selected recommendations.

Current completed sample covers matches 21-32:

- All captured lines: 24 positive settlements from 48, net -1.5500 units.
- `A` tier: 2 positive settlements from 2, net +1.4800 units.
- `B` tier: 1 positive settlement from 8, net -5.9900 units.
- `C` tier: 21 positive settlements from 38, net +2.9600 units.

Interpretation:

- The `A` filter is directionally promising, but the sample is tiny and should not be overfit.
- `B` performed badly because most `B` candidates were protected underdogs, the same pattern that recently failed.
- `C` profitability is not directly actionable because it contains many mutually exclusive opposite sides and lines that were intentionally not selected. It does show that the strategy layer may still be too aggressive in downgrading some contrarian outcomes, but that needs more samples.

Operational rule from now on:

- Only `A` candidates are playable.
- `B` candidates are listed as watch-only, not recommended stakes.
- If a screenshot has no `A`, the recommendation is no play.

## Uncertainty-aware model layer

The model now includes a lightweight version of the Bayesian/partial-pooling ideas reviewed from `playmobil/worldcup-forecast`:

- `data/processed/team_rating_uncertainty.csv` assigns each team a `rating_std_log_xg` based on power rating, club-quality coverage, form, and Elo coverage.
- `data/processed/match_robust_simulation_summary.csv` and `data/processed/match_robust_score_probabilities.csv` are generated by sampling xG around the baseline model with deterministic seeds.
- `data/processed/model_run_metadata.csv` records the robust run seed, draw count, goal cap, and model note.
- Market odds remain a validation and selection baseline; they are not fed into team strength or xG creation.

Current robust run:

- Seed: `20260620`
- Draws per match: `2500`
- Max score grid: `0-8`
- Tempo uncertainty: `0.1000` log-xG standard deviation

`src/reports/score_market_candidates.py` now reads the robust probability files by default and falls back to the baseline Poisson outputs only if the robust files are missing.

## Probability calibration

`src/reports/evaluate_probability_calibration.py` writes `data/processed/probability_calibration_report.csv`.

Current robust calibration on the first 32 final matches:

- Result Brier score: `0.593361`
- Result log loss: `0.990397`
- Total-goals Brier score: `0.241866`
- Total-goals log loss: `0.676667`
