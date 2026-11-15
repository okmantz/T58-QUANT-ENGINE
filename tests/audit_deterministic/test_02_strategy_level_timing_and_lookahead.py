"""Strategy-level known answers through run_backtest (the real chokepoint every tool uses)."""
import warnings
import numpy as np
import pandas as pd
from app.backtest.engine import run_backtest
from app.strategy.base import Strategy, StrategyResult
from synth import frame, risk


class CloseAboveSma3(Strategy):
    source_type = "python"

    def generate(self, df):
        c = df["close"]
        sma = c.rolling(3).mean()
        sig = (c > sma).astype(int)          # known at the CLOSE of bar i
        return StrategyResult(name="close>sma3", source_type="python", signals=sig, stop_loss_pips=1000.0, take_profit_pips=1000.0)


class PeekNextClose(Strategy):
    """PLANTED lookahead bug: signal at bar i uses close[i+1]. The engine's guard must flag it."""
    source_type = "python"

    def generate(self, df):
        c = df["close"]
        sig = (c.shift(-1) > c).astype(int)
        return StrategyResult(name="peek", source_type="python", signals=sig, stop_loss_pips=5.0, take_profit_pips=5.0)


def _bars_flat_then_ramp():
    # closes: 10,10,10,10,12,14,...  => first bar with close > SMA3 is i=4 (12 > (10+10+12)/3 = 10.67)
    closes = [10, 10, 10, 10, 12, 14, 16, 18, 20, 22, 24, 26]
    return [(c, c + 0.1, c - 0.1, c) for c in closes]


def test_signal_on_bar_close_fills_at_next_bar_open():
    df = frame(_bars_flat_then_ramp())
    rc = risk(risk_value=100000.0, contract_size=1.0, sizing_mode="fixed_contracts", fixed_contracts=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = run_backtest(df, CloseAboveSma3(), rc, lookahead_check="skip")
    assert res.trades, "strategy must trade"
    t = res.trades[0]
    assert t.entry_time == df.timestamp[5], "signal known at close of bar 4 => fill at OPEN of bar 5"
    assert t.entry_price == 14.0      # open of bar 5 (frame opens = closes): the bar-5 open is 14, NOT the bar-4 close of 12


def test_planted_lookahead_is_detected():
    rng = np.random.default_rng(11)
    c = 100 + np.cumsum(rng.normal(0, 1, 400))
    df = frame([(x, x + 0.5, x - 0.5, x) for x in c])
    rc = risk(risk_value=100000.0, contract_size=1.0, sizing_mode="fixed_contracts", fixed_contracts=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = run_backtest(df, PeekNextClose(), rc, lookahead_check="always")
    assert any("LOOKAHEAD" in w.upper() for w in res.warnings), "engine failed to flag a strategy that reads the next bar"


def test_clean_strategy_is_not_flagged():
    rng = np.random.default_rng(5)
    c = 100 + np.cumsum(rng.normal(0, 1, 400))
    df = frame([(x, x + 0.5, x - 0.5, x) for x in c])
    rc = risk(risk_value=100000.0, contract_size=1.0, sizing_mode="fixed_contracts", fixed_contracts=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = run_backtest(df, CloseAboveSma3(), rc, lookahead_check="always")
    assert not any("LOOKAHEAD BIAS DETECTED" in w for w in res.warnings)
