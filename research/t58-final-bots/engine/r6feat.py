"""Round 6 new inputs (research/PREREG_R6.md section 4). Every value is known before the trade it filters:
  daily externals (VIX, VIX3M, TICK) use the last close dated BEFORE the session day; FOMC / NFP are calendar flags;
  gap, overnight range and the open's place in the prior value area are known at the 09:30 ET bar open (``KNOWN_AT``): a trade entered
  before 09:30 is never filtered by them."""
import os, sys
sys.path.insert(0, "research/t58_final_bots/engine")
import numpy as np, pandas as pd
import data as D, book, factory as F
EXT = D.WORK / "data_r6" / "ext"
KNOWN_AT = F.RTH_OPEN          # session minute 930 = 09:30 ET
_X = {}

def _daily(name):
    d = pd.read_csv(EXT / f"{name}_1D.csv"); d["date"] = pd.to_datetime(d["date"]).values.astype("datetime64[D]")
    return d.drop_duplicates("date").sort_values("date").set_index("date")["c"].astype(float)

def _prior(series, days):
    """value of the last observation dated strictly before each session day"""
    idx = series.index.values; i = np.searchsorted(idx, days, side="left") - 1
    out = np.where(i >= 0, series.values[np.maximum(i, 0)], np.nan); return out

def _exp_pct(x, minn=250):
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        h = x[:i][np.isfinite(x[:i])]
        if len(h) >= minn and np.isfinite(x[i]): out[i] = (h < x[i]).mean()
    return out

def externals():
    if "ext" in _X: return _X["ext"]
    vix, v3, tick = _daily("VIX"), _daily("VIX3M"), _daily("TICK")
    ev = pd.read_csv(EXT / "events_money_US.csv")
    t = pd.to_datetime(ev["time_utc"], utc=True, format="ISO8601").dt.tz_convert("America/New_York")
    fomc = set(t.dt.tz_localize(None).dt.normalize().values.astype("datetime64[D]"))
    _X["ext"] = (vix, v3, tick, fomc); return _X["ext"]

def day_table(inst):
    """per session day of the inst mats: dict of arrays"""
    if inst in _X: return _X[inst]
    vix, v3, tick, fomc = externals()
    M = book.mats(inst); f = F.feats(inst); days = M["days"]; nd = len(days)
    pv = _prior(vix, days); pv3 = _prior(v3, days); pt = _prior(tick, days)
    v_idx = vix.index.values; i = np.searchsorted(v_idx, days, side="left") - 1
    pv6 = np.where(i >= 5, vix.values[np.maximum(i - 5, 0)], np.nan)
    vixs = vix.values; vpct_all = _exp_pct(vixs); vp = np.where(i >= 0, vpct_all[np.maximum(i, 0)], np.nan)
    O, H, L, C, V = M["O"], M["H"], M["L"], M["C"], M["V"]
    o930 = O[:, KNOWN_AT]; atr = f["atr"]
    gap = (o930 - f["pdc"]) / atr
    onr = (H[:, :KNOWN_AT].max(1) - L[:, :KNOWN_AT].min(1)) / atr
    # prior RTH volume profile: price bins of 4 ticks (ES/NQ 1 pt, GC 0.4), bar volume at its typical price; POC + 70% value area
    va = np.full(nd, np.nan); bw = 4 * D.TICK[inst]
    lo_hi = []
    for k in range(nd):
        if k == 0: lo_hi.append((np.nan, np.nan, np.nan)); continue
        j = k - 1; tp = (H[j, F.RTH_OPEN:F.RTH_CLOSE] + L[j, F.RTH_OPEN:F.RTH_CLOSE] + C[j, F.RTH_OPEN:F.RTH_CLOSE]) / 3; vv = V[j, F.RTH_OPEN:F.RTH_CLOSE]
        if vv.sum() <= 0: lo_hi.append((np.nan, np.nan, np.nan)); continue
        b = np.floor(tp / bw).astype(np.int64); u, inv = np.unique(b, return_inverse=True); vol = np.bincount(inv, vv)
        p = int(vol.argmax()); a, z, tot = p, p, vol[p]
        while tot < 0.7 * vol.sum():
            left = vol[a - 1] if a > 0 else -1; right = vol[z + 1] if z + 1 < len(vol) else -1
            if right >= left: z += 1; tot += vol[z]
            else: a -= 1; tot += vol[a]
        lo_hi.append((u[a] * bw, (u[z] + 1) * bw, (u[p] + 0.5) * bw))
    lo_hi = np.array(lo_hi)
    # the mats are back-adjusted per session (same offset inside a session and its prior session except at rolls): same-basis compare
    va = np.where(o930 > lo_hi[:, 1], 1.0, np.where(o930 < lo_hi[:, 0], -1.0, 0.0)); va[~np.isfinite(lo_hi[:, 0])] = np.nan
    cal = pd.DatetimeIndex(days)
    nfp = np.asarray((cal.dayofweek == 4) & (cal.day <= 7))
    fo = np.array([d in fomc for d in days])
    out = dict(days=days, idx={d: k for k, d in enumerate(days)}, vix_pct=vp, vix_lvl=pv, vix_term=pv / pv3, vix_chg5=pv / pv6, tick=pt,
               gap=gap, gap_abs=np.abs(gap), onr=onr, va=va, nfp=nfp, fomc=fo)
    _X[inst] = out; return out

def _sess_min(t):
    clock = (t.astype("datetime64[m]") - t.astype("datetime64[D]")).astype(int)
    return (clock - 18 * 60) % 1440

def trade_feats(b):
    """per-trade input values (NaN where not known before the entry); directional versions x trade direction."""
    n = len(b["day"]); out = {k: np.full(n, np.nan) for k in ("vix_pct", "vix_term", "vix_chg5", "tick", "tick_dir", "gap_abs", "gap_dir", "onr", "va_dir", "nfp", "fomc_pm")}
    sm = _sess_min(b["entry"])
    for inst in np.unique(b["inst"]):
        T = day_table(inst); m = b["inst"] == inst
        ii = np.array([T["idx"].get(d, -1) for d in b["day"][m]]); ok = ii >= 0; jj = np.maximum(ii, 0)
        dr = b["dir"][m].astype(float); late = sm[m] >= KNOWN_AT
        def put(k, v, cond=None):
            a = np.where(ok, v, np.nan)
            if cond is not None: a = np.where(cond, a, np.nan)
            out[k][m] = a
        put("vix_pct", T["vix_pct"][jj]); put("vix_term", T["vix_term"][jj]); put("vix_chg5", T["vix_chg5"][jj]); put("tick", T["tick"][jj])
        put("tick_dir", T["tick"][jj] * dr); put("gap_abs", T["gap_abs"][jj], late); put("gap_dir", T["gap"][jj] * dr, late)
        put("onr", T["onr"][jj], late); put("va_dir", T["va"][jj] * dr, late)
        put("nfp", T["nfp"][jj].astype(float)); put("fomc_pm", (T["fomc"][jj] & (sm[m] >= 1170)).astype(float))   # 13:30 ET = 1170
    return out
