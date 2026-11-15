"""
ES1! Compression Opening-Range Breakout 5m  (T58 Strategy 04 — Volatility Expansion and Breakout)

Hypothesis: when the prior session was not an expansion day (range <= 1.1 x ATR14) and the first 30 minutes form a NARROW opening range
(<= 0.30 x ATR14), a close outside that range starts an expansion that pays 3R more often than the opposite end of the range costs.

Rules (New York clock, 5m bars, RTH 09:30-16:00):
  OR      = high/low of the first 30 minutes (09:30-09:55 bars). Skip if width > 0.30 ATR14 or < 0.03 ATR14, or prior-session range > 1.1 ATR14.
  TRIGGER = first 5m CLOSE beyond OR high + 0.02 ATR (long) / OR low - 0.02 ATR (short) before 14:00 ET. Skip if the stop would exceed 0.6 ATR.
  ENTRY   = next bar open. One entry per session. STOP = opposite end of the opening range (distance from the signal close).
  TARGET  = 3R. EXIT = stop, target, or flat at the 15:55 open.
Objective: FUNDED/EVAL support leg (low frequency, ~6 trades a month, positive every year 2020-2025).
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


STRATEGY_NAME = "ES Compression Opening-Range Breakout 5m"
TIMEFRAME = "5m"
WARMUP_BARS = 0
MAX_TRADES_PER_DAY = 1
EXCLUDE_DAYS_OF_WEEK = [5, 6]
S0, S1 = 570, 955
OR_MIN = 30
BUF = 0.02
TGT_R = 3.0
WMAX = 0.30                 # opening-range width cap, x ATR14
PRMAX = 1.10                # prior-session range cap, x ATR14
TMAX = S0 + 270             # no entries from 14:00 ET on
STOP_CAP = 0.60


def generate_signals(df):
    P = _prep(df, S0, S1)
    n = len(df); sig = np.zeros(n); slp = np.full(n, np.nan); tpp = np.full(n, np.nan)
    mod, h, l, c = P["mod"], P["h"], P["l"], P["c"]
    nb = OR_MIN // 5
    for si, (a, e) in enumerate(P["ses"]):
        atr = P["atr"][si]
        if si < 1 or not np.isfinite(atr):
            continue
        oh = h[a:a + nb].max(); ol = l[a:a + nb].min(); w = oh - ol
        if w > WMAX * atr or w < 0.03 * atr or P["rng"][si - 1] > PRMAX * atr:
            continue
        for j in range(a + nb, e):
            if mod[j] >= TMAX:
                break
            if c[j] > oh + BUF * atr:
                d = 1
            elif c[j] < ol - BUF * atr:
                d = -1
            else:
                continue
            stop = max((c[j] - ol) if d > 0 else (oh - c[j]), 0.08 * atr)
            if stop > STOP_CAP * atr:
                continue
            for k in range(j, e):
                if mod[k] >= S1 - 5:
                    break
                sig[k] = d; slp[k] = stop; tpp[k] = TGT_R * stop
            break
    out = pd.Series(sig.astype(int), index=df.index)
    out.attrs["stop_loss_distance"] = pd.Series(slp, index=df.index)
    out.attrs["take_profit_distance"] = pd.Series(tpp, index=df.index)
    return out
