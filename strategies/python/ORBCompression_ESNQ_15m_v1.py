"""
Opening-Range Breakout after a compressed day, 15m  (T58 three-bots research, 2026-11-20)

Hypothesis: when the prior regular session was compressed (range < 0.7 x the mean of the 14 sessions before it), the first 15 minutes set
the day's direction more often than not: a 15m close outside the first bar's range starts a move that pays 2R more often than it costs 1R.

Rules (New York clock, 15m bars, RTH 09:30-16:15 ET):
  OR      = high / low of the 09:30 bar. Prior-session range and its 14-session mean come from completed sessions only (causal).
  FILTER  = prior RTH range < 0.7 x mean(prior 14 RTH ranges).
  TRIGGER = first 15m CLOSE above OR high (long) / below OR low (short) on a bar that opens before 12:00 ET. One entry per session.
  ENTRY   = next bar open. STOP = far side of the opening range (distance from the signal close). TARGET = 2R. FLAT from the 16:00 ET bar.
Research (scripts in t58-three-bots/scripts, 15m sim, 1-tick slippage, $1/micro): ES net R per trade train 0.225 / val 0.096 / 2025-26 0.196;
sealed holdout Mar-Nov 2026 ES +0.22R over 42 trades (t 1.3), NQ -0.13R over 24 trades. A lead with a modest edge, not a verdict.
"""

import numpy as np
import pandas as pd

TZ = "America/New_York"
STRATEGY_NAME = "Compression ORB 15m"
TIMEFRAME = "15m"
WARMUP_BARS = 0
MAX_TRADES_PER_DAY = 1
EXCLUDE_DAYS_OF_WEEK = [5, 6]
S0, S1 = 570, 975            # 09:30 .. 16:15 ET (bar open times < S1)
LAST_ENTRY = 720             # signal bar must open before 12:00 ET
FLAT_AT = 960                # flat from the 16:00 ET bar
NR = 0.70
TGT_R = 2.0


def _sessions(df):
    ts = pd.to_datetime(df["timestamp"])
    loc = ts.dt.tz_convert(TZ) if ts.dt.tz is not None else ts.dt.tz_localize("UTC").dt.tz_convert(TZ)
    mod = (loc.dt.hour * 60 + loc.dt.minute).to_numpy()
    day = loc.dt.normalize().dt.tz_localize(None).to_numpy()
    dow = loc.dt.dayofweek.to_numpy()
    rth = (mod >= S0) & (mod < S1) & (dow < 5)
    di = np.flatnonzero(rth)
    ses = []
    if len(di):
        dts = day[di]
        brk = np.flatnonzero(np.r_[True, dts[1:] != dts[:-1]])
        starts = di[brk]
        ends = di[np.r_[brk[1:], len(di)] - 1] + 1
        ses = [(int(a), int(e)) for a, e in zip(starts, ends)]
    return mod, ses


def generate_signals(df):
    mod, ses = _sessions(df)
    h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    n = len(df); sig = np.zeros(n); slp = np.full(n, np.nan); tpp = np.full(n, np.nan)
    rng = np.array([h[a:e].max() - l[a:e].min() for a, e in ses]) if ses else np.zeros(0)
    full = np.array([mod[a] == S0 and (e - a) >= 20 for a, e in ses], dtype=bool) if ses else np.zeros(0, dtype=bool)
    for si, (a, e) in enumerate(ses):
        if si < 15 or not full[si] or not full[si - 1]:
            continue
        prev = np.flatnonzero(full[:si])[-15:-1]            # the 14 complete sessions before yesterday's (as research: ADR14 shifted, prior range vs it)
        if len(prev) < 14:
            continue
        adr = rng[np.flatnonzero(full[:si])[-14:]].mean()   # mean of the 14 complete sessions before today (includes yesterday)
        if not (rng[si - 1] < NR * adr):
            continue
        oh, ol = h[a], l[a]
        for j in range(a + 1, e):
            if mod[j] >= LAST_ENTRY:
                break
            d = 1 if c[j] > oh else (-1 if c[j] < ol else 0)
            if not d:
                continue
            stop = (c[j] - ol) if d > 0 else (oh - c[j])
            if stop <= 0:
                break
            for k in range(j, e):
                if mod[k] >= FLAT_AT:
                    break
                sig[k] = d; slp[k] = stop; tpp[k] = TGT_R * stop
            break
    out = pd.Series(sig.astype(int), index=df.index)
    out.attrs["stop_loss_distance"] = pd.Series(slp, index=df.index)
    out.attrs["take_profit_distance"] = pd.Series(tpp, index=df.index)
    return out
