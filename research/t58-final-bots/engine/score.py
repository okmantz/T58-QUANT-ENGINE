"""Objective scoring on the firm engine (T58 final bots). Metric definitions: research/00_recon.md section 4.

eval_block():   rolling evaluation starts (every session day of the window whose horizon fits inside it): P(pass <= H), median days to
                pass, bust (breach before pass within H), Wilson interval on n_eff = window days / H (overlapping starts are not independent).
funded_block(): rolling fresh funded starts: P(first payout <= H), median days to first payout, funded bust, consistency blocks.
life_block():   path-wise lifecycle from each start for L days: eval -> (breach: reset $120, start again next session) -> funded -> payouts.
                EV = 0.9 x payouts - first fee - resets. Same path, Methodology 4.4.
chain():        one continuous replay of the whole window (accounts in sequence, reset on breach): daily P&L -> Sharpe, Sortino, max DD,
                worst day; booked trades -> PF, expectancy R, trades a month.
"""
from __future__ import annotations
import sys, math
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import firm

D1 = np.timedelta64(1, "D")
STALL = 30     # a live account that could not size one micro for 30 calendar days is abandoned and reset (chain and lifecycle only)


def wilson(k, n, z=1.96):
    if n <= 0: return (float("nan"),) * 2
    ph = k / n; den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den; h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def starts(book, a, b, H):
    """Session days in [a, b) that have trading data and whose H-day horizon ends by b."""
    a, b = np.datetime64(a, "D"), np.datetime64(b, "D")
    d = np.unique(book["day"])
    return d[(d >= a) & (d + np.timedelta64(H, "D") <= b)]


def _pol(policy, book):
    policy.w = book["w"]
    if hasattr(policy, "book"):
        policy.book = book
    return policy


def eval_block(book, policy, plan, a, b, H=30, stride=1):
    pol = _pol(policy, book); S = starts(book, a, b, H)[::stride]
    pd_, br = [], 0
    for s in S:
        o = firm.run(book, s, H, plan, pol)
        if o["pass_day"] is not None: pd_.append(o["pass_day"] + 1)
        elif o["breach_day"] is not None: br += 1
    n = len(S); k = len(pd_)
    neff = max((np.datetime64(b, "D") - np.datetime64(a, "D")) / D1 / H, 1.0)
    lo, hi = wilson(k / n * neff, neff) if n else (np.nan, np.nan)
    return dict(n_starts=n, p_pass=k / n if n else np.nan, pass_lo=lo, pass_hi=hi, med_days_pass=float(np.median(pd_)) if pd_ else np.nan,
                bust=br / n if n else np.nan)


def funded_block(book, policy, plan, a, b, H=30, stride=1):
    pol = _pol(policy, book); S = starts(book, a, b, H)[::stride]
    fd, br, cb, el = [], 0, 0, 0
    for s in S:
        o = firm.run(book, s, H, plan, pol, phase="funded")
        if o["payouts"]: fd.append(o["payouts"][0][0] + 1)
        elif o["breach_day"] is not None: br += 1
        cb += o["cons_block"]; el += o["elig_days"]
    n = len(S); k = len(fd)
    neff = max((np.datetime64(b, "D") - np.datetime64(a, "D")) / D1 / H, 1.0)
    lo, hi = wilson(k / n * neff, neff) if n else (np.nan, np.nan)
    return dict(p_payout=k / n if n else np.nan, payout_lo=lo, med_days_payout=float(np.median(fd)) if fd else np.nan,
                fund_bust=br / n if n else np.nan, cons_blocks_per30=cb / n if n else np.nan,
                cons_block_rate=cb / el if el else 0.0)


def life_block(book, policy, plan, a, b, L=90, stride=1):
    """Lifecycle over L calendar days from each start (unlimited resets). Returns EV and payout counts."""
    pol = _pol(policy, book); S = starts(book, a, b, L)[::stride]
    ev, npay, first_pay = [], [], []
    for s in S:
        t, end, fees, pays, fp = np.datetime64(s, "D"), np.datetime64(s, "D") + np.timedelta64(L, "D"), plan.fee, [], None
        while t < end:
            o = firm.run(book, t, int((end - t) / D1), plan, pol, stop_at_pass=False, stall=STALL)
            for d, amt in o["payouts"]:
                pays.append(amt)
                if fp is None: fp = int((t - np.datetime64(s, "D")) / D1) + d + 1
            bd = next((x for x in (o["breach_day"], o["fund_breach_day"], o["stall_day"]) if x is not None), None)
            if bd is None: break
            t = t + np.timedelta64(bd + 1, "D")
            if t < end: fees += plan.reset
        ev.append(plan.split * sum(pays) - fees); npay.append(len(pays)); first_pay.append(fp)
    fp = [x for x in first_pay if x is not None]
    return dict(ev=float(np.mean(ev)) if ev else np.nan, ev_lo=float(np.percentile(ev, 5)) if ev else np.nan,
                p_any_payout_L=len(fp) / len(S) if S.size else np.nan, med_days_first_payout_L=float(np.median(fp)) if fp else np.nan,
                payouts_per_life=float(np.mean(npay)) if npay else np.nan)


def chain(book, policy, plan, a, b):
    pol = _pol(policy, book)
    a, b = np.datetime64(a, "D"), np.datetime64(b, "D")
    t, daily, trades, accounts = a, [], [], 0
    while t < b:
        accounts += 1
        o = firm.run(book, t, int((b - t) / D1), plan, pol, stop_at_pass=False, daily=daily, trades=trades, stall=STALL)
        bd = next((x for x in (o["breach_day"], o["fund_breach_day"], o["stall_day"]) if x is not None), None)
        if bd is None: break
        t = t + np.timedelta64(bd + 1, "D")
    dp = np.array([x[1] for x in daily]) if daily else np.zeros(1)
    eq = np.cumsum(dp); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    sd = dp.std(ddof=1) if len(dp) > 1 else np.nan
    dn = np.sqrt(np.mean(np.minimum(dp, 0) ** 2)) if len(dp) else np.nan
    pnl = np.array([x[2] for x in trades]); rk = np.array([x[3] for x in trades])
    g, l = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    months = (b - a) / D1 / 30.44
    return dict(pf=g / l if l > 0 else np.inf, exp_R=float(np.mean(pnl / np.where(rk > 0, rk, np.nan))) if len(pnl) else np.nan,
                sharpe=float(dp.mean() / sd * np.sqrt(252)) if sd and sd > 0 else np.nan,
                sortino=float(dp.mean() / dn * np.sqrt(252)) if dn and dn > 0 else np.nan,
                max_dd=dd, worst_day=float(dp.min()), trades_pm=len(pnl) / months, accounts=accounts, net=float(dp.sum()))


def full(book, policy, plan, a, b, H=30, L=90, stride=1):
    r = {}
    r.update(eval_block(book, policy, plan, a, b, H, stride)); r.update(funded_block(book, policy, plan, a, b, H, stride))
    r.update(life_block(book, policy, plan, a, b, L, max(stride, 2))); r.update(chain(book, policy, plan, a, b))
    return r


def sustained_block(book, policy, plan, a, b, H=90, stride=3):
    """Sustained payouts: fresh funded account, H funded days: mean number of payouts, mean $ paid (gross), P(>= 2 payouts), funded bust."""
    pol = _pol(policy, book); S = starts(book, a, b, H)[::stride]
    n, amt, two, br = [], [], 0, 0
    for s in S:
        o = firm.run(book, s, H, plan, pol, phase="funded")
        n.append(len(o["payouts"])); amt.append(sum(x[1] for x in o["payouts"])); two += len(o["payouts"]) >= 2
        br += o["breach_day"] is not None
    k = len(S)
    return dict(f90_payouts=float(np.mean(n)) if k else np.nan, f90_paid=float(np.mean(amt)) if k else np.nan,
                f90_p2=two / k if k else np.nan, f90_bust=br / k if k else np.nan)
