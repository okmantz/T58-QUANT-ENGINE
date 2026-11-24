"""Hypothesis factory (Phase 2): vectorised intraday strategy families on the 1m session matrices.

Every family turns day matrices into signals (day, entry minute, direction, stop, target, last minute). A signal is decided on bars
that have CLOSED (minute m) and filled at the OPEN of minute m+1: no lookahead. Daily features use only prior sessions.
simulate() walks each trade minute by minute: stop first when a bar touches both stop and target (conservative), a gap through the
stop fills at the bar's open (worse), targets fill at the limit price, otherwise exit at the close of the last allowed minute.
Output is a points book in book.py's format (costs are charged in firm.py, never here).

Minute index m = minutes since 18:00 ET of the prior calendar day (data.py). 09:30 = 930, 16:00 = 1320, 16:45 = 1365.
"""
from __future__ import annotations
import sys, itertools, math
from pathlib import Path
import numpy as np
from numba import njit
sys.path.insert(0, str(Path(__file__).parent))
import data as D, book

RTH_OPEN, RTH_CLOSE = 930, 1320
PLACEBO = None         # np.random.Generator -> to_book randomises directions (placebo test)
GC_OPEN = 860          # 08:20 ET COMEX open
LDN_OPEN = 540         # 03:00 ET London open


# ------------------------------------------------------------------------------------------------------------------- kernel
@njit(cache=True)
def simulate(O, H, L, C, V, di, m0, d, stop, tgt, mx):
    n = len(di)
    xp = np.empty(n); xm = np.empty(n, np.int64); mae = np.empty(n); ep = np.empty(n); why = np.zeros(n, np.int64)
    for k in range(n):
        i = di[k]; a = m0[k]; e = O[i, a]; ep[k] = e
        s = stop[k]; t = tgt[k]; worst = e; done = False
        for m in range(a, mx[k] + 1):
            if d[k] > 0:
                if L[i, m] <= s:
                    px = s
                    if m > a and O[i, m] < s and not (V[i, m - 1] == 0 and V[i, m] > 0):   # after a data hole: fill at the stop
                        px = O[i, m]
                    worst = min(worst, px); xp[k] = px; xm[k] = m; why[k] = 1; done = True; break
                worst = min(worst, L[i, m])
                if t == t and H[i, m] >= t:
                    xp[k] = t; xm[k] = m; why[k] = 2; done = True; break
            else:
                if H[i, m] >= s:
                    px = s
                    if m > a and O[i, m] > s and not (V[i, m - 1] == 0 and V[i, m] > 0):
                        px = O[i, m]
                    worst = max(worst, px); xp[k] = px; xm[k] = m; why[k] = 1; done = True; break
                worst = max(worst, H[i, m])
                if t == t and L[i, m] <= t:
                    xp[k] = t; xm[k] = m; why[k] = 2; done = True; break
        if not done:
            xp[k] = C[i, mx[k]]; xm[k] = mx[k]; why[k] = 3
        mae[k] = (e - worst) if d[k] > 0 else (worst - e)
    return ep, xp, xm, mae, why


def to_book(M, inst, di, m0, d, stop, tgt, mx, name):
    """Signals -> points book (book.KEYS). stop/tgt are price levels (tgt NaN = none)."""
    di, m0, d = np.asarray(di, np.int64), np.asarray(m0, np.int64), np.asarray(d, np.int64)
    if len(di) == 0:
        return None
    if PLACEBO is not None:          # placebo: same days, times, stop distances and targets in R, coin-flip direction
        e0 = M["O"][di, m0]; dist = np.abs(e0 - np.asarray(stop, float)); tr = np.abs(np.asarray(tgt, float) - e0) / np.where(dist > 0, dist, np.nan)
        d = np.where(PLACEBO.random(len(di)) < 0.5, 1, -1).astype(np.int64)
        stop = e0 - d * dist; tgt = np.where(np.isfinite(tr), e0 + d * tr * dist, np.nan)
    stop, tgt, mx = np.asarray(stop, float), np.asarray(tgt, float), np.asarray(mx, np.int64)
    ep, xp, xm, mae, why = simulate(M["O"], M["H"], M["L"], M["C"], M["V"], di, m0, d, stop, tgt, mx)
    risk = np.abs(ep - stop)
    ok = (risk >= 2 * D.TICK[inst]) & np.isfinite(risk) & (d * (ep - stop) > 0)
    di, m0, d, ep, xp, xm, mae, risk, why = (x[ok] for x in (di, m0, d, ep, xp, xm, mae, risk, why))
    day = M["days"][di]
    base = day.astype("datetime64[m]") - np.timedelta64(360, "m")
    ent = base + m0.astype("timedelta64[m]"); ex = base + (xm + 1).astype("timedelta64[m]")
    o = np.lexsort((m0, di))
    n = len(di)
    b = dict(entry=ent, exit=ex, day=day, inst=np.array([inst] * n), pts=d * (xp - ep), risk_pts=risk, mae_pts=np.maximum(mae, 0.0),
             dir=d, clip=np.zeros(n, bool), nostop=np.zeros(n, bool), w=np.ones(n), leg=np.array([name] * n), why=why)
    return {k: v[o] for k, v in b.items()}


# ----------------------------------------------------------------------------------------------------------------- features
_F = {}
def feats(inst, sealed=False):
    """Per-day features from prior sessions only (index i uses days < i), plus same-day arrays used causally by the families."""
    k = (inst, sealed)
    if k in _F:
        return _F[k]
    M = book.mats(inst, sealed)
    O, H, L, C, V = M["O"], M["H"], M["L"], M["C"], M["V"]
    nd = len(M["days"])
    rth = slice(RTH_OPEN, RTH_CLOSE)
    rh, rl, rc = H[:, rth].max(1), L[:, rth].min(1), C[:, RTH_CLOSE - 1]
    rng = rh - rl
    sh = lambda x, k=1: np.r_[np.full(k, np.nan), x[:-k]]
    atr = np.array([np.nan if i < 14 else np.nanmean(rng[i - 14:i]) for i in range(nd)])
    sma20 = np.array([np.nan if i < 20 else rc[i - 20:i].mean() for i in range(nd)])
    sma50 = np.array([np.nan if i < 50 else rc[i - 50:i].mean() for i in range(nd)])
    ret20 = np.r_[np.full(21, np.nan), rc[20:-1] / rc[:-21] - 1] if nd > 21 else np.full(nd, np.nan)
    atr_pct = np.array([np.nan if i < 120 else (atr[i - 120:i] < atr[i]).mean() for i in range(nd)])
    # overnight (18:00 .. 09:29) and London (03:00 .. 08:19) ranges are complete at 09:30 / 08:20 of the same session: causal for later entries
    onh, onl = H[:, :RTH_OPEN].max(1), L[:, :RTH_OPEN].min(1)
    lh, ll = H[:, LDN_OPEN:GC_OPEN].max(1), L[:, LDN_OPEN:GC_OPEN].min(1)
    tp = (H + L + C) / 3.0
    vv = np.where(np.arange(O.shape[1]) >= RTH_OPEN, V, 0.0)
    cv = np.cumsum(vv, 1); cpv = np.cumsum(vv * tp, 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        vwap = np.where(cv > 0, cpv / cv, np.nan)          # RTH VWAP through the CLOSE of minute m
    ok = M["full"].astype(bool) & np.isfinite(atr) & np.isfinite(sh(rc))
    f = dict(M=M, nd=nd, pdh=sh(rh), pdl=sh(rl), pdc=sh(rc), prng=sh(rng), atr=atr, sma20=sma20, sma50=sma50, ret20=ret20, atr_pct=atr_pct,
             onh=onh, onl=onl, lh=lh, ll=ll, vwap=vwap, ok=ok, split=D.split_of(M["days"]))
    _F[k] = f
    return f


# ----------------------------------------------------------------------------------------------------------------- families
@njit(cache=True)
def _first_break(H, L, C, hi, lo, a, b, both):
    """First minute in [a, b) whose CLOSE is beyond hi (long) or lo (short). Returns (minute, dir) or (-1, 0)."""
    nd = C.shape[0]
    mm = np.full(nd, -1, np.int64); dd = np.zeros(nd, np.int64)
    for i in range(nd):
        if not (hi[i] == hi[i]) or not (lo[i] == lo[i]):
            continue
        for m in range(a, b):
            if C[i, m] > hi[i]:
                mm[i] = m; dd[i] = 1; break
            if both and C[i, m] < lo[i]:
                mm[i] = m; dd[i] = -1; break
    return mm, dd


@njit(cache=True)
def _fade_after_break(H, L, C, hi, lo, a, b):
    """Break of the range (a wick beyond it) then a CLOSE back inside: fade. Returns (minute, dir, extreme)."""
    nd = C.shape[0]
    mm = np.full(nd, -1, np.int64); dd = np.zeros(nd, np.int64); ex = np.full(nd, np.nan)
    for i in range(nd):
        if not (hi[i] == hi[i]):
            continue
        up = False; dn = False; xh = -1e18; xl = 1e18
        for m in range(a, b):
            if H[i, m] > hi[i]:
                up = True; xh = max(xh, H[i, m])
            if L[i, m] < lo[i]:
                dn = True; xl = min(xl, L[i, m])
            if up and C[i, m] < hi[i] and C[i, m] > lo[i]:
                mm[i] = m; dd[i] = -1; ex[i] = xh; break
            if dn and C[i, m] > lo[i] and C[i, m] < hi[i]:
                mm[i] = m; dd[i] = 1; ex[i] = xl; break
    return mm, dd, ex


@njit(cache=True)
def _vwap_touch(L, H, C, vw, trend, a, b):
    nd = C.shape[0]
    mm = np.full(nd, -1, np.int64)
    for i in range(nd):
        t = trend[i]
        if t == 0:
            continue
        for m in range(a, b):
            v = vw[i, m]
            if not (v == v):
                continue
            if t > 0 and L[i, m] <= v and C[i, m] > v:
                mm[i] = m; break
            if t < 0 and H[i, m] >= v and C[i, m] < v:
                mm[i] = m; break
    return mm


@njit(cache=True)
def _zfade(C, vw, a, b, win, z):
    nd = C.shape[0]
    mm = np.full(nd, -1, np.int64); dd = np.zeros(nd, np.int64)
    for i in range(nd):
        for m in range(a, b):
            v = vw[i, m]
            if not (v == v):
                continue
            s = 0.0; s2 = 0.0
            for j in range(m - win + 1, m + 1):
                x = C[i, j] - vw[i, j]
                s += x; s2 += x * x
            mu = s / win; sd = math.sqrt(max(s2 / win - mu * mu, 1e-12))
            dev = (C[i, m] - v) / max(sd, 1e-9)
            if dev > z:
                mm[i] = m; dd[i] = -1; break
            if dev < -z:
                mm[i] = m; dd[i] = 1; break
    return mm, dd


def _emit(f, inst, mm, dd, stop, tgt_R, mx, name, mask=None):
    """Common tail: valid days, entry at m+1, stop level, target = R multiple."""
    M = f["M"]
    ok = f["ok"] & (mm >= 0) & (dd != 0)
    if mask is not None:
        ok &= mask
    di = np.nonzero(ok)[0]
    m0 = mm[di] + 1
    keep = m0 < mx
    di, m0 = di[keep], m0[keep]
    d = dd[di]; st = stop[di]
    e = M["O"][di, m0]
    risk = d * (e - st)
    tgt = np.where(np.isfinite(tgt_R) & (risk > 0), e + d * tgt_R * risk, np.nan) if np.isfinite(tgt_R) else np.full(len(di), np.nan)
    return to_book(M, inst, di, m0, d, st, tgt, np.full(len(di), mx), name)


def fam_orb(inst, k=15, stop="opp", R=2.0, filt="none", cut=720, both=True, start=RTH_OPEN, exit_m=1314, trend_only=False, sealed=False):
    """F1 opening-range breakout. Range = first k minutes from ``start``; entry on the first CLOSE beyond it before start+cut minutes."""
    f = feats(inst, sealed); M = f["M"]
    hi = M["H"][:, start:start + k].max(1); lo = M["L"][:, start:start + k].min(1)
    mm, dd = _first_break(M["H"], M["L"], M["C"], hi, lo, start + k, min(start + cut, exit_m - 5), both)
    mid = (hi + lo) / 2
    st = np.where(dd > 0, lo, hi) if stop == "opp" else (mid if stop == "mid" else np.where(dd > 0, hi - 0.25 * f["atr"], lo + 0.25 * f["atr"]))
    mask = _filter(f, filt, hi - lo)
    if trend_only:
        mask = mask & (np.sign(f["pdc"] - f["sma20"]) == dd)
    return _emit(f, inst, mm, dd, st, R, exit_m, f"ORB{k}_{stop}_R{R}_{filt}_c{cut}_{'b' if both else 'l'}{'_T' if trend_only else ''}@{inst}", mask)


def fam_orb_fade(inst, k=30, R=1.5, filt="none", cut=360, tgt="R", sealed=False):
    """F2 opening-range fade: wick beyond the range then a close back inside -> trade back toward the other side; stop beyond the wick."""
    f = feats(inst, sealed); M = f["M"]
    hi = M["H"][:, RTH_OPEN:RTH_OPEN + k].max(1); lo = M["L"][:, RTH_OPEN:RTH_OPEN + k].min(1)
    mm, dd, ex = _fade_after_break(M["H"], M["L"], M["C"], hi, lo, RTH_OPEN + k, RTH_OPEN + cut)
    pad = 2 * D.TICK[inst]
    st = np.where(dd > 0, ex - pad, ex + pad)
    mask = _filter(f, filt, hi - lo)
    b = _emit(f, inst, mm, dd, st, R, 1314, f"ORBF{k}_R{R}_{filt}_c{cut}@{inst}", mask)
    return b


def fam_vwap_pb(inst, R=2.0, sm=0.5, t0=630, t1=1260, trend="or", sealed=False):
    """F3 VWAP pullback in a trend day: trend fixed at 10:00 (close above VWAP and above the opening 15m high, or the mirror); first touch of
    VWAP after ``t0`` minutes past 18:00 -> enter; stop ``sm`` x ATR beyond entry."""
    f = feats(inst, sealed); M = f["M"]
    C = M["C"]; m10 = 960
    hi30 = M["H"][:, RTH_OPEN:RTH_OPEN + 15].max(1); lo30 = M["L"][:, RTH_OPEN:RTH_OPEN + 15].min(1)    # opening 15m range, closed by 09:45
    vw10 = f["vwap"][:, m10 - 1]
    if trend == "or":
        tr = np.where((C[:, m10 - 1] > hi30) & (C[:, m10 - 1] > vw10), 1, np.where((C[:, m10 - 1] < lo30) & (C[:, m10 - 1] < vw10), -1, 0))
    else:   # daily trend
        tr = np.where((f["pdc"] > f["sma20"]) & (C[:, m10 - 1] > vw10), 1, np.where((f["pdc"] < f["sma20"]) & (C[:, m10 - 1] < vw10), -1, 0))
    tr = np.nan_to_num(tr).astype(np.int64)
    mm = _vwap_touch(M["L"], M["H"], C, f["vwap"], tr, max(m10, t0), t1)
    dd = tr.copy()
    e_guess = np.array([C[i, mm[i]] if mm[i] >= 0 else np.nan for i in range(f["nd"])])
    st = e_guess - dd * sm * f["atr"]
    return _emit(f, inst, mm, dd, st, R, 1314, f"VWPB_R{R}_s{sm}_{trend}_t{t1}@{inst}")


def fam_sweep(inst, level="on", R=2.0, cut=90, tgt="R", sealed=False):
    """F4 liquidity sweep and reclaim: a wick through the overnight (or prior-day) low / high in the first ``cut`` RTH minutes, then a close
    back inside -> trade the reclaim; stop beyond the sweep extreme."""
    f = feats(inst, sealed); M = f["M"]
    hi, lo = (f["onh"], f["onl"]) if level == "on" else (f["pdh"], f["pdl"])
    mm, dd, ex = _fade_after_break(M["H"], M["L"], M["C"], hi, lo, RTH_OPEN, RTH_OPEN + cut)
    pad = 2 * D.TICK[inst]
    st = np.where(dd > 0, ex - pad, ex + pad)
    return _emit(f, inst, mm, dd, st, R, 1314, f"SWP_{level}_R{R}_c{cut}@{inst}")


def fam_pdl_break(inst, R=2.0, sm=0.5, vol="any", t0=960, t1=1200, sealed=False):
    """F5 trend breakout with a volatility filter: first close beyond the prior-day high / low between t0 and t1; ATR regime filter."""
    f = feats(inst, sealed); M = f["M"]
    mm, dd = _first_break(M["H"], M["L"], M["C"], f["pdh"], f["pdl"], t0, t1, True)
    e_guess = np.array([M["C"][i, mm[i]] if mm[i] >= 0 else np.nan for i in range(f["nd"])])
    st = e_guess - dd * sm * f["atr"]
    mask = np.ones(f["nd"], bool)
    if vol == "low": mask = f["atr_pct"] < 0.5
    elif vol == "high": mask = f["atr_pct"] >= 0.5
    return _emit(f, inst, mm, dd, st, R, 1314, f"PDLB_R{R}_s{sm}_{vol}_{t0}@{inst}", mask)


def fam_mr(inst, z=2.5, win=30, sm=0.4, R=1.0, t0=1020, t1=1260, sealed=False):
    """F6 intraday mean reversion: fade a ``z``-sigma stretch from VWAP (sigma over the last ``win`` minutes) between t0 and t1."""
    f = feats(inst, sealed); M = f["M"]
    mm, dd = _zfade(M["C"], f["vwap"], t0, t1, win, z)
    e_guess = np.array([M["C"][i, mm[i]] if mm[i] >= 0 else np.nan for i in range(f["nd"])])
    st = e_guess - dd * sm * f["atr"]
    return _emit(f, inst, mm, dd, st, R, 1314, f"MR_z{z}_w{win}_s{sm}_R{R}@{inst}")


def fam_tod(inst, sig_m=1290, hold_to=1319, sm=0.3, mode="intraday", thr=0.0, sealed=False):
    """F7 time of day / intraday momentum (Gao-Han-Li-Zhou): the return from the prior close (or from 09:30) to ``sig_m`` sets the
    direction of a trade held to ``hold_to``. ``thr`` = minimum |return| in ATR units."""
    f = feats(inst, sealed); M = f["M"]
    C = M["C"]
    ref = f["pdc"] if mode == "intraday" else M["O"][:, RTH_OPEN]
    r = (C[:, sig_m - 1] - ref) / f["atr"]
    dd = np.where(r > thr, 1, np.where(r < -thr, -1, 0)).astype(np.int64)
    dd = np.nan_to_num(dd).astype(np.int64)
    mm = np.full(f["nd"], sig_m - 1, np.int64)
    st = C[:, sig_m - 1] - dd * sm * f["atr"]
    return _emit(f, inst, mm, dd, st, np.nan, hold_to, f"TOD_{mode}_{sig_m}_{hold_to}_s{sm}_t{thr}@{inst}")


def fam_gold(inst="GC", kind="comex", k=30, stop="opp", R=2.0, cut=240, sealed=False):
    """F8 gold breakout: COMEX opening range (08:20 + k minutes) or the London session range (03:00 .. 08:19) broken after 08:20."""
    f = feats(inst, sealed); M = f["M"]
    if kind == "comex":
        return fam_orb(inst, k=k, stop=stop, R=R, cut=cut, start=GC_OPEN, exit_m=1290, sealed=sealed)
    hi, lo = f["lh"], f["ll"]
    mm, dd = _first_break(M["H"], M["L"], M["C"], hi, lo, GC_OPEN, GC_OPEN + cut, True)
    st = np.where(dd > 0, lo, hi) if stop == "opp" else (hi + lo) / 2
    return _emit(f, inst, mm, dd, st, R, 1290, f"GCLDN_{stop}_R{R}_c{cut}@{inst}")


def fam_gap(inst, g=0.3, sm=0.5, R=2.0, with_trend=True, entry=935, sealed=False):
    """F9 momentum / regime: gap of at least g x ATR at the open, in the direction of the 20-day trend -> go with it at ``entry``."""
    f = feats(inst, sealed); M = f["M"]
    gap = (M["O"][:, RTH_OPEN] - f["pdc"]) / f["atr"]
    dd = np.where(gap > g, 1, np.where(gap < -g, -1, 0))
    if with_trend:
        dd = np.where(np.sign(f["pdc"] - f["sma20"]) == dd, dd, 0)
    dd = np.nan_to_num(dd).astype(np.int64)
    mm = np.full(f["nd"], entry - 1, np.int64)
    st = M["C"][:, entry - 1] - dd * sm * f["atr"]
    return _emit(f, inst, mm, dd, st, R, 1314, f"GAP_g{g}_s{sm}_R{R}_{'T' if with_trend else 'A'}@{inst}")


# ---- round 2 families from the research papers (research/papers_notes.md); pre-registered grids below
def fam_cmf(inst, thr=0.25, win=20, sm=0.45, R=1.67, t0=1000, t1=1200, sealed=False):
    """F11 Chaikin Money Flow on 1-min RTH bars (Huber, MaxAI): first CLOSE with CMF(win) >= thr (long) or <= -thr (short) in [t0, t1),
    one trade a day, stop sm x ATR, target R. CMF uses RTH bars only, window ends at the signal bar."""
    f = feats(inst, sealed); M = f["M"]; H, L, C, V = M["H"], M["L"], M["C"], M["V"].astype(float)
    rng = H - L
    with np.errstate(invalid="ignore", divide="ignore"):
        mfm = np.where(rng > 0, ((C - L) - (H - C)) / rng, 0.0)
    mv = mfm * V
    mv[:, :RTH_OPEN] = 0.0; Vr = V.copy(); Vr[:, :RTH_OPEN] = 0.0
    cm, cv = np.cumsum(mv, 1), np.cumsum(Vr, 1)
    sm_, sv = cm.copy(), cv.copy()
    sm_[:, win:] -= cm[:, :-win]; sv[:, win:] -= cv[:, :-win]
    with np.errstate(invalid="ignore", divide="ignore"):
        cmf = np.where(sv > 0, sm_ / sv, 0.0)
    seg = cmf[:, t0:t1]
    up, dn = seg >= thr, seg <= -thr
    hit = up | dn
    first = np.where(hit.any(1), hit.argmax(1), -1)
    nd = f["nd"]; mm = np.where(first >= 0, first + t0, -1).astype(np.int64)
    dd = np.zeros(nd, np.int64)
    ii = np.nonzero(first >= 0)[0]
    dd[ii] = np.where(up[ii, first[ii]], 1, -1)
    st = np.where(mm >= 0, C[np.arange(nd), np.maximum(mm, 0)] - dd * sm * f["atr"], np.nan)
    return _emit(f, inst, mm, dd, st, R, 1314, f"CMF_t{thr}_w{win}_s{sm}_R{R}_{t0}@{inst}")


def fam_preorb(inst, a=840, k=15, end=930, R=2.0, sealed=False):
    """F12 pre-RTH range (Levine): range of [a, a+k); first CLOSE beyond it before ``end``, then enter on the first pullback to the range
    middle (bar low <= mid for longs) before ``end``; stop at the far side; target R; flat 15:55."""
    f = feats(inst, sealed); M = f["M"]; H, L, C = M["H"], M["L"], M["C"]
    hi = H[:, a:a + k].max(1); lo = L[:, a:a + k].min(1); mid = (hi + lo) / 2
    mb, db = _first_break(H, L, C, hi, lo, a + k, end, True)
    nd = f["nd"]; mm = np.full(nd, -1, np.int64)
    for i in np.nonzero(mb >= 0)[0]:
        seg = L[i, mb[i] + 1:end] <= mid[i] if db[i] > 0 else H[i, mb[i] + 1:end] >= mid[i]
        if seg.any(): mm[i] = mb[i] + 1 + int(seg.argmax())
    st = np.where(db > 0, lo, hi)
    return _emit(f, inst, mm, db, st, R, 1314, f"PREORB_{a}_{k}_e{end}_R{R}@{inst}")


def fam_rev(inst, thr=0.3, sig_m=990, sm=0.35, R=np.nan, sealed=False):
    """F13 short-term reversal (Waldow et al.): prior RTH session moved >= thr x ATR; if the first hour (09:30 -> sig_m close) has already
    turned against it, trade with the first hour from sig_m, stop sm x ATR, target R (nan = hold to 15:55)."""
    f = feats(inst, sealed); M = f["M"]; O, C = M["O"], M["C"]
    po = np.r_[np.nan, O[:-1, RTH_OPEN]]
    pr = (f["pdc"] - po) / f["atr"]
    fh = C[:, sig_m - 1] - O[:, RTH_OPEN]
    dd = np.where((np.abs(pr) >= thr) & (np.sign(fh) == -np.sign(pr)), np.sign(fh), 0)
    dd = np.nan_to_num(dd).astype(np.int64)
    mm = np.full(f["nd"], sig_m - 1, np.int64)
    st = C[:, sig_m - 1] - dd * sm * f["atr"]
    return _emit(f, inst, mm, dd, st, R, 1314, f"REV_t{thr}_{sig_m}_s{sm}_R{R}@{inst}")


def _filter(f, filt, width):
    if filt == "none": return np.ones(f["nd"], bool)
    if filt == "comp": return f["prng"] < 0.7 * f["atr"]                     # compressed prior session
    if filt == "narrow": return width < 0.35 * f["atr"]                      # narrow opening range
    if filt == "wide": return width >= 0.35 * f["atr"]
    if filt == "trend": return np.abs(f["ret20"]) > 0.03
    raise ValueError(filt)


# --------------------------------------------------------------------------------------------------------------------- grids
def grids():
    """(family, function, instrument list, parameter dict list). F10 multi-timeframe confluence = the trend_only ORB variants."""
    G = []
    idx = ("NQ", "ES")
    G.append(("F1_orb", fam_orb, idx + ("GC",), [dict(k=k, stop=s, R=R, filt=fl, cut=c) for k in (5, 15, 30, 60) for s in ("opp", "mid", "atr")
                                                 for R in (1.0, 2.0, 3.0, np.nan) for fl in ("none", "comp", "narrow") for c in (150, 360)]))
    G.append(("F10_mtf", fam_orb, idx, [dict(k=k, stop=s, R=R, cut=c, trend_only=True) for k in (15, 30) for s in ("opp", "mid")
                                       for R in (1.5, 2.0, 3.0, np.nan) for c in (150, 360)]))
    G.append(("F2_orbfade", fam_orb_fade, idx + ("GC",), [dict(k=k, R=R, filt=fl, cut=c) for k in (15, 30, 60) for R in (1.0, 1.5, 2.0, 3.0)
                                                          for fl in ("none", "wide") for c in (180, 360)]))
    G.append(("F3_vwappb", fam_vwap_pb, idx + ("GC",), [dict(R=R, sm=s, t1=t, trend=tr) for R in (1.0, 2.0, 3.0) for s in (0.2, 0.35, 0.5)
                                                       for t in (1140, 1260) for tr in ("or", "daily")]))
    G.append(("F4_sweep", fam_sweep, idx + ("GC",), [dict(level=lv, R=R, cut=c) for lv in ("on", "pd") for R in (1.0, 1.5, 2.0, 3.0, np.nan)
                                                    for c in (30, 60, 90, 180)]))
    G.append(("F5_pdlbreak", fam_pdl_break, idx + ("GC",), [dict(R=R, sm=s, vol=v, t0=t0) for R in (1.0, 2.0, 3.0) for s in (0.25, 0.5)
                                                           for v in ("any", "low", "high") for t0 in (960, 1020)]))
    G.append(("F6_meanrev", fam_mr, idx + ("GC",), [dict(z=z, win=w, sm=s, R=R) for z in (2.0, 2.5, 3.0) for w in (20, 45) for s in (0.25, 0.4)
                                                   for R in (0.75, 1.0, 1.5)]))
    G.append(("F7_tod", fam_tod, idx + ("GC",), [dict(sig_m=sg, hold_to=h, sm=s, mode=md, thr=th) for sg, h in ((1290, 1319), (1260, 1319), (990, 1314), (1170, 1314))
                                                for s in (0.2, 0.4) for md in ("intraday", "rth") for th in (0.0, 0.25)]))
    G.append(("F8_gold", fam_gold, ("GC",), [dict(kind="comex", k=k, stop=s, R=R, cut=c) for k in (15, 30, 60) for s in ("opp", "mid")
                                            for R in (1.0, 2.0, 3.0, np.nan) for c in (120, 240)]
             + [dict(kind="london", stop=s, R=R, cut=c) for s in ("opp", "mid") for R in (1.0, 2.0, 3.0, np.nan) for c in (60, 120, 240)]))
    G.append(("F9_gap", fam_gap, idx + ("GC",), [dict(g=g, sm=s, R=R, with_trend=t) for g in (0.2, 0.4, 0.6) for s in (0.3, 0.5)
                                                for R in (1.5, 2.0, 3.0) for t in (True, False)]))
    G.append(("F11_cmf", fam_cmf, idx + ("GC",), [dict(thr=t, win=w, sm=s, R=R) for t in (0.25, 0.35) for w in (20, 40) for s in (0.3, 0.45)
                                                 for R in (1.67, 2.5)]))
    G.append(("F12_preorb", fam_preorb, idx, [dict(a=a, k=k, end=e, R=R) for a, k in ((840, 15), (870, 30)) for e in (930, 960) for R in (1.5, 2.0, 3.0)]))
    G.append(("F13_rev", fam_rev, idx + ("GC",), [dict(thr=t, sig_m=sg, sm=s, R=R) for t in (0.3, 0.6) for sg in (990, 1020) for s in (0.25, 0.4)
                                                 for R in (2.0, np.nan)]))
    return G
