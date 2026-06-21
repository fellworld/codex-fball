from reports.evaluate_market_recommendations import (
    settle_asian_handicap,
    settle_total,
)


def test_asian_handicap_quarter_lines() -> None:
    assert settle_asian_handicap(1, 3, 1.25) == -1.0
    assert settle_asian_handicap(1, 2, 1.25) == 0.5
    assert settle_asian_handicap(1, 1, 1.25) == 1.0
    assert settle_asian_handicap(3, 1, -1.5) == 1.0
    assert settle_asian_handicap(2, 1, -1.25) == -0.5


def test_goal_total_quarter_lines() -> None:
    assert settle_total(2, 2.25, "over") == -0.5
    assert settle_total(3, 2.25, "over") == 1.0
    assert settle_total(2, 2.75, "under") == 1.0
    assert settle_total(3, 2.75, "under") == -0.5
