import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.data import gamma_data as gd
from app.data.gex_conversion import ConversionError, Conversion, convert_levels, daily_fits, fit_conversion

ROOT = Path(__file__).resolve().parents[2]


def test_bs_gamma_matches_closed_form_and_atm_peak():
    s, k, t, iv = 100.0, 100.0, 30 / 365, 0.2
    d1 = (math.log(s / k) + (gd.BS_RATE + 0.5 * iv * iv) * t) / (iv * math.sqrt(t))
    expected = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) / (s * iv * math.sqrt(t))
    assert gd.bs_gamma(s, k, t, iv) == pytest.approx(expected)
    assert gd.bs_gamma(s, 100.0, t, iv) > gd.bs_gamma(s, 120.0, t, iv)       # at-the-money has the most gamma
    assert gd.bs_gamma(0, k, t, iv) == 0.0 and gd.bs_gamma(s, k, 0, iv) == 0.0 and gd.bs_gamma(s, k, t, 0) == 0.0


def test_compute_gex_uses_bs_fallback_when_gamma_missing():
    from datetime import date
    today = date(2026, 11, 16)
    opts = []
    for k in (95, 100, 105):
        opts.append({"option": f"SPY261120C{int(k*1000):08d}", "open_interest": 1000, "iv": 0.2})
        opts.append({"option": f"SPY261120P{int(k*1000):08d}", "open_interest": 1500, "iv": 0.2})
    res = gd.compute_gex({"current_price": 100.0, "options": opts}, instrument="ES", symbol="SPY", max_dte=7, today=today)
    assert res.strikes and any("Black-Scholes" in n for n in res.notes)
    assert res.call_wall is not None and res.put_wall is not None


def test_fit_conversion_recovers_basis_and_ratio():
    etf = np.linspace(480, 490, 40)
    fut = 10.02 * etf + 37.5                       # ratio drifted from 10 and a carry basis
    c = fit_conversion(etf, fut)
    assert c.slope == pytest.approx(10.02) and c.offset == pytest.approx(37.5) and c.r2 > 0.999999
    lv = convert_levels({"call_wall": 490.0, "put_wall": 480.0, "gamma_flip": None}, c)
    assert lv["call_wall"] == pytest.approx(10.02 * 490 + 37.5, abs=0.01) and lv["gamma_flip"] is None


def test_fit_conversion_rejects_bad_inputs():
    with pytest.raises(ConversionError):
        fit_conversion([1, 2], [10, 20])
    with pytest.raises(ConversionError):
        fit_conversion([5.0] * 10, list(range(10)))


def test_daily_fits_are_per_session():
    idx = pd.date_range("2026-11-10 14:30", periods=10, freq="1min").append(pd.date_range("2026-11-11 14:30", periods=10, freq="1min"))
    etf = pd.Series(np.r_[np.linspace(480, 481, 10), np.linspace(482, 483, 10)], index=idx)
    fut = pd.Series(np.r_[10.0 * np.linspace(480, 481, 10) + 20, 10.0 * np.linspace(482, 483, 10) + 25], index=idx)
    fits = daily_fits(etf, fut)
    assert len(fits) == 2
    offs = sorted(round(f.offset, 3) for f in fits.values())
    assert offs == [20.0, 25.0]


def _load_strategy():
    p = ROOT / "strategies" / "python" / "ES1! IV Wall Reaction 5m.py"
    if not p.exists():
        pytest.skip("strategy file is no longer shipped in strategies/python (removed in the Oct-2026 library audit)")
    spec = importlib.util.spec_from_file_location("ivwall", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _bars(days=40, seed=3):
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2026-01-05 14:30", periods=78, freq="5min", tz="UTC")
    rows, px = [], 5000.0
    for d in range(days):
        for t in ts + pd.Timedelta(days=d):
            if t.dayofweek >= 5:
                continue
            o = px
            c = o + rng.normal(0, 2.5)
            rows.append((t, o, max(o, c) + abs(rng.normal(0, 1.5)), min(o, c) - abs(rng.normal(0, 1.5)), c, 1000))
            px = c
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


def test_iv_wall_strategy_prefix_invariant_and_mode_flag():
    m = _load_strategy()
    df = _bars()
    full = m.generate_signals(df)
    assert m.LAST_RUN_MODE == "proxy"
    for cut in (len(df) // 3, len(df) // 2, len(df) - 7):
        part = m.generate_signals(df.iloc[:cut].copy())
        assert (full.iloc[:cut].to_numpy() == part.to_numpy()).all(), f"signals changed when future bars were removed (cut {cut})"


def test_iv_wall_strategy_uses_real_columns_when_present():
    m = _load_strategy()
    df = _bars()
    df["gex_call_wall"] = df["close"].iloc[0] + 25.0
    df["gex_put_wall"] = df["close"].iloc[0] - 25.0
    m.generate_signals(df)
    assert m.LAST_RUN_MODE == "real"
