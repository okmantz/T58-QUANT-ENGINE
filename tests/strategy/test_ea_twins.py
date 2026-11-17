"""Engine twins of the MQL5 EAs: they must load, return valid level series, be causal (prefix invariant), and stay in step with the EA inputs."""
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.optimize.code_parameter_space import _float_bounds, discover_code_genes, discover_python_parameters
from app.strategy.directives import declared_min_trades, effective_min_trades
from app.strategy.ea_twins import run_twin, twin_genes, twin_name
from app.strategy.mql5 import MQL5Strategy

ROOT = Path(__file__).resolve().parents[2]
MQ = sorted((ROOT / "strategies" / "mql5").glob("*.mq5"))
_TF_MIN = {"5m": 5, "15m": 15, "1d": 1440}


def _tf(code: str) -> str:
    return re.search(r"T58_TIMEFRAME=(\S+)", code).group(1)


def _bars(tf: str, seed: int = 3) -> pd.DataFrame:
    minutes = _TF_MIN[tf]
    rng = np.random.default_rng(seed)
    if tf == "1d":
        ts = pd.bdate_range("2021-01-04", periods=700, tz="UTC") + pd.Timedelta(hours=22)
    else:
        days = pd.bdate_range("2026-01-05", periods=14, tz="UTC")
        per_day = 24 * 60 // minutes
        ts = pd.DatetimeIndex(np.concatenate([(d + pd.Timedelta(hours=0)) + pd.to_timedelta(np.arange(per_day) * minutes, unit="m") for d in days]))
    n = len(ts)
    c = 5000 * np.exp(np.cumsum(rng.normal(0.0001, 0.0015 if tf != "1d" else 0.01, n)))
    o = np.r_[c[0], c[:-1]]
    hi = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.0006, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.0006, n)))
    return pd.DataFrame({"timestamp": ts, "open": o, "high": hi, "low": lo, "close": c, "volume": 1000.0})


@pytest.mark.parametrize("path", MQ, ids=lambda p: p.stem[:30])
def test_every_mql5_ea_declares_a_twin_and_runs(path):
    code = path.read_text(encoding="utf-8")
    assert twin_name(code), "every shipped EA must declare // T58_TWIN="
    d = _bars(_tf(code))
    res = run_twin(code, d)
    sig = res.signals.to_numpy()
    assert len(sig) == len(d) and set(np.unique(sig)) <= {-1, 0, 1}
    s = MQL5Strategy(code)
    out = s.generate(d)
    assert s.engine_used == "twin" and (out.signals.to_numpy() == sig).all()


@pytest.mark.parametrize("path", MQ, ids=lambda p: p.stem[:30])
def test_twins_are_prefix_invariant(path):
    """The level on bar k may never depend on bars after k (what the pipeline's lookahead check enforces)."""
    code = path.read_text(encoding="utf-8")
    d = _bars(_tf(code))
    full = run_twin(code, d).signals.to_numpy()
    for frac in (0.31, 0.57, 0.83):
        cut = max(60, int(len(d) * frac))
        part = run_twin(code, d.iloc[:cut].reset_index(drop=True)).signals.to_numpy()
        assert (part == full[:cut]).all(), (path.name, cut, np.flatnonzero(part != full[:cut])[:5])


@pytest.mark.parametrize("path", MQ, ids=lambda p: p.stem[:30])
def test_twin_genes_sit_inside_their_own_bounds(path):
    code = path.read_text(encoding="utf-8")
    for g in twin_genes(code):
        assert g.lo <= g.base_value <= g.hi, (path.name, g.name, g.lo, g.base_value, g.hi)
    s = MQL5Strategy(code)
    assert [g.name for g in discover_code_genes(s)] == [g.name for g in twin_genes(code)]


def test_gate27_declares_a_low_trade_floor_and_default_is_unchanged_elsewhere():
    g27 = next(p for p in MQ if p.name.startswith("GATE 27"))
    assert declared_min_trades(MQL5Strategy(g27.read_text(encoding="utf-8"))) == 30
    assert effective_min_trades(MQL5Strategy(g27.read_text(encoding="utf-8")), 100) == 30
    other = next(p for p in MQ if "Go Long" in p.name)
    assert effective_min_trades(MQL5Strategy(other.read_text(encoding="utf-8")), 100) == 100
    assert effective_min_trades(MQL5Strategy(g27.read_text(encoding="utf-8")), 10) == 10    # only ever lowers the floor


def test_float_gene_bounds_never_cross_zero():
    lo, hi = _float_bounds(0.02)
    assert 0 < lo < 0.02 < hi
    lo, hi = _float_bounds(3.0)
    assert 0 < lo < 3.0 < hi
    lo, hi = _float_bounds(0.0)
    assert lo < 0 < hi


def test_python_strategy_genes_have_positive_bounds_for_positive_constants(tmp_path):
    f = tmp_path / "s.py"
    f.write_text("WARMUP_BARS = 0\nBUF = 0.02\nTGT_R = 3.0\nOR_MIN = 30\n")
    genes = {g.name: g for g in discover_python_parameters(f)}
    assert "WARMUP_BARS" not in genes
    assert genes["BUF"].lo > 0 and genes["TGT_R"].lo > 0 and genes["OR_MIN"].lo >= 1


def test_pine_calendar_functions_and_commission_constants_parse():
    from app.strategy.pine_interp import _CONSTS, FUNCS
    for name in ("year", "month", "dayofmonth", "dayofweek", "hour", "minute", "second", "weekofyear"):
        assert name in FUNCS, name
    for name in ("strategy.commission.percent", "strategy.commission.cash_per_contract", "strategy.commission.cash_per_order"):
        assert name in _CONSTS, name
