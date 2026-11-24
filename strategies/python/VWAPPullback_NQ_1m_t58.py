"""
NQ1! VWAP pullback in the daily trend (T58 factory leg VWPB_NQ)

Hypothesis: With the prior close above (below) its 20-day mean and price above (below) RTH VWAP at 10:00 ET, the first touch of VWAP that closes back on the trend side before 15:00 resumes the trend.

Rules (New York clock, 1m bars): Stop: 0.35 ATR14. Target 2R. Flat at the 15:55 ET open.
Entry: the repo engine fills at the open of the bar after the signal bar. One trade per session.
Ported from code/factory.py (T58 final bots, 2026-11). Verified against the factory book by code/verify_ports.py.
"""

import numpy as np
import pandas as pd

TZ = "America/New_York"
TIMEFRAME = "1m"
WARMUP_BARS = 0
MAX_TRADES_PER_DAY = 1
EXCLUDE_DAYS_OF_WEEK = [5, 6]
RTH0, RTH1 = 570, 960                      # 09:30 .. 16:00 ET, minutes of the New York day
FLAT = 954                                 # signal drops to 0 on the 15:54 bar: the engine exits at the 15:55 open


def _sessions(df):
    """Session tables. A session starts at 18:00 ET (the futures day); RTH statistics come from its 09:30-15:59 bars."""
    ts = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(TZ)
    mod = (ts.dt.hour * 60 + ts.dt.minute).to_numpy()
    cal = ts.dt.tz_localize(None).dt.normalize()
    sday = np.where(mod >= 1080, (cal + pd.Timedelta(days=1)).to_numpy(), cal.to_numpy()).astype("datetime64[D]")
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    v = df["volume"].to_numpy(float) if "volume" in df else np.ones(len(df))
    days, inv = np.unique(sday, return_inverse=True)
    nd = len(days)
    rth = (mod >= RTH0) & (mod < RTH1)
    rh = np.full(nd, np.nan); rl = np.full(nd, np.nan); rc = np.full(nd, np.nan); nb = np.zeros(nd, int)
    idx = [[] for _ in range(nd)]
    for i in np.flatnonzero(rth):
        idx[inv[i]].append(i)
    for d in range(nd):
        ii = idx[d]
        if ii:
            rh[d] = h[ii].max(); rl[d] = l[ii].min(); rc[d] = c[ii[-1]]; nb[d] = len(ii)
    rng = rh - rl
    sh = lambda x: np.r_[np.nan, x[:-1]]
    atr = np.array([np.nan if d < 14 else np.nanmean(rng[d - 14:d]) for d in range(nd)])
    sma20 = np.array([np.nan if d < 20 else np.nanmean(rc[d - 20:d]) for d in range(nd)])
    atr_pct = np.array([np.nan if d < 120 else np.mean(atr[d - 120:d] < atr[d]) for d in range(nd)])
    return dict(mod=mod, o=o, h=h, l=l, c=c, v=v, idx=idx, nd=nd, atr=atr, sma20=sma20, atr_pct=atr_pct,
                pdh=sh(rh), pdl=sh(rl), pdc=sh(rc), prng=sh(rng))


def _hold(sig, slp, tpp, P, ii, j, d, stop_dist):
    """Hold direction d from bar j until the flat bar; per-bar stop/target distances (target = TGT_R x stop)."""
    for k in ii:
        if k < j:
            continue
        if P["mod"][k] >= FLAT:
            break
        sig[k] = d; slp[k] = stop_dist; tpp[k] = TGT_R * stop_dist


def _complete(P, ii, j):
    """Data guard, causal: at least 80% of the 1m bars from 09:30 through the signal bar are present (skips holidays, early closes and
    feed gaps; the research books dropped sessions with under 80% of their RTH bars)."""
    n = sum(1 for k in ii if k <= j)
    return n >= 0.8 * (P["mod"][j] - RTH0 + 1)


def _out(df, sig, slp, tpp):
    s = pd.Series(sig.astype(int), index=df.index)
    s.attrs["stop_loss_distance"] = pd.Series(slp, index=df.index)
    s.attrs["take_profit_distance"] = pd.Series(tpp, index=df.index)
    return s

STRATEGY_NAME = 'NQ VWAP pullback (T58)'
TREND_AT = 600
LAST_SIGNAL = 900
TGT_R = 2.0
STOP_ATR = 0.35


def generate_signals(df):
    P = _sessions(df); n = len(df)
    sig = np.zeros(n); slp = np.full(n, np.nan); tpp = np.full(n, np.nan)
    mod, h, l, c, v = P["mod"], P["h"], P["l"], P["c"], P["v"]
    for d in range(1, P["nd"]):
        atr = P["atr"][d]; ii = [i for i in P["idx"][d]]
        if not np.isfinite(atr) or not np.isfinite(P["pdc"][d]) or not ii:
            continue
        tp = (h[ii] + l[ii] + c[ii]) / 3.0; cv = np.cumsum(v[ii]); vw = np.where(cv > 0, np.cumsum(v[ii] * tp) / np.where(cv > 0, cv, 1), np.nan)
        pos = {i: q for q, i in enumerate(ii)}
        pre = [i for i in ii if mod[i] < TREND_AT]
        if not pre:
            continue
        j0 = pre[-1]; c10 = c[j0]; vw10 = vw[pos[j0]]
        up = P["pdc"][d] > P["sma20"][d]; dn = P["pdc"][d] < P["sma20"][d]
        tr = 1 if (up and c10 > vw10) else (-1 if (dn and c10 < vw10) else 0)
        if tr == 0:
            continue
        for j in ii:
            if mod[j] < TREND_AT:
                continue
            if mod[j] >= LAST_SIGNAL:
                break
            x = vw[pos[j]]
            if not np.isfinite(x):
                continue
            if (tr > 0 and l[j] <= x and c[j] > x) or (tr < 0 and h[j] >= x and c[j] < x):
                if _complete(P, ii, j):
                    _hold(sig, slp, tpp, P, ii, j, tr, STOP_ATR * atr)
                break
    return _out(df, sig, slp, tpp)
