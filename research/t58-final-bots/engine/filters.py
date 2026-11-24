"""Round 2 regime filters and sizing overlays from the research papers (research/papers_notes.md). Applied to each leg's book
BEFORE the max-open arbiter, so a blocked trade frees its slot exactly as if the leg had not fired.
Every input is causal: daily states use prior sessions only; same-day states (VVG, ATRX) are known at a fixed minute and only
trades entered at or after that minute are touched.

Spec keys (all optional):
  trend:  "sma147" | "ret252" | "both"  -> keep a trade only if its direction agrees with the long-horizon trend
          (Clare et al. 7-month MA; Hurst et al. 12-month TSMOM). "long_only_up": drop longs in a down trend, keep shorts.
  crash:  k  -> weight x k when the 504-session return < 0 and 126-session realised vol > its expanding median (Daniel & Moskowitz)
  vvg:    True -> no entries from 10:00 on VVG days (Mesfin VVG classifier, expanding 66.7th percentiles, prior days only)
  atrx:   x  -> no entries from 10:30 when the 09:30-10:30 range > x times its 20-day average (TwinAlgo ATR-expansion block)
  one_per_inst: False -> two legs may hold the same instrument at once (arbiter setting, not a filter)
  volsz:  True -> weight x clip(median(sig60) / sig60, 0.5, 1.5), sig60 = 60-session std of daily RTH returns, median expanding
"""
import sys, numpy as np
sys.path.insert(0, "research/t58_final_bots/engine")
import book, search as S
from factory import RTH_OPEN, RTH_CLOSE

_ST = {}

def _expanding_pct_flag(x, q):
    """flag[i] = x[i] > q-quantile of x[:i] (finite values only, needs 60 prior values)."""
    out = np.zeros(len(x), bool)
    for i in range(len(x)):
        h = x[:i][np.isfinite(x[:i])]
        if len(h) >= 60 and np.isfinite(x[i]): out[i] = x[i] > np.quantile(h, q)
    return out

def states(inst, sealed=False):
    k = (inst, sealed)
    if k in _ST: return _ST[k]
    M = book.mats(inst, sealed); O, H, L, C, V = M["O"], M["H"], M["L"], M["C"], M["V"]; nd = len(M["days"])
    rc = C[:, RTH_CLOSE - 1]; ro = O[:, RTH_OPEN]
    pdc = np.r_[np.nan, rc[:-1]]
    def sma(n): return np.array([np.nan if i < n else rc[i - n:i].mean() for i in range(nd)])
    def ret(n): return np.array([np.nan if i <= n else rc[i - 1] / rc[i - 1 - n] - 1 for i in range(nd)])
    r1d = np.r_[np.nan, rc[1:] / rc[:-1] - 1]
    def rvol(n): return np.array([np.nan if i <= n else np.nanstd(r1d[i - n:i]) for i in range(nd)])
    s147 = sma(147); t_sma = np.sign(pdc - s147)
    t_ret = np.sign(ret(252))
    r504 = ret(504); v126 = rvol(126)
    v126_hi = np.array([np.isfinite(v126[i]) and np.nanmedian(v126[:i]) < v126[i] if np.isfinite(v126[:i]).sum() > 60 else False for i in range(nd)])
    crash = (r504 < 0) & v126_hi
    sig60 = rvol(60)
    med = np.array([np.nanmedian(sig60[:i]) if np.isfinite(sig60[:i]).sum() > 60 else np.nan for i in range(nd)])
    volsz = np.clip(np.where(np.isfinite(med / sig60), med / sig60, 1.0), 0.5, 1.5)
    # VVG (known at the 09:55 bar close)
    r1 = np.abs(C[:, RTH_OPEN + 24] - ro) / ro
    gap = np.abs(ro - pdc) / pdc
    v5 = V[:, RTH_OPEN:RTH_OPEN + 5].sum(1).astype(float)
    vz = np.array([np.nan if i < 20 else (v5[i] - v5[i - 20:i].mean()) / (v5[i - 20:i].std() + 1e-9) for i in range(nd)])
    vvg = _expanding_pct_flag(r1, 2 / 3) & _expanding_pct_flag(gap, 2 / 3) & _expanding_pct_flag(vz, 2 / 3)
    # first-hour range expansion (known at the 10:29 bar close)
    fh = H[:, RTH_OPEN:RTH_OPEN + 60].max(1) - L[:, RTH_OPEN:RTH_OPEN + 60].min(1)
    fh20 = np.array([np.nan if i < 20 else fh[i - 20:i].mean() for i in range(nd)])
    fhx = fh / fh20
    st = dict(idx={d: i for i, d in enumerate(M["days"])}, t_sma=t_sma, t_ret=t_ret, crash=crash, volsz=volsz, vvg=vvg, fhx=fhx)
    _ST[k] = st
    return st

def _sess_min(t):
    clock = (t.astype("datetime64[m]") - t.astype("datetime64[D]")).astype(int)
    return (clock - 18 * 60) % 1440

def apply(b, spec, sealed=False):
    if not spec or b is None or len(b["day"]) == 0: return b
    keep = np.ones(len(b["day"]), bool); w = b["w"].astype(float).copy()
    sm = _sess_min(b["entry"])
    for inst in np.unique(b["inst"]):
        st = states(inst, sealed); m = b["inst"] == inst
        ii = np.array([st["idx"].get(d, -1) for d in b["day"][m]]); ok = ii >= 0
        def g(name, default):
            a = np.full(m.sum(), default, dtype=float); a[ok] = st[name][ii[ok]]; return a
        dr = b["dir"][m]; kp = np.ones(m.sum(), bool); ww = np.ones(m.sum())
        tr = spec.get("trend")
        if tr:
            ts, tt = g("t_sma", 0), g("t_ret", 0)
            if tr == "sma147": kp &= dr == ts
            elif tr == "ret252": kp &= dr == tt
            elif tr == "both": kp &= (dr == ts) & (dr == tt)
            elif tr == "long_only_up": kp &= ~((dr > 0) & (ts < 0))
        if spec.get("crash") is not None: ww *= np.where(g("crash", 0) > 0, spec["crash"], 1.0)
        if spec.get("vvg"): kp &= ~((g("vvg", 0) > 0) & (sm[m] >= RTH_OPEN + 30))
        if spec.get("atrx"): kp &= ~((g("fhx", 0) > spec["atrx"]) & (sm[m] >= RTH_OPEN + 60))
        if spec.get("volsz"): ww *= g("volsz", 1.0)
        keep[m] = kp; w[m] = w[m] * ww
    out = {k: v[keep] for k, v in b.items()}; out["w"] = w[keep]
    return out

def bot(ws, max_open=2, spec=None, legspec=None, hedge=True, sealed=False):
    """search.bot with filters. spec applies to every leg; legspec {leg: spec} overrides per leg."""
    legs = []
    for j, (k, wt) in enumerate(ws.items()):
        if wt <= 0: continue
        sp = (legspec or {}).get(k, spec)
        legs.append((apply(S.leg(k, sealed), sp, sealed), wt, j))
    opi = (spec or {}).get("one_per_inst", True)          # round 2: False lets two legs hold the same instrument at once
    return book.merge(legs, max_open=max_open, max_per_day=6, one_per_inst=opi, hedge_guard=hedge)
