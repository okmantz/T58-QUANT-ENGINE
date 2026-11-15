"""
NQ1! Liquidity Sweep Reclaim 5m  (T58 Strategy 02 — Liquidity Failure and Reversal)

Hypothesis: a push through an objectively marked liquidity pool (prior-session RTH high/low, or the overnight high/low) that CLOSES back inside
the level on the same 5m bar, with a rejection close (in the far half of the bar), marks failed acceptance and reverses.
Not every sweep: needs a sweep of at least BUF x ATR beyond the level, a reclaim close, and a rejection close.

Rules (New York clock, 5m bars, RTH 09:30-16:00; signal bars 09:30-15:25):
  LEVELS  = prior session RTH high and low; overnight (prior-RTH-close to 09:30) high and low. Long after a low sweep, short after a high sweep.
  TRIGGER = bar extreme beyond the level by > BUF x ATR14, bar CLOSE back inside the level, close in the lower (short) / upper (long) half of the bar.
  ENTRY   = next bar open. First qualifying event of the session only.
  STOP    = beyond the sweep extreme (distance from the signal-bar close + 0.02 ATR); skipped if < 0.10 ATR or > 1.0 ATR.
  TARGET  = TGT_R x stop distance. EXIT = stop, target, or flat at the 15:55 open.
Objective: EVALUATION (33% win rate x 3R: fast, lumpy gains; works best size-scaled by account cushion).
"""

import numpy as np
import pandas as pd

TZ = "America/New_York"


def _prep(df, s0, s1):
    """Causal session tables on the 5m frame. Returns arrays and a list of (first_idx, last_idx_exclusive) RTH sessions."""
    ts = pd.to_datetime(df["timestamp"])
    loc = ts.dt.tz_convert(TZ) if ts.dt.tz is not None else ts.dt.tz_localize("UTC").dt.tz_convert(TZ)
    mod = (loc.dt.hour * 60 + loc.dt.minute).to_numpy()
    day = loc.dt.normalize().dt.tz_localize(None).to_numpy()
    dow = loc.dt.dayofweek.to_numpy()
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    rth = (mod >= s0) & (mod < s1) & (dow < 5)
    di = np.flatnonzero(rth)
    sessions = []
    if len(di):
        dts = day[di]
        brk = np.flatnonzero(np.r_[True, dts[1:] != dts[:-1]])
        starts = di[brk]
        ends = di[np.r_[brk[1:], len(di)] - 1] + 1
        sessions = [(int(a), int(e)) for a, e in zip(starts, ends)]
    n = len(sessions)
    nb = (s1 - s0) // 5
    # A session's own statistics are only ever read by LATER sessions (strictly after it ended), so using its final bar count here is causal.
    full = np.array([(e - a) >= int(0.8 * nb) for a, e in sessions], dtype=bool) if n else np.zeros(0, dtype=bool)
    rng = np.array([h[a:e].max() - l[a:e].min() for a, e in sessions]) if n else np.zeros(0)
    sh = np.array([h[a:e].max() for a, e in sessions]) if n else np.zeros(0)
    sl = np.array([l[a:e].min() for a, e in sessions]) if n else np.zeros(0)
    sc = np.array([c[e - 1] for a, e in sessions]) if n else np.zeros(0)
    atr = np.full(n, np.nan)
    for i in range(14, n):
        prev = np.flatnonzero(full[:i])
        if len(prev) >= 14:
            atr[i] = rng[prev[-14:]].mean()
    return dict(mod=mod, o=o, h=h, l=l, c=c, ses=sessions, rng=rng, sh=sh, sl=sl, sc=sc, atr=atr)


STRATEGY_NAME = "NQ Liquidity Sweep Reclaim 5m"
TIMEFRAME = "5m"
WARMUP_BARS = 0
MAX_TRADES_PER_DAY = 1
EXCLUDE_DAYS_OF_WEEK = [5, 6]
S0, S1 = 570, 955
LAST_SIGNAL_MIN = 925       # no new signals at/after 15:25 ET
BUF = 0.05                  # sweep must exceed the level by BUF x ATR14
TGT_R = 3.0
MIN_STOP_ATR = 0.10
MAX_STOP_ATR = 1.00         # = 2 x sweep_depth_max(0.5)


def generate_signals(df):
    P = _prep(df, S0, S1)
    ts = pd.to_datetime(df["timestamp"])
    n = len(df); sig = np.zeros(n); slp = np.full(n, np.nan); tpp = np.full(n, np.nan)
    mod, o, h, l, c = P["mod"], P["o"], P["h"], P["l"], P["c"]
    ses = P["ses"]
    for si, (a, e) in enumerate(ses):
        atr = P["atr"][si]
        if si < 1 or not np.isfinite(atr):
            continue
        a0 = ses[si - 1][1]
        levels = [(P["sh"][si - 1], -1), (P["sl"][si - 1], 1)]
        if a > a0:
            levels += [(h[a0:a].max(), -1), (l[a0:a].min(), 1)]
        hit = None
        for j in range(a, e):
            if mod[j] >= LAST_SIGNAL_MIN:
                break
            mid = (h[j] + l[j]) / 2
            for L, d in levels:
                if d < 0:
                    if h[j] > L + BUF * atr and c[j] < L and c[j] < mid:
                        ext = h[j]
                    else:
                        continue
                else:
                    if l[j] < L - BUF * atr and c[j] > L and c[j] > mid:
                        ext = l[j]
                    else:
                        continue
                stop = abs(c[j] - ext) + 0.02 * atr
                if stop < MIN_STOP_ATR * atr or stop > MAX_STOP_ATR * atr:
                    continue
                hit = (j, d, stop)
                break
            if hit:
                break
        if not hit:
            continue
        j, d, stop = hit
        for k in range(j, e):
            if mod[k] >= S1 - 5:       # signal off at the 15:50 bar -> flat at the 15:55 open
                break
            sig[k] = d; slp[k] = stop; tpp[k] = TGT_R * stop
    out = pd.Series(sig.astype(int), index=df.index)
    out.attrs["stop_loss_distance"] = pd.Series(slp, index=df.index)
    out.attrs["take_profit_distance"] = pd.Series(tpp, index=df.index)
    return out
