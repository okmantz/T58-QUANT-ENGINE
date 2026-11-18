#!/usr/bin/env python
"""Replay the three shipped Trading Bots (and the bots they replaced) through the REAL bot engine on the bundled 1-minute history.

    python scripts/run_t58_bot_replays.py --out reports/t58_hypotheses/bot_replays.json

Evaluation Passer : a fresh Lucid 50K evaluation every ``--a-stride`` days, 60-day horizon  -> pass rate, breach rate, median days to pass
Payout Hunter     : a fresh evaluation every ``--b-stride`` days, 365-day horizon            -> paid rate, breach rate, payouts, days to first payout
Net Profit        : the last 24 months of bundled history on a sandbox account with no prop rules (Gate 27 swing legs on for the new bot)

Runs headless: no Flask, no store, no demo-account file (each replay uses a clean sandbox account with the bot's prop rule set).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.bots import runner as R  # noqa: E402
from app.bots.engine import BotEngine, rules_for_account  # noqa: E402
from app.bots.models import BotConfig, BotLeg, BotRuntime  # noqa: E402
from app.bots.presets import preset_configs  # noqa: E402
from app.bots.venues import venue_for  # noqa: E402
from app.bots.risk_governor import GovernorConfig  # noqa: E402


def old_presets() -> list[BotConfig]:
    """The three bots as shipped before this study (same three NQ strategies, three risk brains)."""
    od = BotLeg("python/OpenDrive_NQ_5m_v1.py", "Open Drive", "NQ", 1.0, 0, 45)
    ir = BotLeg("python/IndRule_NQ_15m_v1.py", "Ind Rule", "NQ", 1.0, 1, 15)
    cad = BotLeg("python/ContextDriveLong_NQ_1m_v2.py", "Context Drive", "NQ", 1.0, 0, 500)
    new = {c.id: c for c in preset_configs()}
    out = []
    gov = {"bot-pass": GovernorConfig(objective="A", base_risk_pct=1.0, early_mult=1.0, mid_mult=1.0, late_mult=0.7, need_risk_mult=1.0, day_stop_frac=0.40),
           "bot-payout": GovernorConfig(objective="B", base_risk_pct=1.0, cushion_risk_frac=0.25, day_stop_frac=0.30),
           "bot-profit": GovernorConfig(objective="NET", base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0, min_risk_dollars=1.0, cushion_risk_frac=0.5)}
    for bid, g in gov.items():
        c = BotConfig.from_dict(new[bid].to_dict())
        c.legs, c.governor = [od, ir, cad], g.to_dict()
        c.account.venue, c.account.account_id, c.account.preset_key = "paper", "replay", "lucid_50k"   # the old NET bot ran on the prop account's rules
        out.append(c)
    return out


def replay(cfg: BotConfig, start: pd.Timestamp, end: pd.Timestamp, keep_running: bool = True):
    cfg = BotConfig.from_dict(cfg.to_dict())
    if cfg.account.venue == "demo":
        cfg.account.venue, cfg.account.account_id = "paper", "replay"
    rt = BotRuntime(); rt.status = "running"
    trades, events = [], []
    sources, bars = R._build_sim_sources(cfg, start, end, events)
    rules, mx, mm = rules_for_account(cfg.account, objective=cfg.objective)
    eng = BotEngine(cfg, rt, trades, events, venue_for(cfg.account), sources, rules=rules, max_minis=mx, max_micros=mm)
    for ts, d in R._merged_bars(bars):
        eng.on_bars(ts, d)
        if rt.status != "running":
            break
    eng.close_all("end of replay")
    return rt, trades, events, eng


def _bal(eng, trades):
    return float(trades[-1]["balance"]) if trades else float(eng.acct.balance)


def eval_runs(cfg: BotConfig, horizon: int, stride: int, lo: pd.Timestamp, hi: pd.Timestamp) -> dict:
    rows = []
    s = lo
    while s + pd.Timedelta(days=horizon) <= hi:
        rt, tr, ev, eng = replay(cfg, s, s + pd.Timedelta(days=horizon))
        passed = any(e["kind"] == "pass" for e in ev)
        breach = any(e["kind"] == "breach" for e in ev) or rt.status == "halted" or bool(rt.breaches)
        first_pass = next((pd.Timestamp(e["t"]) for e in ev if e["kind"] == "pass"), None)
        paid = int(rt.payouts or 0)
        rows.append({"start": str(s.date()), "passed": passed, "breached": bool(breach and not passed), "days_to_pass": (first_pass - s).days if first_pass is not None else None,
                     "payouts": paid, "trades": len(tr), "end_balance": round(_bal(eng, tr), 0)})
        s += pd.Timedelta(days=stride)
    n = max(len(rows), 1)
    d2p = [r["days_to_pass"] for r in rows if r["days_to_pass"] is not None]
    return {"starts": len(rows), "pass_rate_pct": round(100 * sum(r["passed"] for r in rows) / n, 1),
            "breach_rate_pct": round(100 * sum(r["breached"] for r in rows) / n, 1),
            "paid_rate_pct": round(100 * sum(r["payouts"] > 0 for r in rows) / n, 1), "avg_paid_usd": round(float(np.mean([r["payouts"] for r in rows])), 2) if rows else 0,
            "median_days_to_pass": float(np.median(d2p)) if d2p else None, "rows": rows}


def net_run(cfg: BotConfig, lo: pd.Timestamp, hi: pd.Timestamp) -> dict:
    rt, tr, ev, eng = replay(cfg, lo, hi)
    d = pd.DataFrame(tr)
    if d.empty:
        return {"trades": 0}
    bal = d["balance"].to_numpy(float)
    start = float(cfg.account.size)
    peak = np.maximum.accumulate(np.r_[start, bal])[1:]
    dd = float(((peak - bal) / peak).max() * 100)
    yrs = (hi - lo).days / 365.25
    gross_w, gross_l = d.loc[d.pnl > 0, "pnl"].sum(), -d.loc[d.pnl < 0, "pnl"].sum()
    d["exit_time"] = pd.to_datetime(d["exit_time"], utc=True)
    by_leg = d.groupby("leg")["pnl"].agg(["count", "sum"]).round(0)
    year = d.groupby(d["exit_time"].dt.year)["pnl"].sum().round(0)
    return {"start": str(lo.date()), "end": str(hi.date()), "trades": int(len(d)), "end_balance": round(float(bal[-1]), 0), "net": round(float(bal[-1] - start), 0),
            "return_pct": round(float((bal[-1] / start - 1) * 100), 1), "cagr_pct": round(float(((bal[-1] / start) ** (1 / yrs) - 1) * 100), 1), "max_dd_pct": round(dd, 1),
            "pf": round(float(gross_w / gross_l), 2) if gross_l > 0 else None, "win_pct": round(float((d.pnl > 0).mean() * 100), 1), "status": rt.status,
            "by_leg": {k: {"trades": int(v["count"]), "net": float(v["sum"])} for k, v in by_leg.iterrows()}, "by_year": {int(k): float(v) for k, v in year.items()}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/t58_hypotheses/bot_replays.json")
    ap.add_argument("--a-stride", type=int, default=45)
    ap.add_argument("--b-stride", type=int, default=90)
    ap.add_argument("--first", default="2021-01-01", help="first evaluation start (needs 500 days of warm-up before it)")
    ap.add_argument("--months", type=int, default=24)
    a = ap.parse_args()
    new = {c.id: c for c in preset_configs()}
    old = {c.id: c for c in old_presets()}
    lo0, hi = R.bot_span(new["bot-profit"])
    hi = hi.floor("D")
    first = max(pd.Timestamp(a.first, tz="UTC"), lo0 + pd.Timedelta(days=520))
    res = {}
    t0 = time.time()
    for tag, bots in (("old", old), ("new", new)):
        r = {}
        r["bot-pass"] = eval_runs(bots["bot-pass"], 60, a.a_stride, first, hi); print(tag, "pass", {k: v for k, v in r["bot-pass"].items() if k != "rows"}, round(time.time() - t0), flush=True)
        r["bot-payout"] = eval_runs(bots["bot-payout"], 365, a.b_stride, first, hi); print(tag, "payout", {k: v for k, v in r["bot-payout"].items() if k != "rows"}, round(time.time() - t0), flush=True)
        start = max(hi - pd.DateOffset(months=a.months), lo0 + pd.Timedelta(days=520))
        r["bot-profit"] = net_run(bots["bot-profit"], pd.Timestamp(start), hi); print(tag, "profit", r["bot-profit"], round(time.time() - t0), flush=True)
        res[tag] = r
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
