"""Gate 27 re-evaluation: the original EA rules vs variants, for NET PROFIT (Objective C), with the armored v1.10 guards modelled.

Everything runs on daily session closes through the frozen sizing code in app.bots.gate27 (identical to the EA: monthly SMA gate, inverse-volatility
sizing, 5x leverage cap, three-day phase-in). The grid is searched on TRAIN, confirmed on VALIDATION, and the locked TEST is read once at the end.

Data: US500 = the repo's back-adjusted ES, Gold = the repo's back-adjusted GC (T58 data pack). Oil = the uploaded CRUDEOIL file, which is an UNADJUSTED
front-month continuous series: every roll leaves a calendar-spread gap that a long position "earns", so Oil numbers are shown but never used for a
recommendation. The USD-index leg has no data in the pack or the uploads, so the 4-leg original cannot be reproduced; the 2-leg (and 3-leg with Oil) baskets
are the testable versions.

    python scripts/run_gate27_study.py --out /home/claude/work/results
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from app.bots import gate27 as g  # noqa: E402

SPLIT = {"train": ("2019-01-01", "2024-01-01"), "val": ("2024-01-01", "2025-01-01"), "test": ("2025-01-01", "2027-01-01"), "all": ("2019-01-01", "2027-01-01")}
PV = {"ES": 50.0, "GC": 100.0, "CL": 1000.0}


def closes_from_repo(folder: str) -> pd.DataFrame:
    from app.data.importer import import_csv
    f = next((ROOT / "data" / "raw" / folder).glob("*_1m.parquet"))
    return g.session_closes(import_csv(str(f)).dataframe)


def closes_from_upload(path: str) -> pd.DataFrame:
    from app.data.importer import import_csv
    return g.session_closes(import_csv(path).dataframe)


def basket(closes: dict, cfg: g.Gate27Config, *, equity0: float = 100_000.0, guard: dict | None = None) -> pd.DataFrame:
    """backtest_basket with the armored EA's halt guards. ``guard`` = {"daily": 3.0 (% of day-start equity), "dd": 7.0 (% below the starting baseline),
    "resume": "never" | "month"}; None = the original EA (no guards)."""
    legs = list(closes)
    first = max(closes[k].index[0] for k in legs)
    full = sorted(set().union(*[set(closes[k].index) for k in legs]))
    idx = [d for d in full if d >= first]
    px = pd.DataFrame({k: closes[k]["close"].reindex(full).ffill() for k in legs}).loc[idx]
    raw = pd.DataFrame({k: closes[k]["raw"].reindex(full).ffill() for k in legs}).loc[idx]
    pv = {k: PV.get(k, 50.0) for k in legs}
    months = [d.year * 12 + d.month for d in idx]
    equity, qty = equity0, {k: 0.0 for k in legs}
    start_n, target, step, halted, rows = {k: 0.0 for k in legs}, {k: 0.0 for k in legs}, cfg.phase_in_days, False, []
    day_start = equity0
    for i, d in enumerate(idx):
        pnl = sum(qty[k] * (px[k].iloc[i] - px[k].iloc[i - 1]) * pv[k] for k in legs) if i > 0 else 0.0
        equity += pnl
        new_month = i > 0 and months[i] != months[i - 1]
        if guard and not halted and i > 0:
            if (equity - day_start) / day_start * 100.0 <= -guard["daily"] or (equity0 - equity) / equity0 * 100.0 >= guard["dd"]:
                halted = True
                qty = {k: 0.0 for k in legs}
                target = {k: 0.0 for k in legs}
        if halted and new_month and guard and guard.get("resume") == "month":
            halted = False
        if new_month and not halted:
            sigs = {k: g.leg_signal(px[k].iloc[:i].to_numpy(), cfg) for k in legs}
            new = g.target_notionals(sigs, equity, cfg)
            for k in legs:
                start_n[k] = qty[k] * raw[k].iloc[i - 1] * pv[k]
                target[k] = new.get(k, target[k])
            step = 0
        if not halted and step < cfg.phase_in_days:
            step += 1
            for k in legs:
                want = g.phase_notional(start_n[k], target[k], step, cfg)
                unit = raw[k].iloc[i] * pv[k]
                qty[k] = want / unit if unit > 0 else 0.0
        day_start = equity
        rows.append((d, pnl, equity, sum(abs(qty[k]) * raw[k].iloc[i] * pv[k] for k in legs) / max(equity, 1.0)))
    return pd.DataFrame(rows, columns=["day", "pnl", "equity", "gross_x"]).set_index("day")


def stats(eq: pd.DataFrame, split: str, equity0: float = 100_000.0) -> dict:
    a, b = SPLIT[split]
    e = eq[(eq.index >= pd.Timestamp(a)) & (eq.index < pd.Timestamp(b))]
    e = e[e["gross_x"] > 0].index.min() and e[e.index >= e[e["gross_x"] > 0].index.min()] if (e["gross_x"] > 0).any() else e.iloc[:0]
    if len(e) < 20:
        return {"days": int(len(e)), "net_pct": None}
    r = (e["pnl"] / e["equity"].shift(1).fillna(equity0)).to_numpy(float)
    curve = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.r_[1.0, curve])[1:]
    mdd = float(((peak - curve) / peak).max() * 100.0)
    yrs = max((e.index[-1] - e.index[0]).days / 365.25, 1e-9)
    tot = float(curve[-1] - 1.0)
    cagr = float((curve[-1] ** (1 / yrs) - 1) * 100.0) if curve[-1] > 0 else -100.0
    return {"days": int(len(e)), "years": round(yrs, 2), "net_pct": round(tot * 100.0, 1), "cagr": round(cagr, 1), "max_dd": round(mdd, 1),
            "calmar": round(cagr / mdd, 2) if mdd > 0 else None, "sharpe": round(float(r.mean() / r.std(ddof=1) * np.sqrt(252)), 2) if r.std(ddof=1) > 0 else None,
            "max_gross_x": round(float(e["gross_x"].max()), 2)}


def run_all(out_dir: Path) -> dict:
    es, gc = closes_from_repo("ES1!"), closes_from_repo("GC1!")
    oil = closes_from_upload("/mnt/user-data/uploads/CRUDEOIL_futures_1m_2019-08-02_2026-11-10.parquet")
    sets = {"US500+Gold": {"ES": es, "GC": gc}, "US500+Gold+Oil (unadjusted oil)": {"ES": es, "GC": gc, "CL": oil}, "US500 only": {"ES": es}, "Gold only": {"GC": gc}}
    res: dict = {"data": {"ES": [str(es.index[0].date()), str(es.index[-1].date())], "GC": [str(gc.index[0].date()), str(gc.index[-1].date())],
                          "CL": [str(oil.index[0].date()), str(oil.index[-1].date()), "unadjusted"]}}
    orig = g.Gate27Config()
    res["original"] = {}
    for name, cl in sets.items():
        eq = basket(cl, orig)
        res["original"][name] = {sp: stats(eq, sp) for sp in ("train", "val", "test", "all")}
    # armored guards on the 2-leg basket (the EA's defaults: daily 3%, overall 7%, static, manual resume)
    cl = sets["US500+Gold"]
    res["armored"] = {}
    for label, gd in {"no guards (original v1)": None, "v1.10 guards, manual resume (never resumes)": {"daily": 3.0, "dd": 7.0, "resume": "never"},
                      "v1.10 guards, resume next month": {"daily": 3.0, "dd": 7.0, "resume": "month"},
                      "v1.10 daily guard only, resume next month": {"daily": 3.0, "dd": 1e9, "resume": "month"}}.items():
        eq = basket(cl, orig, guard=gd)
        res["armored"][label] = {sp: stats(eq, sp) for sp in ("train", "val", "test", "all")}
    # grid on the 2-leg basket: select on train, confirm on val, report test
    grid = []
    for sma, vw, vt, cap, ph in itertools.product((100, 150, 200, 210, 250), (20, 40, 60, 90), (0.25, 0.5, 0.75, 1.0), (3.0, 5.0, 8.0), (1, 3, 5)):
        cfg = g.Gate27Config(sma_window=sma, vol_window=vw, daily_vol_target_pct=vt, leverage_cap=cap, phase_in_days=ph)
        eq = basket(cl, cfg)
        grid.append({"cfg": {"sma": sma, "vol_window": vw, "vol_target_pct": vt, "leverage_cap": cap, "phase_in": ph}, **{sp: stats(eq, sp) for sp in ("train", "val", "test")}})
    ok = [r for r in grid if r["train"].get("cagr") is not None and r["val"].get("cagr") is not None and r["train"]["max_dd"] <= 25.0 and r["val"]["max_dd"] <= 25.0]
    for r in ok:
        r["robust"] = min(r["train"]["cagr"], r["val"]["cagr"])
    ok.sort(key=lambda r: -r["robust"])
    res["grid_n"], res["grid_ok_n"], res["grid_top"] = len(grid), len(ok), ok[:12]
    res["grid_original_row"] = next((r for r in grid if r["cfg"] == {"sma": 210, "vol_window": 60, "vol_target_pct": 0.5, "leverage_cap": 5.0, "phase_in": 3}), None)
    # the daily-return stream of the original 2-leg basket, for the Objective C scorecard (added to the intraday book's equity path)
    eq0 = basket(cl, orig)
    r = (eq0["pnl"] / eq0["equity"].shift(1).fillna(100_000.0))
    r.to_frame("ret").to_parquet(out_dir / "gate27_2leg_daily_returns.parquet")
    best = ok[0]["cfg"] if ok else None
    if best:
        eqb = basket(cl, g.Gate27Config(sma_window=best["sma"], vol_window=best["vol_window"], daily_vol_target_pct=best["vol_target_pct"],
                                         leverage_cap=best["leverage_cap"], phase_in_days=best["phase_in"]))
        (eqb["pnl"] / eqb["equity"].shift(1).fillna(100_000.0)).to_frame("ret").to_parquet(out_dir / "gate27_best_daily_returns.parquet")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    r = run_all(out)
    (out / "gate27.json").write_text(json.dumps(r, indent=1, default=str))
    for k, v in r["original"].items():
        print(k, {sp: (x.get("net_pct"), x.get("cagr"), x.get("max_dd")) for sp, x in v.items()})
    print("armored:")
    for k, v in r["armored"].items():
        print(" ", k, {sp: (x.get("net_pct"), x.get("cagr"), x.get("max_dd")) for sp, x in v.items()})
    print("grid ok", r["grid_ok_n"], "/", r["grid_n"])
    for x in r["grid_top"][:5]:
        print(x["cfg"], x["train"].get("cagr"), x["val"].get("cagr"), x["test"].get("cagr"), x["test"].get("max_dd"))
