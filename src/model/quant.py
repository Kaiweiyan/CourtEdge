"""The quant layer: odds math used to turn model probabilities into bets.

All functions are pure and unit-test friendly. American odds in, decisions out.
"""
from __future__ import annotations


def american_to_decimal(odds: float) -> float:
    """American odds -> decimal odds (e.g. -150 -> 1.667, +130 -> 2.30)."""
    return odds / 100.0 + 1.0 if odds > 0 else 100.0 / (-odds) + 1.0


def american_to_implied(odds: float) -> float:
    """American odds -> implied probability (includes the book's vig)."""
    return 100.0 / (odds + 100.0) if odds > 0 else (-odds) / (-odds + 100.0)


def devig_two_way(imp_a: float, imp_b: float) -> tuple[float, float]:
    """Normalise a 2-way market to fair (no-vig) probabilities."""
    total = imp_a + imp_b
    return imp_a / total, imp_b / total


def edge(p_model: float, offered_odds: float) -> float:
    """Displayed edge = model prob - implied prob at the offered price."""
    return p_model - american_to_implied(offered_odds)


def expected_value(p_model: float, offered_odds: float) -> float:
    """EV per 1 unit staked. Positive => +EV bet."""
    b = american_to_decimal(offered_odds) - 1.0
    return p_model * b - (1.0 - p_model)


def kelly_fraction(p_model: float, offered_odds: float) -> float:
    """Full-Kelly stake fraction of bankroll (0 if not +EV)."""
    b = american_to_decimal(offered_odds) - 1.0
    q = 1.0 - p_model
    f = (b * p_model - q) / b
    return max(0.0, f)


def recommended_stake(p_model: float, offered_odds: float,
                      kelly_mult: float, max_frac: float) -> float:
    """Fractional-Kelly stake, capped for safety."""
    return min(max_frac, kelly_mult * kelly_fraction(p_model, offered_odds))


def clv(taken_odds: float, closing_odds: float) -> float:
    """Closing Line Value as a probability delta. Positive => beat the close."""
    return american_to_implied(closing_odds) - american_to_implied(taken_odds)


if __name__ == "__main__":  # quick sanity checks
    assert abs(american_to_implied(-150) - 0.60) < 1e-9
    assert abs(american_to_implied(+130) - 0.4347826) < 1e-6
    assert abs(american_to_decimal(+130) - 2.30) < 1e-9
    a, b = devig_two_way(american_to_implied(-150), american_to_implied(+130))
    assert abs(a + b - 1.0) < 1e-9
    assert kelly_fraction(0.60, -110) > 0           # value bet
    assert kelly_fraction(0.40, -110) == 0          # not +EV
    print("quant.py self-tests passed")
