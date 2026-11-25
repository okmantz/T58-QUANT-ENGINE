# firm.py with one rule change for a what-if check (not used by any frozen result): on a LucidFlex payout request the MLL moves to the
# locked level ($50,100), per Lucid's LucidFlex Drawdown help page read 2026-11-24. Payouts are capped so the balance stays above it.
"""Rule-faithful LucidPro firm engine (Project_Specifications.md sections 2, 3, 5; Statistical_Methodology.md section 2), event driven, no lookahead.

Input: a trade book (dict of numpy arrays, see book.arrays): entry/exit minute stamps (UTC), session day, instrument, direction, gross points per
contract (fills without slippage), risk points (stop distance, > 0), MAE points (worst adverse excursion while open), leg weight.

Sizing: a policy returns DOLLARS AT RISK for trade i; the engine converts it to whole micro contracts:
    n = floor(risk$ / (risk_pts * micro_pv + cost_per_micro)), capped so open micros (mini-equivalent x10) never exceed the plan cap (R6).
Cost per micro round trip = commission (base or stress table, Spec 2.3) + 2 sides x slippage ticks x tick value (Spec 2.3: 1 tick per side).

Rules (defaults = the conservative switches of the spec):
  R1  EOD trailing floor: floor = min(high_EOD - MLL, S0 + 100); locks when it reaches S0 + 100.
  R2  intraday breach: equity at a trade's worst point (realised balance minus this trade's MAE and the MAE of every other open trade,
      i.e. worst cases assumed simultaneous: conservative) at or below the floor -> breach.  breach_check="eod" tests EOD balances only.
  R3  pass: EOD balance >= S0 + target (pass_check="eod"), or realised balance intraday (pass_check="intraday").
  R4  DLL (if on): soft. If realised day P&L minus the open MAE reaches -DLL, the trade is cut at the DLL level and the day is paused.
      Funded: fixed DLL until an EOD close above S0 + MLL + 100, then LucidScale = 60% of the highest EOD profit (never below the fixed DLL).
  R5  flat by 16:45 ET: enforced when the book is built (book.clip_to_flat); entries after 16:44 are dropped there.
  R6  contract cap on mini-equivalents (40 micros on 50K).
  R7  costs both sides; stress mode.
  R8  hedge guard: book.build blocks opposite-sign ES / NQ positions at the same time.
  R10 funded payout machine: buffer S0 + MLL + 100; request needs balance - request >= buffer, request >= 500, cycle profit >= goal,
      best profitable cycle day <= 40% of net cycle profit; caps 2,000 first / 2,500 later (50K); 90% to the trader; cycle resets after a payout.
  R11 request policy: "earliest" (request as soon as eligible, the largest allowed amount) [ASM: Spec 5.3 P1 asks the minimum $500; taking the
      allowed maximum on the same day changes no timing and only adds dollars].
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
import numpy as np

PVM = {"NQ": 2.0, "ES": 5.0, "GC": 10.0}            # micro $/point
TICK = {"NQ": 0.25, "ES": 0.25, "GC": 0.10}
COMM_MICRO = {"base": {"NQ": 1.00, "ES": 1.00, "GC": 1.60}, "stress": {"NQ": 1.32, "ES": 1.32, "GC": 1.82}, "none": {"NQ": 0.0, "ES": 0.0, "GC": 0.0}}
SLIP = {"base": 1.0, "stress": 1.5, "none": 0.0}


def cost_per_micro(inst, cost="base"):
    return COMM_MICRO[cost][inst] + 2 * SLIP[cost] * TICK[inst] * PVM[inst]


@dataclass
class Plan:
    name: str = "pro50"
    S0: float = 50_000.0
    target: float = 3_000.0
    mll: float = 2_000.0
    dll: float | None = 1_200.0          # None = DLL off
    cap_micros: int = 40
    goal: float = 500.0
    cap1: float = 2_000.0
    cap2: float = 2_500.0
    cons: float = 0.40
    breach_check: str = "intraday"
    pass_check: str = "eod"
    cost: str = "base"
    fee: float = 172.0                   # list (Spec 2.2); promo = 120
    reset: float = 120.0
    max_payouts: int = 99
    split: float = 0.90
    kind: str = "pro"                  # "pro" | "flex" (LucidFlex, secondary-source rules: repo preset lucid_flex_50k)
    eval_cons: float | None = None       # flex: best day <= 40% of eval profit
    min_days: int = 1
    win_days: int = 5                    # flex payout: 5 days >= $150 since the last payout, cycle net positive
    win_day: float = 150.0
    pay_frac: float = 0.50               # flex: up to 50% of the cycle profit

    @property
    def lock_floor(self):
        return self.S0 + 100.0

    @property
    def buffer(self):
        return self.S0 + self.mll + 100.0

    @classmethod
    def pro50(cls, **kw):
        return cls(**kw)

    @classmethod
    def flex50(cls, **kw):
        d = dict(name="flex50", kind="flex", eval_cons=0.40, min_days=3, cap1=2_000.0, cap2=2_000.0, max_payouts=5, fee=126.0, reset=126.0)
        d.update(kw)
        return cls(**d)

    @classmethod
    def pro100(cls, **kw):
        d = dict(name="pro100", S0=100_000.0, target=6_000.0, mll=3_000.0, dll=1_800.0, cap_micros=60, goal=750.0, cap1=2_500.0, cap2=3_000.0,
                 fee=285.0, reset=200.0)
        d.update(kw)
        return cls(**d)


@dataclass
class St:
    phase: str
    bal: float
    floor: float
    eod_high: float
    start_day: object
    day: object = None
    day_pnl: float = 0.0
    day_count: int = 0
    days_pnl: dict = field(default_factory=dict)      # eval: day -> pnl; funded: current cycle day -> pnl
    locked: bool = False
    payouts: list = field(default_factory=list)
    cycle_start_bal: float = 0.0
    loss_streak: int = 0
    paused: bool = False
    dll_hits: int = 0
    cons_block_days: int = 0
    elig_days: int = 0
    min_cushion: float = 1e18
    peak_eod_profit: float = 0.0
    peak_eq: float = 0.0          # EOD peak of balance + payouts taken (for a drawdown throttle; not a firm rule)


def _dll(p: Plan, st: St):
    if p.dll is None:
        return None
    if p.kind == "pro" and st.phase == "funded" and st.eod_high > p.buffer:
        return max(p.dll, 0.60 * (st.eod_high - p.S0))
    return p.dll


def run(tr: dict, start_day, horizon: int, p: Plan, policy, *, phase="eval", stop_at_pass=True, funded_horizon=None, daily=None, trades=None, stall=None):
    """One attempt from ``start_day`` (calendar). Returns dict with pass_day / breach_day / payouts [(day_offset, amount)] / funded_day.
    With stop_at_pass=False the attempt continues into a fresh funded account the session after the pass (same path, Methodology 4.4),
    for ``funded_horizon`` more days (default: until start + horizon). ``daily`` (list) receives (day, pnl, phase) for every traded day."""
    start = np.datetime64(start_day, "D")
    end = start + np.timedelta64(horizon, "D")
    i = int(np.searchsorted(tr["day"], start))
    N = len(tr["day"])
    cpm = {k: cost_per_micro(k, p.cost) for k in PVM}
    st = St(phase=phase, bal=p.S0, floor=p.S0 - p.mll, eod_high=p.S0, start_day=start, cycle_start_bal=p.S0)
    out = dict(pass_day=None, breach_day=None, payouts=[], funded_day=0 if phase == "funded" else None, n=0, dll_hits=0, cons_block=0,
               min_cushion=None, profit_at_pass=None, best_day_share_at_pass=None, fund_breach_day=None)
    pend = []   # [exit, pnl$, day, risk$, mae$, micros, book index]
    last_open = start
    out["stall_day"] = None

    def offs(d):
        return int((np.datetime64(d, "D") - start) / np.timedelta64(1, "D"))

    def close_upto(t):
        """Book every open trade with exit <= t, in exit order. Returns 'breach' / 'pass' / None."""
        pend.sort(key=lambda x: x[0])
        while pend and pend[0][0] <= t:
            x = pend.pop(0)
            pnl, mae = x[1], x[4]
            others = sum(y[4] for y in pend)
            worst = st.bal - mae - others
            st.min_cushion = min(st.min_cushion, worst - st.floor)
            dl = _dll(p, st)
            if dl is not None and st.day_pnl - mae - others <= -dl and not st.paused:
                pnl = max(pnl, -dl - st.day_pnl)           # cut at the DLL level (soft)
                st.paused = True; st.dll_hits += 1
            if (p.breach_check == "intraday" and worst <= st.floor + 1e-9) or st.bal + pnl <= st.floor + 1e-9:
                st.bal += pnl
                return "breach"
            st.bal += pnl
            st.day_pnl += pnl
            if trades is not None:
                trades.append((x[6], x[2], pnl, x[3], st.phase))
            st.days_pnl[x[2]] = st.days_pnl.get(x[2], 0.0) + pnl
            st.loss_streak = st.loss_streak + 1 if pnl < 0 else 0
            if st.phase == "eval" and p.pass_check == "intraday" and st.bal >= p.S0 + p.target:
                return "pass"
        return None

    def eod():
        """End of session: daily record, trail/lock the floor, EOD breach/pass checks, payout requests."""
        if daily is not None and st.day is not None:
            daily.append((st.day, st.day_pnl, st.phase))
        st.eod_high = max(st.eod_high, st.bal)
        st.peak_eq = max(st.peak_eq, st.bal + sum(a for _, a in st.payouts))
        if not st.locked:
            st.floor = min(st.eod_high - p.mll, p.lock_floor)
            if st.floor >= p.lock_floor - 1e-9:
                st.locked = True
        if st.bal <= st.floor + 1e-9:
            return "breach"
        if st.phase == "eval":
            if st.bal >= p.S0 + p.target and st.day_count >= p.min_days:
                if p.eval_cons is None:
                    return "pass"
                prof = st.bal - p.S0
                if max(st.days_pnl.values() or [0.0]) <= p.eval_cons * prof + 1e-9:
                    return "pass"
                st.cons_block_days += 1
            return None
        if p.kind == "flex":
            cyc = st.bal - st.cycle_start_bal
            wins = sum(1 for v in st.days_pnl.values() if v >= p.win_day)
            if len(st.payouts) < p.max_payouts and wins >= p.win_days and cyc > 0:
                amt = min(p.pay_frac * cyc, p.cap1 if not st.payouts else p.cap2, st.bal - max(st.floor, p.lock_floor) - 1.0)
                if amt >= 100.0:
                    st.bal -= amt
                    st.payouts.append((st.day, amt))
                    st.floor = max(st.floor, p.lock_floor); st.locked = True   # Lucid Flex: a payout request moves the MLL to $50,100
                    st.cycle_start_bal = st.bal
                    st.days_pnl = {}
            return None
        # funded payout machine (R10, R11)
        cyc = st.bal - st.cycle_start_bal
        if len(st.payouts) < p.max_payouts and cyc >= p.goal and st.bal - p.buffer >= 500.0:
            best = max([v for v in st.days_pnl.values() if v > 0] or [0.0])
            st.elig_days += 1
            if best <= p.cons * cyc + 1e-9:
                amt = min(st.bal - p.buffer, p.cap1 if not st.payouts else p.cap2)
                st.bal -= amt
                st.payouts.append((st.day, amt))
                st.cycle_start_bal = st.bal
                st.days_pnl = {}
            else:
                st.cons_block_days += 1
        return None

    def new_day(d):
        if st.day is not None and d != st.day:
            ev = eod()
            if ev:
                return ev
        if d != st.day:
            st.day, st.day_pnl, st.paused = d, 0.0, False
            st.day_count += 1
        return None

    def to_funded(d_pass):
        nonlocal st
        out["pass_day"] = offs(d_pass)
        out["profit_at_pass"] = st.bal - p.S0
        if st.days_pnl:
            pos = sum(v for v in st.days_pnl.values())
            out["best_day_share_at_pass"] = max(st.days_pnl.values()) / pos if pos > 0 else None
        out["dll_hits"] += st.dll_hits
        old = st
        st = St(phase="funded", bal=p.S0, floor=p.S0 - p.mll, eod_high=p.S0, start_day=np.datetime64(d_pass, "D") + np.timedelta64(1, "D"), cycle_start_bal=p.S0)
        st.day = None        # the pass session is over; the funded account starts with the next session
        out["funded_day"] = out["pass_day"] + 1
        nonlocal last_open
        last_open = np.datetime64(d_pass, "D")
        pend.clear()

    limit = end
    result = None
    while True:
        if i >= N or tr["day"][i] >= limit:
            ev = close_upto(np.datetime64("2100-01-01"))
            if ev == "breach":
                result = ("breach", st.day); break
            ev = eod()
            if ev == "breach":
                result = ("breach", st.day)
            elif ev == "pass":
                result = ("pass", st.day)
            break
        d = tr["day"][i]
        ev = close_upto(tr["entry"][i])
        if ev is None and d != st.day:
            ev = new_day(d)
        if ev == "breach":
            result = ("breach", st.day); break
        if ev == "pass":
            if stop_at_pass:
                result = ("pass", st.day); break
            dpass = st.day
            to_funded(dpass)
            if funded_horizon is not None:
                limit = np.datetime64(dpass, "D") + np.timedelta64(1 + funded_horizon, "D")
            if d == dpass:      # trades of the pass day after the pass are not taken
                i += 1
                while i < N and tr["day"][i] == dpass: i += 1
                continue
            ev = new_day(d)
            continue
        if st.phase == "funded" and len(st.payouts) >= p.max_payouts:
            break
        if st.paused:
            i += 1; continue
        if stall is not None and (d - last_open) / np.timedelta64(1, "D") > stall and not pend:
            result = ("stall", st.day); break     # live account that cannot size one micro for `stall` days: abandoned
        open_risk = sum(x[3] for x in pend)
        cush = st.bal - st.floor - sum(x[4] for x in pend)
        dl = _dll(p, st)
        room = (dl + min(st.day_pnl, 0.0) - open_risk) if dl is not None else 1e18
        risk = policy(st, p, i, open_risk)
        risk = min(risk, max(cush, 0.0) * 0.98, max(room, 0.0))
        if risk > 0:
            inst = tr["inst"][i]
            per = tr["risk_pts"][i] * PVM[inst] + cpm[inst]
            used = sum(x[5] for x in pend)
            n = int(max(0, min(p.cap_micros - used, math.floor(risk / per)))) if per > 0 else 0
            if n > 0:
                pnl = n * (tr["pts"][i] * PVM[inst] - cpm[inst])
                mae = n * (tr["mae_pts"][i] * PVM[inst] + cpm[inst] / 2)     # half the cost (entry slippage + commission side) is already lost at the worst point
                pend.append([tr["exit"][i], pnl, d, n * per, mae, n, i])
                last_open = d
                out["n"] += 1
        i += 1
    kind, dday = result if result else (None, st.day)
    if kind == "breach":
        if st.phase == "eval":
            out["breach_day"] = offs(dday)
        else:
            out["fund_breach_day"] = offs(dday)
            if phase == "funded":
                out["breach_day"] = offs(dday)
    elif kind == "stall":
        out["stall_day"] = offs(dday)
    elif kind == "pass" and st.phase == "eval":
        out["pass_day"] = offs(dday)
        out["profit_at_pass"] = st.bal - p.S0
        pos = sum(st.days_pnl.values())
        out["best_day_share_at_pass"] = max(st.days_pnl.values()) / pos if st.days_pnl and pos > 0 else None
    if daily is not None and kind is None and st.day is not None and (not daily or daily[-1][0] != st.day):
        daily.append((st.day, st.day_pnl, st.phase))
    out["payouts"] = [(offs(dd), a) for dd, a in st.payouts]
    out["dll_hits"] += st.dll_hits
    out["cons_block"] = st.cons_block_days
    out["elig_days"] = st.elig_days
    out["min_cushion"] = st.min_cushion
    out["final_bal"] = st.bal
    out["phase_end"] = st.phase
    return out
