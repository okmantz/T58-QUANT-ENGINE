"""Regression tests for defects CONFIRMED by the 2026-11-14 audit. Each FAILS on the audited commit (dbaf81e) and PASSES with the
corresponding audit patch. Expected values are hand-derived (see each docstring)."""
import os, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from conftest import REPO

warnings.simplefilter("ignore")


def test_futures_specs_tick_size_times_contract_size_equals_tick_value():
    """Identity for every spec that declares a tick value: tick_size x contract_size == tick_value (the engine books pnl = units x price move,
    so this must hold whatever pip_size is).
    6E has tick 0.00005 and tick value $6.25 => contract_size must be 125,000 (audited value was 12.5). Patch A (spec fix)."""
    from app.data.instrument_specs import KNOWN_INSTRUMENTS
    bad = []
    for k, s in KNOWN_INSTRUMENTS.items():
        tv = getattr(s, "tick_value", None)
        if not tv or not getattr(s, "tick_size", None):
            continue
        if abs(s.tick_size * s.contract_size - tv) > 1e-6 * max(1.0, tv):
            bad.append((k, s.tick_size, s.contract_size, tv))
    assert not bad, bad


@pytest.mark.parametrize("lag", [2, 3])
def test_no_trade_exits_before_it_enters_with_fill_lag(lag):
    """A position cannot be managed (and stopped out) on bars BEFORE it fills. Audited code produced exit_time < entry_time at lag>=2."""
    from app.backtest.execution import run_execution
    from synth import risk
    rng = np.random.default_rng(3); n = 3000
    c = 5000 + np.cumsum(rng.normal(0, 2, n)); o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + abs(rng.normal(0, 1, n)); l = np.minimum(o, c) - abs(rng.normal(0, 1, n))
    df = pd.DataFrame(dict(timestamp=pd.date_range("2024-03-04 14:30", periods=n, freq="1min"), open=o, high=h, low=l, close=c, volume=100.0))
    sig = pd.Series(np.where(pd.Series(c).rolling(5).mean() > pd.Series(c).rolling(20).mean(), 1, -1)).fillna(0).astype(int)
    tr, _ = run_execution(df, sig, risk(sizing_mode="fit_stop", risk_value=500.0, max_trades_per_day=50, entry_fill_lag_bars=lag),
                          stop_loss_pips=8.0, take_profit_pips=12.0)
    assert len(tr) > 50
    assert [t for t in tr if t.exit_time < t.entry_time] == []


def _days(k):
    return [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(k)]


def test_consistency_rule_exact_boundary_passes():
    """Best day 1,650 of a 3,000 profit is EXACTLY 55%. A 55% cap must allow it (floating error 55.00000000000001 > 55 denied it)."""
    from app.prop.simulator import PropRules, simulate_account
    r = simulate_account([1650, 1350], _days(2), PropRules(account_size=10000, evaluation_profit_target_pct=30, daily_loss_limit_pct=100,
                         max_drawdown_pct=50, consistency_rule_pct=55, min_trading_days=2))
    assert r.passed_evaluation


def test_payout_buffer_is_not_re_earned_every_cycle():
    """$10k account, 1% payout threshold ($100), 2% buffer ($200). Eval passes on day 1 (+600, 5% target). Then +300 per day.
    First payout: profit 300 - buffer 200 = $100. After it the balance already holds the $200 buffer, so each later +300 day must pay
    out the full $300 and leave the balance at 10,200 (audited code paid $100/day and let the balance grow to 12,200 unpaid)."""
    from app.prop.simulator import PropRules, simulate_account
    r = simulate_account([600] + [300] * 11, _days(12), PropRules(
        account_size=10000, evaluation_profit_target_pct=5, daily_loss_limit_pct=100, max_drawdown_pct=50, consistency_rule_pct=None,
        min_trading_days=1, payout_threshold_pct=1, required_buffer_pct=2, payout_frequency_days=1, winning_days_for_payout=1,
        min_winning_day_profit=0))
    assert r.payouts[0].amount == 100.0
    assert all(p.amount == 300.0 and p.balance_after == 10200.0 for p in r.payouts[1:])
    assert r.total_payout_amount == 100.0 + 300.0 * 10


GC = REPO / "data" / "raw" / "GC1!" / "futures_GC.F_1m.parquet"


@pytest.mark.skipif(not GC.exists(), reason="bundled GC data not present")
def test_daily_bars_on_cme_data_spanning_dst_start_at_the_session_open():
    """One calendar year of CME gold (spans two DST changes): 1d bars must be CME sessions starting 18:00 ET, ~259 of them (audited code:
    313 bars at 19:00/20:00 ET, 52 labelled Saturday)."""
    from app.data.timeframe_resample import resample_ohlcv
    g = pd.read_parquet(GC).rename(columns={"ts": "timestamp"})
    g["timestamp"] = pd.to_datetime(g["timestamp"], utc=True)
    w = g[(g.timestamp >= "2024-01-01") & (g.timestamp < "2025-01-01")][["timestamp", "open", "high", "low", "close", "volume"]]
    r = resample_ohlcv(w, "1d")
    et = r.timestamp.dt.tz_convert("America/New_York")
    assert set(et.dt.strftime("%H:%M")) == {"18:00"} and int((et.dt.dayofweek == 5).sum()) == 0 and 255 <= len(r) <= 262
