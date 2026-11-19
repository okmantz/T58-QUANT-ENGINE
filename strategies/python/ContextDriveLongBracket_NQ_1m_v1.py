"""
Context-Aligned Opening Drive, long only, with a regime-scaled bracket (T58, 2026-11-19). Shipped on NQ in the Payout Hunter (objective B).

Same entries as ContextDriveLong_NQ_1m_v2.py (decision minutes 15/30/45/90/120/180 after the open, daily 50/200 EMA context, gap alignment,
close in the top 30% of the range and above VWAP, drive between 0.15 and 0.6 x ATR14, static news blackout, long only); the exit is a fixed bracket:
  STOP   = 0.20 x ATR14 from entry (stop_loss_distance), ATR14 = mean RTH range of the previous 14 sessions (prior data only). No trailing stop.
  TARGET = 3 x the stop (take_profit_distance). EXIT = stop, target, or flat at 15:55 ET. After a stop or a target a later decision minute
           may enter again (same rule as v2).
Chosen on 2019-10..2023-12, confirmed on 2024, read once on 2025-2026 (docs/T58_BOT_AB_COMBOS_2026-11-19.md). Engine run 2020-2026 on NQ:
254 trades, profit factor 1.74.
"""

import numpy as np
import pandas as pd

STRATEGY_NAME = "Context Drive Long Bracket NQ 1m (0.2 ATR stop, 3R target)"
EXCLUDE_DAYS_OF_WEEK = [5, 6]
WARMUP_BARS = 0                  # the strategy keeps itself flat until it has 14 complete prior sessions

TZ = "America/New_York"
TS_IS_BAR_END = False            # True if your data stamps each bar with its CLOSE time (most vendors: open time)

DECISION_MINUTES = (15, 30, 45, 90, 120, 180)   # minutes after the 09:30 open (check at the close of that minute)
HTF_FILTER = 1                   # 1 = trade only with the daily 50/200 EMA context (prior closes only)
EXT_MAX_ATR = 0.6                # >0: skip when the drive already exceeds this x ATR14 (do not chase)
MIN_MOVE_ATR = 0.15              # |close - open| >= this * ATR14
ATR_DAYS = 14
CLOSE_POS = 0.7                  # close must be in the top (or bottom) 30% of the since-open range
REQUIRE_GAP_ALIGN = True         # the filter that mattered most
STOP_ATR = 0.20                  # stop = STOP_ATR x ATR14 (regime-scaled bracket; no trailing stop)
TP_R = 3.0                     # target = TP_R x stop
FLAT_MIN = 385                   # minutes after 09:30 -> 15:55
SESSION_START = 9 * 60 + 30
SESSION_MIN = 390

LONG_ONLY = 1                    # 1 = drop the short side (shorts earned +0.02R vs +0.40R long in the 2019-2026 sample)
NEWS_BLACKOUT = True             # static time-of-day blackout on new entries (see header, item 3)
NEWS_TIMES = (8 * 60 + 30, 10 * 60, 14 * 60)    # 08:30, 10:00, 14:00 ET as minutes after midnight
NEWS_WINDOW_MIN = 3              # +/- minutes around each release


def _bar_minutes(ts):
    d = ts.diff().dt.total_seconds().dropna()
    d = d[d > 0]
    return int(round(float(d.median()) / 60.0)) if len(d) else 1


def _in_news(minute_of_day):
    return any(abs(minute_of_day - t) <= NEWS_WINDOW_MIN for t in NEWS_TIMES)


def generate_signals(df):
    n = len(df)
    sig = np.zeros(n)
    sl = np.full(n, np.nan)
    tgt = np.full(n, np.nan)

    def _out():
        # Safety net: never emit a position row without a strategy stop (engine would apply a ~1%-of-price fallback).
        bad = (sig != 0) & ~np.isfinite(sl)
        if bad.any():
            sig[bad] = 0
        out = pd.Series(sig.astype(int), index=df.index)
        out.attrs["stop_loss_distance"] = pd.Series(sl, index=df.index)
        out.attrs["take_profit_distance"] = pd.Series(tgt, index=df.index)
        return out

    ts = pd.to_datetime(df["timestamp"])
    loc = ts.dt.tz_convert(TZ) if ts.dt.tz is not None else ts.dt.tz_localize("UTC").dt.tz_convert(TZ)
    bar = _bar_minutes(loc)
    if bar not in (1, 5):
        raise ValueError(f"Load a 1-minute (or 5-minute) dataset; this one looks like {bar}-minute bars.")
    if TS_IS_BAR_END:
        loc = loc - pd.Timedelta(minutes=bar)
    S = SESSION_MIN // bar
    k_min = (loc.dt.hour * 60 + loc.dt.minute - SESSION_START).to_numpy()
    in_rth = (k_min >= 0) & (k_min < SESSION_MIN)
    date = loc.dt.date.to_numpy()

    t = pd.DataFrame({"date": date[in_rth], "slot": k_min[in_rth] // bar, "pos": np.flatnonzero(in_rth)})
    t = t.drop_duplicates(["date", "slot"])
    if t.empty:
        return _out()
    codes, days = pd.factorize(t["date"], sort=True)
    pos = np.full((len(days), S), -1, dtype=np.int64)
    pos[codes, t["slot"].to_numpy()] = t["pos"].to_numpy()
    nd = len(days)
    ok = pos >= 0

    def grab(col, fill):
        a = df[col].to_numpy(float) if col in df.columns else np.full(n, fill)
        return np.where(ok, a[np.where(ok, pos, 0)], np.nan)

    O, H, L, C = grab("open", np.nan), grab("high", np.nan), grab("low", np.nan), grab("close", np.nan)
    V = np.nan_to_num(grab("volume", 1.0), nan=0.0)

    tp = np.nan_to_num((H + L + C) / 3.0, nan=0.0)
    cum_v = np.cumsum(V, axis=1)
    vwap = np.where(cum_v > 0, np.cumsum(tp * V, axis=1) / np.where(cum_v > 0, cum_v, 1.0), C)

    with np.errstate(all="ignore"):
        day_range = np.nanmax(H, axis=1) - np.nanmin(L, axis=1)
    # last close of each complete-enough session (previous session's final traded price)
    last_close = np.full(nd, np.nan)
    for d in range(nd):
        row = C[d][np.isfinite(C[d])]
        if len(row):
            last_close[d] = row[-1]

    ema50 = pd.Series(last_close).ffill().ewm(span=50, adjust=False).mean().to_numpy()
    ema200 = pd.Series(last_close).ffill().ewm(span=200, adjust=False).mean().to_numpy()
    flat_slot = max(0, (FLAT_MIN - bar) // bar)      # signal is 0 on this bar -> engine exits at the 15:55 open
    checks = {}
    for m in DECISION_MINUTES:
        if m % bar == 0:
            checks[m // bar - 1] = True              # slot index of the bar that CLOSES at minute m

    # bars seen so far today, by slot (causal: never uses how many bars the day ends up having)
    seen = np.cumsum(ok, axis=1)
    for d in range(ATR_DAYS + 1, nd):
        o = O[d, 0]
        pc = last_close[d - 1]
        if not (np.isfinite(o) and np.isfinite(pc)):
            continue
        atr = np.nanmean(day_range[d - ATR_DAYS: d])
        if not np.isfinite(atr) or atr <= 0:
            continue
        gap_dir = np.sign(o - pc)
        if d - 1 >= 200:
            dtr = 1 if (ema50[d - 1] > ema200[d - 1] and last_close[d - 1] > ema200[d - 1]) else (-1 if (ema50[d - 1] < ema200[d - 1] and last_close[d - 1] < ema200[d - 1]) else 0)
        else:
            dtr = 0

        side = 0
        sig_start = -1
        pending_fill = -1
        entry = stop = target = stop_d = tp_d = 0.0
        last_exit_slot = -1

        def close_out(k_exit):
            nonlocal side, sig_start
            if sig_start >= 0 and k_exit > sig_start:
                seg = pos[d, sig_start:k_exit]
                seg = seg[seg >= 0]
                sig[seg] = side
                sl[seg] = stop_d          # stop + target on EVERY row of the segment, not just the decision bar
                tgt[seg] = tp_d
            side = 0
            sig_start = -1

        for k in range(S):
            if pos[d, k] < 0:
                if k >= flat_slot and side != 0:
                    close_out(k)
                    break
                continue
            if k >= flat_slot:
                if side != 0:
                    close_out(k)
                break

            # 1) fill of the pending entry at this bar's open
            if side != 0 and k == pending_fill:
                entry = O[d, k]
                stop = entry - side * stop_d
                target = entry + side * tp_d

            # 2) manage the open position inside this bar (mirrors the engine: stop first, then target; both in one bar counts as the stop)
            if side != 0 and k >= pending_fill:
                hit = (O[d, k] <= stop or L[d, k] <= stop) if side == 1 else (O[d, k] >= stop or H[d, k] >= stop)
                won = (H[d, k] >= target) if side == 1 else (L[d, k] <= target)
                if hit or won:
                    close_out(k)
                    last_exit_slot = k     # a later decision minute may enter again after a stop or a target

            # 3) decision at the close of this bar
            if side == 0 and k in checks and k > last_exit_slot and seen[d, k] >= 0.97 * (k + 1):
                if NEWS_BLACKOUT and _in_news(SESSION_START + (k + 1) * bar):
                    continue
                c = C[d, k]
                hh = np.nanmax(H[d, :k + 1])
                ll = np.nanmin(L[d, :k + 1])
                rng = hh - ll
                mv = c - o
                if rng > 0 and abs(mv) >= MIN_MOVE_ATR * atr:
                    p = (c - ll) / rng
                    s = 0
                    if mv > 0 and p >= CLOSE_POS and c > vwap[d, k]:
                        s = 1
                    elif mv < 0 and p <= 1.0 - CLOSE_POS and c < vwap[d, k]:
                        s = -1
                    if s == -1 and LONG_ONLY:
                        s = 0
                    if s != 0 and REQUIRE_GAP_ALIGN and gap_dir != s:
                        s = 0
                    if s != 0 and HTF_FILTER and dtr != s:
                        s = 0
                    if s != 0 and EXT_MAX_ATR > 0 and abs(mv) > EXT_MAX_ATR * atr:
                        s = 0
                    # no fill bar (missing from the series) -> skip the signal instead of entering without a stop
                    if s != 0 and (k + 1 >= flat_slot or pos[d, k + 1] < 0):
                        s = 0
                    if s != 0:
                        stop_d = float(STOP_ATR * atr)
                        tp_d = float(TP_R * stop_d)
                        side = s
                        sig_start = k
                        pending_fill = k + 1
        else:
            if side != 0:
                close_out(S)

    return _out()
