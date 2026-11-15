"""Known-answer boundary tests for the prop account simulator ($10,000 account so 1% = $100).
Semantics pinned: breach when equity is AT OR BELOW the floor (touching the drawdown line liquidates)."""
import pandas as pd
import pytest
from app.prop.simulator import PropRules, simulate_account

D2 = [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]
D1 = [pd.Timestamp("2024-01-01")]


def go(pnls, dates, **kw):
    base = dict(account_size=10000, evaluation_profit_target_pct=50, daily_loss_limit_pct=100, max_drawdown_pct=5,
                consistency_rule_pct=None, min_trading_days=1, drawdown_type="trailing", trailing_distance_basis="account")
    base.update(kw)
    return simulate_account(pnls, dates, PropRules(**base))


def test_static_drawdown_boundary():
    # floor = 10000 - 500 = 9500
    assert go([-250, -249], D2, drawdown_type="static").failed is False
    r = go([-250, -250], D2, drawdown_type="static")
    assert r.failed and "max_drawdown" in r.failure_reason          # equity == floor breaches


def test_trailing_drawdown_follows_the_high_water_mark():
    # peak 10600 => floor 10600 - 500 = 10100. -499 -> 10101 survives; -500 -> 10100 breaches.
    assert go([600, -499], D2).failed is False
    assert go([600, -500], D2).failed is True


def test_trailing_lock_stops_the_floor_at_the_initial_balance():
    # peak 11000 => unlocked floor 10500 but lock caps it at 10000. -999 -> 10001 survives; -1000 -> 10000 breaches.
    assert go([1000, -999], D2, trailing_lock=True).failed is False
    assert go([1000, -1000], D2, trailing_lock=True).failed is True


def test_daily_loss_boundary():
    kw = dict(drawdown_type="static", max_drawdown_pct=100, daily_loss_limit_pct=5)
    assert go([-499], D1, **kw).failed is False
    r = go([-500], D1, **kw)
    assert r.failed and r.failure_reason == "daily_loss_limit"


def test_profit_target_boundary_6_percent():
    assert go([599], D1, evaluation_profit_target_pct=6).passed_evaluation is False
    assert go([600], D1, evaluation_profit_target_pct=6).passed_evaluation is True


def test_default_PropRules_use_legacy_peak_percent_trailing_documented_hazard():
    """HAZARD PIN: with no explicit settings, trailing drawdown is '% of the PEAK' (peak 10,600 x 5% => floor 10,070),
    not the futures-firm convention of a fixed dollar distance from the peak (floor 10,100). Presets must override it."""
    r = simulate_account([600, -500], D2, PropRules(account_size=10000, evaluation_profit_target_pct=50, daily_loss_limit_pct=100,
                         max_drawdown_pct=5, consistency_rule_pct=None, min_trading_days=1, drawdown_type="trailing"))
    assert r.failed is False                      # survives at 10,100 because the floor is 10,070 under the legacy basis
    assert PropRules().trailing_distance_basis == "peak"
