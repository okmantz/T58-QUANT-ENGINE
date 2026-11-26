"""A bot is a Strategy: it runs through run_backtest, the pickers list it, and its leg weights and profit lock reach the engine."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.backtest import fills
from app.backtest.engine import run_backtest
from app.backtest.risk import RiskConfig
from app.backtest.vectorized_fastpath import is_vectorizable
from app.bots import runner
from app.strategy.base import StrategyResult
from app.strategy.bot_strategy import BotStrategy, bot_catalog, build_bot_strategy



@pytest.fixture(autouse=True)
def _isolated_bot_store(monkeypatch, tmp_path):
    """The bots database lives under the app base dir; keep the repo's data/ folder out of it."""
    from app.bots import store
    monkeypatch.setattr(store, "get_app_base_dir", lambda: tmp_path)


@pytest.fixture(scope="module")
def nq_slice() -> pd.DataFrame:
    df = runner.load_history("NQ")
    return df[df["timestamp"] >= df["timestamp"].iloc[-1] - pd.Timedelta(days=60)].reset_index(drop=True)


def test_catalog_lists_the_three_presets():
    ids = {b["id"] for b in bot_catalog()}
    assert {"bot-pass", "bot-payout", "bot-profit"} <= ids


def test_bot_runs_through_run_backtest(nq_slice):
    st = build_bot_strategy("bot-pass")
    res = run_backtest(nq_slice, st, RiskConfig(initial_balance=50_000.0))
    assert res.strategy_name.startswith("Bot:") and len(res.equity_curve) == len(nq_slice)
    assert len(res.trades) > 0


def test_leg_weight_reaches_the_sizer(nq_slice):
    st = build_bot_strategy("bot-pass")
    out = st.generate(nq_slice)
    assert out.size_multiplier is not None
    assert float(out.size_multiplier.max()) >= 1.5 - 1e-9          # the x1.5 round-6 leg
    assert not is_vectorizable(out)                                  # the scalar engine sizes bot weights


def test_swing_basket_and_other_instruments_are_named_not_hidden():
    st = build_bot_strategy("bot-profit", symbol="NQ")
    assert any("Gate 27" in s for s in st.skipped_legs) and any("ES" in s for s in st.skipped_legs)


def test_size_multiplier_scales_whole_contracts_and_default_is_unchanged():
    risk = RiskConfig(initial_balance=50_000.0)
    kw = dict(risk=risk, equity=50_000.0, direction=1, raw_price=20_000.0, bar_sl_distance=50.0, bar_tp_distance=None,
              bar_trail_distance=None, stop_loss_pips=None, take_profit_pips=None)
    a = fills.plan_entry(**kw)
    b = fills.plan_entry(**kw, size_mult=1.0)
    c = fills.plan_entry(**kw, size_mult=3.0)
    assert a.position["size"] == b.position["size"]
    assert c.position["size"] == pytest.approx(3.0 * a.position["size"], rel=0.34)   # whole-contract rounding
    assert c.position["size"] > a.position["size"]


def test_profit_lock_from_the_bot_governor_lands_in_risk_config():
    st = build_bot_strategy("bot-pass")
    st.cfg.governor = {**st.cfg.governor, "profit_lock": True, "loss_cut_frac": 0.8}
    r = st.risk_overlay(RiskConfig(initial_balance=50_000.0))
    assert r.profit_lock_tiers and r.profit_lock_trail_frac > 0 and r.loss_cut_frac == 0.8
    assert st.risk_overlay(RiskConfig(initial_balance=50_000.0, max_trades_per_day=1)).max_trades_per_day == 1


def test_unknown_bot_is_a_clear_error():
    with pytest.raises(FileNotFoundError):
        build_bot_strategy("no-such-bot")


def test_bot_signals_do_not_change_when_later_bars_are_removed(nq_slice):
    """The bot composes its legs from CLOSED leg bars only: its signal at bar i is identical whether or not later bars exist."""
    st = build_bot_strategy("bot-payout")
    full = st.generate(nq_slice.copy())
    for cut in (len(nq_slice) // 3, len(nq_slice) // 2, int(len(nq_slice) * 0.8)):
        part = st.generate(nq_slice.iloc[:cut].copy().reset_index(drop=True))
        a = full.signals.iloc[: cut - 20].reset_index(drop=True)
        b = part.signals.iloc[: cut - 20].reset_index(drop=True)
        assert (a == b).all(), f"signals changed after truncating at {cut}"
