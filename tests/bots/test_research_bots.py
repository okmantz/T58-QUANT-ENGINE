"""The three objective-specific research bots (2026-11-20) and the Compression ORB 15m strategy they add."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from app.bots.presets import preset_configs, research_configs
from app.bots.risk_governor import AccountRulesLite, AccountState, GovernorConfig, decide_risk

ROOT = Path(__file__).resolve().parents[2]


def _strategy():
    spec = importlib.util.spec_from_file_location("orbc", ROOT / "strategies/python/ORBCompression_ESNQ_15m_v1.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _bars(days=40, seed=0):
    """Synthetic 15m RTH bars (09:30-16:00 ET) with every fourth day compressed."""
    rng = np.random.default_rng(seed)
    rows, px = [], 100.0
    for d in pd.bdate_range("2024-01-02", periods=days):
        vol = 0.15 if d.day % 4 == 0 else 0.6
        for k in range(27):
            t = pd.Timestamp(d.date()).tz_localize("America/New_York") + pd.Timedelta(minutes=570 + 15 * k)
            o = px; c = o + rng.normal(0, vol); h = max(o, c) + abs(rng.normal(0, vol / 2)); l = min(o, c) - abs(rng.normal(0, vol / 2))
            rows.append((t.tz_convert("UTC"), o, h, l, c)); px = c
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


def test_research_bots_are_separate_from_the_presets():
    ids = {c.id for c in research_configs()}
    assert ids == {"bot-a-evaluation-passer", "bot-b-payout-hunter", "bot-c-net-profit-compounder"}
    assert not ids & {c.id for c in preset_configs()}


def test_research_governors_round_trip_and_legs_exist():
    for c in research_configs():
        g = GovernorConfig.from_dict(c.governor)
        assert g.to_dict() == c.governor
        for lg in c.legs:
            if lg.kind == "intraday":
                assert (ROOT / "strategies" / lg.strategy).exists(), lg.strategy
            assert lg.weight > 0


def test_bot_a_sizes_flat_until_the_cushion_cap():
    a = next(c for c in research_configs() if c.id == "bot-a-evaluation-passer")
    g = GovernorConfig.from_dict(a.governor)
    st = AccountState.fresh(AccountRulesLite.lucid_50k(), phase="evaluation")
    d = decide_risk(st, g)
    assert d.allow and abs(d.risk_dollars - 300.0) < 1e-6          # 0.6% of $50K, no ladder, no pace before day 5
    st.balance = 48_250.0                                         # $250 above the floor: capped at 90% of the cushion... then the 0.9 hard cap
    d = decide_risk(st, g)
    assert d.risk_dollars <= 0.9 * 250.0 + 1e-6


def test_orb_strategy_is_causal_and_one_shot_a_day():
    m = _strategy()
    df = _bars()
    full = m.generate_signals(df)
    assert set(np.unique(full.values)) <= {-1, 0, 1}
    for cut in (300, 600, 900):
        part = m.generate_signals(df.iloc[:cut].reset_index(drop=True))
        assert (part.values == full.values[:cut]).all(), "signals changed when later bars were removed"
    loc = pd.to_datetime(df["timestamp"]).dt.tz_convert("America/New_York")
    starts = (full.values != 0) & (np.r_[0, full.values[:-1]] == 0)
    per_day = pd.Series(starts, index=loc.dt.date).groupby(level=0).sum()
    assert per_day.max() <= 1
    st = full.attrs["stop_loss_distance"]; tp = full.attrs["take_profit_distance"]
    on = full.values != 0
    assert (st[on] > 0).all() and np.allclose(tp[on], 2.0 * st[on])
    assert not ((loc.dt.hour * 60 + loc.dt.minute).values[on] >= 960).any()   # flat from 16:00 ET
