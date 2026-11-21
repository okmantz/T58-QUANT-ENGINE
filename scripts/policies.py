"""Sizing policies (risk dollars per trade) for the account simulator, plus an adapter that runs the repo's own risk governor
(app.bots.risk_governor.decide_risk) so the shipped books are sized exactly as the shipped bots size them."""
from __future__ import annotations
import numpy as np


def pass_policy(base=800.0, cush_cap=0.8, k_need=None, tgt_r=2.0, behind=1.0, pace_days=30, min_risk=250.0, nr_boost=None):
    """BOT A sizing. Risk ``base`` dollars per trade (x leg weight), never more than ``cush_cap`` x the cushion left above the floor (minus open
    risk). Bold near the target: with ``k_need``, never risk more than (need / tgt_r) x k_need -- but never less than ``min_risk`` so the last
    stretch can still be finished. ``behind`` raises size when the 30-day clock is ahead of progress (after day 5)."""
    def pol(st, r, i, open_risk, tr=None):
        cush = st.bal - st.floor - open_risk
        w = pol.w[i] if pol.w is not None else 1.0
        risk = base * w
        if behind != 1.0 and st.day is not None:
            el = (st.day - st.start_day) / np.timedelta64(1, "D")
            prog = max(st.bal - r.size, 0) / r.target
            if el >= 5 and el / pace_days > prog:
                risk *= behind
        need = r.target - (st.bal - r.size)
        if k_need is not None and need > 0:
            risk = min(risk, max(need / tgt_r * k_need, min_risk))
        return min(risk, cush_cap * cush)
    pol.w = None
    return pol


def payout_policy(base=250.0, f_cush=0.25, win_lock=None, loss_stop=None, funded_mult=1.0, eval_base=None, eval_f=None, streak=None):
    """BOT B sizing. Small fixed dollar risk capped at a share of the cushion; stand down for the day once the day already qualifies
    (win_lock dollars) or after loss_stop dollars; optional different sizing during the evaluation."""
    def pol(st, r, i, open_risk, tr=None):
        if win_lock is not None and st.day_pnl >= win_lock:
            return 0.0
        if loss_stop is not None and st.day_pnl <= -loss_stop:
            return 0.0
        b, f = (base, f_cush) if st.phase == "funded" else (eval_base or base, eval_f or f_cush)
        risk = min(b, f * (st.bal - st.floor - open_risk))
        if st.phase == "funded":
            risk *= funded_mult
        if streak is not None and st.loss_streak >= streak[0]:
            risk *= streak[1]
        return risk * (pol.w[i] if pol.w is not None else 1.0)
    pol.w = None
    return pol


def repo_policy(gov, lite):
    """The repo's own governor, fed a mirror of the simulator's account state (phase, balance, floor, day P&L, clock, streak)."""
    from app.bots.risk_governor import AccountState, decide_risk
    def pol(st, r, i, open_risk, tr=None):
        a = AccountState.fresh(lite, phase="funded" if st.phase == "funded" else "evaluation")
        a.balance, a.floor, a.eod_high = st.bal, st.floor, st.eod_high
        a.day_start = st.bal - st.day_pnl
        a.day = str(st.day)
        a.start_day = str(st.start_day)
        a.peak_equity = max(st.eod_high, st.bal)
        a.loss_streak = st.loss_streak
        a.last_payout_balance = st.cycle_start_bal
        a.day_high = max(st.day_pnl, 0.0)
        if st.phase == "funded":
            a.cycle_days = dict((str(k), v) for k, v in st.days_pnl.items())
        elif lite.eval_consistency:
            a.eval_days = dict((str(k), v) for k, v in st.days_pnl.items())
        dec = decide_risk(a, gov, open_risk=open_risk, weight=float(pol.w[i]) if pol.w is not None else 1.0)
        return dec.risk_dollars if dec.allow else 0.0
    pol.w = None
    return pol


def repo_policy_cons(gov, lite, cons=0.40, pad=1.05):
    """repo governor + eval consistency awareness: while the evaluation's best day is above ``cons`` x profit, the governor aims at the
    effective target max(target, best_day / cons) x pad instead of the nominal one (the change proposed for AccountRulesLite)."""
    import dataclasses
    base = repo_policy(gov, lite)
    def pol(st, r, i, open_risk, tr=None):
        if st.phase != "funded" and st.days_pnl:
            best = max(max(st.days_pnl.values()), st.day_pnl if st.day_pnl > 0 else 0.0)
            eff = max(lite.profit_target, pad * best / cons)
            if eff > lite.profit_target:
                p2 = repo_policy(gov, dataclasses.replace(lite, profit_target=eff)); p2.w = pol.w
                return p2(st, r, i, open_risk, tr)
        base.w = pol.w
        return base(st, r, i, open_risk, tr)
    pol.w = None
    return pol
