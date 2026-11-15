"""Whole-pipeline look-ahead harness in CI (audit item C / probes/C_lookahead_harness.py::check_pipeline), offline on a synthetic 1m frame.

Truncating or randomising the FUTURE of the raw 1m frame must not change any signal on an execution bar that is already complete at the
cut. The pipeline is the engine's own prepare_run (HTF resample+merge -> generate -> filters -> overlays), run on the RAW frame.
A planted peek-ahead strategy must be caught, so the harness cannot silently pass everything."""
import numpy as np
import pandas as pd
import pytest

from app.backtest.engine import prepare_run
from app.backtest.risk import RiskConfig
from app.strategy.base import Strategy, StrategyResult


def _raw(n_days=12, seed=5):
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2024-01-02 14:30", periods=n_days * 1440, freq="1min")
    close = 4500 * np.exp(np.cumsum(rng.normal(0, 4e-4, len(ts))))
    op = np.concatenate([[close[0]], close[:-1]])
    sp = np.abs(rng.normal(0, 4e-4, len(ts))) * close
    return pd.DataFrame({"timestamp": ts, "open": op, "high": np.maximum(op, close) + sp,
                         "low": np.minimum(op, close) - sp, "close": close, "volume": rng.integers(100, 5000, len(ts)).astype(float)})


def _perturb(df, cut, seed=7):
    rng = np.random.default_rng(seed)
    out = df.copy()
    m = len(df) - (cut + 1)
    lvl = float(df["close"].iloc[cut])
    close = lvl * 1.35 * np.exp(np.cumsum(rng.normal(0, 1.6e-3, m)))
    op = np.concatenate([[lvl * 1.35], close[:-1]])
    out.loc[cut + 1:, "open"] = op
    out.loc[cut + 1:, "close"] = close
    out.loc[cut + 1:, "high"] = np.maximum(op, close) * 1.001
    out.loc[cut + 1:, "low"] = np.minimum(op, close) * 0.999
    out.loc[cut + 1:, "volume"] = rng.integers(1, 100000, m).astype(float)
    return out


class _Causal(Strategy):
    source_type = "python"

    def generate(self, df):
        c = df["close"]
        return StrategyResult(name="causal", source_type="python", signals=(c > c.rolling(30).mean()).astype(int),
                              stop_loss_pips=20.0, take_profit_pips=40.0)


class _Peek(Strategy):
    source_type = "python"

    def generate(self, df):
        c = df["close"]
        return StrategyResult(name="peek", source_type="python", signals=(c.shift(-5) > c).astype(int),
                              stop_loss_pips=20.0, take_profit_pips=40.0)


def _signals(raw, strat):
    prep = prepare_run(raw, strat, RiskConfig(), lookahead_check="skip")
    return pd.Series(prep.strat_result.signals.to_numpy(float), index=pd.to_datetime(prep.df["timestamp"]).to_numpy())


def _violations(strat, raw, cuts=(4000, 9000, 14000)):
    full = _signals(raw, strat)
    bad = 0
    for cut in cuts:
        t_end = raw["timestamp"].iloc[cut]
        for rr in (raw.iloc[: cut + 1].copy(), _perturb(raw, cut)):
            part = _signals(rr, strat)
            idx = part.index[part.index + pd.Timedelta(minutes=1) <= t_end + pd.Timedelta(minutes=1)]
            a, b = full.reindex(idx).to_numpy(), part.reindex(idx).to_numpy()
            bad += int((~np.isclose(a, b, equal_nan=True)).sum())
    return bad


def test_causal_strategy_passes_the_whole_pipeline_check():
    assert _violations(_Causal(), _raw()) == 0


def test_planted_peek_is_caught_by_the_harness():
    assert _violations(_Peek(), _raw()) > 0


@pytest.mark.parametrize("seed", [1000, 1001, 1002])
def test_random_grammar_strategies_are_causal_through_the_pipeline(seed):
    import random
    from app.search import grammar as G
    from app.strategy.manual import ManualStrategy
    cfg = G.generate_random(rng=random.Random(seed))
    assert _violations(ManualStrategy(cfg), _raw(n_days=12), cuts=(6000, 12000)) == 0
