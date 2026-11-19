"""Objective scorecards: the numbers each of the three objectives is judged on, computed from one trade list with the app's own simulators.

    score_pass(trades, ...)      OBJECTIVE A  P(pass within 30 days) primary, 60 days the maximum; median days to pass, breach probability, risk of ruin,
                                              profit-target efficiency.
    score_payout(trades, ...)    OBJECTIVE B  P(first payout inside 365 days, account alive) primary; time to first payout, payout expectancy, survival,
                                              max drawdown, consistency compliance, repeat-payout probability.
    score_net(trades, ...)       OBJECTIVE C  net profit and compounded growth (CAGR) primary; Calmar, expectancy, max drawdown, return on capital,
                                              robustness across calendar-year regimes.

``trades`` is a DataFrame with ``entry`` / ``exit`` timestamps (naive, one clock), ``pnl`` in dollars at 1x and ``dir`` (+1 / -1). Every evaluation start is a
fresh evaluation replayed through ``app.prop.simulator.simulate_account`` (trailing floor, daily limit, consistency, payouts), so a pass or a payout here is
a pass or a payout under the firm's rules, not an approximation. A governor (``app.bots.risk_governor.GovernorConfig``) may re-size every trade from the
evolving account state, which is exactly what the trading bots do.

Honest-odds rules, shared by the three scores:
  * a start counts only when the data covers its whole horizon (no right-censoring in either direction);
  * overlapping starts are not independent, so every interval uses ``n_eff = window days / horizon`` independent windows (Wilson interval);
  * the splits (train / validation / locked test) are chosen by the CALLER; this module never looks at which one it was given.

Pure NumPy / pandas, no I/O, no randomness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from app.objectives import A_MAX_DAYS, A_TARGET_DAYS, B_PAYOUT_HORIZON_DAYS

FEE_DEFAULT = 172.0           # Lucid 50K evaluation fee, dollars per attempt
SIZE_CAP_DEFAULT = 250_000.0  # Objective C: compounding stops growing the position once the account passes this size (index-futures liquidity / slippage)


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion k/n (k and n may be fractional effective counts)."""
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0)) / d
    return max(0.0, c - h), min(1.0, c + h)


def frame(trades) -> pd.DataFrame:
    df = pd.DataFrame(trades) if not isinstance(trades, pd.DataFrame) else trades.copy()
    if df.empty:
        return df
    for c in ("entry", "exit"):
        df[c] = pd.to_datetime(df[c])
        if getattr(df[c].dt, "tz", None) is not None:
            df[c] = df[c].dt.tz_convert("UTC").dt.tz_localize(None)
    if "dir" not in df:
        df["dir"] = 1
    return df.sort_values("entry").reset_index(drop=True)


@dataclass(frozen=True)
class Window:
    start: pd.Timestamp
    end: pd.Timestamp

    @classmethod
    def of(cls, a, b) -> "Window":
        return cls(pd.Timestamp(a), pd.Timestamp(b))


def _payout_stats(r, start, horizon: int) -> tuple[Optional[float], float, int]:
    """(calendar days from ``start`` to the first payout or None, payout dollars inside ``horizon`` days, number of payouts inside ``horizon``)."""
    first, tot, n = None, 0.0, 0
    for ev in getattr(r, "payouts", []) or []:
        try:
            dd = (pd.Timestamp(ev.date) - pd.Timestamp(start)).days
        except Exception:  # noqa: BLE001
            continue
        if first is None:
            first = float(dd)
        if dd <= horizon:
            tot += float(ev.amount)
            n += 1
    return first, tot, n


def _session_dates(ts: pd.Series) -> pd.Series:
    """Naive-UTC timestamps -> the trading day each belongs to (New York day shifted by the 18:00 ET Globex open), as normalised naive dates."""
    ix = pd.DatetimeIndex(ts)
    et = ix.tz_localize("UTC").tz_convert("America/New_York") + pd.Timedelta(hours=6)
    return pd.Series(et.tz_localize(None).normalize(), index=ts.index)


def simulate_starts(df: pd.DataFrame, win: Window, horizon: int, *, stride: int = 2, gov=None, lite=None, prop_rules=None, data_end=None,
                    session_days: bool = False) -> list[dict]:
    """Start a fresh evaluation on every ``stride``-th trading day inside ``win`` and replay the trades through the real simulator.

    With ``gov`` every trade is first re-sized by the bot risk governor from the evolving account state (the same ``decide_risk`` the bots call). A ``w`` column
    in ``df`` is each trade's leg weight: it goes to ``decide_risk`` as the weight, so the caps apply AFTER it exactly as in the bot engine. ``session_days`` groups
    trades by the CME session day (rolls at 18:00 ET) instead of the UTC calendar day, which is the clock the firm's daily limit and trailing floor run on."""
    from app.prop.presets import get_preset
    from app.prop.simulator import simulate_account
    rl = prop_rules or get_preset("lucid_50k").to_prop_rules()
    if df is None or len(df) == 0:
        return []
    d = df.sort_values("entry").reset_index(drop=True)
    d["day"] = _session_dates(d["entry"]) if session_days else d["entry"].dt.normalize()
    ws = d["w"].to_numpy(float) if "w" in d.columns else np.ones(len(d))
    last = pd.Timestamp(data_end) if data_end is not None else d["exit"].max()
    cand = [x for x in sorted(d["day"].unique()) if win.start <= x < win.end][::max(1, stride)]
    entries, exits, pnls, dirs, dayv = d["entry"].tolist(), d["exit"].tolist(), d["pnl"].to_numpy(float), d["dir"].tolist(), d["day"].tolist()
    dvals = d["day"].values
    base_total = 0.0
    if gov is not None:
        from app.bots.risk_governor import AccountRulesLite, AccountState, decide_risk
        from app.prop.lifecycle_v2 import V2Rules
        lite = lite or AccountRulesLite.from_v2(V2Rules.lucid_50k())
        base_total = lite.account_size * gov.base_risk_pct / 100.0
    out = []
    for sd in cand:
        end = sd + pd.Timedelta(days=horizon)
        if end > last + pd.Timedelta(days=1):
            continue                                   # the window is not fully covered by data: not a sample
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
                st.roll_day(str(dayv[i].date()))
                if st.phase == "passed":
                    st.to_funded()
                dec = decide_risk(st, gov, weight=float(ws[i]))
                if not dec.allow:
                    continue
                m = dec.risk_dollars / base_total if base_total else 1.0
                p = float(pnls[i]) * m
                o_p.append(p); o_d.append(dayv[i].date()); o_en.append(entries[i]); o_ex.append(exits[i]); o_di.append(dirs[i])
                st.update(p, str(dayv[i].date()), risk=dec.risk_dollars)
                if st.phase == "funded":
                    st.take_payout()
        if not o_p:
            out.append({"start": sd, "passed": False, "cal": None, "payout": False, "bust_before_pass": False, "failed": False, "payout_days": None,
                        "payout_usd": 0.0, "n_payouts": 0, "n": 0, "best_day_share": None, "breach_day": None})
            continue
        r = simulate_account(o_p, o_d, rl, trade_entry_times=o_en, trade_exit_times=o_ex, trade_sides=o_di)
        cal = float(r.calendar_days_to_pass) if (r.passed_evaluation and r.calendar_days_to_pass is not None) else None
        fp, usd, npay = _payout_stats(r, sd, horizon)
        breach_day = None
        if r.failed and r.failure_day_index is not None:
            ud = sorted(set(o_d))
            if 0 <= int(r.failure_day_index) < len(ud):
                breach_day = float((pd.Timestamp(ud[int(r.failure_day_index)]) - pd.Timestamp(sd)).days)
        prof = float(r.final_balance) - float(rl.account_size) + float(r.total_payout_amount)
        share = (float(r.best_day_profit) / prof) if prof > 0 and r.best_day_profit else None
        out.append({"start": sd, "passed": bool(r.passed_evaluation), "cal": cal, "payout": bool(r.reached_first_payout),
                    "bust_before_pass": bool(r.failed and not r.passed_evaluation), "failed": bool(r.failed), "payout_days": fp, "payout_usd": usd,
                    "n_payouts": npay, "n": len(o_p), "best_day_share": share, "mdd_pct": float(r.max_drawdown_pct_reached),
                    "breach_day": breach_day})
    return out


def _n_eff(df: pd.DataFrame, win: Window, horizon: int) -> float:
    hi = min(win.end, df["exit"].max())
    return max(1.0, (hi - win.start).days / float(horizon))


# ---------------------------------------------------------------------------------------------------------------------- OBJECTIVE A
def score_pass(trades, win: Window, *, target_days: int = A_TARGET_DAYS, max_days: int = A_MAX_DAYS, stride: int = 2, gov=None, lite=None,
               prop_rules=None, session_days: bool = False) -> dict:
    """Objective A. Primary: P(pass within ``target_days``, no breach). The same starts are read again at ``max_days`` (the longest acceptable horizon).

    Returns percentages: p_pass_30 / p_pass_60 (+ 95% lower bounds), median_days_to_pass, breach_30 / breach_60 (a breach before the pass),
    risk_of_ruin (= breach_60), pass_per_breach, target_efficiency (profit target dollars per median day to pass)."""
    from app.prop.presets import get_preset
    df = frame(trades)
    rl = prop_rules or get_preset("lucid_50k").to_prop_rules()
    empty = {"n_starts": 0, "p_pass_30": 0.0, "p_pass_60": 0.0, "p_pass_30_lo": 0.0, "p_pass_60_lo": 0.0, "median_days_to_pass": None, "breach_30": 0.0,
             "breach_60": 0.0, "risk_of_ruin": 0.0, "pass_per_breach": None, "target_efficiency": None}
    if df.empty:
        return empty
    res = simulate_starts(df, win, max_days, stride=stride, gov=gov, lite=lite, prop_rules=rl, session_days=session_days)
    n = len(res)
    if n == 0:
        return empty
    ne = _n_eff(df, win, max_days)
    k30 = sum(1 for x in res if x["passed"] and x["cal"] is not None and x["cal"] <= target_days)
    k60 = sum(1 for x in res if x["passed"] and x["cal"] is not None and x["cal"] <= max_days)
    b60 = sum(1 for x in res if x["bust_before_pass"])
    # breach inside the first 30 days needs the 30-day clock: a start whose breach happens later than day 30 is not a 30-day breach.
    b30 = sum(1 for x in res if x["bust_before_pass"] and x.get("breach_day") is not None and x["breach_day"] <= target_days)
    cals = [x["cal"] for x in res if x["cal"] is not None and x["cal"] <= max_days]
    med = float(np.median(cals)) if cals else None
    ne30 = max(1.0, (min(win.end, df["exit"].max()) - win.start).days / float(target_days))
    return {"n_starts": n, "n_eff_60": round(ne, 1), "p_pass_30": round(100 * k30 / n, 1), "p_pass_60": round(100 * k60 / n, 1),
            "p_pass_30_lo": round(100 * wilson(k30 / n * ne30, ne30)[0], 1), "p_pass_60_lo": round(100 * wilson(k60 / n * ne, ne)[0], 1),
            "median_days_to_pass": med, "breach_30": round(100 * b30 / n, 1), "breach_60": round(100 * b60 / n, 1),
            "breach_60_hi": round(100 * wilson(b60 / n * ne, ne)[1], 1), "risk_of_ruin": round(100 * b60 / n, 1),
            "pass_per_breach": round(k60 / b60, 2) if b60 else None,
            "target_efficiency": round(float(rl.account_size) * float(rl.evaluation_profit_target_pct) / 100.0 / med, 1) if med else None}


# ---------------------------------------------------------------------------------------------------------------------- OBJECTIVE B
def max_drawdown_usd(pnl: np.ndarray, start: float = 0.0) -> float:
    if len(pnl) == 0:
        return 0.0
    eq = start + np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[start], eq]))[1:]
    return float((peak - eq).max())


def losing_streak(pnl: np.ndarray) -> int:
    best = cur = 0
    for p in pnl:
        cur = cur + 1 if p < 0 else 0
        best = max(best, cur)
    return int(best)


def score_payout(trades, win: Window, *, horizon: int = B_PAYOUT_HORIZON_DAYS, fee: float = FEE_DEFAULT, stride: int = 3, gov=None, lite=None,
                 prop_rules=None, consistency_cap: float = 0.40, session_days: bool = False) -> dict:
    """Objective B. Primary: P(first payout within ``horizon`` days, no breach on the way). Also: median days to the first payout, payout expectancy per
    attempt (mean payout dollars inside the horizon less the fee, counting a repurchase after every breach), survival (share of starts never breached),
    max drawdown of the trade stream, the worst losing streak, consistency compliance (share of paid starts whose best day stayed under ``consistency_cap``
    of the profit) and the repeat-payout probability (a second payout given a first)."""
    df = frame(trades)
    empty = {"n_starts": 0, "p_paid": 0.0, "p_paid_lo": 0.0, "bust": 0.0, "survival": 0.0, "paid_usd": 0.0, "ev": 0.0, "median_days_to_pay": None,
             "repeat_payout": None, "consistency_compliance": None, "max_dd_usd": 0.0, "worst_losing_streak": 0}
    if df.empty:
        return empty
    res = simulate_starts(df, win, horizon, stride=stride, gov=gov, lite=lite, prop_rules=prop_rules, session_days=session_days)
    n = len(res)
    if n == 0:
        return empty
    ne = _n_eff(df, win, horizon)
    k = sum(1 for x in res if x["payout"] and x["payout_days"] is not None and x["payout_days"] <= horizon)
    failed = sum(1 for x in res if x["failed"])
    pay = float(np.mean([x["payout_usd"] for x in res]))
    bust_before_pass = float(np.mean([x["bust_before_pass"] for x in res]))
    pdays = [x["payout_days"] for x in res if x["payout_days"] is not None and x["payout_days"] <= horizon]
    paid = [x for x in res if x["payout"]]
    twice = sum(1 for x in paid if x["n_payouts"] >= 2)
    shares = [x["best_day_share"] for x in paid if x.get("best_day_share") is not None]
    pn = df["pnl"].to_numpy(float)
    return {"n_starts": n, "n_eff": round(ne, 1), "p_paid": round(100 * k / n, 1), "p_paid_lo": round(100 * wilson(k / n * ne, ne)[0], 1),
            "bust": round(100 * failed / n, 1), "bust_hi": round(100 * wilson(failed / n * ne, ne)[1], 1), "survival": round(100 * (1 - failed / n), 1),
            "paid_usd": round(pay, 0), "ev": round(pay - fee * (1.0 + bust_before_pass), 0),
            "median_days_to_pay": float(np.median(pdays)) if pdays else None,
            "repeat_payout": round(100 * twice / len(paid), 1) if paid else None,
            "consistency_compliance": round(100 * float(np.mean([s <= consistency_cap for s in shares])), 1) if shares else None,
            "max_dd_usd": round(max_drawdown_usd(pn), 0), "worst_losing_streak": losing_streak(pn)}


# ---------------------------------------------------------------------------------------------------------------------- OBJECTIVE C
def score_net(trades, *, equity0: float = 50_000.0, gov=None, extra_daily: Optional[pd.Series] = None, rank_years: bool = True,
              size_cap: float = SIZE_CAP_DEFAULT) -> dict:
    """Objective C. Primary: net profit and compounded growth (CAGR) on an account with no prop rules. Every trade is re-sized from the evolving equity by the
    NET governor (compounding, drawdown throttle); ``extra_daily`` is a daily RETURN series (a swing book such as Gate 27) added to the equity path.

    Position size is capped once the account reaches ``size_cap`` dollars of sizing equity: compounding a $50K account to millions and still trading
    1% of it per index-futures trade would assume liquidity and slippage that do not exist, so growth beyond the cap is not counted.

    Also: Calmar (CAGR / max drawdown %), expectancy per trade, max drawdown, return on capital (net / starting equity), and robustness across regimes
    (share of calendar years with a positive return and the worst year)."""
    from app.bots.risk_governor import AccountRulesLite, AccountState, GovernorConfig, decide_risk
    gov = gov or GovernorConfig(objective="NET", base_risk_pct=1.0, compounding=True, dd_throttle_tol_pct=10.0, min_risk_dollars=1.0)
    df = frame(trades) if trades is not None and len(trades) else pd.DataFrame(columns=["entry", "exit", "pnl"])
    if df.empty and extra_daily is None:
        return {"n": 0, "net": 0.0, "cagr": 0.0, "max_dd_pct": 0.0, "calmar": None}
    st = AccountState.fresh(AccountRulesLite.live_account(equity0))
    d = df.sort_values("exit").reset_index(drop=True) if not df.empty else df
    pn = d["pnl"].to_numpy(float) if not d.empty else np.array([])
    exits = d["exit"].dt.normalize().tolist() if not d.empty else []
    base_total = equity0 * gov.base_risk_pct / 100.0
    events: dict = {}
    for i, x in enumerate(exits):
        events.setdefault(x, []).append(i)
    days = sorted(set(exits) | (set(extra_daily.index) if extra_daily is not None else set()))
    curve, peak, mdd_pct, mdd_usd, taken = [], equity0, 0.0, 0.0, []
    wn = d["w"].to_numpy(float) if (not d.empty and "w" in d.columns) else None
    for x in days:
        for i in events.get(x, []):
            dec = decide_risk(st, gov, weight=float(wn[i]) if wn is not None else 1.0)
            if not dec.allow:
                continue
            m = min(dec.risk_dollars / base_total, size_cap / equity0)
            p = float(pn[i]) * m
            st.update(p, str(x.date()), risk=m * base_total)
            taken.append(p)
        if extra_daily is not None and x in extra_daily.index:
            st.balance += float(extra_daily.loc[x]) * max(st.balance, 0.0)
            st.peak_equity = max(st.peak_equity, st.balance)
        curve.append((x, st.balance))
        peak = max(peak, st.balance)
        mdd_pct = max(mdd_pct, (peak - st.balance) / peak * 100.0 if peak > 0 else 0.0)
        mdd_usd = max(mdd_usd, peak - st.balance)
        if st.balance <= 0:
            break
    yrs = max((days[-1] - days[0]).days / 365.25, 1e-9) if days else 1.0
    end = st.balance
    cagr = ((max(end, 1e-9) / equity0) ** (1 / yrs) - 1) * 100.0
    out = {"end": round(end, 0), "net": round(end - equity0, 0), "cagr": round(cagr, 1), "max_dd_pct": round(mdd_pct, 1), "max_dd_usd": round(mdd_usd, 0),
           "calmar": round(cagr / mdd_pct, 2) if mdd_pct > 0 else None, "n": len(taken), "years": round(yrs, 1),
           "return_on_capital_pct": round((end - equity0) / equity0 * 100.0, 1),
           "expectancy_usd": round(float(np.mean(taken)), 2) if taken else 0.0}
    if taken:
        t = np.array(taken)
        w, l = t[t > 0].sum(), -t[t < 0].sum()
        out["profit_factor"] = round(float(w / l), 2) if l > 0 else None
        out["win_rate"] = round(float((t > 0).mean() * 100.0), 1)
    if rank_years and curve:
        s = pd.Series({pd.Timestamp(x): b for x, b in curve})
        ye = s.groupby(s.index.year).last()
        prev = pd.concat([pd.Series([equity0]), ye.iloc[:-1]]).to_numpy()
        yr = (ye.to_numpy() / prev - 1.0) * 100.0
        out["yearly_return_pct"] = {int(y): round(float(r), 1) for y, r in zip(ye.index, yr)}
        out["years_positive"] = f"{int((yr > 0).sum())}/{len(yr)}"
        out["worst_year_pct"] = round(float(yr.min()), 1)
    out["curve"] = curve
    return out
