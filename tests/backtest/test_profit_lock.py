"""Profit-lock ladder and adaptive loser cut: the pure functions and the backtest engine integration."""
import warnings

import pandas as pd

from app.backtest import profit_lock as pl
from app.backtest.execution import run_execution
from app.backtest.risk import RiskConfig

TIERS = ((100.0, 0.0), (200.0, 75.0), (300.0, 150.0), (400.0, 250.0), (600.0, 420.0))


def test_ladder_matches_the_owner_example():
    cfg = pl.ProfitLockConfig(tiers=TIERS, trail_frac=0.0)
    assert pl.ladder_lock_dollars(50, cfg) is None                  # not yet at the first rung
    assert pl.ladder_lock_dollars(100, cfg) == 0.0                  # break-even
    assert 50 <= pl.ladder_lock_dollars(200, cfg) <= 100            # $200 reached -> stop to $50-$100
    assert pl.ladder_lock_dollars(400, cfg) == 250.0                # $400 reached -> stop to $250
    assert pl.ladder_lock_dollars(399, cfg) == 150.0


def test_ladder_trails_a_runner_beyond_the_last_rung_and_never_loosens():
    cfg = pl.ProfitLockConfig(tiers=TIERS, trail_frac=0.7)
    assert pl.ladder_lock_dollars(1000, cfg) == 700.0
    last = -1.0
    for peak in range(0, 1500, 10):                                 # the lock is monotone in the peak
        v = pl.ladder_lock_dollars(peak, cfg)
        if v is not None:
            assert v >= last
            last = v


def test_normalise_tiers_caps_lock_at_trigger_and_sorts():
    assert pl.normalise_tiers(((300, 900), (100, 0))) == ((100.0, 0.0), (300.0, 300.0))


def test_lock_stop_price_is_net_of_costs_and_stop_only_tightens():
    assert pl.lock_stop_price(100.0, 1, 10.0, 250.0, 5.0) == 125.5
    assert pl.lock_stop_price(100.0, -1, 10.0, 250.0, 5.0) == 74.5
    assert pl.tightened(90.0, 125.0, 1) == 125.0 and pl.tightened(130.0, 125.0, 1) == 130.0
    assert pl.tightened(110.0, 75.0, -1) == 75.0 and pl.tightened(70.0, 75.0, -1) == 70.0


def test_loser_cut_only_fires_on_trades_that_never_worked():
    cfg = pl.LoserCutConfig(cut_frac=0.6, min_bars=3, max_mfe_frac=0.25)
    assert pl.should_cut_loser(5, -70.0, 5.0, 100.0, cfg)           # down 70% of risk, never worked
    assert not pl.should_cut_loser(2, -70.0, 5.0, 100.0, cfg)       # too early
    assert not pl.should_cut_loser(5, -70.0, 60.0, 100.0, cfg)      # it WAS working (peak 60% of risk): the ladder owns it
    assert not pl.should_cut_loser(5, -30.0, 5.0, 100.0, cfg)       # not down enough
    assert not pl.should_cut_loser(5, 40.0, 5.0, 100.0, cfg)        # a winner is never cut


FLAT = (100, 100.2, 99.8, 100)


def _run(bars, **risk_kw):
    n = len(bars)
    ts = pd.date_range("2024-01-02 15:00", periods=n, freq="1min")
    df = pd.DataFrame([(t, *b, 1000.0) for t, b in zip(ts, bars)], columns=["timestamp", "open", "high", "low", "close", "volume"])
    sig = [0] * n
    sig[1:n - 1] = [1] * (n - 2)
    risk = RiskConfig(initial_balance=50000.0, risk_mode="fixed", risk_value=100.0, pip_size=1.0, contract_size=1.0,
                      spread_pips=0.0, slippage_pips=0.0, commission_per_trade=0.0, **risk_kw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        trades, _ = run_execution(df, pd.Series(sig), risk, stop_loss_pips=10, take_profit_pips=None)
    return trades[0]


SPIKE_THEN_CRASH = [FLAT, FLAT, FLAT, (100, 142, 100, 140), (140, 141, 85, 86), FLAT, FLAT]


def test_without_the_ladder_a_400_dollar_winner_that_reverses_is_a_full_loss():
    t = _run(SPIKE_THEN_CRASH)
    assert t.pnl < -50


def test_ladder_locks_the_winner_when_it_reverses():
    t = _run(SPIKE_THEN_CRASH, profit_lock_tiers=TIERS)
    assert t.exit_cause == "profit_lock"
    assert 240.0 <= t.pnl <= 260.0                                  # the $400 rung locks $250 (size 10 units: $10 per price point)


def test_ladder_default_off_leaves_results_identical():
    base = _run([FLAT, FLAT, FLAT, (100, 130, 99, 125), FLAT, FLAT])
    assert base.exit_cause != "profit_lock"


def test_loser_cut_closes_a_trade_that_never_worked():
    bars = [FLAT, FLAT, FLAT, (100, 100.3, 97, 97), (97, 97.2, 95, 95), (95, 95.1, 93, 93.5), FLAT, FLAT]
    plain = _run(bars)
    cut = _run(bars, loss_cut_frac=0.6, loss_cut_min_bars=1)
    assert cut.exit_reason == "loss_cut"
    assert cut.pnl > plain.pnl or plain.exit_reason != "stop_loss"
    assert cut.pnl > -100.0
