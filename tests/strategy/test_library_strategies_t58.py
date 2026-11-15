"""Regression tests for the strategy files added/fixed in this change: GAD GA safety, TSMOM prefix invariance, twin smoke."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.optimize.code_parameter_space import discover_python_parameters

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "strategies" / "python"
GAD = PY / "MNQ1! Gap Aligned Drive RW Tight Stop 1m.py"
TSMOM = PY / "ES1! TSMOM V1 1d.py"
TWINS = ["ES1! Go Long Daily 5m.py", "ES1! Turnaround Tuesday 5m.py", "ES1! Ninja Turtle Donchian 5m.py",
         "ES1! Range Breakout 5m.py", "ES1! Fisherman Retracement 15m.py", "ES1! ATR Candle Breakout 15m.py", "ES1! IV Wall Reaction 5m.py"]


def _load(path):
    spec = importlib.util.spec_from_file_location("m_" + path.stem.replace(" ", "_").replace("!", ""), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_gad_session_grid_constants_are_not_tunable():
    names = {g.name for g in discover_python_parameters(GAD)}
    assert "FLAT_MIN" not in names and "SESSION_MIN" not in names      # a GA moving these crashed the day grid (index out of bounds)
    assert {"STOP_FRAC", "REWARD_MULT", "ATR_DAYS"} <= names           # real parameters stay searchable


def test_gad_flat_slot_is_clamped():
    src = GAD.read_text()
    assert "flat_slot = min(int(FLAT_MIN), S - 1)" in src


def _daily(n=900, seed=11):
    rng = np.random.default_rng(seed)
    ts = pd.bdate_range("2021-01-04", periods=n, tz="UTC") + pd.Timedelta(hours=23)
    c = 4000 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, n)))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.002, n))
    return pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) * 1.003, "low": np.minimum(o, c) * 0.997, "close": c, "volume": 1e5})


def test_tsmom_prefix_invariant_at_every_cut():
    m = _load(TSMOM)
    d = _daily()
    full = m.generate_signals(d)
    for cut in list(range(300, len(d), 41)) + [len(d) - 1]:
        part = m.generate_signals(d.iloc[:cut].copy())
        assert (full.iloc[:cut].to_numpy() == part.to_numpy()).all(), cut
        a = np.nan_to_num(np.asarray(full.attrs["stop_loss_distance"], float)[:cut])
        b = np.nan_to_num(np.asarray(part.attrs["stop_loss_distance"], float))
        assert np.allclose(a, b), cut


@pytest.mark.parametrize("name", TWINS)
def test_twins_load_and_return_valid_series(name):
    m = _load(PY / name)
    n = 3000
    rng = np.random.default_rng(5)
    bar = getattr(m, "BAR", 5)
    ts = pd.date_range("2026-02-02 14:30", periods=n, freq=f"{bar}min", tz="UTC")
    c = 5000 + np.cumsum(rng.normal(0, 3, n))
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) + 1, "low": np.minimum(o, c) - 1, "close": c, "volume": 1000})
    s = m.generate_signals(df)
    assert len(s) == n and set(np.unique(s.to_numpy())) <= {-1, 0, 1}
    assert "stop_loss_distance" in s.attrs
