"""Round 6 helpers (research/PREREG_R6.md). Env T58_R6=1 (implies R5/R4): ES/NQ/GC dev = every day to 2026-11-20 (all read);
CL/NG from data_r6 (no energy leg passed the screen, so no bot uses them). Plans pro50 / pro100 / flex50. Windows W1, W2, H6 plus the
round-5 windows. fspec = round-6 input filters per leg: {leg: [(input, side, thr), ...]} (r6feat.trade_feats)."""
import os, sys, copy
os.environ["T58_R6"] = "1"; os.environ["T58_R5"] = "1"; os.environ["T58_R4"] = "1"; sys.path.insert(0, "research/t58_final_bots/engine")
from dataclasses import replace
import numpy as np
import r4, firm, score, search as S, filters as FL, regime, book, baseline as BL, r6feat as X
from policy import Pol
from app.bots.risk_governor import AccountRulesLite
OUT = r4.OUT
SPL = dict(r4.SPL); SPL.update(h3=("2016-11-24", "2020-01-02"), W1=("2021-01-04", "2024-07-16"), W2=("2024-07-16", "2026-01-05"),
                              H6=("2026-01-05", "2026-11-21"))
CELLS = [("pro50", "W1"), ("pro50", "W2"), ("pro100", "W1"), ("pro100", "W2")]
DOLLAR_KNOBS = ("r_eval", "r_fund", "r_min", "day_stop", "eval_day_cap", "fund_day_cap", "fund_day_stop", "dd_lvl", "cons_min")

def plan_of(name, cost):
    if name == "pro50": return firm.Plan(cost=cost)
    if name == "pro100": return firm.Plan.pro100(cost=cost, fee=268.0, reset=188.0)      # [ASM] 100K fee / reset (PREREG_R6 section 3)
    return firm.Plan.flex50(cost=cost)

def lite(p):
    if p.name == "pro100":
        return AccountRulesLite(account_size=100_000.0, profit_target=6_000.0, loss_limit=3_000.0, soft_daily_limit=1_800.0,
                                lock_floor_offset=100.0, funded_buffer=3_100.0, payout_goal=750.0)
    return BL.lite(p)

def scaled(policy, p, k100=1.5):
    pol = dict(policy); k = k100 if p.name == "pro100" else p.mll / 2_000.0
    if k != 1.0:
        for kk in DOLLAR_KNOBS:
            if pol.get(kk) is not None: pol[kk] = pol[kk] * k
    return pol

def fapply(b, fl):
    if not fl or b is None or len(b["day"]) == 0: return b
    tf = X.trade_feats(b); keep = np.ones(len(b["day"]), bool)
    for name, side, thr in fl:
        v = tf[name]; f = np.isfinite(v)
        if side == "skip_low": keep &= ~(f & (v <= thr))
        elif side == "skip_high": keep &= ~(f & (v >= thr))
        elif side in ("skip_against", "skip_inside", "skip_with"): keep &= ~(v == thr)
        elif side in ("skip_day", "skip_after_1330"): keep &= ~(v == 1)
        else: raise ValueError(side)
    return {k: v[keep] for k, v in b.items()}

_LB = {}
def leg_book(k, sp, rs, fl, sealed):
    key = (k, repr(sp), repr(rs), repr(fl), sealed)
    if key not in _LB:
        b0 = FL.apply(S.leg(k, sealed), sp, sealed)
        _LB[key] = (b0, fapply(regime.apply(b0, rs, sealed), fl))
    return _LB[key]

def bot_book(pk, sealed=False):
    legs, raw = [], []
    spec = pk.get("spec"); rsp = pk.get("rspec") or {}; fsp = pk.get("fspec") or {}
    for j, (k, wt) in enumerate(pk["legs"].items()):
        if wt <= 0: continue
        sp = (pk.get("legspec") or {}).get(k, spec)
        b0, b = leg_book(k, sp, rsp.get(k, rsp.get("*")), fsp.get(k), sealed)
        raw.append(b0); legs.append((b, wt, j))
    opi = (spec or {}).get("one_per_inst", True)
    out = book.merge(legs, max_open=pk["max_open"], max_per_day=6, one_per_inst=opi, hedge_guard=True)
    if pk.get("bot_eq"):
        raise NotImplementedError("bot_eq not used by the round-4 picks")
    return out

def book_pol(pk, p, sealed=False):
    if isinstance(pk, str):
        obj = pk[-1]; return BL.bot_book(BL.LEGS_A if obj == "A" else BL.LEGS_B, sealed=sealed), BL.policy(obj, lite(p))
    return bot_book(pk, sealed), Pol(**scaled(pk["policy"], p, pk.get("k100", 1.5)))

def run(pk, planname, sp, cost="stress", stride=1, sealed=False, sustained=True):
    p = plan_of(planname, cost); x, y = SPL[sp]; bk, pol = book_pol(pk, p, sealed)
    r = score.full(bk, pol, p, x, y, stride=stride)
    if sustained: r.update(score.sustained_block(bk, pol, p, x, y, stride=max(3, stride)))
    return r

a_bar = r4.a_bar
def b_bar(new, base): return S.beats(new, base, sustained=True)
