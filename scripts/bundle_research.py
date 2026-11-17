#!/usr/bin/env python3
"""Bundle research harness: strategy trade lists -> bundles -> chronological Lucid-rule replay.

Reproduces the "chronological replay" the Strategy Evaluation Report / Game Plan used for Objectives A and B, but with many more
start dates (every ``--stride`` trading days instead of ~30-40 starts) so the error bars shrink, and it can merge several
strategies into ONE account with the engine's rules (one NQ position at a time, earlier signal keeps the slot, combined daily
loss cap, optional per-strategy size multipliers).

    python scripts/bundle_research.py trades  --out reports/bundle_research/trades      # run every library strategy once
    python scripts/bundle_research.py replay  --trades reports/bundle_research/trades --out reports/bundle_research

Honest-odds note: every number is a backtest of fixed, pre-registered parameters. Overlapping start dates are NOT independent, so the
effective sample size is roughly (history length / evaluation horizon); the reported 95% interval uses ``n_eff`` for that reason.
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
import warnings
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DATA = {"NQ": "data/raw/NQ1!/futures_NQ.F_1m.parquet", "ES": "data/raw/ES1!/futures_ES.F_1m.parquet",
        "GC": "data/raw/GC1!/futures_GC.F_1m.parquet"}
PRESET = "lucid_50k"


# ----------------------------------------------------------------------------------------------------------------- trade lists
def load_strategy(path: Path):
    from app.strategy.mql5 import MQL5Strategy
    from app.strategy.pinescript import PineScriptStrategy
    from app.strategy.python import PythonStrategy
    if path.suffix == ".py":
        return PythonStrategy(str(path))
    text = path.read_text(encoding="utf-8")
    return MQL5Strategy(text) if path.suffix == ".mq5" else PineScriptStrategy(text)


def run_trades(strategy_path: Path, instrument: str, df: pd.DataFrame, *, risk_pct: float = 1.0, preset: str = PRESET,
               risk_overrides: dict | None = None) -> list[dict]:
    """The engine's prop sizing (rr_planned, micro substitution, 1% cap) -> one dict per closed trade, dollars."""
    from app.backtest.engine import run_backtest
    from app.backtest.risk import RiskConfig, with_prop_safety_defaults
    from app.data.instrument_specs import apply_instrument_spec
    from app.prop.presets import get_preset
    rules = get_preset(preset).to_prop_rules()
    risk = apply_instrument_spec(RiskConfig(), instrument)
    risk = replace(risk, initial_balance=rules.account_size, sizing_mode="rr_planned", risk_value=risk_pct, reset_on_breach=False)
    risk = with_prop_safety_defaults(risk, rules)
    risk = replace(risk, max_account_drawdown_pct=None, daily_loss_limit_pct=None, halt_on_breach=False, reset_on_breach=False)
    if risk_overrides:
        risk = replace(risk, **risk_overrides)
    bt = run_backtest(df, load_strategy(strategy_path), risk)
    out = []
    for t in bt.trades:
        et, xt = pd.Timestamp(t.entry_time), pd.Timestamp(t.exit_time)
        out.append({"entry": et.tz_localize(None) if et.tzinfo else et, "exit": xt.tz_localize(None) if xt.tzinfo else xt,
                    "pnl": float(t.pnl), "dir": int(t.direction), "size": float(t.size),
                    "risk_usd": float((t.initial_risk or 0.0) * t.size * (risk.contract_size or 1.0)),
                    "mae": float(getattr(t, "mae_dollars", 0.0) or 0.0)})
    return out


# ------------------------------------------------------------------------------------------------------------- bundle assembly
@dataclass
class Leg:
    name: str
    trades: list            # list of dicts from run_trades
    mult: float = 1.0       # size multiplier applied to pnl (whole-contract rounding ignored: research-level scaling)
    priority: int = 0       # lower wins a same-time conflict
    inst: str = "NQ"        # one open position per instrument (an ES filler may overlap an NQ trade)


def merge_bundle(legs: list[Leg], *, daily_loss_cap: float | None = None, one_position: bool = True) -> list[dict]:
    """One account, several strategies: earlier entry keeps the slot (ties -> lower priority number); optional combined daily
    realised-loss cap (stop taking NEW trades for the day once realised day pnl <= -cap)."""
    rows = []
    for lg in legs:
        for t in lg.trades:
            rows.append({**t, "pnl": t["pnl"] * lg.mult, "leg": lg.name, "prio": lg.priority, "inst": lg.inst})
    rows.sort(key=lambda r: (r["entry"], r["prio"]))
    out, busy_until, day_pnl = [], {}, {}
    for r in rows:
        if one_position and r["entry"] < busy_until.get(r["inst"], pd.Timestamp.min):
            continue
        d = (r["entry"] - pd.Timedelta(hours=17)).normalize()    # CME session day (17:00 ET roll) approximated on naive-UTC stamps
        if daily_loss_cap is not None and day_pnl.get(d, 0.0) <= -daily_loss_cap:
            continue
        out.append(r)
        busy_until[r["inst"]] = r["exit"]
        day_pnl[d] = day_pnl.get(d, 0.0) + r["pnl"]
    return out


# ------------------------------------------------------------------------------------------------------------------ replay
def _wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0)) / d
    return max(0.0, c - h), min(1.0, c + h)


def _payout_stats(r, sd) -> tuple:
    """(calendar days from start to first payout or None, total payout $ within 365 calendar days of the start)."""
    first, tot = None, 0.0
    for ev in getattr(r, "payouts", []) or []:
        try:
            dd = (pd.Timestamp(ev.date) - pd.Timestamp(sd)).days
        except Exception:  # noqa: BLE001
            continue
        if first is None:
            first = float(dd)
        if dd <= 365:
            tot += float(ev.amount)
    return first, tot


def replay(trades: list[dict], rules, *, stride_days: int = 5, horizon_days: int = 730, windows=(30, 60, 90),
           start_min=None, start_max=None) -> dict:
    """Start a fresh account on every ``stride_days``-th trading day that has a trade, replay the real trade list forward through
    ``simulate_account`` and aggregate: pass within W calendar days, pass any time, bust-before-pass, first payout."""
    from app.prop.simulator import simulate_account
    if not trades:
        return {"n_starts": 0}
    tdf = pd.DataFrame(trades).sort_values("entry").reset_index(drop=True)
    tdf["day"] = tdf["entry"].dt.normalize()
    days = sorted(tdf["day"].unique())
    last = tdf["exit"].max()
    starts = [d for d in days[::max(1, stride_days)]
              if (start_min is None or d >= pd.Timestamp(start_min)) and (start_max is None or d < pd.Timestamp(start_max))]
    res = []
    for sd in starts:
        end = sd + pd.Timedelta(days=horizon_days)
        if end > last + pd.Timedelta(days=1):
            continue        # horizon not fully observed: right-censored, excluded rather than counted as a failure
        sub = tdf[(tdf["day"] >= sd) & (tdf["entry"] < end)]
        if sub.empty:
            continue
        r = simulate_account(sub["pnl"].tolist(), [d.date() for d in sub["day"]], rules,
                             trade_entry_times=sub["entry"].tolist(), trade_exit_times=sub["exit"].tolist(),
                             trade_sides=sub["dir"].tolist())
        cal = None
        if r.passed_evaluation and r.calendar_days_to_pass is not None:
            cal = float(r.calendar_days_to_pass)
        fp, p365 = _payout_stats(r, sd)
        res.append({"start": sd, "passed": bool(r.passed_evaluation), "failed": bool(r.failed), "cal": cal,
                    "payout": bool(r.reached_first_payout), "n": len(sub), "payout_days": fp, "payout_365": p365,
                    "bust_before_pass": bool(r.failed and not r.passed_evaluation),
                    "total_payout": float(r.total_payout_amount)})
    return _summarize(res, days, horizon_days, windows)


def govern_and_replay(trades: list[dict], rules, gov_cfg, *, stride_days: int = 3, horizon_days: int = 730, windows=(30, 60, 90),
                      start_min=None, start_max=None, lite=None, keep=False) -> dict:
    """Like ``replay`` but every trade is re-sized by the bot risk governor (app.bots.risk_governor) from the CURRENT account state:
    each start date walks its own path, the governor sees the evolving cushion / progress / day P&L, skips or scales each trade, and
    the scaled list is then judged by the real ``simulate_account`` (so pass / bust / payout verdicts are the engine's, not the tracker's).
    Multiplier 1.0 = the trade as the engine sized it under the 1% cap."""
    from app.bots.risk_governor import AccountRulesLite, AccountState, decide_risk
    from app.prop.simulator import simulate_account
    lite = lite or AccountRulesLite.from_v2(__import__("app.prop.lifecycle_v2", fromlist=["V2Rules"]).V2Rules.lucid_50k())
    if not trades:
        return {"n_starts": 0}
    tdf = pd.DataFrame(trades).sort_values("entry").reset_index(drop=True)
    tdf["day"] = tdf["entry"].dt.normalize()
    days = sorted(tdf["day"].unique())
    last = tdf["exit"].max()
    starts = [d for d in days[::max(1, stride_days)]
              if (start_min is None or d >= pd.Timestamp(start_min)) and (start_max is None or d < pd.Timestamp(start_max))]
    entries, pnls, dayv, exits, dirs = (tdf["entry"].tolist(), tdf["pnl"].to_numpy(), tdf["day"].tolist(), tdf["exit"].tolist(), tdf["dir"].tolist())
    base_total = lite.account_size * gov_cfg.base_risk_pct / 100.0
    res = []
    for sd in starts:
        end = sd + pd.Timedelta(days=horizon_days)
        if end > last + pd.Timedelta(days=1):
            continue
        i0 = int(np.searchsorted(tdf["day"].values, np.datetime64(sd)))
        st = AccountState.fresh(lite)
        o_pnl, o_day, o_en, o_ex, o_dir = [], [], [], [], []
        passed_at = None
        for i in range(i0, len(tdf)):
            if entries[i] >= end:
                break
            d = dayv[i]
            st.roll_day(str(d.date()))
            dec = decide_risk(st, gov_cfg)
            if st.phase == "passed":
                if gov_cfg.objective == "B" or gov_cfg.funded_mult != 1.0 or True:
                    st.to_funded()
                    dec = decide_risk(st, gov_cfg)
            if not dec.allow:
                continue
            m = dec.risk_dollars / base_total if base_total else 1.0
            p = float(pnls[i]) * m
            o_pnl.append(p); o_day.append(d.date()); o_en.append(entries[i]); o_ex.append(exits[i]); o_dir.append(dirs[i])
            before = st.phase
            st.update(p, str(d.date()))
            if st.phase == "funded":
                st.take_payout()
        if not o_pnl:
            continue
        r = simulate_account(o_pnl, o_day, rules, trade_entry_times=o_en, trade_exit_times=o_ex, trade_sides=o_dir)
        cal = float(r.calendar_days_to_pass) if (r.passed_evaluation and r.calendar_days_to_pass is not None) else None
        fp, p365 = _payout_stats(r, sd)
        res.append({"start": sd, "passed": bool(r.passed_evaluation), "cal": cal, "payout": bool(r.reached_first_payout),
                    "payout_days": fp, "payout_365": p365,
                    "bust_before_pass": bool(r.failed and not r.passed_evaluation), "total_payout": float(r.total_payout_amount)})
    return _summarize(res, days, horizon_days, windows)


def _summarize(res, days, horizon_days, windows) -> dict:
    n = len(res)
    if n == 0:
        return {"n_starts": 0}
    n_eff = max(1.0, (days[-1] - days[0]).days / float(horizon_days))
    out = {"n_starts": n, "n_eff": round(n_eff, 1)}
    for w in windows:
        k = sum(1 for x in res if x["passed"] and x["cal"] is not None and x["cal"] <= w)
        out[f"pass_{w}d"] = round(100 * k / n, 1)
        out[f"pass_{w}d_lo"] = round(100 * _wilson(k / n * n_eff, n_eff)[0], 1)
    out["pass_any"] = round(100 * sum(x["passed"] for x in res) / n, 1)
    out["bust"] = round(100 * sum(x["bust_before_pass"] for x in res) / n, 1)
    out["bust_hi"] = round(100 * _wilson(sum(x["bust_before_pass"] for x in res) / n * n_eff, n_eff)[1], 1)
    out["payout"] = round(100 * sum(x["payout"] for x in res) / n, 1)
    out["payout_lo"] = round(100 * _wilson(sum(x["payout"] for x in res) / n * n_eff, n_eff)[0], 1)
    cals = [x["cal"] for x in res if x["cal"] is not None]
    out["median_days_to_pass"] = float(np.median(cals)) if cals else None
    out["mean_payout_usd"] = round(float(np.mean([x["total_payout"] for x in res])), 0)
    for w in (120, 180, 270):
        k = sum(1 for x in res if x.get("payout_days") is not None and x["payout_days"] <= w)
        out[f"payout_{w}d"] = round(100 * k / n, 1)
        out[f"payout_{w}d_lo"] = round(100 * _wilson(k / n * n_eff, n_eff)[0], 1)
    pd_ = [x["payout_days"] for x in res if x.get("payout_days") is not None]
    out["median_days_to_payout"] = float(np.median(pd_)) if pd_ else None
    out["mean_payout_365_usd"] = round(float(np.mean([x.get("payout_365", 0.0) for x in res])), 0)
    return out


def trade_stats(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0, "net": 0.0, "pf": 0.0, "maxdd": 0.0}
    p = np.array([t["pnl"] for t in sorted(trades, key=lambda r: r["exit"])])
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max())
    return {"n": int(len(p)), "net": round(float(p.sum()), 0), "pf": round(float(gw / gl), 2) if gl > 0 else float("inf"),
            "maxdd": round(dd, 0), "net_dd": round(float(p.sum() / dd), 1) if dd > 0 else None}


# ------------------------------------------------------------------------------------------------------------------ CLI
def cmd_trades(a) -> int:
    from app.data.importer import import_csv
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    frames = {k: import_csv(str(ROOT / v)).dataframe.reset_index(drop=True) for k, v in DATA.items() if k in a.instruments}
    files = sorted(list((ROOT / "strategies").glob("*/*.py")) + list((ROOT / "strategies").glob("*/*.mq5")) +
                   list((ROOT / "strategies").glob("*/*.pine")))
    for f in files:
        for inst, df in frames.items():
            key = out / f"{f.stem.replace('!', '').replace(' ', '_')}__{inst}.pkl"
            if key.exists() and not a.force:
                continue
            try:
                tr = run_trades(f, inst, df)
            except Exception as e:  # noqa: BLE001
                print(f"[skip] {f.name} on {inst}: {type(e).__name__}: {str(e)[:120]}")
                continue
            pickle.dump(tr, key.open("wb"))
            print(f"{f.name:50s} {inst}: {trade_stats(tr)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trades")
    t.add_argument("--out", default="reports/bundle_research/trades")
    t.add_argument("--instruments", nargs="*", default=["NQ", "ES", "GC"])
    t.add_argument("--force", action="store_true")
    t.set_defaults(fn=cmd_trades)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
