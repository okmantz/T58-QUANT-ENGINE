"""Signal sources for bot legs: the library strategy's own ``generate`` output, read one closed leg-bar at a time.

Strategies emit a LEVEL signal per bar (+1 / -1 / 0) with per-bar stop and target distances; the engine fills at the NEXT bar's open.
A bot therefore needs exactly one thing per closed leg-bar: (signal, stop distance, target distance). Two sources give it:

  PrecomputedSignals  Simulation. ``generate`` runs ONCE over the replay span (plus warm-up). The library's look-ahead and prefix-invariance
                      tests guarantee a signal at bar j depends only on bars <= j, so reading the cached row is identical to computing it live.
  RollingSignals      Real-time. ``generate`` re-runs on the last ``lookback_days`` of 1-minute bars each time a leg-bar closes (~0.1-0.5 s).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STRATEGIES_DIR = ROOT / "strategies"


@dataclass(frozen=True)
class LegSignal:
    sig: int
    stop: float          # price points; nan when the strategy gave none
    tp: float            # price points; nan when none
    bar_close: pd.Timestamp


def resolve_strategy_path(rel: str) -> Path:
    p = Path(rel)
    if not p.is_absolute():
        p = STRATEGIES_DIR / rel
    p = p.resolve()
    if STRATEGIES_DIR.resolve() not in p.parents and not p.exists():
        raise FileNotFoundError(rel)
    if not p.exists():
        raise FileNotFoundError(f"strategy file not found: {rel}")
    return p


def load_strategy(rel: str):
    from app.strategy.mql5 import MQL5Strategy
    from app.strategy.pinescript import PineScriptStrategy
    from app.strategy.python import PythonStrategy
    p = resolve_strategy_path(rel)
    if p.suffix == ".py":
        return PythonStrategy(str(p))
    text = p.read_text(encoding="utf-8")
    return MQL5Strategy(text) if p.suffix == ".mq5" else PineScriptStrategy(text)


def _tf_minutes(strategy, df_native: pd.DataFrame) -> int:
    from app.data.timeframe_resample import _resolve_python_declaration  # declared TIMEFRAME ("5m" ...) -> minutes
    decl = _resolve_python_declaration(strategy) if hasattr(strategy, "module_attr") else None
    label = getattr(decl, "execution_timeframe", None) if decl else None
    if not label:
        from app.data.timeframe_resample import _resolve_directive_declaration
        d2 = _resolve_directive_declaration(strategy)
        label = getattr(d2, "execution_timeframe", None)
    if not label:
        return 1
    s = str(label).lower()
    if s.endswith("m"):
        return int(s[:-1])
    if s.endswith("h"):
        return int(s[:-1]) * 60
    return 1


def strategy_timeframe_minutes(strategy) -> int:
    return _tf_minutes(strategy, None)


def _generate(strategy, df_1m: pd.DataFrame):
    from app.data.timeframe_resample import prepare_timeframe_aligned_data
    d2, _w = prepare_timeframe_aligned_data(df_1m, strategy)
    res = strategy.generate(d2)
    sig = res.signals.to_numpy()
    stop = res.stop_loss_distance.to_numpy(dtype=float) if res.stop_loss_distance is not None else np.full(len(sig), np.nan)
    tp = res.take_profit_distance.to_numpy(dtype=float) if res.take_profit_distance is not None else np.full(len(sig), np.nan)
    return pd.DatetimeIndex(pd.to_datetime(d2["timestamp"])), sig, stop, tp


def _daily_cap(strategy) -> Optional[int]:
    """The strategy's own MAX_TRADES_PER_DAY (one-shot-per-day systems), or None."""
    try:
        v = strategy.module_attr("MAX_TRADES_PER_DAY", None) if hasattr(strategy, "module_attr") else None
        return int(v) if v else None
    except Exception:  # noqa: BLE001
        return None


class PrecomputedSignals:
    def __init__(self, strategy, df_1m: pd.DataFrame, tf_minutes: int):
        idx, sig, stop, tp = _generate(strategy, df_1m)
        self.max_trades_per_day = _daily_cap(strategy)
        self.tf = max(1, int(tf_minutes))
        # key by the leg-bar CLOSE time (bar start + tf) in UTC
        close = (idx + pd.Timedelta(minutes=self.tf))
        if close.tz is None:
            close = close.tz_localize("UTC")
        self._close = close
        self._pos = {t.value: i for i, t in enumerate(close)}
        self._sig, self._stop, self._tp = sig, stop, tp

    def at(self, bar_close: pd.Timestamp) -> Optional[LegSignal]:
        i = self._pos.get(pd.Timestamp(bar_close).value)
        if i is None:
            return None
        return LegSignal(int(self._sig[i]), float(self._stop[i]), float(self._tp[i]), pd.Timestamp(bar_close))


class RollingSignals:
    """Real-time source: recompute over the trailing window each time a leg-bar closes."""

    def __init__(self, strategy, tf_minutes: int, get_window):
        self.strategy, self.tf, self._get = strategy, max(1, int(tf_minutes)), get_window
        self.max_trades_per_day = _daily_cap(strategy)

    def at(self, bar_close: pd.Timestamp) -> Optional[LegSignal]:
        df = self._get()
        if df is None or len(df) < 50:
            return None
        idx, sig, stop, tp = _generate(self.strategy, df)
        want = pd.Timestamp(bar_close) - pd.Timedelta(minutes=self.tf)
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        pos = idx.searchsorted(want)
        if pos >= len(idx) or idx[pos] != want:
            return None
        return LegSignal(int(sig[pos]), float(stop[pos]), float(tp[pos]), pd.Timestamp(bar_close))
