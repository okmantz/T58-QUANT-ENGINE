"""T58 session sleeve (template): one trade a day in a chosen New York clock window, three entry modes.

    MODE "momentum"  the move since WIN0 is at least K x ATR at a bar close inside the entry window -> trade WITH it.
    MODE "fade"      the same trigger -> trade AGAINST it (a fade of the drive), target = TARGET_R x stop.
    MODE "breakout"  the high/low of [WIN0, WIN1) is broken by a bar close inside the entry window -> trade the break.

ATR = mean 00:00-16:00 ET high-low range of the previous 14 sessions (prior data only). The decision is taken on a bar CLOSE and filled at
the next open (engine lag); the position is carried as a level until the stop / target (attached as per-row distances) or FLAT_MIN ET.
Causal by construction: nothing reads a bar later than the one being decided on.
"""
import numpy as np
import pandas as pd

STRATEGY_NAME = "T58 session sleeve"
TIMEFRAME = "5m"
WARMUP_BARS = 0
MAX_TRADES_PER_DAY = 1
EXCLUDE_DAYS_OF_WEEK = [5, 6]
TZ = "America/New_York"

MODE = "momentum"
WIN0 = 180            # measurement window start, minutes after midnight ET
WIN1 = 240            # measurement window end (breakout range end)
ENTRY0 = 240          # earliest decision-bar close, minutes ET
ENTRY1 = 300          # latest decision-bar close, minutes ET
FLAT_MIN = 570        # flat from this minute ET (signal off)
K = 0.15              # trigger size in ATR (momentum / fade)
STOP_K = 0.20         # stop distance in ATR
TARGET_R = 0.0        # target as a multiple of the stop (0 = none)
SIDE = 0              # 0 both, 1 long only, -1 short only
BAR = 5


def generate_signals(df):
    n = len(df)
    sig = np.zeros(n)
    slp = np.full(n, np.nan)
    tpp = np.full(n, np.nan)
    ts = pd.to_datetime(df["timestamp"])
    loc = ts.dt.tz_convert(TZ) if ts.dt.tz is not None else ts.dt.tz_localize("UTC").dt.tz_convert(TZ)
    mod = (loc.dt.hour * 60 + loc.dt.minute).to_numpy()
    day = loc.dt.normalize().dt.tz_localize(None).to_numpy()
    dow = loc.dt.dayofweek.to_numpy()
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    # session table: [00:00, 16:00) ET per calendar day, weekdays only
    inday = (mod < 960) & (dow < 5)
    idx = np.flatnonzero(inday)
    if len(idx) == 0:
        return _out(df, sig, slp, tpp)
    dd = day[idx]
    brk = np.flatnonzero(np.r_[True, dd[1:] != dd[:-1]])
    starts = idx[brk]
    ends = idx[np.r_[brk[1:], len(idx)] - 1] + 1
    sess = [(int(a), int(e)) for a, e in zip(starts, ends)]
    rng = np.array([h[a:e].max() - l[a:e].min() for a, e in sess])
    full = np.array([(e - a) * BAR >= 0.7 * 960 for a, e in sess])
    for si, (a, e) in enumerate(sess):
        if si < 15:
            continue
        prev = np.flatnonzero(full[:si])
        if len(prev) < 14:
            continue
        atr = float(rng[prev[-14:]].mean())
        if not atr > 0:
            continue
        m = mod[a:e]
        w0 = np.flatnonzero(m == WIN0)
        if len(w0) == 0:
            continue
        j0 = a + int(w0[0])
        d = 0
        jd = -1
        if MODE == "breakout":
            rm = (m >= WIN0) & (m < WIN1)
            if rm.sum() < 2:
                continue
            hi, lo = h[a:e][rm].max(), l[a:e][rm].min()
            for j in range(a, e):
                cl = mod[j] + BAR                      # close minute of bar j
                if cl < max(ENTRY0, WIN1) or cl > ENTRY1:
                    continue
                if c[j] > hi + 0.02 * atr:
                    d, jd = 1, j
                elif c[j] < lo - 0.02 * atr:
                    d, jd = -1, j
                if d:
                    break
            stop_d = STOP_K * atr
        else:
            ref = o[j0]
            for j in range(j0, e):
                cl = mod[j] + BAR
                if cl < ENTRY0 or cl > ENTRY1:
                    continue
                mv = c[j] - ref
                if abs(mv) >= K * atr:
                    d = 1 if mv > 0 else -1
                    if MODE == "fade":
                        d = -d
                    jd = j
                    break
            stop_d = STOP_K * atr
        if d == 0 or jd < 0 or (SIDE and d != SIDE):
            continue
        if jd + 1 >= e:
            continue
        for j in range(jd, e):
            if mod[j] >= FLAT_MIN and mod[j] < 960:
                break
            sig[j] = d
            slp[j] = stop_d
            if TARGET_R > 0:
                tpp[j] = TARGET_R * stop_d
    return _out(df, sig, slp, tpp)


def _out(df, sig, slp, tpp):
    out = pd.Series(sig.astype(int), index=df.index)
    out.attrs["stop_loss_distance"] = pd.Series(slp, index=df.index)
    if np.isfinite(tpp).any():
        out.attrs["take_profit_distance"] = pd.Series(tpp, index=df.index)
    return out
