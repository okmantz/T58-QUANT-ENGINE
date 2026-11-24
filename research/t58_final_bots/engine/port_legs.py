"""Write repo-style strategy files (strategies/python/*.py, generate_signals(df) -> -1/0/1 with per-bar stop/target distances) for the
T58 factory legs used by the final bots. Each file is self-contained and causal: daily features use prior sessions only; a signal is read
on a CLOSED 1m bar and the repo engine fills at the next bar's open. Stops are expressed as distances from the signal bar's close
(the repo convention), so a fill that gaps away from the close moves the stop by the gap; the factory books used levels. verify_ports.py
measures the difference."""
from pathlib import Path
OUT = Path("research/t58_final_bots/repo_zip/strategies/python")
COMMON = r'''
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
'''
ORB = r'''
def generate_signals(df):
    P = _sessions(df); n = len(df)
    sig = np.zeros(n); slp = np.full(n, np.nan); tpp = np.full(n, np.nan)
    mod, h, l, c = P["mod"], P["h"], P["l"], P["c"]
    for d in range(1, P["nd"]):
        atr = P["atr"][d]; ii = P["idx"][d]
        if not np.isfinite(atr) or not np.isfinite(P["pdc"][d]) or not ii:
            continue
        orb = [i for i in ii if mod[i] < RTH0 + OR_MIN]
        if len(orb) < OR_MIN // 2:
            continue
        hi = h[orb].max(); lo = l[orb].min()
        if FILTER == "comp" and not (P["prng"][d] < 0.7 * atr):
            continue
        for j in ii:
            if mod[j] < RTH0 + OR_MIN:
                continue
            if mod[j] >= LAST_SIGNAL:
                break
            dd = 1 if c[j] > hi else (-1 if c[j] < lo else 0)
            if dd == 0:
                continue
            if TREND_ONLY and np.sign(P["pdc"][d] - P["sma20"][d]) != dd:
                break
            if STOP == "opp":
                lvl = lo if dd > 0 else hi
            else:
                lvl = hi - 0.25 * atr if dd > 0 else lo + 0.25 * atr
            dist = dd * (c[j] - lvl)
            if dist > 0 and _complete(P, ii, j):
                _hold(sig, slp, tpp, P, ii, j, dd, dist)
            break
    return _out(df, sig, slp, tpp)
'''
VWPB = r'''
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
'''
PDLB = r'''
def generate_signals(df):
    P = _sessions(df); n = len(df)
    sig = np.zeros(n); slp = np.full(n, np.nan); tpp = np.full(n, np.nan)
    mod, c = P["mod"], P["c"]
    for d in range(1, P["nd"]):
        atr = P["atr"][d]; ii = P["idx"][d]; hi = P["pdh"][d]; lo = P["pdl"][d]
        if not (np.isfinite(atr) and np.isfinite(hi) and np.isfinite(lo) and np.isfinite(P["pdc"][d])) or not ii:
            continue
        if VOL == "low" and not (P["atr_pct"][d] < 0.5):
            continue
        for j in ii:
            if mod[j] < FIRST_SIGNAL:
                continue
            if mod[j] >= LAST_SIGNAL:
                break
            dd = 1 if c[j] > hi else (-1 if c[j] < lo else 0)
            if dd:
                if _complete(P, ii, j):
                    _hold(sig, slp, tpp, P, ii, j, dd, STOP_ATR * atr)
                break
    return _out(df, sig, slp, tpp)
'''
GAP = r'''
def generate_signals(df):
    P = _sessions(df); n = len(df)
    sig = np.zeros(n); slp = np.full(n, np.nan); tpp = np.full(n, np.nan)
    mod, o = P["mod"], P["o"]
    for d in range(1, P["nd"]):
        atr = P["atr"][d]; ii = P["idx"][d]; pdc = P["pdc"][d]
        if not (np.isfinite(atr) and np.isfinite(pdc) and np.isfinite(P["sma20"][d])) or not ii or mod[ii[0]] != RTH0:
            continue
        g = (o[ii[0]] - pdc) / atr
        dd = 1 if g > GAP_ATR else (-1 if g < -GAP_ATR else 0)
        if dd == 0 or np.sign(pdc - P["sma20"][d]) != dd:
            continue
        j = next((k for k in ii if mod[k] == SIGNAL_AT), None)
        if j is not None and _complete(P, ii, j):
            _hold(sig, slp, tpp, P, ii, j, dd, STOP_ATR * atr)
    return _out(df, sig, slp, tpp)
'''
FILES = {
    "ORB15Compression_NQ_1m_t58": ("NQ1! 15-minute opening-range breakout after a compressed session (T58 factory leg ORB15C_NQ)",
        "After a prior RTH session narrower than 0.7 x ATR14, the first 1m close beyond the 09:30-09:44 range before 12:00 ET runs 3R more often than it loses 1R.",
        "Stop: 0.25 ATR14 inside the far side of the broken edge (hi - 0.25 ATR for longs). Target 3R. Flat at the 15:55 ET open.",
        dict(STRATEGY_NAME="NQ ORB15 compression (T58)", OR_MIN=15, LAST_SIGNAL=720, TGT_R=3.0, STOP="atr", FILTER="comp", TREND_ONLY=False), ORB),
    "ORB15Compression_ES_1m_t58": ("ES1! 15-minute opening-range breakout after a compressed session (T58 factory leg ORB15C_ES)",
        "Same rule as the NQ leg; ES pays at 2R rather than 3R.",
        "Stop: 0.25 ATR14 inside the far side of the broken edge. Target 2R. Flat at the 15:55 ET open.",
        dict(STRATEGY_NAME="ES ORB15 compression (T58)", OR_MIN=15, LAST_SIGNAL=720, TGT_R=2.0, STOP="atr", FILTER="comp", TREND_ONLY=False), ORB),
    "ORB30Trend_NQ_1m_t58": ("NQ1! 30-minute opening-range breakout with the daily trend (T58 factory leg ORB30T_NQ)",
        "A close beyond the 09:30-09:59 range before 12:00 ET in the direction of the prior close vs its 20-day mean continues.",
        "Stop: opposite edge of the opening range. Target 3R. Only the first break counts; a break against the trend ends the day. Flat at the 15:55 ET open.",
        dict(STRATEGY_NAME="NQ ORB30 with trend (T58)", OR_MIN=30, LAST_SIGNAL=720, TGT_R=3.0, STOP="opp", FILTER="none", TREND_ONLY=True), ORB),
    "VWAPPullback_NQ_1m_t58": ("NQ1! VWAP pullback in the daily trend (T58 factory leg VWPB_NQ)",
        "With the prior close above (below) its 20-day mean and price above (below) RTH VWAP at 10:00 ET, the first touch of VWAP that closes back on the trend side before 15:00 resumes the trend.",
        "Stop: 0.35 ATR14. Target 2R. Flat at the 15:55 ET open.",
        dict(STRATEGY_NAME="NQ VWAP pullback (T58)", TREND_AT=600, LAST_SIGNAL=900, TGT_R=2.0, STOP_ATR=0.35), VWPB),
    "PriorDayBreak_GC_1m_t58": ("GC1! prior-day high/low break in a quiet regime (T58 factory leg PDLB_GC)",
        "When ATR14 sits in the lower half of its last 120 sessions, the first 1m close beyond the prior RTH high or low between 10:00 and 14:00 ET runs 3R.",
        "Stop: 0.5 ATR14. Target 3R. Flat at the 15:55 ET open.",
        dict(STRATEGY_NAME="GC prior-day break, low vol (T58)", FIRST_SIGNAL=600, LAST_SIGNAL=840, TGT_R=3.0, STOP_ATR=0.5, VOL="low"), PDLB),
    "GapTrend_GC_1m_t58": ("GC1! opening gap with the daily trend (T58 factory leg GAP_GC)",
        "An RTH open more than 0.4 x ATR14 away from the prior RTH close, in the direction of the prior close vs its 20-day mean, keeps going.",
        "Signal on the 09:34 bar close, entry at the 09:35 open. Stop 0.5 ATR14. Target 3R. Flat at the 15:55 ET open.",
        dict(STRATEGY_NAME="GC gap with trend (T58)", GAP_ATR=0.4, SIGNAL_AT=574, TGT_R=3.0, STOP_ATR=0.5), GAP),
}
for stem, (title, hyp, rules, consts, body) in FILES.items():
    head = f'"""\n{title}\n\nHypothesis: {hyp}\n\nRules (New York clock, 1m bars): {rules}\nEntry: the repo engine fills at the open of the bar after the signal bar. One trade per session.\nPorted from code/factory.py (T58 final bots, 2026-11). Verified against the factory book by code/verify_ports.py.\n"""\n'
    cs = "\n".join(f"{k} = {v!r}" for k, v in consts.items())
    (OUT / f"{stem}.py").write_text(head + COMMON + "\n" + cs + "\n\n" + body)
    print("wrote", stem)
