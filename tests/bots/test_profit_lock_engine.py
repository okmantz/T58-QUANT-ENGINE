"""Bots cut losers short and let winners run: the profit-lock ladder and the adaptive loser cut inside BotEngine."""
from __future__ import annotations

import pandas as pd

from app.bots.engine import BotEngine
from app.bots.models import BotConfig, BotLeg, BotRuntime, OpenPos
from app.bots.risk_governor import GovernorConfig
from app.bots.venues import PaperVenue


def _engine(**gov) -> BotEngine:
    cfg = BotConfig(name="t", objective="B", legs=[BotLeg("python/IndRule_NQ_15m_v1.py", "Ind Rule", "NQ", 1.0, 0, 15)],
                    governor=GovernorConfig(objective="B", **gov).to_dict())
    eng = BotEngine(cfg, BotRuntime(status="running"), [], [], PaperVenue(), {})
    eng.lanes["NQ"].pos = OpenPos("Ind Rule", "NQ", 1, "mini", 1, "2024-03-05T15:00:00+00:00", 21000.0, 20975.0, None, 500.0, 25.0, 1.0)
    return eng


def _bars(eng, rows, start="2024-03-05 15:01"):
    t0 = pd.Timestamp(start, tz="UTC")
    for i, (o, h, l, c) in enumerate(rows):
        eng.on_bar(t0 + pd.Timedelta(minutes=i), o, h, l, c)


def test_ratchet_locks_profit_when_a_winner_reverses():
    eng = _engine(profit_lock=True)
    # +$500 peak on the first bar (1 mini NQ = $20/pt -> 25 pts), then a full reversal through the entry
    _bars(eng, [(21000, 21025, 21000, 21020), (21020, 21022, 20940, 20950)])
    t = eng.trades[-1]
    assert t["reason"] == "profit lock" and 200.0 <= t["pnl"] <= 260.0     # the $400 rung locked $250 (net of slippage and commission)


def test_without_the_ladder_the_same_reversal_is_a_full_loss():
    eng = _engine()
    _bars(eng, [(21000, 21025, 21000, 21020), (21020, 21022, 20940, 20950)])
    assert eng.trades[-1]["reason"] == "stop loss" and eng.trades[-1]["pnl"] < -400


def test_ladder_never_widens_the_stop_and_trails_a_runner():
    eng = _engine(profit_lock=True)
    p = eng.lanes["NQ"].pos
    _bars(eng, [(21000, 21025, 21000, 21020), (21020, 21030, 21019, 21029), (21029, 21060, 21028, 21058)])
    assert p.stop_price > 21000.0 and p.locked is not None and p.locked >= 250.0
    stops = []
    for k in range(3):                                                    # a pull-back does not loosen anything
        _bars(eng, [(21058, 21058, 21050, 21055)], start=f"2024-03-05 15:0{5 + k}")
        stops.append(p.stop_price)
    assert stops == sorted(stops)


def test_loss_cut_closes_a_trade_that_never_worked():
    eng = _engine(loss_cut_frac=0.6, loss_cut_min_minutes=2)
    rows = [(21000, 21002, 20990, 20992), (20992, 20995, 20980, 20985), (20985, 20988, 20972, 20974)]   # down 26 pts ($520) over 3 min, never up
    _bars(eng, rows)
    assert eng.trades and eng.trades[-1]["reason"] in ("loss cut", "stop loss")
    eng2 = _engine(loss_cut_frac=0.6, loss_cut_min_minutes=2)
    _bars(eng2, [(21000, 21002, 20990, 20992), (20992, 20995, 20980, 20985), (20985, 20988, 20978, 20980)])  # down $400 = 0.8 of risk: cut before the stop
    assert eng2.trades[-1]["reason"] == "loss cut" and eng2.trades[-1]["pnl"] > -500.0
