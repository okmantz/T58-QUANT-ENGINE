"""Independent oracle: a from-scratch, 25-line re-statement of the documented bar semantics, compared with the engine on seeded
random synthetic bars (long & short, stops, targets, gaps, per-side spread+slippage, per-contract commission).
Semantics encoded (all pinned individually by test_01): fill at open[e]+d*side_cost; stop/target anchored to the FILL price;
per bar: gap through stop -> open; else stop touched -> stop; else target touched -> target; any exit pays side_cost against
the trade; stop beats target when both are touched in one bar."""
import warnings
import numpy as np
import pandas as pd
from app.backtest.execution import run_execution
from synth import risk

CS, COMM, SLIP, SPR = 50.0, 2.0, 0.25, 0.25


def make_bars(rng, n=60):
    ts = pd.date_range("2024-03-04 14:30", periods=n, freq="1min")
    c = 5000 + np.cumsum(rng.normal(0, 2.5, n)); o = np.r_[c[0], c[:-1]] + rng.normal(0, 1.0, n)
    h = np.maximum(o, c) + np.abs(rng.normal(0, 1.2, n)); l = np.minimum(o, c) - np.abs(rng.normal(0, 1.2, n))
    return pd.DataFrame(dict(timestamp=ts, open=o, high=h, low=l, close=c, volume=100.0))


def oracle(df, k, d, SL, TP, contracts):
    side = SLIP + SPR
    e = k + 1
    ep = df.open[e] + d * side
    stop, tp = ep - d * SL, ep + d * TP
    for j in range(e, len(df)):
        o, h, l = df.open[j], df.high[j], df.low[j]
        xp = None
        if d == 1:
            if o <= stop: xp = o
            elif l <= stop: xp = stop
            elif h >= tp: xp = tp
        else:
            if o >= stop: xp = o
            elif h >= stop: xp = stop
            elif l <= tp: xp = tp
        if xp is not None:
            xp -= d * side
            return ep, xp, (xp - ep) * d * CS * contracts - COMM * contracts
    return None


def test_engine_matches_oracle_on_random_bars():
    rng = np.random.default_rng(2026)
    compared = 0
    for _ in range(400):
        df = make_bars(rng)
        k = int(rng.integers(1, 15)); d = int(rng.choice([1, -1])); SL = float(rng.uniform(4, 20)); TP = float(rng.uniform(4, 30))
        sig = pd.Series(0, index=df.index); sig.iloc[k:] = d
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tr, _ = run_execution(df, sig, risk(sizing_mode="fixed_contracts", fixed_contracts=3, commission_per_contract=COMM,
                                                slippage_pips=SLIP, spread_pips=SPR, max_trades_per_day=50),
                                  stop_loss_pips=SL, take_profit_pips=TP)
        ref = oracle(df, k, d, SL, TP, 3)
        if ref is None or not tr:
            continue
        ep, xp, pnl = ref
        t = tr[0]
        assert t.entry_time == df.timestamp[k + 1]
        assert abs(t.entry_price - ep) < 1e-9, (k, d, SL, TP)
        assert abs(t.exit_price - xp) < 1e-9, (k, d, SL, TP, t.exit_reason)
        assert abs(t.pnl - pnl) < 0.01, (k, d, SL, TP, t.pnl, pnl)
        compared += 1
    assert compared > 250
