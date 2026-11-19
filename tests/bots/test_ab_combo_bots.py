"""The 2026-11-19 bot books (docs/T58_BOT_AB_COMBOS_2026-11-19.md): the Payout Hunter's new leg, the Evaluation Passer kept as it was, and the bracket strategy file.

ContextDriveLongBracket_NQ_1m_v1 keeps the entries of ContextDriveLong_NQ_1m_v2 and replaces the exit with a stop of 0.2 x ATR14 and a target of
TP_R x the stop. The engine test runs the file through the real backtest engine on a slice of the bundled 1-minute history and checks what that means:
no lookahead, every exit is the stop, the target or the flatten (never held into the next session, half days included), and the target sits at
TP_R times the stop."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from app.bots.presets import PRESET_REV, preset_configs

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "strategies" / "python"
BRACKETS = [("ContextDriveLongBracket_NQ_1m_v1.py", "NQ", 3.0)]


def _by_id():
    return {c.id: c for c in preset_configs()}


def test_evaluation_passer_keeps_its_book():
    # the S&P 500 bracket legs tested for objective A lost to this book on train and validation once the scorer stopped looking ahead, so it stays
    b = _by_id()["bot-pass"]
    assert b.objective == "A" and b.preset_rev == PRESET_REV == 4
    assert [(lg.strategy, lg.symbol, lg.weight) for lg in b.legs] == [
        ("python/OpenDrive_NQ_5m_v1.py", "NQ", 1.0),
        ("python/IndRule_NQ_15m_v1.py", "NQ", 3.0),
        ("python/ContextDriveLong_NQ_1m_v2.py", "NQ", 1.0),
    ]


def test_payout_hunter_is_the_objective_b_combo():
    b = _by_id()["bot-payout"]
    assert b.objective == "B" and b.preset_rev == PRESET_REV
    assert [(lg.strategy, lg.symbol, lg.weight) for lg in b.legs] == [
        ("python/IndRule_NQ_15m_v1.py", "NQ", 1.0),
        ("python/CompressionORB_ES_5m_v1.py", "ES", 0.25),
        ("python/OpenDrive_NQ_5m_v1.py", "NQ", 0.25),
        ("python/ContextDriveLongBracket_NQ_1m_v1.py", "NQ", 0.5),
    ]
    assert "5-winning-days" in b.description
    assert [lg.priority for lg in b.legs] == list(range(len(b.legs)))


def test_governors_are_unchanged_by_the_new_books():
    by = _by_id()
    ga, gb = by["bot-pass"].governor_cfg(), by["bot-payout"].governor_cfg()
    assert (ga.objective, ga.base_risk_pct, ga.day_stop_frac, ga.cushion_risk_frac, ga.pace_max_mult) == ("A", 0.75, 0.40, 0.75, 1.5)
    assert (gb.objective, gb.base_risk_pct, gb.day_stop_frac, gb.cushion_risk_frac, gb.funded_mult, gb.win_day_lock_mult) == ("B", 1.0, 0.30, 0.25, 0.6, 0.5)


@pytest.mark.parametrize("bid", ["bot-pass", "bot-payout"])
def test_leg_labels_are_unique_and_every_file_exists(bid):
    from app.bots.signals import resolve_strategy_path
    b = _by_id()[bid]
    labels = [lg.label for lg in b.legs]
    assert len(labels) == len(set(labels))            # the runner keys each leg's signal source by its label
    for lg in b.legs:
        assert resolve_strategy_path(lg.strategy).exists(), lg.strategy


def test_store_seeds_the_new_books():
    from app.bots import store
    rows = {r["config"]["id"]: r["config"] for r in store.list_bots()}
    assert rows["bot-pass"]["preset_rev"] == rows["bot-payout"]["preset_rev"] == PRESET_REV
    assert rows["bot-payout"]["legs"][-1]["strategy"] == "python/ContextDriveLongBracket_NQ_1m_v1.py"


def _module(fn: str):
    spec = importlib.util.spec_from_file_location(fn[:-3], PY / fn)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("fn,inst,r", BRACKETS)
def test_bracket_file_declares_its_bracket(fn, inst, r):
    m = _module(fn)
    assert m.TP_R == r and m.STOP_ATR == 0.20 and m.LONG_ONLY == 1
    assert "trailing_stop_distance" not in (PY / fn).read_text()


def _history(inst: str) -> pd.DataFrame:
    """2022-06 .. 2024-06: 200+ sessions of warm-up for the daily EMA context, then a year and a half of trades."""
    from app.bots.runner import load_history
    try:
        df = load_history(inst)
    except FileNotFoundError:
        pytest.skip(f"no bundled {inst} history")
    ts = pd.to_datetime(df["timestamp"])
    out = df[(ts >= pd.Timestamp("2022-06-01", tz="UTC")) & (ts < pd.Timestamp("2024-07-01", tz="UTC"))].reset_index(drop=True)
    if len(out) < 100_000:
        pytest.skip(f"bundled {inst} history does not cover 2022-06 .. 2024-06")
    return out


def _ny(x) -> pd.Timestamp:
    x = pd.Timestamp(x)
    return (x.tz_localize("UTC") if x.tzinfo is None else x).tz_convert("America/New_York")


@pytest.mark.parametrize("fn,inst,r", BRACKETS)
def test_bracket_file_in_the_engine(fn, inst, r):
    from app.backtest.engine import prepare_timeframe_aligned_data, run_backtest
    from app.backtest.risk import RiskConfig
    from app.data.instrument_specs import apply_instrument_spec
    from app.strategy.lookahead_check import check_for_lookahead
    from app.strategy.python import PythonStrategy

    df = _history(inst)
    strat = PythonStrategy(str(PY / fn))
    bars, _ = prepare_timeframe_aligned_data(df, strat)
    lk = check_for_lookahead(strat, bars)
    assert lk.checked and not lk.bug_detected, lk.summary()

    from app.backtest.risk import with_prop_safety_defaults
    from app.prop.presets import get_preset
    risk = with_prop_safety_defaults(apply_instrument_spec(RiskConfig(), inst), get_preset("lucid_50k").to_prop_rules())   # as the bots' research runs it
    res = run_backtest(df, PythonStrategy(str(PY / fn)), risk, lookahead_check="skip")
    tr = res.trades
    assert len(tr) >= 10, "the slice should hold enough trades to test the bracket"
    reasons = {t.exit_reason for t in tr}
    assert reasons <= {"stop_loss", "take_profit", "signal", "end_of_data", "session_flatten_forced_close", "prop_floor_liquidation"}
    assert "take_profit" in reasons and "stop_loss" in reasons
    for t in tr:
        assert t.initial_risk and t.initial_risk > 0
        move = (t.exit_price - t.entry_price) * t.direction
        if t.exit_reason == "take_profit":
            assert move == pytest.approx(r * t.initial_risk, rel=0.02, abs=0.5)
        if t.exit_reason == "stop_loss":
            assert move <= -0.9 * t.initial_risk
        en, et = (_ny(t.entry_time), _ny(t.exit_time))
        assert et.date() == en.date() and et.hour * 60 + et.minute <= 16 * 60 + 45, (t.entry_time, t.exit_time)   # flat by the firm's 16:45 ET cut,
        #                                                                     early-close (holiday) sessions included: never held into the next session
