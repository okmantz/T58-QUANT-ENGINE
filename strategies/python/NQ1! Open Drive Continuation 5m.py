"""
NQ1! Open-Drive Continuation 5m  (T58 Strategy 01 — Trend Continuation / intraday momentum)

Hypothesis: when NQ has already moved away from the regular-session open by the 10:25 ET bar close, the move persists into the close more
often than a 0.35-ATR stop costs (intraday momentum, Gao et al. JFE 2018; Zarattini-Aziz 2024). One trade per day, hold to 15:50 ET.

Rules (New York clock, 5m bars, RTH 09:30-16:00):
  ATR     = mean RTH high-low range of the previous 14 sessions (prior data only).
  TRIGGER = the 10:25 bar CLOSE is at least MINMOVE x ATR away from the 09:30 session open; direction = sign of that move.
  ENTRY   = next bar open (10:30), engine lag. One entry per session.
  STOP    = STOPK x ATR from entry (stop_loss_distance, points). No profit target. EXIT = stop, or flat at 15:55 (signal off at the 15:50 bar).
Objective: FUNDED (steadiest of the three: ~49% win rate, positive every year 2020-2025).
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


STRATEGY_NAME = "NQ Open-Drive Continuation 5m"
TIMEFRAME = "5m"
WARMUP_BARS = 0
MAX_TRADES_PER_DAY = 1
EXCLUDE_DAYS_OF_WEEK = [5, 6]
S0, S1 = 570, 955          # RTH 09:30-16:00 ET (bar-start minutes)
ENTRY_MIN = 630            # entry bar 10:30 ET; trigger uses the close of the bar before it
FLAT_MIN = 950             # signal off at the 15:50 bar -> exit at the 15:55 open
STOPK = 0.35               # stop = STOPK x ATR14 (points)
MINMOVE = 0.10             # |close(10:25) - session open| >= MINMOVE x ATR14


def generate_signals(df):
    P = _prep(df, S0, S1)
    n = len(df); sig = np.zeros(n); slp = np.full(n, np.nan)
    mod, o, c = P["mod"], P["o"], P["c"]
    for si, (a, e) in enumerate(P["ses"]):
        atr = P["atr"][si]
        if si < 1 or not np.isfinite(atr):
            continue
        js = np.flatnonzero(mod[a:e] == ENTRY_MIN)
        if len(js) == 0:
            continue
        j0 = a + int(js[0])
        if j0 <= a:
            continue
        mv = c[j0 - 1] - o[a]
        if abs(mv) < MINMOVE * atr:
            continue
        d = 1 if mv > 0 else -1
        for j in range(j0 - 1, e):
            if mod[j] >= FLAT_MIN:
                break
            sig[j] = d; slp[j] = STOPK * atr
    out = pd.Series(sig.astype(int), index=df.index)
    out.attrs["stop_loss_distance"] = pd.Series(slp, index=df.index)
    return out
