"""Vectorised twins of the seven T58 MQL5 EAs (see ``_common`` for why they exist and the timing/causality conventions).

Every twin takes (ctx, inputs) and returns (level, stop_dist, target_dist). Inputs are the EA's own ``input`` values, so the
optimiser patching an EA's input line changes the twin. ``TUNABLE`` lists the inputs that are real signal parameters, with their
search bounds; everything else (lots, magic numbers, money risk, break-even/trailing) is deliberately not searched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.strategy.base import StrategyError
from app.strategy.ea_twins._common import (
    Ctx, Inputs, build_levels, calc_distance, htf_groups, htf_ohlc, ma_arr, reject_unsupported, sma_arr,
)


def _day_close_hard(ctx: Ctx, d: int, close_on: bool, hh: int, mm: int) -> int:
    """Bar whose OPEN force-closes day-slot ``d``'s positions (``ctx.n + 1`` = NO close bar: the EA never closes, or the data ends first)."""
    if not close_on:
        return ctx.n + 1
    # the EA closes on the first tick at/after the close time; on a half-day with no such tick it carries to a later day's close time
    for d2 in range(d, min(len(ctx.day_start), d + 6)):
        k = ctx.first_bar_ending_at_or_after(d2, hh * 60 + mm)
        if k >= 0:
            return k + 1
    return ctx.n + 1


# ----------------------------------------------------------------------------------------------------------------------
# T58 Go Long EA -- long once per weekday at a server time, optional "wait for a new day high", closes at a set time
# ----------------------------------------------------------------------------------------------------------------------
def go_long(ctx: Ctx, P: Inputs):
    reject_unsupported(P, "Go Long")
    start = P.int("InpStartHour", 16) * 60 + P.int("InpStartMinute", 30)
    wait_high = P.flag("InpWaitNewDayHigh", False)
    sm, sv = P.mode("InpStopMode", "CALC_MODE_PERCENT"), P.num("InpStopValue", 1.0)
    tm, tv = P.mode("InpTargetMode", "CALC_MODE_OFF"), P.num("InpTargetValue", 0.0)
    close_on = P.flag("InpClosePositions", True)
    ch, cm = P.int("InpCloseHour", 22), P.int("InpCloseMinute", 55)
    entries = []
    for d in range(len(ctx.day_start)):
        a, e = ctx.day_start[d], ctx.day_end[d]
        if ctx.dow[a] in (0, 6):
            continue
        ks = ctx.first_bar_ending_at_or_after(d, start)
        hard = _day_close_hard(ctx, d, close_on, ch, cm)
        if ks < 0 or ks + 1 >= min(hard, ctx.n):
            continue
        if wait_high:
            hi_run = np.maximum.accumulate(ctx.h[a:e])
            cand = np.flatnonzero((ctx.c[a:e] >= hi_run) & (np.arange(a, e) >= ks)) + a
            cand = cand[cand + 1 < min(hard, ctx.n)]
            if not len(cand):
                continue
            ks = int(cand[0])
        px = ctx.c[ks]
        entries.append((ks + 1, 1, calc_distance(sm, sv, px, 0.0, ctx.point), calc_distance(tm, tv, px, 0.0, ctx.point), hard))
    return build_levels(ctx, entries, max_per_day=1)


# ----------------------------------------------------------------------------------------------------------------------
# T58 Turnaround Tuesday EA -- long Monday (if the last completed D1 close is above its D1 MA), out Tuesday
# ----------------------------------------------------------------------------------------------------------------------
def turnaround_tuesday(ctx: Ctx, P: Inputs):
    reject_unsupported(P, "Turnaround Tuesday")
    start = P.int("InpStartHour", 16) * 60 + P.int("InpStartMinute", 30)
    ch, cm = P.int("InpCloseHour", 22), P.int("InpCloseMinute", 55)
    open_dow, close_dow = P.int("InpOpenDow", 1), P.int("InpCloseDow", 2)
    sm, sv = P.mode("InpStopMode", "CALC_MODE_PERCENT"), P.num("InpStopValue", 1.5)
    tm, tv = P.mode("InpTargetMode", "CALC_MODE_OFF"), P.num("InpTargetValue", 0.0)
    use_ma = P.flag("InpUseMA", True)
    ma_p, ma_m = P.int("InpMAPeriods", 200), P.mode("InpMAMethod", "MODE_SMA")
    wait_high = P.flag("InpWaitNewDayHigh", False)

    gid = htf_groups(ctx, 1440)
    _, _, _, dcl = htf_ohlc(ctx, gid)
    dma = ma_arr(dcl, ma_p, ma_m)
    entries = []
    ndays = len(ctx.day_start)
    for d in range(ndays):
        a, e = ctx.day_start[d], ctx.day_end[d]
        if int(ctx.dow[a]) != open_dow:
            continue
        ks = ctx.first_bar_ending_at_or_after(d, start)
        kclose = ctx.first_bar_ending_at_or_after(d, ch * 60 + cm)
        if ks < 0 or (kclose >= 0 and ks >= kclose):
            continue
        g = int(gid[ks])
        if use_ma:
            if g < 1 or not np.isfinite(dma[g - 1]) or dcl[g - 1] <= dma[g - 1]:
                continue
        if wait_high:
            hi_run = np.maximum.accumulate(ctx.h[a:e])
            cand = np.flatnonzero((ctx.c[a:e] >= hi_run) & (np.arange(a, e) >= ks)) + a
            if kclose >= 0:
                cand = cand[cand < kclose]
            if not len(cand):
                continue
            ks = int(cand[0])
        # exit: first close-weekday AFTER the open day, at the close time
        hard = ctx.n + 1
        for d2 in range(d + 1, min(ndays, d + 8)):
            if int(ctx.dow[ctx.day_start[d2]]) == close_dow:
                k2 = ctx.first_bar_ending_at_or_after(d2, ch * 60 + cm)
                hard = ctx.n + 1 if k2 < 0 else k2 + 1
                break
        px = ctx.c[ks]
        entries.append((ks + 1, 1, calc_distance(sm, sv, px, 0.0, ctx.point), calc_distance(tm, tv, px, 0.0, ctx.point), hard))
    return build_levels(ctx, entries, max_per_day=None)


# ----------------------------------------------------------------------------------------------------------------------
# T58 Range Breakout EA -- range between two server times, then a buy-stop above / sell-stop below (one trade per day)
# ----------------------------------------------------------------------------------------------------------------------
def range_breakout(ctx: Ctx, P: Inputs):
    reject_unsupported(P, "Range Breakout")
    if P.int("InpMaxLong", 1) > 1 or P.int("InpMaxShort", 1) > 1:
        raise StrategyError("Range Breakout: more than one fill per side per day is not simulated by the engine twin (InpMaxLong/InpMaxShort must be 1 or 0).")
    rs = P.int("InpRangeStartHour", 16) * 60 + P.int("InpRangeStartMinute", 30)
    re_ = P.int("InpRangeEndHour", 17) * 60 + P.int("InpRangeEndMinute", 0)
    dele = P.int("InpDeleteOrdersHour", 19) * 60 + P.int("InpDeleteOrdersMinute", 0)
    close_on = P.flag("InpClosePositions", True)
    ch, cm = P.int("InpCloseHour", 22), P.int("InpCloseMinute", 55)
    buf = P.num("InpOrderBufferPoints", 0.0) * ctx.point
    sm, sv = P.mode("InpStopMode", "CALC_MODE_FACTOR"), P.num("InpStopValue", 1.0)
    tm, tv = P.mode("InpTargetMode", "CALC_MODE_FACTOR"), P.num("InpTargetValue", 1.5)
    allow_long, allow_short = P.int("InpMaxLong", 1) > 0, P.int("InpMaxShort", 1) > 0
    min_pts, min_pct = P.num("InpMinRangePoints", 0.0), P.num("InpMinRangePercent", 0.0)
    max_pts, max_pct = P.num("InpMaxRangePoints", 0.0), P.num("InpMaxRangePercent", 0.0)
    entries = []
    for d in range(len(ctx.day_start)):
        a, e = ctx.day_start[d], ctx.day_end[d]
        if int(ctx.dow[a]) in (0, 6):
            continue
        m = ctx.minute[a:e]
        rng = np.flatnonzero((m >= rs) & (m < re_)) + a
        if not len(rng):
            continue
        hi, lo = ctx.h[rng].max(), ctx.l[rng].min()
        size, mid = hi - lo, (hi + lo) / 2.0
        if size <= 0:
            continue
        pts, pct = size / ctx.point, size / mid * 100.0
        if (min_pts > 0 and pts < min_pts) or (min_pct > 0 and pct < min_pct) or (max_pts > 0 and pts > max_pts) or (max_pct > 0 and pct > max_pct):
            continue
        live = np.flatnonzero((m >= re_) & (m < dele)) + a
        if not len(live):
            continue
        hard = _day_close_hard(ctx, d, close_on, ch, cm)
        buy_px, sell_px = hi + buf, lo - buf
        up = (ctx.h[live] >= buy_px) & allow_long
        dn = (ctx.l[live] <= sell_px) & allow_short
        both = up & dn
        hit = np.flatnonzero(up | dn)
        if not len(hit):
            continue
        k = int(live[hit[0]])
        if both[hit[0]]:
            side = 1 if ctx.o[k] >= mid else -1
        else:
            side = 1 if up[hit[0]] else -1
        if k + 1 >= min(hard, ctx.n):
            continue
        ref = buy_px if side > 0 else sell_px
        sl_level = ref - side * calc_distance(sm, sv, ref, size, ctx.point) if sv > 0 else None
        tp_level = ref + side * calc_distance(tm, tv, ref, size, ctx.point) if tv > 0 else None
        px = ctx.c[k]
        tick = ctx.point
        sl_d = max(side * (px - sl_level), tick) if sl_level is not None else 0.0
        tp_d = max(side * (tp_level - px), tick) if tp_level is not None else 0.0
        entries.append((k + 1, side, sl_d, tp_d, hard))
    return build_levels(ctx, entries, max_per_day=1)


# ----------------------------------------------------------------------------------------------------------------------
# T58 Fisherman EA -- MA-trend filter + %-retracement entry, %-SL/TP, up to N trades a day
# ----------------------------------------------------------------------------------------------------------------------
def _htf_ma_and_close(ctx: Ctx, minutes: int, period: int, method: str):
    """For every base bar k: (last completed HTF close, MA at that HTF bar) as of the close of bar k's own HTF bar-or-earlier."""
    if minutes <= 0 or minutes == ctx.bar_min:
        return ctx.c.copy(), ma_arr(ctx.c, period, method)
    gid = htf_groups(ctx, minutes)
    _, _, _, cl = htf_ohlc(ctx, gid)
    ma = ma_arr(cl, period, method)
    # decision at the close of base bar k uses the HTF bar completed before the NEXT bar's HTF bar
    nxt = np.r_[gid[1:], gid[-1] + 1] if len(gid) else gid
    prev_g = np.maximum(nxt - 1, 0)
    # if bar k is the last base bar of its HTF bar then HTF bar gid[k] is complete, else the previous one is
    prev_g = np.minimum(prev_g, len(cl) - 1)
    return cl[prev_g], ma[prev_g]


def fisherman(ctx: Ctx, P: Inputs):
    reject_unsupported(P, "Fisherman")
    ret_pct, look = P.num("InpRetracementPercent", 0.35), P.int("InpRetLookback", 8)
    tp_pct, sl_pct = P.num("InpTPPercent", 0.6), P.num("InpSLPercent", 0.6)
    close_on = P.flag("InpClosePositions", True)
    ch, cm = P.int("InpCloseHour", 22), P.int("InpCloseMinute", 45)
    max_day = P.int("InpMaxTradesPerDay", 4)
    do_buy, do_sell = P.flag("InpBuyTrades", True), P.flag("InpSellTrades", True)
    use_ma, use_rsi = P.flag("InpMAFilter", True), P.flag("InpRSIFilter", False)
    if sl_pct <= 0:
        raise StrategyError("Fisherman: InpSLPercent must be > 0.")
    c, h, l, n = ctx.c, ctx.h, ctx.l, ctx.n
    hh = pd.Series(h).rolling(look, min_periods=look).max().to_numpy()
    ll = pd.Series(l).rolling(look, min_periods=look).min().to_numpy()
    pulled = (hh - c) / c * 100.0 >= ret_pct
    bounced = (c - ll) / c * 100.0 >= ret_pct
    up = dn = np.ones(n, bool)
    if use_ma:
        mc, ma = _htf_ma_and_close(ctx, P.tf_minutes("InpMATimeframe", ctx.bar_min), P.int("InpMAPeriods", 200), P.mode("InpMAMethod", "MODE_SMA"))
        up, dn = mc > ma, mc < ma
        up = up & np.isfinite(ma)
        dn = dn & np.isfinite(ma)
    rb = rs = np.ones(n, bool)
    if use_rsi:
        from app.strategy.indicators import rsi as rsi_fn
        r = rsi_fn(pd.Series(c), P.int("InpRSIPeriods", 14)).to_numpy()
        lvl = P.num("InpRSILevel", 40.0)
        rb, rs = r < lvl, r > 100.0 - lvl
    buy = do_buy & up & pulled & rb & np.isfinite(hh)
    sell = do_sell & dn & bounced & rs & np.isfinite(ll)
    ok = (buy ^ sell)
    hard_by_day = {}
    entries = []
    for k in np.flatnonzero(ok[:-1]):
        i = k + 1
        if int(ctx.dow[i]) in (0, 6):
            continue
        d_idx = int(np.searchsorted(ctx.day_start, i, side="right") - 1)
        if close_on and int(ctx.end_minute[k]) >= ch * 60 + cm:
            continue
        if d_idx not in hard_by_day:
            hard_by_day[d_idx] = _day_close_hard(ctx, d_idx, close_on, ch, cm)
        px = c[k]
        entries.append((i, 1 if buy[k] else -1, px * sl_pct / 100.0, px * tp_pct / 100.0 if tp_pct > 0 else 0.0, hard_by_day[d_idx]))
    return build_levels(ctx, entries, max_per_day=max_day)


# ----------------------------------------------------------------------------------------------------------------------
# T58 ATR Candle Breakout EA -- big ATR candle that closes near its extreme, trend filter on a higher timeframe
# ----------------------------------------------------------------------------------------------------------------------
def atr_candle(ctx: Ctx, P: Inputs):
    reject_unsupported(P, "ATR Candle Breakout")
    if P.flag("InpUseMTF", False) or P.flag("InpUseSR", False):
        raise StrategyError("ATR Candle Breakout: the MTF-ATR and S/R filters are not simulated by the engine twin (InpUseMTF / InpUseSR must be false).")
    atr_p, mult = P.int("InpATRPeriod", 14), P.num("InpATRMult", 1.5)
    prox, body = P.num("InpCloseProxPct", 25.0), P.num("InpMinBodyPct", 50.0)
    sl_pct, tp_pct = P.num("InpSLPercent", 0.5), P.num("InpTPPercent", 1.0)
    max_day = P.int("InpMaxTradesPerDay", 3)
    use_time, sh, eh = P.flag("InpUseTime", True), P.int("InpStartHour", 16), P.int("InpEndHour", 22)
    skip_fri, skip_mon = P.flag("InpSkipFriLate", True), P.flag("InpSkipMonEarly", True)
    if sl_pct <= 0:
        raise StrategyError("ATR Candle Breakout: InpSLPercent must be > 0.")
    o, h, l, c, n = ctx.o, ctx.h, ctx.l, ctx.c, ctx.n
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - pc), np.abs(l - pc)]), axis=0)
    tr[0] = h[0] - l[0]
    atr = sma_arr(tr, atr_p)                      # MetaTrader's iATR is a SIMPLE average of true range
    rng = h - l
    with np.errstate(divide="ignore", invalid="ignore"):
        big = (rng > 0) & (rng >= mult * atr)
        bod = (np.abs(c - o) / rng * 100.0 >= body) if body > 0 else np.ones(n, bool)
        bull = ((h - c) / rng * 100.0 <= prox) & (c > o)
        bear = ((c - l) / rng * 100.0 <= prox) & (c < o)
    sig_up, sig_dn = big & bod & bull & ~bear, big & bod & bear & ~bull
    if P.flag("InpUseTrend", True):
        tfm = P.tf_minutes("InpTrendTF", 240)
        gid = htf_groups(ctx, tfm)
        _, _, _, cl = htf_ohlc(ctx, gid)
        tma = ma_arr(cl, P.int("InpTrendPeriod", 50), P.mode("InpTrendMethod", "MODE_EMA"))
        nxt = np.r_[gid[1:], gid[-1] + 1]
        pg = np.minimum(np.maximum(nxt - 1, 0), len(cl) - 1)
        tc, tm_ = cl[pg], tma[pg]
        sig_up = sig_up & (tc > tm_) & np.isfinite(tm_)
        sig_dn = sig_dn & (tc < tm_) & np.isfinite(tm_)
    entries = []
    em = ctx.end_minute
    for k in np.flatnonzero((sig_up | sig_dn) & np.isfinite(atr))[:]:
        i = k + 1
        if i >= n:
            continue
        dow = int(ctx.dow[i])
        if dow in (0, 6):
            continue
        if use_time:
            hour = int(em[k] % 1440) // 60
            if hour < sh or hour >= eh:
                continue
            if skip_fri and dow == 5 and hour >= eh - 2:
                continue
            if skip_mon and dow == 1 and hour < sh + 2:
                continue
        px = c[k]
        entries.append((i, 1 if sig_up[k] else -1, px * sl_pct / 100.0, px * tp_pct / 100.0 if tp_pct > 0 else 0.0, n))
    return build_levels(ctx, entries, max_per_day=max_day)


# ----------------------------------------------------------------------------------------------------------------------
# T58 Ninja Turtle Scalper EA -- Donchian breakout (the just-closed bar breaks the prior N-bar channel), tight %-SL/TP, reverses
# ----------------------------------------------------------------------------------------------------------------------
def ninja_turtle(ctx: Ctx, P: Inputs):
    reject_unsupported(P, "Ninja Turtle")
    per = P.int("InpDCPeriod", 20)
    sl_pct, tp_pct = P.num("InpSLPercent", 0.30), P.num("InpTPPercent", 0.45)
    s0 = P.int("InpSessionStartHour", 16) * 60 + P.int("InpSessionStartMinute", 35)
    s1 = P.int("InpSessionEndHour", 22) * 60 + P.int("InpSessionEndMinute", 55)
    max_day = P.int("InpMaxTradesPerDay", 6)
    if sl_pct <= 0:
        raise StrategyError("Ninja Turtle: InpSLPercent must be > 0.")
    c, h, l, n = ctx.c, ctx.h, ctx.l, ctx.n
    up = pd.Series(h).shift(1).rolling(per, min_periods=per).max().to_numpy()       # channel of the N bars BEFORE the signal bar
    lo = pd.Series(l).shift(1).rolling(per, min_periods=per).min().to_numpy()
    go_l, go_s = c > up, c < lo
    ok = go_l ^ go_s
    entries = []
    hard_by_day = {}
    for k in np.flatnonzero(ok[:-1]):
        i = k + 1
        if int(ctx.dow[i]) in (0, 6):
            continue
        em = int(ctx.end_minute[k])
        if em < s0 or em >= s1:
            continue
        d_idx = int(np.searchsorted(ctx.day_start, i, side="right") - 1)
        if d_idx not in hard_by_day:
            kk = ctx.first_bar_ending_at_or_after(d_idx, s1)
            hard_by_day[d_idx] = ctx.n + 1 if kk < 0 else kk + 1
        px = c[k]
        entries.append((i, 1 if go_l[k] else -1, px * sl_pct / 100.0, px * tp_pct / 100.0 if tp_pct > 0 else 0.0, hard_by_day[d_idx]))
    return build_levels(ctx, entries, max_per_day=max_day, allow_reverse=True)


# ----------------------------------------------------------------------------------------------------------------------
# GATE 27 -- monthly, long-only, 210-day trend + 60-day-vol-targeted legs (US500 / Gold / Oil / USDX). The engine is single
# instrument, so the twin runs ONE leg on whichever market is loaded. Each month is booked as its own trade (a rebalance month)
# so the engine can measure the strategy. Like the EA there is no stop by default (its guards sit at account level);
# ``InpTwinStopSigma`` > 0 adds an optional wide vol-scaled disaster stop.
# ----------------------------------------------------------------------------------------------------------------------
def gate27(ctx: Ctx, P: Inputs):
    sma_w, vol_w = P.int("InpSmaWindow", 210), P.int("InpVolWindow", 60)
    stop_sigma = P.num("InpTwinStopSigma", 0.0)
    gid = htf_groups(ctx, 1440)
    _, _, _, dcl = htf_ohlc(ctx, gid)
    dsma = sma_arr(dcl, sma_w)
    ret = np.r_[np.nan, dcl[1:] / dcl[:-1] - 1.0]
    dvol = pd.Series(ret).rolling(vol_w, min_periods=vol_w).std(ddof=1).to_numpy()
    srv_month = ctx.srv.dt.year.to_numpy() * 12 + ctx.srv.dt.month.to_numpy() - 1
    first = np.flatnonzero(np.r_[True, srv_month[1:] != srv_month[:-1]])
    ends = np.r_[first[1:], ctx.n]
    entries = []
    for a, e in zip(first, ends):
        g = int(gid[a])
        if g < 1 or not np.isfinite(dsma[g - 1]) or not np.isfinite(dvol[g - 1]) or dvol[g - 1] <= 0:
            continue
        if dcl[g - 1] <= dsma[g - 1]:
            continue
        # decision is the month's first bar: filled at the next open, held to the month's last bar
        k = int(a)
        px = ctx.c[k]
        entries.append((k + 1, 1, stop_sigma * dvol[g - 1] * px, 0.0, int(e)))
    return build_levels(ctx, entries, max_per_day=None)


# Inputs that are real signal parameters, with search bounds (lo, hi). Anything not listed is never searched.
TUNABLE: dict[str, dict[str, tuple[float, float]]] = {
    "go_long": {"InpStopValue": (0.2, 3.0), "InpStartHour": (14, 19), "InpStartMinute": (0, 59), "InpCloseHour": (20, 23), "InpCloseMinute": (0, 59)},
    "turnaround_tuesday": {"InpStopValue": (0.3, 4.0), "InpMAPeriods": (20, 300), "InpStartHour": (14, 19), "InpCloseHour": (20, 23), "InpCloseMinute": (0, 59)},
    "range_breakout": {"InpStopValue": (0.3, 3.0), "InpTargetValue": (0.5, 4.0), "InpRangeStartHour": (14, 18), "InpRangeStartMinute": (0, 59),
                       "InpRangeEndHour": (16, 19), "InpRangeEndMinute": (0, 59), "InpMinRangePercent": (0.0, 0.4), "InpMaxRangePercent": (0.0, 2.0)},
    "fisherman": {"InpRetracementPercent": (0.1, 1.0), "InpRetLookback": (3, 30), "InpTPPercent": (0.2, 1.5), "InpSLPercent": (0.2, 1.5),
                  "InpMAPeriods": (20, 400), "InpMaxTradesPerDay": (1, 8), "InpRSILevel": (20, 50)},
    "atr_candle": {"InpATRPeriod": (5, 50), "InpATRMult": (0.8, 3.0), "InpCloseProxPct": (10, 40), "InpMinBodyPct": (0, 80), "InpTrendPeriod": (10, 200),
                   "InpSLPercent": (0.2, 1.5), "InpTPPercent": (0.3, 3.0), "InpMaxTradesPerDay": (1, 6), "InpStartHour": (14, 19), "InpEndHour": (19, 23)},
    "ninja_turtle": {"InpDCPeriod": (5, 80), "InpSLPercent": (0.1, 1.0), "InpTPPercent": (0.1, 1.5), "InpMaxTradesPerDay": (1, 10)},
    "gate27": {"InpSmaWindow": (60, 300)},
}

TWINS = {"go_long": go_long, "turnaround_tuesday": turnaround_tuesday, "range_breakout": range_breakout, "fisherman": fisherman,
         "atr_candle": atr_candle, "ninja_turtle": ninja_turtle, "gate27": gate27}
