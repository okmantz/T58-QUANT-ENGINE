"""Shared plumbing for the T58 EA "engine twins".

WHY THIS EXISTS. The shipped T58 MQL5 EAs are full MetaTrader programs (CTrade, enums, helper functions, pending orders). The
engine's MQL5 interpreter runs those bar-by-bar in Python, which is far too slow to optimise (tens of minutes for one backtest) and
rejected several of the EAs outright (``SetTypeFillingBySymbol`` etc.). Each EA therefore carries a ``// T58_TWIN=<name>`` directive
and this package holds a vectorised twin of its rules. The twin reads the EA's OWN ``input`` lines from the .mq5 text, so the
optimiser (which patches those lines) and the EA stay one source of truth.

Timing convention. The EAs are written in broker SERVER time (IC-style: GMT+2/+3, midnight = 17:00 New York, i.e. server = New York
+ 7h all year). All twin clocks use that server clock so the EA's hour/minute inputs mean exactly what they mean in MetaTrader.

Causality convention (same as every other Python strategy in the library): ``level[k]`` is the position wanted AFTER bar ``k``
closes and is filled at the open of bar ``k+1``. An EA action at the first tick of bar ``i`` therefore becomes a decision on bar
``i-1``; every condition used is known at that bar's close, so signals are prefix-invariant (the engine's lookahead probe passes).
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from app.strategy.base import StrategyError

SERVER_OFFSET_HOURS = 7          # server = New York + 7h (NY close 17:00 == server midnight), year-round

_INPUT_RE = re.compile(r"^\s*(?:input|sinput)\s+([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*=\s*([^;]+?)\s*;", re.M)


class Inputs:
    """The EA's ``input`` declarations (name -> python value). Enums stay as their identifier string."""

    def __init__(self, code: str):
        self.values: dict[str, object] = {}
        for m in _INPUT_RE.finditer(code):
            self.values[m.group(2)] = self._parse(m.group(3))

    @staticmethod
    def _parse(tok: str):
        tok = tok.split("//")[0].strip()
        low = tok.lower()
        if low in ("true", "false"):
            return low == "true"
        if tok.startswith('"'):
            return tok.strip('"')
        try:
            return int(tok) if re.fullmatch(r"-?\d+", tok) else float(tok)
        except ValueError:
            return tok

    def num(self, name: str, default: float) -> float:
        v = self.values.get(name, default)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else float(default)

    def int(self, name: str, default: int) -> int:
        return int(round(self.num(name, default)))

    def flag(self, name: str, default: bool) -> bool:
        v = self.values.get(name, default)
        return bool(v)

    def mode(self, name: str, default: str) -> str:
        v = self.values.get(name, default)
        return str(v)

    def tf_minutes(self, name: str, default: int) -> int:
        return TF_MINUTES.get(str(self.values.get(name, "")), default)


TF_MINUTES = {"PERIOD_M1": 1, "PERIOD_M5": 5, "PERIOD_M15": 15, "PERIOD_M30": 30, "PERIOD_H1": 60,
              "PERIOD_H4": 240, "PERIOD_D1": 1440, "PERIOD_CURRENT": 0}


class Ctx:
    """Arrays every twin needs, built once per call from the (already resampled) frame."""

    def __init__(self, df: pd.DataFrame):
        ts = pd.to_datetime(df["timestamp"])
        if getattr(ts.dt, "tz", None) is None:
            ts = ts.dt.tz_localize("UTC")
        srv = (ts.dt.tz_convert("America/New_York") + pd.Timedelta(hours=SERVER_OFFSET_HOURS)).dt.tz_localize(None)
        self.n = len(df)
        self.srv = srv
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.minute = (srv.dt.hour * 60 + srv.dt.minute).to_numpy()
        self.dow = ((srv.dt.day_of_week.to_numpy() + 1) % 7)          # MqlDateTime: 0 = Sunday ... 6 = Saturday
        self.day = srv.dt.normalize().to_numpy().astype("datetime64[D]").astype(np.int64)
        if self.n > 2:
            dm = np.diff(srv.to_numpy().astype("datetime64[s]").astype(np.int64))
            dm = dm[dm > 0]
            self.bar_min = int(max(1, round(float(np.median(dm[:5000])) / 60.0))) if len(dm) else 1
        else:
            self.bar_min = 1
        self.end_minute = self.minute + self.bar_min                    # server minute at which each bar CLOSES
        # first / last bar index of every server day
        chg = np.flatnonzero(np.r_[True, self.day[1:] != self.day[:-1]]) if self.n else np.zeros(0, int)
        self.day_start = chg
        self.day_end = np.r_[chg[1:], self.n] if self.n else np.zeros(0, int)    # exclusive
        px = np.unique(np.round(self.c[: min(self.n, 40000)], 4))
        step = np.diff(px)
        step = step[step > 1e-9]
        self.point = float(np.round(step.min(), 4)) if len(step) else 0.01

    def first_bar_ending_at_or_after(self, d: int, minute: int) -> int:
        """Index of the first bar of server-day slot ``d`` whose CLOSE is at/after ``minute`` (-1 if none)."""
        a, e = self.day_start[d], self.day_end[d]
        k = np.flatnonzero(self.end_minute[a:e] >= minute)
        return int(a + k[0]) if len(k) else -1


def calc_distance(mode: str, value: float, price: float, range_size: float = 0.0, point: float = 0.01) -> float:
    if value <= 0.0:
        return 0.0
    if mode == "CALC_MODE_PERCENT":
        return price * value / 100.0
    if mode == "CALC_MODE_POINTS":
        return value * point
    if mode == "CALC_MODE_FACTOR":
        return range_size * value
    return 0.0


def reject_unsupported(inp: Inputs, ea: str) -> None:
    """Break-even / trailing management is not simulated by the twin: refuse loudly rather than backtest something else."""
    for trig, val in (("InpBETrigger", 0), ("InpBETriggerPercent", 0), ("InpTSLValue", 0), ("InpTSLPercent", 0)):
        if inp.num(trig, 0.0) > 0.0:
            raise StrategyError(f"{ea}: break-even / trailing-stop management ({trig}) is not simulated by the engine twin; "
                                "leave it at 0 for backtests (the MT5 EA itself supports it).")


def _first_hit(d: int, i: int, stop: float, tgt: float, end: int, h: np.ndarray, l: np.ndarray, chunk: int = 4096) -> int:
    j0 = i
    while j0 < end:
        j1 = min(end, j0 + chunk)
        if d > 0:
            m = (l[j0:j1] <= stop) | (h[j0:j1] >= tgt)
        else:
            m = (h[j0:j1] >= stop) | (l[j0:j1] <= tgt)
        k = int(m.argmax())
        if m[k]:
            return j0 + k
        j0 = j1
    return -1


def build_levels(ctx: Ctx, entries, max_per_day: int | None = None, allow_reverse: bool = False):
    """Turn EA entry events into the engine's level series.

    ``entries``: iterable of (i, d, sl_dist, tp_dist, hard) -- ``i`` = bar whose OPEN the EA fills on, ``d`` = +1/-1,
    distances are price units (0 = none), ``hard`` = bar whose OPEN force-closes the position (use ctx.n + 1 for NONE -- ``ctx.n`` itself means "flat decision on the last bar", a real close).
    One position at a time; stops/targets are replayed on bar ranges (stop wins a same-bar tie, like the engine).
    With ``allow_reverse`` an opposite entry while a position is open closes it at that bar's open and flips.
    Returns (level int8, stop_dist float, target_dist float).
    """
    n = ctx.n
    level = np.zeros(n, dtype=np.int8)
    slp = np.full(n, np.nan)
    tpp = np.full(n, np.nan)
    o, h, l = ctx.o, ctx.h, ctx.l
    day_cnt: dict[int, int] = {}
    prev = None           # last accepted position: d, s0 (first signal bar), e_sig (exclusive end of its signal run), alive_end (exclusive)
    for (i, d, sl, tp, hard) in sorted(entries, key=lambda e: e[0]):
        if i >= n or i < 1:
            continue
        if prev is not None and i < prev["alive_end"]:
            if not allow_reverse or d == prev["d"]:
                continue
            cut = i - 1                                   # flip: the old run ends before the new signal bar
            level[cut:prev["e_sig"]] = 0
            slp[cut:prev["e_sig"]] = np.nan
            tpp[cut:prev["e_sig"]] = np.nan
        dk = int(ctx.day[i])
        if max_per_day is not None and day_cnt.get(dk, 0) >= max_per_day:
            continue
        px = o[i]
        stop = px - d * sl if sl > 0 else (-np.inf if d > 0 else np.inf)
        tgt = px + d * tp if tp > 0 else (np.inf if d > 0 else -np.inf)
        end = min(int(hard), n + 1)
        if end <= i:
            continue
        j = _first_hit(d, i, stop, tgt, min(end, n), h, l)
        s0 = i - 1
        if j >= 0:
            e_sig = j                                      # bar j itself stays flat: the stop/target closed it intrabar
            alive_end = j + 1
        else:
            e_sig = n if end > n else max(s0, end - 1)     # no close bar yet: hold; else flat decision on the last bar before the close open
            alive_end = end
        level[s0:e_sig] = d
        if e_sig > s0:
            slp[s0:e_sig] = sl if sl > 0 else np.nan
            tpp[s0:e_sig] = tp if tp > 0 else np.nan
        else:                                              # stopped out on the entry bar itself: keep one tagged signal bar
            level[s0] = d
            slp[s0] = sl if sl > 0 else np.nan
            tpp[s0] = tp if tp > 0 else np.nan
            e_sig = s0 + 1
        day_cnt[dk] = day_cnt.get(dk, 0) + 1
        prev = {"d": d, "s0": s0, "e_sig": e_sig, "alive_end": alive_end}
    return level, slp, tpp


def htf_groups(ctx: Ctx, minutes: int):
    """Group id of every base bar on a higher timeframe aligned to the SERVER clock (H4 = 00,04,08.. server; D1 = server date)."""
    t = ctx.srv.to_numpy().astype("datetime64[m]").astype(np.int64)
    key = t // minutes if minutes < 1440 else (t // 1440)
    # group ids must be consecutive in time order
    chg = np.r_[True, key[1:] != key[:-1]]
    gid = np.cumsum(chg) - 1
    return gid


def htf_ohlc(ctx: Ctx, gid: np.ndarray):
    ng = int(gid[-1]) + 1 if len(gid) else 0
    first = np.flatnonzero(np.r_[True, gid[1:] != gid[:-1]])
    last = np.r_[first[1:], len(gid)] - 1
    op = ctx.o[first]
    cl = ctx.c[last]
    hi = np.maximum.reduceat(ctx.h, first)
    lo = np.minimum.reduceat(ctx.l, first)
    return op, hi, lo, cl


def sma_arr(x: np.ndarray, p: int) -> np.ndarray:
    return np.array(pd.Series(x).rolling(int(p), min_periods=int(p)).mean().to_numpy(), dtype=float)


def ema_arr(x: np.ndarray, p: int) -> np.ndarray:
    return np.array(pd.Series(x).ewm(span=int(p), adjust=False).mean().to_numpy(), dtype=float)


def ma_arr(x: np.ndarray, p: int, method: str) -> np.ndarray:
    if method == "MODE_EMA":
        out = ema_arr(x, p)
        out[: max(0, int(p) - 1)] = np.nan
        return out
    return sma_arr(x, p)


def sensible_ref(price: float) -> float:
    return price if price > 0 else 1.0
