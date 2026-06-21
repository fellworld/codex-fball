import importlib


MODULES = [
    "collectors.fifa_squad_collector",
    "collectors.match_context_collector",
    "collectors.odds_collector",
    "collectors.public_football_data",
    "features.match_prediction_inputs",
    "features.model_input_builder",
    "features.odds_implied_probabilities",
    "features.team_club_features",
    "features.team_form_features",
    "features.team_power_ratings",
    "features.team_strength_rating",
    "reports.generate_prematch_reports",
    "reports.evaluate_market_recommendations",
    "reports.evaluate_probability_calibration",
    "reports.inject_match_intelligence",
    "reports.score_market_candidates",
    "reports.backtest_strategy_tiers",
    "pipelines.full_refresh",
    "simulation.group_stage_simulator",
    "simulation.poisson_match_simulator",
    "simulation.robust_match_simulator",
]


def test_core_modules_import() -> None:
    for module in MODULES:
        importlib.import_module(module)
