"""The objective scorecard sizes every trade from what the account knew at the trade's ENTRY (no lookahead across overlapping positions).

Before 2026-11-19 ``simulate_starts`` booked each trade the moment it was sized, so a second position opened while the first was still running was
sized (and allowed or blocked by the day stop) already knowing how the first one ended. ``score_net`` had the same flaw (it sized at the exit), and
the research bundler's daily loss cap counted a trade the moment it was entered."""
from __future__ import annotations

import pandas as pd

from app.bots.risk_governor import GovernorConfig
from app.prop import objective_scorecard as sc

D = pd.Timestamp("2024-03-04")          # a Monday


def _t(entry: str, exit_: str, pnl: float, w: float = 1.0) -> dict:
    return {"entry": D + pd.Timedelta(entry), "exit": D + pd.Timedelta(exit_), "pnl": pnl, "dir": 1, "w": w}


def _gov_a() -> GovernorConfig:
    # plain objective-A governor: day stop at 40% of the $1,200 soft limit ($480), no adaptive controls
    return GovernorConfig(objective="A", base_risk_pct=0.75, day_stop_frac=0.40, cushion_risk_frac=0.75)


def _taken(trades: list[dict]) -> int:
    df = sc.frame(trades)
    win = sc.Window.of("2024-03-01", "2024-03-10")
    out = sc.simulate_starts(df, win, 30, stride=1, gov=_gov_a(), data_end="2024-12-31")
    first = next(r for r in out if r["start"] == D)
    return first["n"]


def test_overlapping_trade_is_not_blocked_by_a_loss_that_has_not_happened_yet():
    # trade 1 loses far more than the day stop but only closes at 16:00; trade 2 (other instrument) opens at 14:35, while trade 1 is still open
    trades = [_t("14:30:00", "16:00:00", -900.0), _t("14:35:00", "15:00:00", 200.0)]
    assert _taken(trades) == 2


def test_a_trade_after_the_loss_closed_is_blocked_by_the_day_stop():
    trades = [_t("14:30:00", "16:00:00", -900.0), _t("16:30:00", "17:00:00", 200.0)]
    assert _taken(trades) == 1


def test_open_risk_comes_off_the_room_of_an_overlapping_trade(monkeypatch):
    import app.bots.risk_governor as rg
    from app.prop.lifecycle_v2 import V2Rules
    lite = rg.AccountRulesLite.from_v2(V2Rules.lucid_50k())
    st = rg.AccountState.fresh(lite)
    st.roll_day(str(D.date()))
    gov = _gov_a()
    first = rg.decide_risk(st, gov).risk_dollars
    assert rg.decide_risk(st, gov, open_risk=first, weight=3.0).risk_dollars < rg.decide_risk(st, gov, weight=3.0).risk_dollars

    seen = []
    real = rg.decide_risk

    def spy(state, cfg, open_risk=0.0, weight=1.0):
        seen.append(open_risk)
        return real(state, cfg, open_risk=open_risk, weight=weight)

    monkeypatch.setattr(rg, "decide_risk", spy)
    df = sc.frame([_t("14:30:00", "16:00:00", 100.0), _t("14:35:00", "15:00:00", 100.0, w=3.0), _t("16:30:00", "17:00:00", 100.0)])
    win = sc.Window.of("2024-03-04", "2024-03-05")
    sc.simulate_starts(df, win, 30, stride=1, gov=gov, data_end="2024-12-31")
    assert seen[0] == 0.0                         # nothing open yet
    assert abs(seen[1] - first) < 1e-6            # the scorer hands the first position's risk to the governor, as the bot engine does
    assert seen[2] == 0.0                         # both closed by 16:30


def test_results_do_not_depend_on_trades_that_close_later():
    # the first trade's size must not change when an overlapping trade that closes LATER turns from a loss into a win
    a = [_t("14:30:00", "15:00:00", 100.0), _t("14:20:00", "16:00:00", -900.0)]
    b = [_t("14:30:00", "15:00:00", 100.0), _t("14:20:00", "16:00:00", +900.0)]
    win = sc.Window.of("2024-03-01", "2024-03-10")
    na = next(r for r in sc.simulate_starts(sc.frame(a), win, 30, stride=1, gov=_gov_a(), data_end="2024-12-31") if r["start"] == D)
    nb = next(r for r in sc.simulate_starts(sc.frame(b), win, 30, stride=1, gov=_gov_a(), data_end="2024-12-31") if r["start"] == D)
    assert na["n"] == nb["n"] == 2


def test_score_net_sizes_at_entry_not_at_exit():
    # NET compounding governor: with lookahead the second trade was sized after the first trade's -$5,000 had shrunk the equity and throttled size.
    gov = GovernorConfig(objective="NET", base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0, min_risk_dollars=1.0)
    trades = [_t("14:30:00", "16:00:00", -5_000.0), _t("14:35:00", "15:00:00", 1_000.0)]
    r = sc.score_net(trades, gov=gov, rank_years=False)
    assert r["n"] == 2
    assert r["net"] == -4_000.0                   # both at full size: the second opened before the first's loss was known


def test_research_bundle_daily_cap_reads_realised_pnl_only():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import run_objective_scores as ros
    nq = sc.frame([_t("14:30:00", "16:00:00", -900.0)]); nq["inst"] = "NQ"
    es = sc.frame([_t("14:35:00", "15:00:00", 200.0), _t("16:30:00", "17:00:00", 200.0)]); es["inst"] = "ES"
    out = ros.bundle([("nq", nq, 1.0, 0), ("es", es, 1.0, 1)], daily_cap=480.0, max_open=2)
    # the 14:35 ES trade opens while the NQ loss is still open (not blocked); the 16:30 one opens after it closed (blocked)
    assert len(out) == 2 and sorted(out["entry"].dt.strftime("%H:%M")) == ["14:30", "14:35"]
    w = ros.bundle([("nq", nq, 3.0, 0), ("es", es, 1.0, 1)], daily_cap=None, max_open=2, as_weight=True)
    assert "w" in w.columns and sorted(w["w"].tolist()) == [1.0, 1.0, 3.0]
    assert w.loc[w["w"] == 3.0, "pnl"].iloc[0] == -900.0            # 1x P&L kept, the multiplier travels as the weight
