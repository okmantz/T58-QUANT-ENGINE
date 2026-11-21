"""
Level Breakout with trend filter, 15m  (T58 new-bots research, 2026-11-21)

Hypothesis: the overnight (Globex) high / low and the prior regular session's high / low are where resting stops sit. When the regular
session breaks one of them on a 15m CLOSE in the direction of the daily trend, the stops it triggers feed the move, so it continues for
more than the distance back inside the level costs. (The reversal version, a sweep that reclaims the level, was tested on 2026-11-20 and failed;
this is the opposite bet, filtered by trend.)

Rules (New York clock, 15m bars, RTH 09:30-16:15 ET):
  LEVELS  = MODE "on": overnight high / low (18:00 ET .. 09:30 ET); MODE "pd": prior RTH session high / low.
  TREND   = sign of (prior RTH close - mean of the prior TREND_N RTH closes); TREND_N = 0 turns the filter off. Causal.
  TRIGGER = first 15m close above the high (long) / below the low (short) on a bar opening 09:45..LAST_ENTRY, in the trend direction,
            when the session opened inside the levels (a gap through a level is not a break).
  ENTRY   = next bar open. STOP = STOP_ATR x ATR14 (mean prior 14 RTH ranges) from the signal close. TARGET = TGT_R x stop.
  FLAT    = from the 16:00 ET bar. One entry per session.
"""

import numpy as np
import pandas as pd

TZ = "America/New_York"
STRATEGY_NAME = "Level Breakout 15m"
TIMEFRAME = "15m"
WARMUP_BARS = 0
MAX_TRADES_PER_DAY = 1
EXCLUDE_DAYS_OF_WEEK = [5, 6]
S0, S1 = 570, 975            # 09:30 .. 16:15 ET
MODE = "on"
TREND_N = 20
LAST_ENTRY = 690             # signal bar opens before 11:30 ET
FLAT_AT = 960
STOP_ATR = 0.3
TGT_R = 2.0


def _clock(df):
    ts = pd.to_datetime(df["timestamp"])
    loc = ts.dt.tz_convert(TZ) if ts.dt.tz is not None else ts.dt.tz_localize("UTC").dt.tz_convert(TZ)
    mod = (loc.dt.hour * 60 + loc.dt.minute).to_numpy()
    day = loc.dt.normalize().dt.tz_localize(None).to_numpy()
    dow = loc.dt.dayofweek.to_numpy()
    return mod, day, dow


def generate_signals(df):
    mod, day, dow = _clock(df)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    n = len(df); sig = np.zeros(n); slp = np.full(n, np.nan); tpp = np.full(n, np.nan)
    rth = (mod >= S0) & (mod < S1) & (dow < 5)
    di = np.flatnonzero(rth)
    if not len(di):
        out = pd.Series(sig.astype(int), index=df.index)
        out.attrs["stop_loss_distance"] = pd.Series(slp, index=df.index); out.attrs["take_profit_distance"] = pd.Series(tpp, index=df.index)
        return out
    dts = day[di]
    brk = np.flatnonzero(np.r_[True, dts[1:] != dts[:-1]])
    starts = di[brk]; ends = di[np.r_[brk[1:], len(di)] - 1] + 1
    ses = [(int(a), int(e)) for a, e in zip(starts, ends)]
    full = np.array([mod[a] == S0 and (e - a) >= 20 for a, e in ses], dtype=bool)
    rh = np.array([h[a:e].max() for a, e in ses]); rl = np.array([l[a:e].min() for a, e in ses])
    rc = np.array([c[e - 1] for a, e in ses]); rng = rh - rl
    for si, (a, e) in enumerate(ses):
        if si < 21 or not full[si] or not full[si - 1]:
            continue
        prev = np.flatnonzero(full[:si])
        if len(prev) < max(14, TREND_N):
            continue
        atr = rng[prev[-14:]].mean()
        tr = 0
        if TREND_N:
            tr = 1 if rc[si - 1] > rc[prev[-TREND_N:]].mean() else -1
        if MODE == "on":
            pe = ses[si - 1][1]                     # bars after the prior RTH session, before today's open = overnight
            if a - pe < 4:
                continue
            hi, lo = h[pe:a].max(), l[pe:a].min()
        else:
            hi, lo = rh[si - 1], rl[si - 1]
        if not (lo < o[a] < hi):
            continue
        for j in range(a + 1, e):
            if mod[j] >= LAST_ENTRY:
                break
            d = 1 if c[j] > hi else (-1 if c[j] < lo else 0)
            if not d:
                continue
            if TREND_N and d != tr:
                break
            stop = STOP_ATR * atr
            for k in range(j, e):
                if mod[k] >= FLAT_AT:
                    break
                sig[k] = d; slp[k] = stop; tpp[k] = TGT_R * stop
            break
    out = pd.Series(sig.astype(int), index=df.index)
    out.attrs["stop_loss_distance"] = pd.Series(slp, index=df.index)
    out.attrs["take_profit_distance"] = pd.Series(tpp, index=df.index)
    return out
