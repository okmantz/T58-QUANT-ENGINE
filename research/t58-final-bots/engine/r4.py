"""Round 4 scoring helpers (env T58_R4=1). One function scores any pick (round 1-4) or a baseline on any split with identical code."""
import sys, os, json
sys.path.insert(0, "research/t58_final_bots/engine")
import data as D
assert D.R4, "set T58_R4=1"
import numpy as np
import search as S, score, firm, filters, regime, baseline as BL
from policy import Pol
OUT = "research/t58_final_bots/research"
SPL = {"research": ("2020-01-01", "2024-01-01"), "validation": ("2024-01-01", "2026-11-21"), "holdout": ("2016-11-24", "2020-01-02")}
assert S.VAL == SPL["validation"]

def plan_of(name, cost, lock=False):
    if name == "pro50": return firm.Plan(cost=cost)
    return firm.Plan.flex50(cost=cost)

def book_pol(pk, p, sealed=False):
    if isinstance(pk, str):
        obj = pk[-1]; return BL.bot_book(BL.LEGS_A if obj == "A" else BL.LEGS_B, sealed=sealed), BL.policy(obj, BL.lite(p))
    if pk.get("rspec") or pk.get("bot_eq"):
        bk = regime.bot(pk["legs"], max_open=pk["max_open"], spec=pk.get("spec"), legspec=pk.get("legspec"), rspec=pk.get("rspec"),
                        bot_eq=pk.get("bot_eq"), sealed=sealed)
    elif pk.get("spec") is not None or pk.get("legspec") is not None:
        bk = filters.bot(pk["legs"], max_open=pk["max_open"], spec=pk.get("spec"), legspec=pk.get("legspec"), sealed=sealed)
    else:
        bk = S.bot(pk["legs"], max_open=pk["max_open"], sealed=sealed)
    return bk, Pol(**pk["policy"])

def run(pk, planname, sp, cost, stride=1, sealed=False, sustained=True, life_stride=None):
    p = plan_of(planname, cost); x, y = SPL[sp]; bk, pol = book_pol(pk, p, sealed)
    r = score.full(bk, pol, p, x, y, stride=stride)
    if sustained: r.update(score.sustained_block(bk, pol, p, x, y, stride=max(3, stride)))
    return r

# ---- BOT-A bar (PREREG_R4.md)
A_PRIMARY_HI, A_PRIMARY_LO = ["p_pass", "ev"], ["med_days_pass", "bust"]
A_LIM10_HI = ["pf", "exp_R", "sharpe", "sortino", "p_payout", "trades_pm"]
A_LIM10_LO = ["med_days_payout", "fund_bust", "cons_blocks_per30", "cons_block_rate"]
A_LIM25_LO = ["max_dd"]

def a_bar(new, base):
    """(primary fails, limit fails) of a BOT-A result against baseline_A in the same cell."""
    pf, lf = [], []
    for k in A_PRIMARY_HI:
        if not (new[k] >= base[k]): pf.append(k)
    for k in A_PRIMARY_LO:
        if not (new[k] <= base[k]) : pf.append(k)
    if not (new["med_days_pass"] < 30): pf.append("med_days_pass<30")
    def worse_hi(a, b, t): return not (a >= b - t * abs(b))
    def worse_lo(a, b, t): return not (a <= b + t * abs(b))
    for k in A_LIM10_HI:
        if np.isfinite(base.get(k, np.nan)) and worse_hi(new[k], base[k], .10): lf.append(k)
    for k in A_LIM10_LO:
        b = base.get(k, np.nan)
        if np.isfinite(b) and (b == 0 and new[k] > 0.01 or b != 0 and worse_lo(new[k], b, .10)): lf.append(k)
    if worse_lo(new["max_dd"], base["max_dd"], .25): lf.append("max_dd")
    if worse_hi(new["worst_day"], base["worst_day"], .25) or new["worst_day"] < -1200: lf.append("worst_day")
    return pf, lf
