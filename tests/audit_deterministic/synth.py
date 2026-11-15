"""Hand-built synthetic data with KNOWN answers. Nothing here is random unless seeded; every expected number in the tests is
derived by hand in the test's docstring, not copied from engine output."""
from __future__ import annotations
import warnings
import pandas as pd
from app.backtest.execution import run_execution
from app.backtest.risk import RiskConfig

F = (100.0, 100.2, 99.8, 100.0)          # a flat, harmless bar (open, high, low, close)
T0 = "2024-01-02 15:00"                  # a Tuesday, mid-session (CT 09:00), no DST edge

def frame(bars, start=T0, freq="1min"):
    ts = pd.date_range(start, periods=len(bars), freq=freq)
    return pd.DataFrame([(t, *b, 1000.0) for t, b in zip(ts, bars)],
                        columns=["timestamp", "open", "high", "low", "close", "volume"])

def risk(**kw):
    """ES-like: 1 point = $50 (pip_size 1.0, contract_size 50). Zero friction unless a test sets it."""
    base = dict(initial_balance=50000.0, risk_mode="fixed", risk_value=1050.0, pip_size=1.0, contract_size=50.0,
                commission_per_trade=0.0, commission_per_contract=0.0, slippage_pips=0.0, spread_pips=0.0,
                sizing_mode="skip")
    base.update(kw)
    return RiskConfig(**base)

def run(bars, direction=1, sl=10.0, tp=20.0, start=1, trail=None, be=None, **riskkw):
    """Signal = `direction` from bar `start` to the second-to-last bar, flat on the last bar. Entry therefore fills at
    open[start + 1] (one-bar lag). Returns the FIRST trade (later trades are re-entries and not under test)."""
    df = frame(bars)
    n = len(df)
    sig = [0] * n
    sig[start:n - 1] = [direction] * (n - 1 - start)
    td = None if trail is None else pd.Series([float(trail)] * n)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        trades, eq = run_execution(df, pd.Series(sig), risk(**riskkw), stop_loss_pips=sl, take_profit_pips=tp,
                                   trailing_stop_distance=td, breakeven_trigger_r=be)
    return trades, df, eq
