"""Lucid 50K account simulator (rules in research/LUCID_RULES_2026-11-20.md), event driven, no lookahead.

A trade is sized at its ENTRY from the realised account (closed trades only), and booked at its EXIT. Open positions' dollars at risk come off
the room a new trade may use. Sizes are whole micro contracts: n = floor(risk$ / (stop_pts * pv_micro + cost)), capped by the plan's micro limit.
Trades given only as R multiples (the repo's engine trades) are booked as R * risk$ (continuous size; their costs are already inside R).

Rule model
  evaluation: target +$3,000; EOD trailing MLL $2,000 (floor = max EOD balance - 2,000) that locks at $50,100 once an EOD balance reaches $52,100;
              a breach is any realised balance at or below the floor; DLL $1,200 soft (no new entries after a realised day loss of $1,200, and a new
              trade may not risk more than the room left); Flex: pass also needs best day <= 40% of total profit and >= 3 trading days.
  funded:     fresh $50,000 account and floor. Pro: payout when cycle profit >= $500, best cycle day <= 40% of cycle profit and the balance stays
              above $52,100 after it; amount = min(balance - 52,100, 2,000 first / 2,500 later). Flex: 5 days of >= $150 since the last payout,
              amount = min(50% of cycle profit, 2,000), at least $500; the floor locks at $50,100 at the first payout; 20/30/40 micro scaling;
              at most 5 payouts.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

PVM = {"NQ": 2.0, "ES": 5.0, "GC": 10.0}
COST_MICRO = 1.00          # $ per micro round trip (commission + fees); slippage is in the fill prices


@dataclass
class Rules:
    plan: str = "pro"            # pro | flex
    size: float = 50_000.0
    target: float = 3_000.0
    mll: float = 2_000.0
    lock_trigger: float = 52_100.0
    lock_floor: float = 50_100.0
    dll: float = 1_200.0
    max_micros: int = 40
    eval_consistency: float | None = None
    min_eval_days: int = 1
    dead: float = 250.0          # cushion (balance - floor) below which the account can no longer trade a real stop: counted as a breach

    @classmethod
    def pro(cls):
        return cls()

    @classmethod
    def flex(cls):
        return cls(plan="flex", eval_consistency=0.40, min_eval_days=3, dll=1e9)


@dataclass
class St:
    phase: str
    bal: float
    floor: float
    eod_high: float
    day: object = None
    day_pnl: float = 0.0
    day_count: int = 0
    days_pnl: dict = field(default_factory=dict)      # day -> pnl in the current phase (eval) or cycle (funded)
    locked: bool = False
    payouts: list = field(default_factory=list)
    cycle_start_bal: float = 50_000.0
    loss_streak: int = 0
    start_day: object = None


def micros(risk_dollars: float, risk_pts: float, inst: str, cap: int) -> int:
    per = risk_pts * PVM[inst] + COST_MICRO
    return int(max(0, min(cap, math.floor(risk_dollars / per)))) if per > 0 else 0


def micro_cap(r: Rules, st: St) -> int:
    if st.phase == "funded" and r.plan == "flex":
        prof = st.bal - r.size
        return 20 if prof < 1000 else (30 if prof < 2000 else 40)
    return r.max_micros


def eod(r: Rules, st: St, day) -> None:
    """End of the trading day: trail/lock the floor, payouts (funded), consistency bookkeeping."""
    st.eod_high = max(st.eod_high, st.bal)
    if not st.locked:
        st.floor = max(st.floor, st.eod_high - r.mll)
        if st.eod_high >= r.lock_trigger:
            st.floor, st.locked = max(st.floor, r.lock_floor), True
    if st.phase == "funded":
        cyc = st.bal - st.cycle_start_bal
        amt = 0.0
        if r.plan == "pro":
            best = max(st.days_pnl.values()) if st.days_pnl else 0.0
            if cyc >= 500 and best <= 0.40 * cyc and st.bal - r.lock_trigger >= 500:
                amt = min(st.bal - r.lock_trigger, 2_000.0 if not st.payouts else 2_500.0)
        else:
            good = sum(1 for v in st.days_pnl.values() if v >= 150)
            if len(st.payouts) < 5 and good >= 5 and cyc > 0:
                amt = min(0.5 * cyc, 2_000.0)
                if amt < 500:
                    amt = 0.0
        if amt > 0:
            st.bal -= amt
            st.payouts.append((day, amt))
            st.cycle_start_bal = st.bal
            st.days_pnl = {}
            if r.plan == "flex" and not st.locked:
                st.floor, st.locked = r.lock_floor, True


def passed(r: Rules, st: St) -> bool:
    prof = st.bal - r.size
    if prof < r.target:
        return False
    if len(st.days_pnl) < r.min_eval_days:
        return False
    if r.eval_consistency is not None:
        best = max(st.days_pnl.values()) if st.days_pnl else 0.0
        if best > r.eval_consistency * prof:
            return False
    return True


def run(tr: dict, start_day, horizon: int, r: Rules, policy, *, phase: str = "eval", stop_at_pass: bool = True, until=None) -> dict:
    """Replay the trade arrays ``tr`` (dict of numpy arrays: entry, exit, day, inst, pts, risk_pts, R, w, kind) from ``start_day``.

    ``policy(st, r, i, open_risk) -> risk dollars`` for trade i. Returns pass / breach days (calendar days from start), payouts."""
    start = np.datetime64(start_day)
    end = start + np.timedelta64(horizon, "D") if until is None else np.datetime64(until)
    i0 = int(np.searchsorted(tr["day"], start))
    st = St(phase="funded" if phase == "funded" else "eval", bal=r.size, floor=r.size - r.mll, eod_high=r.size, cycle_start_bal=r.size, start_day=start)
    out = dict(pass_day=None, breach_day=None, payouts=[], n=0, phase_end=None, funded_day=0 if phase == "funded" else None)
    pend = []                       # (exit, pnl, day, risk$)
    N = len(tr["day"])

    def book(upto):
        pend.sort(key=lambda x: x[0])
        while pend and pend[0][0] <= upto:
            _x, p, d, rk = pend.pop(0)
            st.bal += p
            st.day_pnl += p
            st.days_pnl[d] = st.days_pnl.get(d, 0.0) + p
            st.loss_streak = st.loss_streak + 1 if p < 0 else 0
            if st.bal <= st.floor + 1e-9:
                return "breach"
            if st.phase == "eval" and passed(r, st):
                return "pass"
        return None

    def new_day(d):
        if st.day is not None and d != st.day:
            ev = book(np.datetime64("2100-01-01")) if False else None
            eod(r, st, st.day)
        if d != st.day:
            st.day, st.day_pnl = d, 0.0
            st.day_count += 1

    def finish(kind, d):
        dd = int((d - start) / np.timedelta64(1, "D"))
        if kind == "breach":
            out["breach_day"] = dd
        return dd

    i = i0
    while i < N and tr["day"][i] < end:
        d = tr["day"][i]
        # close everything that exited before this entry (it may cross into this day)
        ev = book(tr["entry"][i])
        if ev == "breach":
            finish("breach", st.day); break
        if ev == "pass":
            out["pass_day"] = int((st.day - start) / np.timedelta64(1, "D"))
            if stop_at_pass:
                break
            # move to funded: fresh account the next day
            st = St(phase="funded", bal=r.size, floor=r.size - r.mll, eod_high=r.size, cycle_start_bal=r.size, start_day=st.day)
            out["funded_day"] = out["pass_day"]
            pend.clear()
            prev_day = d
        new_day(d)
        if st.phase == "funded" and r.plan == "flex" and len(st.payouts) >= 5:
            break
        open_risk = sum(x[3] for x in pend)
        room = r.dll + min(st.day_pnl, 0.0) - open_risk if st.phase == "eval" or r.plan == "pro" else 1e9
        if st.bal - st.floor - open_risk < r.dead and not pend:
            finish("breach", st.day); out["dead"] = True; break
        if st.day_pnl <= -r.dll:
            i += 1; continue
        risk = policy(st, r, i, open_risk)
        risk = min(risk, max(st.bal - st.floor - open_risk, 0.0) * 0.98, max(room, 0.0))
        if risk > 0:
            if tr["kind"][i] == 0:
                n = micros(risk, tr["risk_pts"][i], tr["inst"][i], micro_cap(r, st))
                if n > 0:
                    p = n * (tr["pts"][i] * PVM[tr["inst"][i]] - COST_MICRO)
                    pend.append((tr["exit"][i], p, d, n * (tr["risk_pts"][i] * PVM[tr["inst"][i]] + COST_MICRO)))
                    out["n"] += 1
            else:
                pend.append((tr["exit"][i], tr["R"][i] * risk, d, risk))
                out["n"] += 1
        i += 1
    else:
        ev = book(np.datetime64("2100-01-01"))
        if ev == "breach":
            finish("breach", st.day)
        elif ev == "pass":
            out["pass_day"] = int((st.day - start) / np.timedelta64(1, "D"))
        if st.day is not None and ev is None:
            eod(r, st, st.day)
    out["payouts"] = [(int((np.datetime64(dd) - start) / np.timedelta64(1, "D")), a) for dd, a in st.payouts] if st.phase == "funded" else []
    out["final_bal"] = st.bal
    return out


def arrays(df: pd.DataFrame) -> dict:
    d = df.sort_values("entry").reset_index(drop=True)
    return dict(entry=d["entry"].values.astype("datetime64[m]"), exit=d["exit"].values.astype("datetime64[m]"),
                day=d["day"].values.astype("datetime64[D]"), inst=d["inst"].to_numpy(), pts=d["pts"].to_numpy(float),
                risk_pts=d["risk_pts"].to_numpy(float), R=d["R"].to_numpy(float), w=d["w"].to_numpy(float) if "w" in d else np.ones(len(d)),
                kind=d["kind"].to_numpy(int) if "kind" in d else np.zeros(len(d), int), leg=d["leg"].to_numpy() if "leg" in d else np.array([""] * len(d)))


def starts(tr: dict, a, b, horizon: int, last_day, stride: int = 1) -> list:
    days = np.unique(tr["day"])
    # every weekday between a and b whose horizon is covered by data
    cal = pd.bdate_range(a, b, inclusive="left").values.astype("datetime64[D]")
    lim = np.datetime64(last_day) - np.timedelta64(horizon, "D")
    return [x for x in cal[::stride] if x <= lim]
