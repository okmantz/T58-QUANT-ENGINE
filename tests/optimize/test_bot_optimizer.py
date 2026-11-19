"""Bot optimizer building blocks: the time split, the arbiter-style bundle, and the 'change nothing unless it wins twice' rule."""
from __future__ import annotations

import pandas as pd

from app.optimize import bot_optimizer as bo


def _trades(rows):
    return pd.DataFrame([{"entry": pd.Timestamp(e), "exit": pd.Timestamp(x), "pnl": p, "dir": 1, "inst": i} for e, x, p, i in rows])


def test_splits_are_60_20_20_in_time_and_do_not_overlap():
    df = pd.DataFrame({"timestamp": pd.date_range("2020-01-01", periods=1000, freq="D", tz="UTC")})
    s = bo._splits(df)
    assert s["train"][1] == s["val"][0] and s["val"][1] == s["test"][0]
    assert (s["train"][1] - s["train"][0]) > (s["val"][1] - s["val"][0])


def test_bundle_keeps_one_position_per_instrument_and_honours_weights_and_zero():
    a = _trades([("2024-01-02 10:00", "2024-01-02 12:00", 100.0, "NQ")])
    b = _trades([("2024-01-02 11:00", "2024-01-02 13:00", 50.0, "NQ"), ("2024-01-02 11:00", "2024-01-02 13:00", 70.0, "ES")])
    book = bo._bundle([(a, 2.0), (b, 1.0)], None, 5)
    assert sorted(book["pnl"]) == [70.0, 200.0]                 # NQ b is blocked while NQ a is open; ES b trades
    assert bo._bundle([(a, 0.0), (b, 1.0)], None, 5)["pnl"].sum() == 120.0


def test_bundle_daily_loss_cap_blocks_new_entries():
    t = _trades([("2024-01-02 10:00", "2024-01-02 10:30", -500.0, "NQ"), ("2024-01-02 11:00", "2024-01-02 11:30", 300.0, "NQ")])
    assert len(bo._bundle([(t, 1.0)], 400.0, 5)) == 1


def test_too_thin_a_book_scores_as_unjudgeable():
    s, info = bo._score("A", _trades([("2024-01-02 10:00", "2024-01-02 10:30", 10.0, "NQ")]), (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")), None)
    assert s < -1e8 and info["trades"] == 1
