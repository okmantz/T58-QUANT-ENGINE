"""Gate 27 swing basket, per-instrument lanes, merged multi-instrument replay timeline, open-risk-aware governor, builder expansion."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.bots import gate27 as g
from app.bots.risk_governor import AccountRulesLite, AccountState, GovernorConfig, decide_risk


# ------------------------------------------------------------------------------------------------------------- Gate 27 maths
def test_leg_signal_needs_210_sessions_and_follows_the_sma():
    assert g.leg_signal(np.linspace(100, 110, 100)) is None
    up = np.linspace(100, 200, 260)
    long_, vol = g.leg_signal(up)
    assert long_ is True and vol > 0
    assert g.leg_signal(up[::-1].copy())[0] is False


def test_target_notionals_are_volatility_scaled_and_capped():
    t = g.target_notionals({"ES": (True, 0.01), "GC": (False, 0.01)}, 100_000.0)
    assert t["ES"] > 0 and t["GC"] == 0.0                       # gated-off legs carry nothing
    hot = g.target_notionals({"ES": (True, 0.0001), "GC": (True, 0.0001)}, 100_000.0)
    assert sum(hot.values()) <= 100_000.0 * g.LEVERAGE_CAP + 1e-6   # the leverage cap binds on very quiet markets


def test_phase_in_reaches_the_target_in_three_steps():
    steps = [g.phase_notional(0.0, 90.0, k) for k in (1, 2, 3)]
    assert steps == [30.0, 60.0, 90.0]


def test_contracts_round_to_nearest_whole_contract():
    assert g.contracts_for_notional(26_000.0, 5_000.0, 5.0) == 1       # 26,000 / 25,000 per micro = 1.04 -> 1
    assert g.contracts_for_notional(0.0, 5_000.0, 5.0) == 0


def _closes(n=300, drift=0.001):
    idx = pd.bdate_range("2021-01-04", periods=n)
    px = 100 * np.cumprod(1 + np.full(n, drift) + np.random.default_rng(1).normal(0, 0.002, n))
    return pd.DataFrame({"close": px, "raw": px}, index=idx)


def test_source_uses_only_sessions_before_the_day_asked():
    fr = _closes()
    src = g.Gate27Source({"ES": fr})
    day = fr.index[250]
    a = src.signals(day)
    fr2 = fr.copy(); fr2.loc[fr2.index >= day, "close"] = 1.0          # wreck today and the future
    b = g.Gate27Source({"ES": fr2}).signals(day)
    assert a == b                                                      # no look-ahead
    assert src.signals(fr.index[100]) is None                          # not enough history yet


def test_basket_backtest_is_flat_before_history_and_marks_to_market():
    eq = g.backtest_basket({"ES": _closes(400), "GC": _closes(400, 0.0005)}, equity0=100_000.0)
    assert {"pnl", "equity"} <= set(eq.columns)
    assert abs(float(eq["pnl"].iloc[0])) < 1e-9
    assert np.isfinite(eq["equity"]).all()


# ------------------------------------------------------------------------------------------------------------- governor
def test_open_risk_is_deducted_from_the_cushion_and_day_room():
    s = AccountState.fresh(AccountRulesLite.lucid_50k())
    free = decide_risk(s, GovernorConfig(objective="A", cushion_risk_frac=0.05))
    held = decide_risk(s, GovernorConfig(objective="A", cushion_risk_frac=0.05), open_risk=free.risk_dollars)
    assert held.risk_dollars < free.risk_dollars


# ------------------------------------------------------------------------------------------------------------- merged timeline
def test_merged_bars_unions_instruments_in_time_order():
    from app.bots.runner import _merged_bars
    t = pd.date_range("2024-03-04 14:30", periods=5, freq="1min", tz="UTC")
    mk = lambda ix: pd.DataFrame({"timestamp": ix, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})  # noqa: E731
    out = list(_merged_bars({"NQ": mk(t[:4]), "ES": mk(t[1:])}))
    assert [x[0] for x in out] == list(t)
    assert set(out[0][1]) == {"NQ"} and set(out[2][1]) == {"NQ", "ES"} and set(out[4][1]) == {"ES"}
    one = list(_merged_bars({"NQ": mk(t)}))
    assert len(one) == 5 and list(one[0][1]) == ["NQ"]


def test_merged_bars_handles_second_resolution_timestamps():
    from app.bots.runner import _merged_bars
    t = pd.date_range("2024-03-04 14:30", periods=3, freq="1min", tz="UTC").as_unit("s")
    mk = lambda ix: pd.DataFrame({"timestamp": ix, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})  # noqa: E731
    out = list(_merged_bars({"NQ": mk(t), "ES": mk(t)}))
    assert out[0][0] == pd.Timestamp("2024-03-04 14:30", tz="UTC")


# ------------------------------------------------------------------------------------------------------------- engine lanes
def test_engine_builds_one_lane_per_instrument_and_gates_swing_on_rules():
    from app.bots.engine import BotEngine
    from app.bots.models import AccountLink, BotConfig, BotLeg, BotRuntime
    from app.bots.venues import PaperVenue
    legs = [BotLeg("python/NQ1! Ind Rule 15m.py", "IR", "NQ"), BotLeg("builtin/x", "G ES", "ES", kind="gate27"), BotLeg("builtin/x", "G GC", "GC", kind="gate27")]
    cfg = BotConfig(name="t", objective="NET", legs=legs, account=AccountLink(venue="paper", account_id="p", size=50_000.0, preset_key=""))
    src = {"IR": object(), "G ES": object(), "G GC": object()}
    live, mx, mm = __import__("app.bots.engine", fromlist=["rules_for_account"]).rules_for_account(cfg.account, objective="NET")
    eng = BotEngine(cfg, BotRuntime(status="running"), [], [], PaperVenue(), src, rules=live, max_minis=mx, max_micros=mm)
    assert set(eng.lanes) == {"NQ", "ES", "GC"} and eng.swing_enabled
    prop = AccountRulesLite.lucid_50k()
    ev: list = []
    eng2 = BotEngine(cfg, BotRuntime(status="running"), [], ev, PaperVenue(), src, rules=prop, max_minis=4, max_micros=40)
    assert not eng2.swing_enabled and any(e["kind"] == "warn" for e in ev)      # overnight holds are refused on a prop account


# ------------------------------------------------------------------------------------------------------------- builder
def test_builder_expands_gate27_into_two_swing_legs_and_keeps_their_symbols():
    from app.bots import builder
    cat = {r["id"]: r for r in builder.strategy_catalog()}
    assert builder.GATE27_ID in cat and cat[builder.GATE27_ID]["supported"]
    cfg, errors, warnings = builder.build_config({"name": "n", "objective": "NET", "strategies": [
        {"strategy": "python/NQ1! Ind Rule 15m.py"}, {"strategy": builder.GATE27_ID, "weight": 0.5}], "instrument": "NQ"})
    assert not errors, errors
    swing = [lg for lg in cfg.legs if lg.kind == "gate27"]
    assert sorted(lg.symbol for lg in swing) == ["ES", "GC"] and all(lg.weight == 0.5 for lg in swing)
    assert [lg.symbol for lg in cfg.legs if lg.kind != "gate27"] == ["NQ"]


def test_shipped_presets_use_the_winning_legs():
    from app.bots.presets import preset_configs
    by = {c.id: c for c in preset_configs()}
    assert [lg.weight for lg in by["bot-pass"].legs] == [1.0, 3.0, 1.0]
    assert any(lg.kind == "gate27" for lg in by["bot-profit"].legs) and not any(lg.kind == "gate27" for lg in by["bot-pass"].legs + by["bot-payout"].legs)
    assert by["bot-payout"].governor["funded_mult"] == 0.6
