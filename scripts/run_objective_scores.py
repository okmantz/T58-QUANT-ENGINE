"""Score every strategy and every combination against the three objectives, with one rule for honesty:

  * SELECTION uses train + validation only (2019-10 .. 2024-12, "tv"). The locked test (2025-01 .. 2026-11) is read once, for the finished books.
  * Each objective is selected with ITS OWN scorecard and nothing else (app/objectives.py ENGINE DIRECTIVE): A never sees payout numbers, B never sees
    30-day pass odds, C never sees prop-firm pass / payout odds.
  * Every number comes from the real bar-engine trades cached by scripts/run_objective_study.py and the real simulators (app.prop.simulator via
    app.prop.objective_scorecard). Nothing is typed in.

    python scripts/run_objective_scores.py sleeves --cache <dir> --out <dir>      # per-sleeve table, all splits
    python scripts/run_objective_scores.py books   --cache <dir> --out <dir>      # per-objective forward selection on TV, then the locked test
"""
from __future__ import annotations

import argparse
import itertools
import json
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from app.prop import objective_scorecard as sc  # noqa: E402

SPLITS = {"train": ("2019-10-01", "2024-01-01"), "val": ("2024-01-01", "2025-01-01"), "test": ("2025-01-01", "2027-01-01"), "tv": ("2019-10-01", "2025-01-01"),
          "all": ("2019-10-01", "2027-01-01")}
AVG_LOSS_1X = 500.0
MIN_PF, MIN_N = 1.10, 60
CAPS = {"A": 480.0, "B": 360.0, "NET": None}          # combined daily realised-loss cap in dollars (bot config: 40% / 30% of the $1,200 soft limit)
MAX_OPEN = {"A": 2, "B": 2, "NET": 3}


def W(split: str) -> sc.Window:
    return sc.Window.of(*SPLITS[split])


def load(cache: Path) -> dict:
    out = {}
    for p in sorted(cache.glob("*__*.pkl")):
        stem, inst = p.stem.split("__")
        d = sc.frame(pickle.load(p.open("rb")))
        if d.empty:
            continue
        d["inst"] = inst
        out[f"{stem}|{inst}"] = d
    return out


def at_1x(d: pd.DataFrame, k: float = 1.0) -> pd.DataFrame:
    neg = d.loc[d["pnl"] < 0, "pnl"]
    al = float(-neg.mean()) if len(neg) else 0.0
    m = AVG_LOSS_1X * k / al if al > 0 else 0.0
    out = d.copy()
    out["pnl"] = out["pnl"] * m
    return out


def cut(d: pd.DataFrame, split: str) -> pd.DataFrame:
    a, b = SPLITS[split]
    return d[(d["entry"] >= pd.Timestamp(a)) & (d["entry"] < pd.Timestamp(b))].reset_index(drop=True)


def pf(d: pd.DataFrame) -> float:
    p = d["pnl"].to_numpy(float)
    gl = -p[p < 0].sum()
    return float(p[p > 0].sum() / gl) if gl > 0 else float("inf")


def bundle(legs, *, daily_cap=None, max_open: int = 99, as_weight: bool = False) -> pd.DataFrame:
    """legs = [(name, trades_at_1x, multiplier, priority)] -> one account. Rules, identical to the bots' arbiter: one position per instrument (the earlier entry
    keeps the slot), at most ``max_open`` positions at once account-wide, and a combined daily realised-loss cap that blocks NEW entries.

    The cap reads REALISED P&L only: a trade counts toward its day once it has closed before the new entry (until 2026-11-19 it counted the moment it was
    entered, so a still-open loser could block, and a still-open winner unblock, a later entry: lookahead).

    ``as_weight`` keeps each trade's 1x P&L and puts the leg multiplier in a ``w`` column instead of multiplying it in, so the scorer hands it to the risk
    governor as the leg weight BEFORE the caps, exactly as the bot engine does (``decide_risk(..., weight=leg.weight)``)."""
    rows = []
    for (n, t, m, p) in legs:
        for r in t.to_dict("records"):
            rows.append({**r, "pnl": r["pnl"] * m, "w": float(m), "leg": n, "prio": p})
    rows.sort(key=lambda r: (r["entry"], r["prio"]))
    out, busy, dpn, live, unreal = [], {}, {}, [], []
    for r in rows:
        live = [e for e in live if e > r["entry"]]
        still = []
        for (x, dd, pn) in unreal:                      # book the trades that have closed by this entry
            if x <= r["entry"]:
                dpn[dd] = dpn.get(dd, 0.0) + pn
            else:
                still.append((x, dd, pn))
        unreal = still
        if r["entry"] < busy.get(r["inst"], pd.Timestamp.min) or len(live) >= max_open:
            continue
        day = (r["entry"] - pd.Timedelta(hours=17)).normalize()
        if daily_cap is not None and dpn.get(day, 0.0) <= -daily_cap:
            continue
        out.append(r)
        busy[r["inst"]] = r["exit"]
        live.append(r["exit"])
        unreal.append((r["exit"], day, r["pnl"]))
    if not out:
        return pd.DataFrame(columns=["entry", "exit", "pnl", "dir"])
    df = sc.frame(out)
    if as_weight:
        df["pnl"] = df["pnl"] / df["w"].where(df["w"] > 0, 1.0)
    else:
        df = df.drop(columns=["w"])
    return df


# ------------------------------------------------------------------------------------------------------------- per-objective scores
def gov_for(key: str):
    from app.bots.presets import preset_configs
    cfg = next(c for c in preset_configs() if c.governor.get("objective") == key)
    return cfg.governor_cfg()


def selection_score(key: str, d: pd.DataFrame, gov=None, split: str = "train") -> float:
    """The ONE number each objective maximises while building a book. Uses that objective's own metrics, on ``split`` (train while building; val to confirm)."""
    if d is None or len(d) < MIN_N:
        return -1e9
    if key == "A":
        r = sc.score_pass(d, W(split), gov=gov)
        # primary: P(pass <= 30 d); the 60-day maximum and breach odds are the stated secondary priorities
        return r["p_pass_30_lo"] + 0.35 * r["p_pass_60_lo"] - 0.35 * r["breach_60"]
    if key == "B":
        r = sc.score_payout(d, W(split), gov=gov)
        # 365-day starts leave n_eff of only ~4 windows in train, so the Wilson bounds are too wide to rank books: rank on the point estimates
        # (primary P(payout), breach as the penalty) and print the intervals in the report.
        return r["p_paid"] - 0.5 * r["bust"] if r["n_starts"] else -1e9
    r = sc.score_net(cut(d, split), gov=gov, rank_years=True)
    if r["n"] < (100 if split == "train" else 20) or r.get("max_dd_pct", 0) > 30.0 or int(r.get("years_positive", "0/1").split("/")[0]) < 0.7 * int(r.get("years_positive", "0/1").split("/")[1]):
        return -1e9
    return float(r["cagr"])


def greedy(key: str, sleeves: dict, mults, max_legs: int, gov, min_gain: float):
    """Forward selection on the TRAIN split only. Returns the whole path (every prefix is a candidate book) so validation can pick how far to go."""
    chosen, cur, path = [], -1e9, []
    while len(chosen) < max_legs:
        best = None
        for n in sleeves:
            if any(n == c[0] for c in chosen):
                continue
            for m in mults:
                legs = [(c[0], sleeves[c[0]], c[1], i) for i, c in enumerate(chosen)] + [(n, sleeves[n], m, len(chosen))]
                v = selection_score(key, bundle(legs, daily_cap=CAPS[key], max_open=MAX_OPEN[key]), gov, "train")
                if best is None or v > best[0]:
                    best = (v, n, m)
        if best is None or best[0] < cur + min_gain:
            break
        cur = best[0]
        chosen.append((best[1], best[2]))
        path.append((list(chosen), cur))
        print(f"  [{key}] + {best[1]} x{best[2]} -> train {best[0]:.2f}", flush=True)
    return path


def full_card(key: str, d: pd.DataFrame, gov) -> dict:
    out = {}
    for sp in ("train", "val", "test"):
        x = cut(d, sp)
        # A and B start fresh evaluations inside the window but replay the FULL trade list after each start, so a start late in the window still sees its
        # whole horizon; only Objective C (one continuous account) is scored on the window's own trades.
        if key == "A":
            out[sp] = sc.score_pass(d, W(sp), gov=gov) if len(x) else {}
        elif key == "B":
            out[sp] = sc.score_payout(d, W(sp), gov=gov) if len(x) else {}
        else:
            r = sc.score_net(x, gov=gov) if len(x) else {}
            r.pop("curve", None)
            out[sp] = r
        out[sp]["n_trades"] = int(len(x))
    return out


# --------------------------------------------------------------------------------------------------------------------------- commands
def cmd_sleeves(a) -> None:
    S = load(Path(a.cache))
    rows = []
    for name, d in S.items():
        row = {"sleeve": name, "n": len(d), "pf_all": round(pf(d), 2), "net_all_raw": round(float(d["pnl"].sum()), 0)}
        for sp in ("train", "val", "test"):
            x = cut(d, sp)
            row[f"n_{sp}"], row[f"pf_{sp}"] = len(x), round(pf(x), 2) if len(x) else None
        keep = len(cut(d, "tv")) >= MIN_N and pf(cut(d, "tv")) >= 1.0
        row["scored"] = bool(keep)
        if keep:
            for k in (1.0, 2.0, 3.0):
                d1 = at_1x(d, k)
                row[f"A_{k:g}x"] = {sp: sc.score_pass(d1, W(sp)) for sp in ("train", "val", "test")}
            for k in (0.5, 1.0):
                d1 = at_1x(d, k)
                row[f"B_{k:g}x"] = {sp: sc.score_payout(d1, W(sp)) for sp in ("train", "val", "test")}
            row["NET_1pct"] = {}
            for sp in ("train", "val", "test"):
                r = sc.score_net(cut(at_1x(d), sp))
                r.pop("curve", None)
                row["NET_1pct"][sp] = r
        rows.append(row)
        print(name, row["n"], row["pf_all"], flush=True)
    Path(a.out, "sleeves.json").write_text(json.dumps(rows, default=str, indent=1))


OLD_PRESETS = {      # the books that shipped before this study (strategies/ names mapped to the new convention)
    "A": [("OpenDrive_NQ_5m_v1|NQ", 1.0), ("IndRule_NQ_15m_v1|NQ", 3.0), ("ContextDriveLong_NQ_1m_v2|NQ", 1.0)],
    "B": [("IndRule_NQ_15m_v1|NQ", 1.0), ("ContextDriveLong_NQ_1m_v2|NQ", 1.0)],
    "NET": [("IndRule_NQ_15m_v1|NQ", 1.0), ("ContextDriveLong_NQ_1m_v2|NQ", 1.0)],
}


def cmd_books(a) -> None:
    S = {k: at_1x(v) for k, v in load(Path(a.cache)).items()}
    ok = {k: v for k, v in S.items() if len(cut(v, "tv")) >= MIN_N and pf(cut(v, "tv")) >= MIN_PF}
    print(f"{len(ok)} sleeves pass the PF>={MIN_PF}, n>={MIN_N} screen on train+val:", ", ".join(sorted(ok)), flush=True)
    out = {"screen": sorted(ok), "books": {}, "candidates": {}}
    plan = {"A": dict(mults=(1.0, 2.0, 3.0, 4.0), max_legs=4, min_gain=0.5), "B": dict(mults=(0.5, 1.0), max_legs=4, min_gain=0.25),
            "NET": dict(mults=(0.5, 1.0, 2.0), max_legs=6, min_gain=0.25)}
    for key, p in plan.items():
        gov = gov_for(key)
        path = greedy(key, ok, p["mults"], p["max_legs"], gov, p["min_gain"])
        cands = {f"greedy-{len(c)}": c for c, _ in path}
        cands["previous preset"] = [x for x in OLD_PRESETS[key] if x[0] in S]
        for n in ok:
            for m in p["mults"]:
                cands[f"single {n} x{m:g}"] = [(n, m)]
        rows = []
        for label, chosen in cands.items():
            legs = [(n, S[n], m, i) for i, (n, m) in enumerate(chosen)]
            book = bundle(legs, daily_cap=CAPS[key], max_open=MAX_OPEN[key])
            tr, va = selection_score(key, book, gov, "train"), selection_score(key, book, gov, "val")
            rows.append({"label": label, "legs": chosen, "train": tr, "val": va, "robust": min(tr, va)})
        rows.sort(key=lambda r: -r["robust"])
        out["candidates"][key] = rows
        print(f"  [{key}] top by min(train, val):", [(r["label"], round(r["robust"], 1)) for r in rows[:4]], flush=True)
        keep = rows[:5] + [r for r in rows if r["label"] == "previous preset"] + [r for r in rows if r["label"].startswith("greedy")]
        seen, finals = set(), []
        for r in keep:
            if r["label"] in seen:
                continue
            seen.add(r["label"])
            legs = [(n, S[n], m, i) for i, (n, m) in enumerate(r["legs"])]
            book = bundle(legs, daily_cap=CAPS[key], max_open=MAX_OPEN[key])
            finals.append({**r, "n_trades": int(len(book)), "card": full_card(key, book, gov),
                           "card_flat": full_card(key, book, None) if key != "NET" else None})
        out["books"][key] = {"chosen": rows[0], "finals": finals}
        print(key, "CHOSEN", rows[0]["label"], rows[0]["legs"], flush=True)
    Path(a.out, "books.json").write_text(json.dumps(out, default=str, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sleeves", "books"])
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    {"sleeves": cmd_sleeves, "books": cmd_books}[a.cmd](a)
