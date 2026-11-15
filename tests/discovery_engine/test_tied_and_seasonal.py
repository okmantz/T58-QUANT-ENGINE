"""F8: instrument-tied routing follows the v13 registry. F6: the time-of-day tilt reads the NEXT bar's clock minute."""
import numpy as np
import pandas as pd


def test_every_registry_tied_family_is_routed_as_tied():
    from app.discovery_engine.promotion import is_instrument_tied
    from app.search.families_v13 import V13_META
    tied = [n for n, m in V13_META.items() if m.tied]
    assert tied and all(is_instrument_tied({}, n) for n in tied)
    assert not is_instrument_tied({}, "trend_breakout")


def test_seas_tod_next_uses_only_bars_up_to_t():
    from app.strategy.indicators_v13_market import seas_tod, seas_tod_next
    ts = []
    for d in pd.bdate_range("2024-01-02", periods=40):
        ts += list(pd.date_range(d + pd.Timedelta(hours=9, minutes=30), periods=78, freq="5min"))
    f = pd.DataFrame({"timestamp": ts, "open": 100.0, "high": 101.0, "low": 99.0, "volume": 1.0,
                      "close": 100 + np.cumsum(np.random.default_rng(1).normal(0, .1, len(ts)))})
    b = seas_tod_next(f, 0, None, None)
    assert b.notna().sum() > 0
    cut = 2500
    assert np.allclose(b.iloc[:cut].to_numpy(float), seas_tod_next(f.iloc[:cut].copy(), 0, None, None).to_numpy(float), equal_nan=True)   # prefix-invariant
    f2 = f.copy()
    f2.loc[f2.index[-1], "close"] += 50.0                    # changing the LAST bar cannot change any earlier value
    assert np.allclose(seas_tod_next(f2, 0, None, None).iloc[:-2].dropna(), b.iloc[:-2].dropna())
