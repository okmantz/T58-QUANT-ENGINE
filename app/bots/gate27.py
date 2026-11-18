"""Gate 27 V1 as a bot sleeve: monthly 210-day trend gate, long or flat, inverse-volatility sizing, three-day phase-in.

The shipped MT5 EA (strategies/mql5/GATE 27 ...mq5) is a daily-bar basket (US500 / Gold / Oil / USDX). The bot engine trades the legs the T58
data pack carries -- US500 (ES / MES) and Gold (GC / MGC) -- and holds them through the intraday flatten window, one monthly cycle at a time.

Rules (frozen, identical to the EA and to ``InpSmaWindow`` ... ``InpPhaseInDays``):
  signal   at the first session of a month, a leg is LONG when the last completed daily close is above its 210-day SMA, otherwise FLAT.
  vol      standard deviation (ddof=1) of the last 60 daily returns of that leg.
  sizing   risk budget = equity x 0.5% a day; k = budget / sqrt(number of long legs); leg notional = k / vol; the sum of the notionals is capped at
           equity x 5 (leverage cap).
  phase-in the book walks from the old notional to the new one in three equal daily steps (1/3, 2/3, 3/3).

Pure functions and one small state-free signal source; no I/O and no clock, so the bot engine, the research harness and the unit tests share them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

SMA_WINDOW = 210
VOL_WINDOW = 60
DAILY_VOL_TARGET_PCT = 0.5
LEVERAGE_CAP = 5.0
PHASE_IN_DAYS = 3
LEG_NAMES = {"ES": "US500", "GC": "Gold"}


@dataclass(frozen=True)
class Gate27Config:
    sma_window: int = SMA_WINDOW
    vol_window: int = VOL_WINDOW
    daily_vol_target_pct: float = DAILY_VOL_TARGET_PCT
    leverage_cap: float = LEVERAGE_CAP
    phase_in_days: int = PHASE_IN_DAYS


def config_from_params(params: Optional[dict]) -> Gate27Config:
    """A Gate27Config from a leg's ``params`` dict (unknown keys ignored, missing keys keep the frozen original EA value)."""
    p = dict(params or {})
    keys = {"sma_window": int, "vol_window": int, "daily_vol_target_pct": float, "leverage_cap": float, "phase_in_days": int}
    return Gate27Config(**{k: cast(p[k]) for k, cast in keys.items() if k in p and p[k] is not None})


def session_closes(df_1m: pd.DataFrame) -> pd.DataFrame:
    """One row per CME session day: ``close`` (back-adjusted, used for the signal) and ``raw`` (the unadjusted price level, used for notional).

    Uses the importer's ``trading_day`` column; frames without it fall back to the New York calendar day shifted by the 18:00 ET Globex open."""
    ts = pd.to_datetime(df_1m["timestamp"], utc=True)
    if "trading_day" in df_1m.columns:
        day = pd.to_datetime(df_1m["trading_day"]).dt.normalize()
    else:
        day = (ts.dt.tz_convert("America/New_York") + pd.Timedelta(hours=6)).dt.tz_localize(None).dt.normalize()
    close = df_1m["close"].astype(float)
    off = df_1m["adj_offset"].astype(float) if "adj_offset" in df_1m.columns else pd.Series(0.0, index=df_1m.index)
    g = pd.DataFrame({"day": day.to_numpy(), "close": close.to_numpy(), "raw": (close - off).to_numpy()})
    out = g.groupby("day").last()
    out = out[out.index.weekday < 5]
    return out


def leg_signal(closes: np.ndarray, cfg: Gate27Config = Gate27Config()) -> Optional[tuple[bool, float]]:
    """(is_long, daily vol) from daily closes up to and including the last COMPLETED session, or None when there is not enough history."""
    c = np.asarray(closes, dtype=float)
    c = c[np.isfinite(c)]
    if len(c) < max(cfg.sma_window, cfg.vol_window + 1):
        return None
    sma = float(c[-cfg.sma_window:].mean())
    r = c[-cfg.vol_window:] / c[-cfg.vol_window - 1:-1] - 1.0
    vol = float(np.std(r, ddof=1))
    return bool(c[-1] > sma), vol


def target_notionals(signals: dict, equity: float, cfg: Gate27Config = Gate27Config()) -> dict:
    """{leg: target dollar notional} from ``signals`` = {leg: (is_long, vol) or None}. A leg without a signal is absent (the caller carries it forward)."""
    longs = [k for k, s in signals.items() if s and s[0] and s[1] > 1e-9]
    budget = max(equity, 0.0) * cfg.daily_vol_target_pct / 100.0
    k = budget / math.sqrt(len(longs)) if longs else 0.0
    tgt = {leg: (k / s[1] if (s and s[0] and s[1] > 1e-9) else 0.0) for leg, s in signals.items() if s is not None}
    gross = sum(tgt.values())
    cap = max(equity, 0.0) * cfg.leverage_cap
    if gross > cap > 0:
        tgt = {leg: v * cap / gross for leg, v in tgt.items()}
    return tgt


def phase_notional(start: float, target: float, step: int, cfg: Gate27Config = Gate27Config()) -> float:
    """Notional wanted on phase-in step ``step`` (1-based); step >= phase_in_days gives the target."""
    if step >= cfg.phase_in_days:
        return float(target)
    return float(start + (target - start) * step / cfg.phase_in_days)


def contracts_for_notional(notional: float, price: float, point_value: float, *, round_to_nearest: bool = True, max_contracts: int = 10_000) -> int:
    """Whole contracts for a dollar notional. Nearest by default so a small account still holds a leg whose target is at least half a contract."""
    unit = price * point_value
    if unit <= 0 or notional <= 0:
        return 0
    x = notional / unit
    n = int(math.floor(x + 0.5)) if round_to_nearest else int(math.floor(x))
    return max(0, min(n, max_contracts))


# ------------------------------------------------------------------------------------------------------------------ research backtest
def backtest_basket(closes: dict, *, equity0: float = 100_000.0, point_value: Optional[dict] = None, cfg: Gate27Config = Gate27Config(),
                    compound: bool = True, whole_contracts: bool = False) -> pd.DataFrame:
    """Daily mark-to-market equity of the basket from ``closes`` = {leg: session_closes frame}. P&L is points x contracts x point value on the
    back-adjusted series, so it is exact across contract rolls. Returns a frame indexed by day with ``pnl`` and ``equity``.

    ``whole_contracts`` rounds every leg to whole contracts of ``point_value[leg]`` (e.g. micro $5 / $10 per point); otherwise notional is fractional."""
    point_value = point_value or {"ES": 50.0, "GC": 100.0}
    legs = list(closes)
    first = max(closes[k].index[0] for k in legs)                  # start when every leg has history
    idx = sorted(d for d in set().union(*[set(closes[k].index) for k in legs]) if d >= first)
    full = sorted(set().union(*[set(closes[k].index) for k in legs]))
    px = pd.DataFrame({k: closes[k]["close"].reindex(full).ffill() for k in legs}).loc[idx]
    raw = pd.DataFrame({k: closes[k]["raw"].reindex(full).ffill() for k in legs}).loc[idx]
    months = pd.Series([d.year * 12 + d.month for d in idx], index=idx)
    equity = equity0
    start_n = {k: 0.0 for k in legs}
    target = {k: 0.0 for k in legs}
    step = cfg.phase_in_days
    qty = {k: 0.0 for k in legs}
    rows = []
    for i, d in enumerate(idx):
        # P&L of yesterday's holdings over today's move
        pnl = 0.0
        if i > 0:
            for k in legs:
                pnl += qty[k] * (px[k].iloc[i] - px[k].iloc[i - 1]) * point_value[k]
        equity += pnl
        # first session of a new month: new cycle from the last COMPLETED close (yesterday's)
        if i > 0 and months.iloc[i] != months.iloc[i - 1]:
            sigs = {k: leg_signal(px[k].iloc[:i].to_numpy(), cfg) for k in legs}
            base = equity if compound else equity0
            new = target_notionals(sigs, base, cfg)
            for k in legs:
                start_n[k] = qty[k] * raw[k].iloc[i - 1] * point_value[k]
                target[k] = new.get(k, target[k])
            step = 0
        if step < cfg.phase_in_days:
            step += 1
            for k in legs:
                want = phase_notional(start_n[k], target[k], step, cfg)
                unit = raw[k].iloc[i] * point_value[k]
                q = want / unit if unit > 0 else 0.0
                qty[k] = float(contracts_for_notional(want, raw[k].iloc[i], point_value[k])) if whole_contracts else q
        rows.append((d, pnl, equity, sum(abs(qty[k]) * raw[k].iloc[i] * point_value[k] for k in legs) / max(equity, 1.0)))
    out = pd.DataFrame(rows, columns=["day", "pnl", "equity", "gross_x"]).set_index("day")
    return out


def summarize_equity(eq: pd.DataFrame, equity0: float) -> dict:
    if eq.empty:
        return {"net": 0.0, "max_dd": 0.0}
    e = eq["equity"].to_numpy(float)
    peak = np.maximum.accumulate(np.r_[equity0, e])[1:]
    dd = float((peak - e).max())
    yrs = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    r = eq["pnl"].to_numpy(float) / np.r_[equity0, e[:-1]]
    sharpe = float(r.mean() / r.std(ddof=1) * math.sqrt(252)) if r.std(ddof=1) > 0 else 0.0
    return {"net": float(e[-1] - equity0), "max_dd": dd, "net_dd": float((e[-1] - equity0) / dd) if dd > 0 else None,
            "cagr_pct": float(((e[-1] / equity0) ** (1 / yrs) - 1) * 100), "sharpe": sharpe, "max_gross_x": float(eq["gross_x"].max())}


class Gate27Source:
    """Signal source for the Gate 27 swing legs: monthly (long?, vol) per instrument from the daily closes strictly BEFORE the session asked about.

    Simulation hands it the full history once (``closes`` = {symbol: ``session_closes`` frame}); a real-time run refreshes it with ``update``. A leg with
    fewer than 210 completed sessions has no signal and is carried flat."""
    tf = 1440
    max_trades_per_day = None

    def __init__(self, closes: dict, cfg: Gate27Config = Gate27Config(), dd_guard_pct: float = 25.0):
        self.cfg = cfg
        self.dd_guard_pct = float(dd_guard_pct)
        self._idx: dict = {}
        self._close: dict = {}
        for sym, fr in closes.items():
            self.update(sym, fr)

    def update(self, symbol: str, frame: pd.DataFrame) -> None:
        self._idx[symbol] = pd.DatetimeIndex(frame.index).to_numpy()
        self._close[symbol] = frame["close"].to_numpy(float)

    def signals(self, session_day: pd.Timestamp) -> Optional[dict]:
        """{symbol: (is_long, vol) or None} using sessions strictly before ``session_day``; None when no leg has enough history."""
        out = {}
        for sym, idx in self._idx.items():
            n = int(np.searchsorted(idx, np.datetime64(pd.Timestamp(session_day).tz_localize(None)), side="left"))
            out[sym] = leg_signal(self._close[sym][:n], self.cfg)
        return out if any(v is not None for v in out.values()) else None

    def at(self, bar_close):                      # the engine never reads swing sources bar by bar
        return None
