"""T58 hypothesis lab: shared plumbing for testing the Strategy Testing Plan hypotheses through the REAL engine.

Everything here sits on the same pieces the app uses:
  * trades      come from ``app.backtest.engine.run_backtest`` (the bar engine, prop sizing, costs, slippage) via scripts/bundle_research.run_trades
  * verdicts    come from ``app.prop.simulator.simulate_account`` with the Lucid 50K preset (trailing floor, daily limit, consistency, payouts)
  * governors   are ``app.bots.risk_governor`` (the same code the Trading Bots run)

Scoring conventions (match the plan, section 4):
  1x size   every sleeve is scaled so its AVERAGE LOSS is $500 (1% of the 50K account); "k x" multiplies that.
  A score   P(pass the evaluation within 60 calendar days, no breach); 95% lower bound uses n_eff = window days / 60 independent windows.
  B score   P(pass AND reach a first payout within 365 calendar days); EV after the $172 fee counts one purchase per attempt.
  NET       net profit shrunk by drawdown and a thin sample: net / max-drawdown x n / (n + 30).
  Splits    train 2019-10 .. 2023-12, validate 2024, test 2025-01 .. 2026-11 (locked until a candidate is final).
"""
from __future__ import annotations

import math
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
warnings.filterwarnings("ignore")

import bundle_research as br  # noqa: E402

FEE = 172.0
AVG_LOSS_1X = 500.0
SPLITS = {"train": ("2019-10-01", "2024-01-01"), "val": ("2024-01-01", "2025-01-01"), "test": ("2025-01-01", "2027-01-01"),
          "tv": ("2019-10-01", "2025-01-01"), "oos": ("2024-01-01", "2027-01-01"), "all": ("2019-10-01", "2027-01-01")}
H_A, H_B = 60, 365


def rules(preset: str = "lucid_50k"):
    from app.prop.presets import get_preset
    return get_preset(preset).to_prop_rules()


# ------------------------------------------------------------------------------------------------------------------ trade frames
def frame(trades: list[dict] | pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(trades) if not isinstance(trades, pd.DataFrame) else trades.copy()
    if df.empty:
        return df
    df = df.sort_values("entry").reset_index(drop=True)
    if "inst" not in df:
        df["inst"] = "NQ"
    return df


def avg_loss(df: pd.DataFrame) -> float:
    neg = df.loc[df["pnl"] < 0, "pnl"]
    return float(-neg.mean()) if len(neg) else 0.0


def at_1x(df: pd.DataFrame, k: float = 1.0) -> pd.DataFrame:
    """Scale so the average loss is k x $500 (the plan's sizing convention)."""
    d = frame(df)
    if d.empty:
        return d
    al = avg_loss(d)
    m = AVG_LOSS_1X * k / al if al > 0 else 0.0
    d = d.copy()
    d["pnl"] = d["pnl"] * m
    if "risk_usd" in d:
        d["risk_usd"] = d["risk_usd"] * m
    d["mult"] = m
    return d


def window(df: pd.DataFrame, split: str) -> pd.DataFrame:
    a, b = SPLITS[split]
    return df[(df["entry"] >= pd.Timestamp(a)) & (df["entry"] < pd.Timestamp(b))].reset_index(drop=True)


def trade_hour(df: pd.DataFrame) -> pd.Series:
    return df["entry"].dt.hour


# ---------------------------------------------------------------------------------------------------------------------- stats
def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    return br._wilson(k, n, z)


def trade_summary(df: pd.DataFrame) -> dict:
    if df is None or len(df) == 0:
        return {"n": 0}
    p = df["pnl"].to_numpy(float)
    al = avg_loss(df) or 1.0
    r = p / al
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    d = df.sort_values("exit")
    eq = np.cumsum(d["pnl"].to_numpy(float))
    dd = float((np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max()) if len(eq) else 0.0
    span_w = max((df["entry"].max() - df["entry"].min()).days / 7.0, 1.0)
    mon = df.assign(m=df["exit"].dt.to_period("M")).groupby("m")["pnl"].sum()
    # worst losing streak
    streak = best = 0
    for x in d["pnl"].to_numpy(float):
        streak = streak + 1 if x < 0 else 0
        best = max(best, streak)
    return {"n": int(len(p)), "per_week": round(len(p) / span_w, 2), "win_pct": round(100 * float((p > 0).mean()), 1),
            "avg_R": round(float(r.mean()), 3), "pf": round(float(gw / gl), 2) if gl > 0 else float("inf"),
            "net": round(float(p.sum()), 0), "max_dd": round(dd, 0), "net_dd": round(float(p.sum() / dd), 1) if dd > 0 else None,
            "pos_months_pct": round(100 * float((mon > 0).mean()), 0) if len(mon) else 0.0, "worst_streak": int(best)}


def yearly(df: pd.DataFrame) -> dict:
    if len(df) == 0:
        return {}
    g = df.groupby(df["entry"].dt.year)["pnl"]
    return {int(y): round(float(v), 0) for y, v in g.sum().items()}


def years_positive(df: pd.DataFrame, haircut: float = 0.0) -> tuple[int, int]:
    """(years with positive net, years traded) after taking ``haircut`` of the average per-trade edge off every trade."""
    if len(df) == 0:
        return 0, 0
    mu = float(df["pnl"].mean())
    d = df.assign(p=df["pnl"] - haircut * mu)
    g = d.groupby(d["entry"].dt.year)["p"].sum()
    g = g[d.groupby(d["entry"].dt.year).size() >= 5]
    return int((g > 0).sum()), int(len(g))


def net_score(df: pd.DataFrame) -> float:
    s = trade_summary(df)
    if not s.get("n") or not s.get("max_dd"):
        return 0.0
    return float(s["net"] / s["max_dd"] * s["n"] / (s["n"] + 30.0))


def daily_pnl(df: pd.DataFrame) -> pd.Series:
    if len(df) == 0:
        return pd.Series(dtype=float)
    return df.groupby(df["exit"].dt.normalize())["pnl"].sum()


def daily_corr(a: pd.DataFrame, b: pd.DataFrame) -> float:
    x, y = daily_pnl(a), daily_pnl(b)
    if len(x) < 20 or len(y) < 20:
        return float("nan")
    j = pd.concat([x, y], axis=1).fillna(0.0)
    return float(j.corr().iloc[0, 1])


# ------------------------------------------------------------------------------------------------------------------ evaluation
def _starts(df, a, b, horizon):
    days = sorted(df["entry"].dt.normalize().unique())
    last = df["exit"].max()
    out = [d for d in days if pd.Timestamp(a) <= d < pd.Timestamp(b) and d + pd.Timedelta(days=horizon) <= last + pd.Timedelta(days=1)]
    return out


def sim_starts(df: pd.DataFrame, split: str, horizon: int, *, stride: int = 2, gov=None, lite=None, prop_rules=None,
               data_end: pd.Timestamp | None = None) -> list[dict]:
    """Start a fresh Lucid evaluation on every ``stride``-th trade day inside ``split``, replay the trade list through the real simulator.
    With ``gov`` (a GovernorConfig) every trade is first re-sized by the bot governor from the evolving account state."""
    from app.prop.simulator import simulate_account
    rl = prop_rules or rules()
    if df is None or len(df) == 0:
        return []
    a, b = SPLITS[split]
    d = df.sort_values("entry").reset_index(drop=True)
    d["day"] = d["entry"].dt.normalize()
    last = data_end if data_end is not None else d["exit"].max()
    days = sorted(d["day"].unique())
    cand = [x for x in days if pd.Timestamp(a) <= x < pd.Timestamp(b)]
    cand = cand[::max(1, stride)]
    entries, exits, pnls, dirs, dayv = d["entry"].tolist(), d["exit"].tolist(), d["pnl"].to_numpy(float), d["dir"].tolist(), d["day"].tolist()
    dvals = d["day"].values
    if gov is not None:
        from app.bots.risk_governor import AccountRulesLite, AccountState, decide_risk
        from app.prop.lifecycle_v2 import V2Rules
        lite = lite or AccountRulesLite.from_v2(V2Rules.lucid_50k())
        base_total = lite.account_size * gov.base_risk_pct / 100.0
    res = []
    for sd in cand:
        end = sd + pd.Timedelta(days=horizon)
        if end > last + pd.Timedelta(days=1):
            continue
        i0 = int(np.searchsorted(dvals, np.datetime64(sd)))
        if gov is None:
            sel = [i for i in range(i0, len(d)) if entries[i] < end]
            o_p, o_d, o_en, o_ex, o_di = pnls[sel].tolist(), [dayv[i].date() for i in sel], [entries[i] for i in sel], [exits[i] for i in sel], [dirs[i] for i in sel]
        else:
            st = AccountState.fresh(lite)
            o_p, o_d, o_en, o_ex, o_di = [], [], [], [], []
            for i in range(i0, len(d)):
                if entries[i] >= end:
                    break
                dd_ = dayv[i]
                st.roll_day(str(dd_.date()))
                if st.phase == "passed":
                    st.to_funded()
                dec = decide_risk(st, gov)
                if not dec.allow:
                    continue
                m = dec.risk_dollars / base_total if base_total else 1.0
                p = float(pnls[i]) * m
                o_p.append(p); o_d.append(dd_.date()); o_en.append(entries[i]); o_ex.append(exits[i]); o_di.append(dirs[i])
                st.update(p, str(dd_.date()))
                if st.phase == "funded":
                    st.take_payout()
        if not o_p:
            res.append({"start": sd, "passed": False, "cal": None, "payout": False, "bust_before_pass": False, "payout_days": None,
                        "payout_365": 0.0, "total_payout": 0.0, "n": 0})
            continue
        r = simulate_account(o_p, o_d, rl, trade_entry_times=o_en, trade_exit_times=o_ex, trade_sides=o_di)
        cal = float(r.calendar_days_to_pass) if (r.passed_evaluation and r.calendar_days_to_pass is not None) else None
        fp, p365 = br._payout_stats(r, sd)
        res.append({"start": sd, "passed": bool(r.passed_evaluation), "cal": cal, "payout": bool(r.reached_first_payout),
                    "bust_before_pass": bool(r.failed and not r.passed_evaluation), "payout_days": fp, "payout_365": p365,
                    "total_payout": float(r.total_payout_amount), "n": len(o_p), "failed": bool(r.failed)})
    return res


def score_A(df, split="all", **kw) -> dict:
    res = sim_starts(df, split, H_A, **kw)
    n = len(res)
    if n == 0:
        return {"n_starts": 0, "A": 0.0, "A_lo": 0.0, "bust": 0.0}
    a, b = SPLITS[split]
    lo, hi = pd.Timestamp(a), min(pd.Timestamp(b), df["exit"].max())
    n_eff = max(1.0, (hi - lo).days / float(H_A))
    k = sum(1 for x in res if x["passed"] and x["cal"] is not None and x["cal"] <= H_A)
    kb = sum(1 for x in res if x["bust_before_pass"])
    cals = [x["cal"] for x in res if x["cal"] is not None and x["cal"] <= H_A]
    return {"n_starts": n, "n_eff": round(n_eff, 1), "A": round(100 * k / n, 1), "A_lo": round(100 * wilson(k / n * n_eff, n_eff)[0], 1),
            "bust": round(100 * kb / n, 1), "bust_hi": round(100 * wilson(kb / n * n_eff, n_eff)[1], 1),
            "med_days": float(np.median(cals)) if cals else None}


def score_B(df, split="all", **kw) -> dict:
    res = sim_starts(df, split, H_B, **kw)
    n = len(res)
    if n == 0:
        return {"n_starts": 0, "B": 0.0, "B_lo": 0.0, "bust": 0.0, "ev": 0.0}
    a, b = SPLITS[split]
    lo, hi = pd.Timestamp(a), min(pd.Timestamp(b), df["exit"].max())
    n_eff = max(1.0, (hi - lo).days / float(H_B))
    k = sum(1 for x in res if x["payout"] and x["payout_days"] is not None and x["payout_days"] <= H_B)
    kb = sum(1 for x in res if x["bust_before_pass"] or x.get("failed"))
    pay = float(np.mean([x["payout_365"] for x in res]))
    ev = pay - FEE * (1.0 + float(np.mean([x["bust_before_pass"] for x in res])))
    pdays = [x["payout_days"] for x in res if x["payout_days"] is not None and x["payout_days"] <= H_B]
    return {"n_starts": n, "n_eff": round(n_eff, 1), "B": round(100 * k / n, 1), "B_lo": round(100 * wilson(k / n * n_eff, n_eff)[0], 1),
            "bust": round(100 * kb / n, 1), "paid_usd": round(pay, 0), "ev": round(ev, 0), "med_days_to_pay": float(np.median(pdays)) if pdays else None}


def bundle(legs: list[tuple[str, pd.DataFrame, float, int]], *, daily_loss_cap: float | None = None) -> pd.DataFrame:
    """legs = [(name, trades_at_1x, size_multiplier, priority)] -> one account: one open position per instrument (earlier entry keeps the slot),
    optional combined daily realised-loss cap."""
    rows = []
    for (n, t, m, p) in legs:
        f = frame(t)
        for r in f.to_dict("records"):
            rows.append({**r, "pnl": r["pnl"] * m, "leg": n, "prio": p})
    rows.sort(key=lambda r: (r["entry"], r["prio"]))
    out, busy, dpn = [], {}, {}
    for r in rows:
        inst = r.get("inst", "NQ")
        if r["entry"] < busy.get(inst, pd.Timestamp.min):
            continue
        d = (r["entry"] - pd.Timedelta(hours=17)).normalize()
        if daily_loss_cap is not None and dpn.get(d, 0.0) <= -daily_loss_cap:
            continue
        out.append(r)
        busy[inst] = r["exit"]
        dpn[d] = dpn.get(d, 0.0) + r["pnl"]
    return frame(out)


# -------------------------------------------------------------------------------------------------------------- trade library
CACHE = Path("/home/claude/work/cache/trades")


def load_trades(stem: str, inst: str) -> pd.DataFrame:
    p = CACHE / f"{stem}__{inst}.pkl"
    d = frame(pickle.load(p.open("rb")))
    d["inst"] = inst
    return d


# ------------------------------------------------------------------------------------------------------------- regime gate (R2)
def rth_range_table(path: str) -> pd.DataFrame:
    """Prior-session regular-hours (09:30-16:00 ET) range and its causal trailing percentile rank, one row per New York calendar date."""
    d = pd.read_parquet(path, columns=["ts", "high", "low"])
    et = pd.to_datetime(d["ts"], utc=True).dt.tz_convert("America/New_York")
    mod = (et.dt.hour * 60 + et.dt.minute).to_numpy()
    m = (mod >= 570) & (mod < 960) & (et.dt.dayofweek.to_numpy() < 5)
    x = pd.DataFrame({"day": et.dt.normalize().dt.tz_localize(None)[m], "h": d["high"][m], "l": d["low"][m]})
    g = x.groupby("day").agg(h=("h", "max"), l=("l", "min"))
    g["range"] = g["h"] - g["l"]
    # percentile rank of each day's range inside the trailing 250 sessions INCLUDING that day (known at that day's close)
    g["rank"] = g["range"].rolling(250, min_periods=60).apply(lambda w: float((w[:-1] < w[-1]).mean()) if len(w) > 1 else np.nan, raw=True)
    g["prior_rank"] = g["rank"].shift(1)      # what is known BEFORE the day we are deciding on
    return g


def apply_regime_gate(trades: pd.DataFrame, table: pd.DataFrame, floor: float = 1 / 3) -> pd.DataFrame:
    """Drop trades on days whose previous session range sits in the bottom ``floor`` of its trailing year. Days with no rank yet are kept."""
    day = trades["entry"].dt.tz_localize(None).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None) \
        if trades["entry"].dt.tz is None else trades["entry"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    r = day.map(table["prior_rank"])
    keep = r.isna() | (r >= floor)
    return trades[keep.to_numpy()].reset_index(drop=True)


# ------------------------------------------------------------------------------------------------------------------ NET (compounding)
def net_run(df: pd.DataFrame, gov=None, equity0: float = 50_000.0, extra_daily: pd.Series | None = None) -> dict:
    """Net-profit objective on an account with no prop rules: every trade is re-sized by the NET governor from the evolving equity (compounding,
    drawdown throttle), trades booked in exit order. ``extra_daily`` = a daily RETURN series (e.g. the Gate 27 basket) added to the equity path."""
    from app.bots.risk_governor import AccountRulesLite, AccountState, GovernorConfig, decide_risk
    gov = gov or GovernorConfig(objective="NET", base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0, min_risk_dollars=1.0)
    rl = AccountRulesLite.live_account(equity0)
    st = AccountState.fresh(rl)
    d = df.sort_values("exit").reset_index(drop=True)
    pn = d["pnl"].to_numpy(float)
    exits = d["exit"].dt.normalize().tolist()
    base_total = equity0 * gov.base_risk_pct / 100.0
    events = {}
    for i, (x, p) in enumerate(zip(exits, pn)):
        events.setdefault(x, []).append(i)
    days = sorted(set(exits) | (set(extra_daily.index) if extra_daily is not None else set()))
    eq_curve, peak, mdd_pct, mdd_usd = [], equity0, 0.0, 0.0
    n_taken, taken_pnl = 0, []
    for x in days:
        for i in events.get(x, []):
            dec = decide_risk(st, gov)
            if not dec.allow:
                continue
            m = dec.risk_dollars / base_total
            # compounding: base follows equity, so the multiplier already carries equity / start
            st.update(float(pn[i]) * m, str(x.date()))
            n_taken += 1
            taken_pnl.append(float(pn[i]) * m)
        if extra_daily is not None and x in extra_daily.index:
            st.balance += float(extra_daily.loc[x]) * max(st.balance, 0.0)
            st.peak_equity = max(st.peak_equity, st.balance)
        eq_curve.append((x, st.balance))
        peak = max(peak, st.balance)
        mdd_pct = max(mdd_pct, (peak - st.balance) / peak * 100.0 if peak > 0 else 0.0)
        mdd_usd = max(mdd_usd, peak - st.balance)
        if st.balance <= 0:
            break
    yrs = max((days[-1] - days[0]).days / 365.25, 1e-9) if days else 1.0
    end = st.balance
    cagr = ((max(end, 1e-9) / equity0) ** (1 / yrs) - 1) * 100.0
    return {"end": round(end, 0), "net": round(end - equity0, 0), "cagr": round(cagr, 1), "max_dd_pct": round(mdd_pct, 1), "max_dd_usd": round(mdd_usd, 0),
            "calmar": round(cagr / mdd_pct, 2) if mdd_pct > 0 else None, "n": n_taken, "years": round(yrs, 1), "curve": eq_curve}


def greedy_book(sleeves: dict, score_fn, *, mults=(0.5, 1.0, 2.0), max_legs: int = 5, min_gain: float = 0.5, verbose: bool = True, seed_legs=None):
    """Forward selection: add the (sleeve, size multiplier) that most improves ``score_fn(book_df)`` (bigger is better); stop when no addition
    improves it by ``min_gain``. Priority = order of addition (earlier legs keep a contested slot)."""
    chosen = list(seed_legs or [])
    cur = score_fn(bundle([(n, sleeves[n], m, i) for i, (n, m) in enumerate(chosen)])) if chosen else -1e9
    while len(chosen) < max_legs:
        best = None
        for n in sleeves:
            if any(n == c[0] for c in chosen):
                continue
            for m in mults:
                legs = [(c[0], sleeves[c[0]], c[1], i) for i, c in enumerate(chosen)] + [(n, sleeves[n], m, len(chosen))]
                v = score_fn(bundle(legs))
                if best is None or v > best[0]:
                    best = (v, n, m)
        if best is None or best[0] < cur + min_gain:
            break
        cur = best[0]
        chosen.append((best[1], best[2]))
        if verbose:
            print(f"  + {best[1]} x{best[2]}  -> {best[0]:.1f}", flush=True)
    return chosen, cur
