#!/usr/bin/env python3
"""Bot optimisation study: does a profit-lock ladder, an adaptive loser cut or an FOMC overlay make the three bots hit their objective better?

    python scripts/run_bot_optimization.py trades --cache DIR            # every strategy x instrument x risk variant through the real bar engine (resumable)
    python scripts/run_bot_optimization.py books  --cache DIR --out DIR  # forward selection per objective on TRAIN, confirmed on VALIDATION, TEST read once

Honesty rules (same as scripts/run_objective_scores.py, whose scorers and book builder this reuses):
  * selection uses train (2020-01..2023-12) and validation (2024) only; the locked test (2025-01..) is read once, for the finished books;
  * a book may hold ONE variant of a strategy (never "base" and "locked" of the same leg at once);
  * every number is a real bar-engine trade run through the real simulators; the previous presets are scored with the same code as the baseline.

Variants (RiskConfig overlays, app/backtest/profit_lock.py):  base | lockN (ladder rungs x N, trail 72%) | cut (adaptive loser cut) | lockN+cut.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
warnings.filterwarnings("ignore")

INSTRUMENTS = ("NQ", "ES")
LADDER = ((100, 0), (200, 75), (300, 150), (400, 250), (600, 420))
VARIANTS = {
    "base": {},
    "lock3": {"profit_lock_tiers": LADDER, "profit_lock_trail_frac": 0.72, "profit_lock_scale": 3.0},
    "lock6": {"profit_lock_tiers": LADDER, "profit_lock_trail_frac": 0.72, "profit_lock_scale": 6.0},
    "cut": {"loss_cut_frac": 0.8},
    "lock6cut": {"profit_lock_tiers": LADDER, "profit_lock_trail_frac": 0.72, "profit_lock_scale": 6.0, "loss_cut_frac": 0.8},
}


def cmd_trades(a) -> None:
    import bundle_research as br
    from app.bots import runner
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    frames = {i: runner.load_history(i) for i in INSTRUMENTS}
    files = sorted((ROOT / "strategies" / "python").glob("*.py"))
    for f in files:
        for inst in INSTRUMENTS:
            for vn, ov in VARIANTS.items():
                out = cache / f"{f.stem}+{vn}__{inst}.pkl"
                if out.exists():
                    continue
                t0 = time.time()
                try:
                    tr = br.run_trades(f, inst, frames[inst], risk_overrides=dict(ov) or None)
                except Exception as exc:  # noqa: BLE001 -- a strategy that cannot run on an instrument is a result, not a crash
                    print(f"{f.stem} {inst} {vn}: skipped ({type(exc).__name__}: {exc})", flush=True)
                    continue
                pickle.dump(tr, out.open("wb"))
                print(f"{f.stem} {inst} {vn}: {len(tr)} trades in {time.time() - t0:.1f}s", flush=True)


# ------------------------------------------------------------------------------------------------------------------------------- books
def _fomc_days() -> set:
    import pandas as pd
    from app.data.event_calendar import FOMC_DECISION_DATES
    return {pd.Timestamp(d).normalize() for d in FOMC_DECISION_DATES}


def _base_leg(name: str) -> str:
    stem, inst = name.split("|")
    return stem.split("+")[0] + "|" + inst


def _greedy(key, sleeves, mults, max_legs, gov, min_gain, S):
    """Forward selection on TRAIN only (scripts/run_objective_scores.greedy) with one variant per underlying strategy."""
    chosen, cur, path = [], -1e9, []
    while len(chosen) < max_legs:
        best = None
        used = {_base_leg(c[0]) for c in chosen}
        for n in sleeves:
            if _base_leg(n) in used:
                continue
            for m in mults:
                legs = [(c[0], S[c[0]], c[1], i) for i, c in enumerate(chosen)] + [(n, S[n], m, len(chosen))]
                v = ros.selection_score(key, ros.bundle(legs, daily_cap=ros.CAPS[key], max_open=ros.MAX_OPEN[key]), gov, "train")
                if best is None or v > best[0]:
                    best = (v, n, m)
        if best is None or best[0] < cur + min_gain:
            break
        cur = best[0]
        chosen.append((best[1], best[2]))
        path.append((list(chosen), cur))
        print(f"  [{key}] + {best[1]} x{best[2]} -> train {best[0]:.2f}", flush=True)
    return path


def cmd_books(a) -> None:
    global ros
    import run_objective_scores as ros
    import pandas as pd
    cache, out_dir = Path(a.cache), Path(a.out)
    raw = ros.load(cache)
    fomc = _fomc_days()
    S = {}
    for k, v in raw.items():
        v1 = ros.at_1x(v)
        S[k] = v1
        stem, inst = k.split("|")
        # FOMC overlay: no new entries on a decision day (the statement lands at 14:00 ET; the spike is the risk, not the edge)
        keep = ~v1["entry"].dt.normalize().isin(fomc)
        if (~keep).any():
            S[f"{stem}+nofomc|{inst}"] = v1[keep].reset_index(drop=True)
    ok = {k: v for k, v in S.items() if len(ros.cut(v, "tv")) >= ros.MIN_N and ros.pf(ros.cut(v, "tv")) >= ros.MIN_PF}
    print(f"{len(ok)} of {len(S)} sleeve variants pass PF>={ros.MIN_PF}, n>={ros.MIN_N} on train+val", flush=True)
    plan = {"A": dict(mults=(1.0, 2.0, 3.0, 4.0), max_legs=4, min_gain=0.5), "B": dict(mults=(0.5, 1.0), max_legs=4, min_gain=0.25),
            "NET": dict(mults=(0.5, 1.0, 2.0), max_legs=6, min_gain=0.25)}
    res = {"screen": sorted(ok), "books": {}}
    only = set(a.only.split(",")) if getattr(a, "only", "") else set(plan)
    for key, p in plan.items():
        if key not in only:
            continue
        gov = ros.gov_for(key)
        path = _greedy(key, ok, p["mults"], p["max_legs"], gov, p["min_gain"], S)
        cands = {f"greedy-{len(c)}": c for c, _ in path}
        old = [(n.replace("|", "+base|"), m) for n, m in ros.OLD_PRESETS[key]]
        cands["previous preset"] = [x for x in old if x[0] in S]
        rows = []
        for label, chosen in cands.items():
            legs = [(n, S[n], m, i) for i, (n, m) in enumerate(chosen)]
            book = ros.bundle(legs, daily_cap=ros.CAPS[key], max_open=ros.MAX_OPEN[key])
            tr, va = ros.selection_score(key, book, gov, "train"), ros.selection_score(key, book, gov, "val")
            rows.append({"label": label, "legs": chosen, "train": tr, "val": va, "robust": min(tr, va)})
        rows.sort(key=lambda r: -r["robust"])
        finals = []
        for r in rows:
            legs = [(n, S[n], m, i) for i, (n, m) in enumerate(r["legs"])]
            book = ros.bundle(legs, daily_cap=ros.CAPS[key], max_open=ros.MAX_OPEN[key])
            finals.append({**r, "n_trades": int(len(book)), "card": ros.full_card(key, book, gov)})
        res["books"][key] = {"chosen": rows[0], "finals": finals}
        print(key, "CHOSEN", rows[0]["label"], rows[0]["legs"], flush=True)
        (out_dir / "bot_books.json").write_text(json.dumps(res, default=str, indent=1))


# ------------------------------------------------------------------------------------------------ B under the owner's payout rule + paired overlay tests
SHIPPED = {
    "A": [("OpenDrive_NQ_5m_v1|NQ", 1.0), ("IndRule_NQ_15m_v1|NQ", 3.0), ("ContextDriveLong_NQ_1m_v2|NQ", 1.0)],
    "B": [("IndRule_NQ_15m_v1|NQ", 1.0), ("ContextDriveLong_NQ_1m_v2|NQ", 1.0)],
    "NET": [("ContextDriveLong_NQ_1m_v2|ES", 2.0), ("IndRule_NQ_15m_v1|NQ", 2.0), ("OpenDrive_NQ_5m_v1|NQ", 2.0),
            ("LiquiditySweepReclaim_NQ_5m_v1|NQ", 2.0), ("ContextDriveLong_NQ_1m_v2|NQ", 2.0), ("IndRuleA_NQ_30m_v1|ES", 2.0)],
}


def _with_variant(legs, variant):
    return [(n.replace("|", f"+{variant}|"), m) for n, m in legs]


def _card(key, d, gov, ros, sc):
    out = {}
    for sp in ("train", "val", "test"):
        x = ros.cut(d, sp)
        if key == "A":
            r = sc.score_pass(d, ros.W(sp), gov=gov) if len(x) else {}
        elif key == "B":
            from app.bots.risk_governor import AccountRulesLite
            from app.prop.payout_rule import objective_b_rules
            from app.prop.presets import get_preset
            r = sc.score_payout(d, ros.W(sp), gov=gov, prop_rules=objective_b_rules(get_preset("lucid_50k").to_prop_rules()),
                                lite=AccountRulesLite.lucid_50k().with_winning_days_payout()) if len(x) else {}
        else:
            r = sc.score_net(x, gov=gov) if len(x) else {}
            r.pop("curve", None)
        r["n_trades"] = int(len(x))
        out[sp] = r
    return out


def cmd_paired(a) -> None:
    """(1) Objective B re-selected under the owner's rule (5 days of $250, wins > losses) from the BASE sleeves, train-picked, val-confirmed.
    (2) For every objective's shipped book and the B pick: ONE paired comparison per overlay (lock3, lock6, cut, lock6cut, nofomc) -- six overlays on
    six books is 30 looks, so a difference counts only when train AND validation agree in sign."""
    global ros
    import run_objective_scores as ros
    from app.prop import objective_scorecard as sc
    cache, out_dir = Path(a.cache), Path(a.out)
    raw = ros.load(cache)
    S = {k: ros.at_1x(v) for k, v in raw.items()}
    fomc = _fomc_days()
    for k in list(S):
        stem, inst = k.split("|")
        v = S[k]
        keep = ~v["entry"].dt.normalize().isin(fomc)
        S[f"{stem}+nofomc|{inst}"] = v[keep].reset_index(drop=True)
    base = {k: v for k, v in S.items() if "+base|" in k and len(ros.cut(v, "tv")) >= ros.MIN_N and ros.pf(ros.cut(v, "tv")) >= ros.MIN_PF}
    gov_b = ros.gov_for("B")

    def book(key, legs):
        return ros.bundle([(n, S[n], m, i) for i, (n, m) in enumerate(legs)], daily_cap=ros.CAPS[key], max_open=ros.MAX_OPEN[key])

    def b_score(d, split):
        r = _card("B", d, gov_b, ros, sc)[split]
        return (r.get("p_paid", 0.0) - 0.5 * r.get("bust", 0.0)) if r.get("n_starts") else -1e9

    chosen, cur, path = [], -1e9, []
    while len(chosen) < 5:
        used = {_base_leg(c[0]) for c in chosen}
        best = None
        for n in base:
            if _base_leg(n) in used:
                continue
            for m in (0.25, 0.5, 1.0):
                v = b_score(book("B", chosen + [(n, m)]), "train")
                if best is None or v > best[0]:
                    best = (v, n, m)
        if best is None or best[0] < cur + 0.25:
            break
        cur = best[0]
        chosen.append((best[1], best[2]))
        path.append(list(chosen))
        print(f"  [B/new rule] + {best[1]} x{best[2]} -> train {best[0]:.2f}", flush=True)
    res = {"b_path": [], "paired": {}}
    ship_b = _with_variant(SHIPPED["B"], "base")
    cands = {"shipped": ship_b, **{f"greedy-{len(p)}": p for p in path}}
    for lbl, legs in cands.items():
        res["b_path"].append({"label": lbl, "legs": legs, "card": _card("B", book("B", legs), gov_b, ros, sc)})
        print("B", lbl, {sp: (c.get("p_paid"), c.get("bust"), c.get("median_days_to_pay")) for sp, c in res["b_path"][-1]["card"].items()}, flush=True)
    books = {"A": ("A", _with_variant(SHIPPED["A"], "base")), "B": ("B", ship_b), "NET": ("NET", _with_variant(SHIPPED["NET"], "base"))}
    if path:
        books["B-greedy"] = ("B", path[-1])
    for name, (key, legs) in books.items():
        gov = ros.gov_for(key)
        res["paired"][name] = {}
        for var in ("base", "lock3", "lock6", "cut", "lock6cut", "nofomc"):
            if var == "base":
                vl = legs
            elif var == "nofomc":
                vl = [(n.replace("+base|", "+base+nofomc|"), m) for n, m in legs]
            else:
                vl = [(n.replace("+base|", f"+{var}|"), m) for n, m in legs]
            res["paired"][name][var] = _card(key, book(key, vl), gov, ros, sc)
            print(name, var, flush=True)
        (out_dir / "bot_paired.json").write_text(json.dumps(res, default=str, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["trades", "books", "paired"])
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", default=".")
    ap.add_argument("--only", default="", help="comma list of objectives (A,B,NET)")
    a = ap.parse_args()
    {"trades": cmd_trades, "books": cmd_books, "paired": cmd_paired}[a.cmd](a)
