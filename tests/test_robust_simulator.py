from simulation.robust_match_simulator import (
    draw_lambda,
    summarize_score_grid,
    team_uncertainty,
)


def test_team_uncertainty_increases_for_sparse_profile() -> None:
    strong = team_uncertainty(
        {
            "team": "Strong",
            "power_rating": "95",
            "club_quality_rating": "90",
            "form_rating": "90",
            "elo_normalized": "90",
        }
    )
    sparse = team_uncertainty(
        {
            "team": "Sparse",
            "power_rating": "45",
            "club_quality_rating": "30",
            "form_rating": "55",
            "elo_normalized": "50",
        }
    )

    assert float(sparse["rating_std_log_xg"]) > float(strong["rating_std_log_xg"])


def test_draw_lambda_keeps_positive_expected_goals() -> None:
    import random

    rng = random.Random(1)
    assert draw_lambda(1.4, 0.15, rng, 0.0) > 0


def test_summarize_score_grid_normalizes_probabilities() -> None:
    match = {
        "source_order": "1",
        "group": "A",
        "date_china": "2026-06-12",
        "time_china": "03:00",
        "team_a": "A",
        "team_b": "B",
        "team_a_expected_goals": "1.0",
        "team_b_expected_goals": "1.0",
        "total_expected_goals": "2.0",
    }
    summary, scores = summarize_score_grid(match, [[0.25, 0.25], [0.25, 0.25]], 1)

    assert summary["most_likely_score"] == "0-0"
    assert round(sum(float(row["probability"]) for row in scores), 6) == 1.0
