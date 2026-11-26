"""The three shipped bots, one per objective: T58 final bot A (round 6, 2026-11-25), T58 final bot B (round 4 pick) and BOT_C (2026-11-20).

Every leg's strategy file exists and loads, the configs round-trip, the store seeds exactly these three, and the compression-ORB strategy files are causal."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.bots.models import BotConfig
from app.bots.presets import LEG_FILES, PRESET_REV, T58_PICKS, preset_configs
from app.bots.risk_governor import GovernorConfig

ROOT = Path(__file__).resolve().parents[2]


def _by_id() -> dict:
    return {c.id: c for c in preset_configs()}


def test_exactly_one_bot_per_objective():
    by = _by_id()
    assert set(by) == {"bot-pass", "bot-payout", "bot-profit"}
    assert [by[i].objective for i in ("bot-pass", "bot-payout", "bot-profit")] == ["A", "B", "NET"]
    assert all(c.preset_rev == PRESET_REV == 6 for c in by.values())


def test_a_and_b_legs_are_the_frozen_round_picks():
    by = _by_id()
    for bid, obj in (("bot-pass", "A"), ("bot-payout", "B")):
        want = [(LEG_FILES[k][0], LEG_FILES[k][2], float(w)) for k, w in T58_PICKS[obj]["legs"].items() if w > 0]
        assert [(lg.strategy, lg.symbol, lg.weight) for lg in by[bid].legs] == want
        assert by[bid].max_open_positions == T58_PICKS[obj]["max_open"]
    assert by["bot-pass"].account.preset_key == "lucid_50k" and by["bot-payout"].account.preset_key == "lucid_flex_50k"
    assert by["bot-pass"].legs[0].weight == 1.0 and len(by["bot-pass"].legs) == 7 and len(by["bot-payout"].legs) == 12


def test_net_bot_is_the_gate27_compounder_on_a_rule_free_account():
    c = _by_id()["bot-profit"]
    assert c.account.venue == "paper" and c.account.preset_key == ""
    assert [lg.kind for lg in c.legs].count("gate27") == 2
    assert c.governor_cfg().compounding is True


@pytest.mark.parametrize("bid", ["bot-pass", "bot-payout", "bot-profit"])
def test_configs_round_trip_and_every_leg_resolves(bid):
    from app.bots.signals import resolve_strategy_path
    c = _by_id()[bid]
    assert BotConfig.from_dict(c.to_dict()).to_dict() == c.to_dict()
    g = GovernorConfig.from_dict(c.governor)
    assert g.to_dict() == c.governor
    labels = [lg.label for lg in c.legs]
    assert len(labels) == len(set(labels))            # the runner keys each leg's signal source by its label
    if bid != "bot-profit":                           # the two Gate 27 swing legs share one priority
        assert [lg.priority for lg in c.legs] == list(range(len(c.legs)))
    for lg in c.legs:
        assert lg.weight > 0
        if lg.kind != "gate27":
            assert resolve_strategy_path(lg.strategy).exists(), lg.strategy


def test_store_seeds_exactly_the_three_bots():
    from app.bots import store
    rows = {r["config"]["id"]: r["config"] for r in store.list_bots() if r["config"].get("preset_key")}
    assert set(rows) == {"bot-pass", "bot-payout", "bot-profit"}
    assert all(c["preset_rev"] == PRESET_REV for c in rows.values())


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_every_bot_strategy_file_has_generate_signals():
    used = {Path(v[0]).name for v in LEG_FILES.values()} | {c_leg.strategy.split("/")[-1] for c in preset_configs() for c_leg in c.legs if c_leg.kind != "gate27"}
    for name in sorted(used):
        assert callable(_load(ROOT / "strategies" / "python" / name).generate_signals), name


def test_new_t58_strategies_are_flat_on_tiny_data():
    ts = pd.date_range("2026-01-05 14:30", periods=400, freq="1min", tz="UTC")
    px = 100 + np.cumsum(np.random.default_rng(0).normal(0, 0.1, len(ts)))
    df = pd.DataFrame({"timestamp": ts, "open": px, "high": px + 0.1, "low": px - 0.1, "close": px, "volume": 1.0})
    files = sorted((ROOT / "strategies" / "python").glob("*_t58.py"))
    assert files
    for p in files:
        s = _load(p).generate_signals(df)
        assert len(s) == len(df) and (s == 0).all()      # no prior sessions -> no ATR -> no trades


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


def test_compression_orb_strategy_is_causal_and_one_shot_a_day():
    m = _load(ROOT / "strategies/python/ORBCompression_ESNQ_15m_v1.py")
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
