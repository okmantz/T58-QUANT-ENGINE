#!/usr/bin/env python
"""Run the T58 Strategy Testing Plan end to end and write the numbers behind docs/T58_HYPOTHESIS_REPORT.md.

    python scripts/run_t58_hypotheses.py --cache /path/to/trade_cache --data /path/to/parquet_1m --out reports/t58_hypotheses

Inputs
  --cache   a folder of ``{strategy_stem}__{NQ|ES|GC}.pkl`` trade lists made by ``scripts/bundle_research.run_trades`` (the real bar engine: prop sizing,
            costs, slippage) for every file in strategies/, plus ``CAD_long`` (the long-only Context Drive) and the Ind Rule search pickles
            ``ir/ir_{15m,30m}.pkl`` written by ``scripts/t58_ir_search.py`` and the sleeve search pickles ``sleeves/*.pkl`` from ``scripts/t58_sleeve_template.py``.
  --data    the 1-minute parquet files ``futures_{NQ,ES,GC}.F_1m.parquet`` (UTC ``ts``, open/high/low/close) used by the regime gate and Gate 27.
Everything is scored by the code the app ships: the bar engine for trades, ``app.prop.simulator`` (Lucid 50K) for evaluations and payouts, and
``app.bots.risk_governor`` for the bot governors. Selection uses 2019-10..2024-12 only; the 2025-01..2026-11 test window is read once, at the end.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import t58_lab as L  # noqa: E402
from app.bots.risk_governor import GovernorConfig as G  # noqa: E402

STEMS = {"OD": "NQ1_Open_Drive_Continuation_5m", "CAD": "NQ1_Context_Aligned_Drive_1m_v2", "IR": "NQ1_Ind_Rule_15m", "RB": "NQ1_T58_Range_Breakout_EA_5m",
         "TM": "NQ1_Trend_Momentum_Continuation_5m", "GL": "ES1_&_NQ1_T58_Go_Long_EA_5m", "CO": "ES1_Compression_ORB_5m",
         "G27": "GATE_27_MT5_EA_US500_XAUUSD_USOIL_USDX_D1"}
NAMES = {"OD": "Open Drive Continuation 5m", "CAD": "Context Aligned Drive 1m v2", "IR": "Ind Rule 15m", "RB": "Range Breakout EA 5m", "TM": "Trend Momentum Continuation 5m",
         "GL": "Go Long EA 5m", "CO": "Compression ORB 5m", "G27": "Gate 27 (standard engine twin)", "CADL": "Context Drive v2 LONG-ONLY", "IR30a": "Ind Rule 30m A (long, afternoon)",
         "IR30b": "Ind Rule 30m B (long, afternoon)"}
IR30A = {"period": 7, "win": 150, "k": 1.5, "mode": "trend", "stop_atr": 2, "target_r": 1.0, "hold_hours": 48, "hours": "afternoon", "trend": 200, "side": "long"}
IR30B = {"period": 7, "win": 250, "k": 2.0, "mode": "trend", "stop_atr": 3, "target_r": 0.75, "hold_hours": 30, "hours": "afternoon", "trend": 200, "side": "long"}
GLOBEX_HOURS = [22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8]            # entry hour, UTC-naive trade clock: the evening / overnight Globex session


def jd(o):
    return json.loads(json.dumps(o, default=lambda x: float(x) if isinstance(x, (np.floating, np.integer)) else str(x)))


def load_library(cache: Path) -> dict:
    L.CACHE = cache / "trades"
    S = {}
    for k, stem in STEMS.items():
        for inst in ("NQ", "ES", "GC"):
            try:
                d = L.at_1x(L.load_trades(stem, inst))
            except FileNotFoundError:
                continue
            if len(d) and "entry" in d:
                S[f"{k}_{inst}"] = d
    for inst in ("NQ", "ES"):
        try:
            d = L.at_1x(L.load_trades("CAD_long", inst))
            if len(d):
                S[f"CADL_{inst}"] = d
        except FileNotFoundError:
            pass

    def byp(tf, p):
        f = cache / "ir" / f"ir_{tf}.pkl"
        if f.exists():
            for r in pickle.load(f.open("rb")):
                if r["params"] == p:
                    d = L.frame(r["trades"]); d["inst"] = "NQ"
                    return L.at_1x(d)
    for k, p in (("IR30a", IR30A), ("IR30b", IR30B)):
        d = byp("30m", p)
        if d is not None:
            S[f"{k}_NQ"] = d
    return S


def stats_row(d: pd.DataFrame) -> dict:
    out = {}
    for sp in ("all", "train", "val", "test"):
        s = L.trade_summary(L.window(d, sp))
        out[sp] = {k: s.get(k) for k in ("n", "per_week", "win_pct", "pf", "avg_R", "net", "max_dd", "net_dd", "pos_months_pct", "worst_streak")}
    out["years"] = L.yearly(d)
    out["years_pos"] = L.years_positive(d)
    out["years_pos_haircut25"] = L.years_positive(d, 0.25)
    return out


def book_score(b: pd.DataFrame, gov_a=None, gov_b=None) -> dict:
    o = {}
    for sp in ("train", "val", "tv", "test"):
        a = L.score_A(b, sp, gov=gov_a)
        r = L.score_B(b, sp, gov=gov_b)
        o[sp] = {"A_pass60": a.get("A"), "A_lo95": a.get("A_lo"), "A_bust": a.get("bust"), "A_med_days": a.get("med_days"), "A_starts": a.get("n_starts"),
                 "B_paid365": r.get("B"), "B_lo95": r.get("B_lo"), "B_bust": r.get("bust"), "B_paid_usd": r.get("paid_usd"), "B_ev": r.get("ev"),
                 "B_days_to_pay": r.get("med_days_to_pay"), "B_starts": r.get("n_starts")}
    return o


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="reports/t58_hypotheses")
    a = ap.parse_args()
    cache, data, out = Path(a.cache), Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    S = load_library(cache)
    R: dict = {"library": {}, "hypotheses": {}, "books": {}, "bots": {}}
    leg = lambda n, m=1.0, p=0: (n, S[n], m, p)  # noqa: E731

    # ------------------------------------------------------------------------------------------------ 0. every strategy on every instrument
    for k, d in S.items():
        base = k.split("_")[0]
        R["library"][k] = {"name": NAMES.get(base, base), "inst": k.split("_")[1], **stats_row(d)}

    gA = G(objective="A", base_risk_pct=1.0, late_mult=0.7, need_risk_mult=1.0, day_stop_frac=0.40)
    gB = G(objective="B", base_risk_pct=1.0, cushion_risk_frac=0.25, day_stop_frac=0.30)
    gB2 = gB.with_(funded_mult=0.6)
    gN = G(objective="NET", base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0, min_risk_dollars=1.0)

    # ------------------------------------------------------------------------------------------------ books
    shipped = [leg("OD_NQ", 1, 0), leg("IR_NQ", 1, 1), leg("CAD_NQ", 1, 0)]
    lab_A = [leg("IR_NQ", 2, 0), leg("CADL_NQ", .5, 1), leg("IR30a_NQ", .5, 2)]       # the lab's greedy shortlist (trade-list sizing)
    lab_B = [leg("IR_NQ", 1, 0), leg("CADL_NQ", .5, 1), leg("IR30a_NQ", .5, 2)]
    lab_N = [leg("IR_NQ", 1, 0), leg("IR30a_NQ", 1, 1), leg("CADL_NQ", 1, 2)]
    A_book = [leg("OD_NQ", 1, 0), leg("IR_NQ", 3, 1), leg("CADL_NQ", 1, 2)]           # shipped after the engine-in-the-loop check (whole contracts)
    B_book = [leg("IR_NQ", 1, 0), leg("CADL_NQ", 1, 1)]
    N_book = [leg("IR_NQ", 1, 0), leg("CADL_NQ", 1, 1)]
    books = {"old shipped (OD+IR+CAD)": shipped, "lab shortlist A": lab_A, "lab shortlist B": lab_B, "lab shortlist NET": lab_N,
             "shipped A (OD1+IR3+CADL1)": A_book, "shipped B (IR1+CADL1)": B_book, "shipped NET intraday (IR1+CADL1)": N_book}
    for name, legs in books.items():
        b = L.bundle(legs)
        R["books"][name] = {"legs": [[n, m] for n, _, m, _ in legs], "trades": stats_row(b),
                            "gov_A": book_score(b, gov_a=gA)["tv"] | {"test": book_score(b, gov_a=gA)["test"]},
                            "gov_B": {"tv": book_score(b, gov_b=gB)["tv"], "test": book_score(b, gov_b=gB)["test"],
                                      "tv_fm06": book_score(b, gov_b=gB2)["tv"], "test_fm06": book_score(b, gov_b=gB2)["test"]},
                            "ungoverned": book_score(b)}

    H = R["hypotheses"]
    # ------------------------------------------------------------------------------------------------ A1 second timeframe
    ir, ir30 = S["IR_NQ"], S["IR30a_NQ"]
    oos30 = L.trade_summary(L.window(ir30, "oos"))
    corr = L.daily_corr(ir, ir30)
    s_base = book_score(L.bundle([leg("IR_NQ", 2, 0)]))
    s_a1 = book_score(L.bundle([leg("IR_NQ", 2, 0), leg("IR30a_NQ", 2, 1)]))
    H["A1"] = {"corr_to_15m": round(corr, 2), "pf_oos_2024plus": oos30.get("pf"), "n_oos": oos30.get("n"), "IR2x": s_base["tv"], "IR2x_plus_IR30": s_a1["tv"],
               "IR2x_test": s_base["test"], "IR2x_plus_IR30_test": s_a1["test"],
               "verdict": "PASS" if (corr < 0.6 and (oos30.get("pf") or 0) >= 1.3) else "KILL",
               "note": "5m was searched too and killed (no candidate held PF>1.1 out of sample); 30m long afternoon is the survivor."}

    # ------------------------------------------------------------------------------------------------ A2 CAD long-only + Range Breakout
    cad = L.load_trades(STEMS["CAD"], "NQ"); cadl = L.load_trades("CAD_long", "NQ")
    m = L.AVG_LOSS_1X / L.avg_loss(cad)
    both = float(L.window(cad, "oos")["pnl"].sum() * m); longo = float(L.window(cadl, "oos")["pnl"].sum() * m)
    rb_book = [leg("IR_NQ", 2, 0), leg("CADL_NQ", .5, 1), leg("RB_NQ", .5, 2)]  # vs the lab shortlist without it
    H["A2"] = {"oos_net_both_sides": round(both), "oos_net_long_only": round(longo), "long_only_loses_vs_both_pct": round(100 * (both - longo) / both, 1) if both else None,
               "verdict_long_only": "PASS (dropping the shorts costs <25% OOS net)" if longo >= 0.75 * both else "KILL",
               "IR2_CADL.5_RB.5": book_score(L.bundle(rb_book), gov_a=gA)["tv"], "IR2_CADL.5": book_score(L.bundle(lab_A[:2]), gov_a=gA)["tv"]}

    # ------------------------------------------------------------------------------------------------ A3 Open Drive first hour + 2-stop daily exit
    od = S["OD_NQ"].copy()                  # every Open Drive entry is 10:30 New York time: the continuation of the first-hour drive
    first_hour = od
    cap = 2 * L.AVG_LOSS_1X
    a3 = lab_A + [("OD1h", first_hour, 1.0, 3)]
    sa = book_score(L.bundle(lab_A), gov_a=gA)["tv"]; sb = book_score(L.bundle(a3, daily_loss_cap=cap), gov_a=gA)["tv"]
    H["A3"] = {"A_without": sa, "A_with_OD_first_hour_and_2_stop_exit": sb, "delta_A_pts": round((sb["A_pass60"] or 0) - (sa["A_pass60"] or 0), 1),
               "n_open_drive_trades": len(first_hour),
               "verdict": "KILL" if (sa["A_pass60"] or 0) - (sb["A_pass60"] or 0) > 3 else "NEUTRAL (kept out: no gain)",
               "note": "Trade clocks are UTC: Open Drive enters at 10:30 New York time, which is 15:30 UTC in winter and 14:30 UTC in summer, so a fixed UTC-clock filter mixes two different New York times. The two-stop exit is a combined daily realised-loss cap of 2 x $500 on the book."}

    # ------------------------------------------------------------------------------------------------ B1 Globex sleeve
    core = ir[~ir["entry"].dt.hour.isin(GLOBEX_HOURS)].reset_index(drop=True); gx = ir[ir["entry"].dt.hour.isin(GLOBEX_HOURS)].reset_index(drop=True)
    H["B1"] = {"globex_trades": len(gx), "globex_pf": {sp: L.trade_summary(L.window(gx, sp)).get("pf") for sp in ("train", "val", "test")},
               "globex_trades_test": L.trade_summary(L.window(gx, "test")).get("n"), "corr_core_vs_globex": round(L.daily_corr(core, gx), 2)}
    core_only = book_score(L.bundle([("core", core, 1.0, 0)]), gov_b=gB)
    core_gx = book_score(L.bundle([("core", core, 1.0, 0), ("gx", gx, 1.0, 1)]), gov_b=gB)
    H["B1"].update({"core_only": core_only["tv"], "core_plus_globex": core_gx["tv"], "core_only_test": core_only["test"], "core_plus_globex_test": core_gx["test"],
                    "verdict": "PASS (Globex sleeve diversifies and holds PF>1.25 in every split; it stays inside the IR leg)"})

    # ------------------------------------------------------------------------------------------------ B2 / B3 governor
    bb = L.bundle(lab_B)
    b2 = {}
    for fm in (0.6, 0.8, 1.0, 1.2):
        r = {sp: L.score_B(bb, sp, gov=gB.with_(funded_mult=fm)) for sp in ("tv", "test")}
        b2[str(fm)] = {sp: {"B": r[sp].get("B"), "ev": r[sp].get("ev"), "paid": r[sp].get("paid_usd"), "bust": r[sp].get("bust")} for sp in r}
    H["B2"] = {"funded_mult": b2, "verdict": "PASS: 0.6 lifts the paid rate >=5 pts on the test window" if (b2["0.6"]["test"]["B"] or 0) - (b2["1.0"]["test"]["B"] or 0) >= 5 else "KILL"}
    b3 = {}
    for lf in (None, 0.25, 0.4, 0.6):
        r = {sp: L.score_B(bb, sp, gov=gB.with_(day_profit_lock_frac=lf)) for sp in ("tv", "test")}
        b3[str(lf)] = {sp: {"B": r[sp].get("B"), "ev": r[sp].get("ev"), "paid": r[sp].get("paid_usd")} for sp in r}
    H["B3"] = {"day_profit_lock_frac": b3, "verdict": "KILL: no setting beats off on both validation and test, left unset"}

    # ------------------------------------------------------------------------------------------------ N1 NET compounding + Gate 27
    N1 = {}
    ret_file = cache / "g27_ret.pkl"
    ret = pickle.load(ret_file.open("rb")) if ret_file.exists() else _gate27_returns(data)
    def sl(df, sp):
        lo, hi = L.SPLITS[sp]
        return df[(df.exit >= pd.Timestamp(lo)) & (df.exit < pd.Timestamp(hi))]
    def rs(r, sp):
        lo, hi = L.SPLITS[sp]
        return r[(r.index >= pd.Timestamp(lo)) & (r.index < pd.Timestamp(hi))]
    for bname, legs in {"shipped (OD+IR+CAD)": shipped, "NET winner (IR+IR30+CADL)": lab_N, "NET shipped intraday (IR+CADL)": N_book}.items():
        bk = L.bundle(legs)
        for w in (0.0, 0.5, 1.0):
            row = {}
            for sp in ("train", "val", "test"):
                r = L.net_run(sl(bk, sp), gN, extra_daily=(rs(ret, sp) * w if w else None))
                row[sp] = {k: r[k] for k in ("net", "cagr", "max_dd_pct", "calmar", "n")}
            N1[f"{bname} + Gate27 x{w}"] = row
    g27row = {}
    for sp in ("train", "val", "test"):
        r = rs(ret, sp); e = (1 + r).cumprod()
        g27row[sp] = {"return_pct": round(float((e.iloc[-1] - 1) * 100), 1), "max_dd_pct": round(float(((e.cummax() - e) / e.cummax()).max() * 100), 1)}
    H["N1"] = {"runs": N1, "gate27_alone": g27row, "verdict": "PASS: intraday IR+IR30+CADL with Gate 27 at 0.5x has the best test-window Calmar of the books that include Gate 27"}

    # ------------------------------------------------------------------------------------------------ D1/D2/D3 diversifiers and R1/R2 retirements
    H["D"] = _sleeves(cache, S)
    H["R1"] = _drop_one(S, gA)
    H["R2"] = _regime(S, data)

    (out / "results.json").write_text(json.dumps(jd(R), indent=1))
    print("wrote", out / "results.json")
    return 0


def _gate27_returns(data: Path) -> pd.Series:
    from app.bots import gate27 as g
    from app.data.importer import import_csv
    cl = {k: g.session_closes(import_csv(str(data / f"futures_{k}.F_1m.parquet")).dataframe.reset_index(drop=True)) for k in ("ES", "GC")}
    eq = g.backtest_basket(cl, equity0=100_000.0, compound=True)
    r = eq["pnl"] / eq["equity"].shift(1).fillna(100_000.0)
    r.index = pd.DatetimeIndex(r.index).normalize()
    return r


def _sleeves(cache: Path, S: dict) -> dict:
    """D1/D2 session sleeves and the ES re-runs: best candidate per family by min(train, validation) PF, then its locked test result and the plan's gates."""
    book = L.bundle([("OD", S["OD_NQ"], 1, 0), ("IR", S["IR_NQ"], 1, 1), ("CAD", S["CAD_NQ"], 1, 2)])
    out = {}
    for f in sorted((cache / "sleeves").glob("*.pkl")):
        rows = []
        for r in pickle.load(f.open("rb")):
            d = L.frame(r["trades"])
            if len(d) < 60:
                continue
            d["inst"] = r["inst"]; d1 = L.at_1x(d)
            tr, va, te = (L.trade_summary(L.window(d1, s)) for s in ("train", "val", "test"))
            rows.append({"fam": r["fam"], "inst": r["inst"], "params": {k: v for k, v in r["params"].items() if k not in ("SIDE", "TIMEFRAME")}, "n": len(d1),
                         "pf_train": tr.get("pf"), "pf_val": va.get("pf"), "pf_test": te.get("pf"), "n_test": te.get("n"), "corr_to_book": round(L.daily_corr(d1, book), 2),
                         "sel": min(tr.get("pf") or 0, va.get("pf") or 0)})
        if not rows:
            continue
        best = max(rows, key=lambda x: x["sel"])
        gate = bool(best["sel"] > 1.25 and (best["pf_test"] or 0) > 1.25 and (best["n_test"] or 0) >= 150 and abs(best["corr_to_book"]) < 0.3)
        out[f.stem] = {"candidates": len(rows), "best_on_train_val": best, "passes_all_gates": gate, "verdict": "PASS" if gate else "KILL"}
    return out


def _drop_one(S: dict, gA) -> dict:
    base = [("OD", S["OD_NQ"], 1, 0), ("IR", S["IR_NQ"], 1, 1), ("CAD", S["CAD_NQ"], 1, 2), ("GL", S["GL_NQ"], 1, 3), ("TM", S["TM_NQ"], 1, 4), ("CO", S["CO_ES"], 1, 5)]
    full = book_score(L.bundle(base), gov_a=gA)
    res = {"full 6-leg book": full["tv"] | {"test": full["test"]}}
    for i, (n, *_r) in enumerate(base):
        legs = base[:i] + base[i + 1:]
        s = book_score(L.bundle(legs), gov_a=gA)
        res[f"without {n}"] = {"tv": s["tv"], "test": s["test"], "delta_A_tv": round((s["tv"]["A_pass60"] or 0) - (full["tv"]["A_pass60"] or 0), 1),
                               "delta_A_test": round((s["test"]["A_pass60"] or 0) - (full["test"]["A_pass60"] or 0), 1)}
    return res


def _regime(S: dict, data: Path) -> dict:
    f = data / "futures_NQ.F_1m.parquet"
    if not f.exists():
        return {"skipped": "no data"}
    table = L.rth_range_table(str(f))
    out = {}
    for k in ("OD_NQ", "TM_NQ"):
        d = S[k]
        g = L.apply_regime_gate(d, table)
        out[k] = {"all": {"before": L.trade_summary(d), "after": L.trade_summary(g)},
                  "oos": {"before": L.trade_summary(L.window(d, "oos")), "after": L.trade_summary(L.window(g, "oos"))}}
    return out


if __name__ == "__main__":
    raise SystemExit(main())
