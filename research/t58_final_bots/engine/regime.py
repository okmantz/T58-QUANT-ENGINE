"""Round 4 regime filters (research/PREREG_R4.md, point 3). Causal: daily states use prior sessions only; the equity filters use only
signals that closed before the trade's entry. Applied per leg BEFORE the arbiter (as filters.py), so a blocked trade frees its slot.

rspec per leg (dict, all keys optional):
  vol: (lo, hi)  keep only when the prior-session ATR20 percentile (expanding, >= 120 prior sessions) is in [lo, hi]
  er:  q         keep only when the prior-20-session efficiency ratio is above its expanding q-quantile (>= 120 prior)
  eq:  N         keep only when the leg's last N closed signals (all its signals, taken or not) have mean net R > 0
Bot-level: bot_eq=(N, k): weight x k when the last N closed signals of all legs together have mean net R <= 0.
Net R = (points x $/pt/micro - stress cost per micro) / (stop points x $/pt/micro)."""
import sys, numpy as np
sys.path.insert(0, "research/t58_final_bots/engine")
import book, search as S, filters as FL
from factory import RTH_OPEN, RTH_CLOSE
from firm import PVM, cost_per_micro

_ST = {}
def _exp_pct(x, minn=120):
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        h = x[:i]; h = h[np.isfinite(h)]
        if len(h) >= minn and np.isfinite(x[i]): out[i] = (h < x[i]).mean()
    return out

def states(inst, sealed=False):
    k = (inst, sealed)
    if k in _ST: return _ST[k]
    M = book.mats(inst, sealed); H, L, C = M["H"], M["L"], M["C"]; nd = len(M["days"])
    hi, lo, cl = H.max(1), L.min(1), C[:, -1]
    pc = np.r_[np.nan, cl[:-1]]
    tr = np.nanmax(np.c_[hi - lo, np.abs(hi - pc), np.abs(lo - pc)], 1)
    atr = np.array([np.nan if i < 20 else tr[i - 20:i].mean() / cl[i - 1] for i in range(nd)])     # prior 20 sessions, as % of price
    rc = C[:, RTH_CLOSE - 1]
    er = np.array([np.nan if i < 21 else abs(rc[i - 1] - rc[i - 21]) / (np.abs(np.diff(rc[i - 21:i])).sum() + 1e-12) for i in range(nd)])
    st = dict(idx={d: i for i, d in enumerate(M["days"])}, atr_p=_exp_pct(atr), er_p=_exp_pct(er))
    _ST[k] = st
    return st

def net_R(b, cost="stress"):
    pv = np.array([PVM[i] for i in b["inst"]]); c = np.array([cost_per_micro(i, cost) for i in b["inst"]])
    return (b["pts"] * pv - c) / np.maximum(b["risk_pts"] * pv, 1e-9)

def _eq_ok(b, N, R=None):
    """keep[j] = mean net R of the last N signals of this book that exited before entry j is > 0 (needs N closed signals)."""
    R = net_R(b) if R is None else R
    ex, en = b["exit"].astype("int64"), b["entry"].astype("int64")
    o = np.argsort(ex); exs, Rs = ex[o], R[o]; cs = np.r_[0, np.cumsum(Rs)]
    n = np.searchsorted(exs, en, side="right")         # signals closed at or before entry
    ok = np.zeros(len(en), bool); m = n >= N
    ok[m] = (cs[n[m]] - cs[n[m] - N]) / N > 0
    return ok

def apply(b, rs, sealed=False):
    if not rs or b is None or len(b["day"]) == 0: return b
    keep = np.ones(len(b["day"]), bool)
    for inst in np.unique(b["inst"]):
        st = states(inst, sealed); m = b["inst"] == inst
        ii = np.array([st["idx"].get(d, -1) for d in b["day"][m]]); ok = ii >= 0
        def g(name):
            a = np.full(m.sum(), np.nan); a[ok] = st[name][ii[ok]]; return a
        kp = np.ones(m.sum(), bool)
        if rs.get("vol") is not None:
            lo, hi = rs["vol"]; a = g("atr_p"); kp &= ~np.isfinite(a) | ((a >= lo) & (a <= hi))
        if rs.get("er") is not None:
            a = g("er_p"); kp &= ~np.isfinite(a) | (a > rs["er"])
        keep[m] = kp
    if rs.get("eq"): keep &= _eq_ok(b, rs["eq"])
    return {k: v[keep] for k, v in b.items()}

def bot(ws, max_open=2, spec=None, legspec=None, rspec=None, bot_eq=None, hedge=True, sealed=False):
    """filters.bot + round-4 regime filters. rspec {leg: rs} (or {"*": rs} for every leg)."""
    legs, raw = [], []
    for j, (k, wt) in enumerate(ws.items()):
        if wt <= 0: continue
        sp = (legspec or {}).get(k, spec)
        b0 = FL.apply(S.leg(k, sealed), sp, sealed); raw.append(b0)
        rs = (rspec or {}).get(k, (rspec or {}).get("*"))
        legs.append((apply(b0, rs, sealed), wt, j))
    opi = (spec or {}).get("one_per_inst", True)
    out = book.merge(legs, max_open=max_open, max_per_day=6, one_per_inst=opi, hedge_guard=hedge)
    if bot_eq and out is not None and len(out["day"]):
        N, kk = bot_eq
        allb = {k: np.concatenate([r[k] for r in raw if r is not None and len(r["day"])]) for k in ("entry", "exit", "pts", "risk_pts", "inst")}
        R = net_R(allb); ex = allb["exit"].astype("int64"); o = np.argsort(ex); exs, cs = ex[o], np.r_[0, np.cumsum(R[o])]
        n = np.searchsorted(exs, out["entry"].astype("int64"), side="right"); bad = np.zeros(len(n), bool); m = n >= N
        bad[m] = (cs[n[m]] - cs[n[m] - N]) / N <= 0
        out = dict(out); out["w"] = np.where(bad, out["w"] * kk, out["w"])
    return out
