"""A T58 Trading Bot as a Strategy, so Test / Optimize / Validate (and every pipeline that takes a Strategy) can run a bot exactly like a strategy.

What a bot is, mapped onto the strategy contract
  * legs        each intraday leg is the library strategy file it points at, generated on the 1-minute frame and read from the close of its own
                bar (a 15m leg's signal is known 15 minutes after the bar opened, and never earlier). Legs combine like the bot arbiter: the signed
                sum of ``weight x signal`` decides the side; opposite legs net out; the dominant leg (largest weight, then lowest priority number)
                supplies the stop and target distances.
  * weights     ``StrategyResult.size_multiplier`` carries |net weight| to the sizer (Ind Rule x3 opens three times the one-leg size).
  * governor    the bot's profit-lock ladder and adaptive loser cut become ``RiskConfig`` fields through ``risk_overlay`` (the engine calls it next to
                the strategy's behaviour rules), and the bot's trades-per-day cap tightens ``max_trades_per_day``.
  * Gate 27     the monthly swing basket is a daily-bar sleeve with its own simulator; it is not part of a one-instrument intraday backtest.
                ``skipped_legs`` lists what was left out so the run never pretends otherwise (the Simulator / Replay run the whole bot).

Legs on another instrument than the dataset under test are skipped the same way: a bot is tested on one instrument at a time.
"""
from __future__ import annotations

import warnings
from dataclasses import replace

import numpy as np
import pandas as pd

from app.strategy.base import Strategy, StrategyResult

BOT_TYPE = "bot"
LOOKAHEAD_VERIFIED = True        # engine: the legs are library strategies that already pass the look-ahead gate individually


_GEN_CACHE: dict = {}          # (bot id, weights, frame fingerprint) -> (side, mult, stop, tp, skipped); a pipeline re-generates on the same frame many times
_GEN_CACHE_MAX = 6


def bot_catalog() -> list[dict]:
    """[{id, name, objective, legs, tagline}] for every stored bot (presets first)."""
    from app.bots import store
    out = []
    for rec in store.list_bots():
        c = rec.get("config") or {}
        out.append({"id": c.get("id"), "name": c.get("name") or c.get("id"), "objective": c.get("objective", "A"),
                    "tagline": c.get("tagline", ""), "legs": len(c.get("legs") or []), "preset_key": c.get("preset_key", "")})
    return [b for b in out if b["id"]]


def bot_config(bot_id: str):
    from app.bots import store
    from app.bots.models import BotConfig
    rec = store.get_bot(bot_id)
    if rec is None:
        raise FileNotFoundError(f"bot not found: {bot_id}")
    return BotConfig.from_dict(rec["config"])


def _leg_arrays(strategy, df: pd.DataFrame):
    """(leg-bar close times UTC ns, signal, stop, tp) of one library strategy generated on its own declared timeframe."""
    from app.bots.signals import strategy_timeframe_minutes
    from app.data.timeframe_resample import prepare_timeframe_aligned_data
    d2, _w = prepare_timeframe_aligned_data(df, strategy)
    res = strategy.generate(d2)
    tf = max(1, int(strategy_timeframe_minutes(strategy)))
    idx = pd.DatetimeIndex(pd.to_datetime(d2["timestamp"]))
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    close = (idx + pd.Timedelta(minutes=tf)).tz_convert("UTC").as_unit("ns").asi8
    sig = res.signals.to_numpy().astype(float)
    n = len(sig)
    stop = res.stop_loss_distance.to_numpy(dtype=float) if res.stop_loss_distance is not None else np.full(n, np.nan)
    tp = res.take_profit_distance.to_numpy(dtype=float) if res.take_profit_distance is not None else np.full(n, np.nan)
    return close, sig, stop, tp


class BotStrategy(Strategy):
    """A stored bot, runnable anywhere a Strategy is."""

    source_type = BOT_TYPE
    LOOKAHEAD_VERIFIED = True

    def __init__(self, cfg, symbol: str | None = None):
        self.cfg = cfg
        self.bot_id = cfg.id
        self.name = cfg.name
        legs = [lg for lg in cfg.legs if lg.kind != "gate27"]
        self.symbol = symbol or (legs[0].symbol if legs else "NQ")
        self.legs = [lg for lg in legs if lg.symbol == self.symbol]
        self.skipped_legs = [f"{lg.label} ({'swing basket' if lg.kind == 'gate27' else lg.symbol})" for lg in cfg.legs if lg not in self.legs]
        self._loaded: dict = {}

    # ----------------------------------------------------------------------------------------------------------- engine hooks
    def risk_overlay(self, risk):
        """RiskConfig with the bot's profit lock / loser cut (and trades-per-day cap) layered on. Only ever adds protection."""
        gov = self.cfg.governor_cfg()
        kw: dict = {}
        if getattr(gov, "profit_lock", False):
            kw["profit_lock_tiers"] = tuple(tuple(t) for t in (gov.lock_tiers or ())) or None
            kw["profit_lock_trail_frac"] = float(gov.lock_trail_frac)
            # dollar rungs are written for a 50K account: scale with the account under test unless the bot pins its own scale
            base = float(getattr(risk, "initial_balance", 50_000.0) or 50_000.0) / 50_000.0
            kw["profit_lock_scale"] = float(gov.lock_scale) * (base if gov.lock_scale_by_risk else 1.0)
            if not kw["profit_lock_tiers"]:
                from app.backtest.profit_lock import DEFAULT_TIERS
                kw["profit_lock_tiers"] = tuple(DEFAULT_TIERS)
        if getattr(gov, "loss_cut_frac", None):
            kw["loss_cut_frac"] = float(gov.loss_cut_frac)
            kw["loss_cut_max_mfe_frac"] = float(gov.loss_cut_max_mfe_frac)
        cap = int(getattr(self.cfg, "max_trades_per_day", 0) or 0)
        if cap and cap < int(getattr(risk, "max_trades_per_day", cap) or cap):
            kw["max_trades_per_day"] = cap
        # The bot sizes in MICRO contracts (risk dollars / stop, floored to whole micros), so a backtest of it must too: on a full NQ/ES
        # contract a 60-250 point stop costs $1,200-$5,000 and a $500-$1,000 risk budget rounds to ZERO contracts -- a bot "that took no trades".
        cs = float(getattr(risk, "contract_size", 0) or 0)
        micro = {20.0: 2.0, 50.0: 5.0}.get(cs)
        if micro is not None:
            kw["contract_size"] = micro
            kw["commission_per_contract"] = float(getattr(risk, "micro_commission_per_contract", 1.32) or 1.32)
        return replace(risk, **kw) if kw else risk

    # ----------------------------------------------------------------------------------------------------------- generation
    def _strategy_for(self, leg):
        if leg.strategy not in self._loaded:
            from app.bots.signals import load_strategy
            self._loaded[leg.strategy] = load_strategy(leg.strategy)
        return self._loaded[leg.strategy]

    def _fingerprint(self, df: pd.DataFrame) -> tuple:
        n = len(df)
        t = df["timestamp"]
        c = df["close"].to_numpy(float)
        return (self.bot_id, self.symbol, tuple((lg.strategy, lg.label, float(lg.weight), int(lg.priority)) for lg in self.legs), n,
                str(t.iloc[0]), str(t.iloc[-1]), float(c[0]), float(c[-1]), float(c[n // 2]), float(np.nansum(c[:: max(1, n // 997)])))

    def generate(self, df: pd.DataFrame) -> StrategyResult:
        key = self._fingerprint(df) if len(df) else None
        hit = _GEN_CACHE.get(key) if key is not None else None
        if hit is None:
            hit = self._generate(df)
            if key is not None:
                if len(_GEN_CACHE) >= _GEN_CACHE_MAX:
                    _GEN_CACHE.pop(next(iter(_GEN_CACHE)))
                _GEN_CACHE[key] = hit
        side, mult, stop, tp, has_mult = hit
        idx = df.index
        return StrategyResult(
            name=f"Bot: {self.name}", source_type=BOT_TYPE, signals=pd.Series(side.copy(), index=idx),
            stop_loss_distance=pd.Series(stop.copy(), index=idx) if np.isfinite(stop).any() else None,
            take_profit_distance=pd.Series(tp.copy(), index=idx) if np.isfinite(tp).any() else None,
            size_multiplier=pd.Series(mult.copy(), index=idx) if has_mult else None)

    def _generate(self, df: pd.DataFrame) -> tuple:
        n = len(df)
        ts = pd.DatetimeIndex(pd.to_datetime(df["timestamp"]))
        if ts.tz is None:
            ts = ts.tz_localize("UTC")
        # a 1-minute bar opening at t closes at t+1m: the leg's latest closed bar at that moment is the one whose close <= t+1m
        bar_close = (ts + pd.Timedelta(minutes=1)).tz_convert("UTC").as_unit("ns").asi8
        net = np.zeros(n)
        best_w = np.full(n, -1.0)
        stop = np.full(n, np.nan)
        tp = np.full(n, np.nan)
        loaded = 0
        for lg in sorted(self.legs, key=lambda x: x.priority):
            try:
                strat = self._strategy_for(lg)
            except FileNotFoundError:
                self.skipped_legs.append(f"{lg.label} (strategy file missing)")
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                close, sig, s_stop, s_tp = _leg_arrays(strat, df)
            if len(close) == 0:
                continue
            loaded += 1
            pos = np.searchsorted(close, bar_close, side="right") - 1      # last leg-bar closed by this 1m bar's close
            ok = pos >= 0
            safe = np.where(ok, pos, 0)
            lsig = np.where(ok, sig[safe], 0.0)
            w = float(lg.weight)
            net += w * lsig
            active = (lsig != 0) & (w > best_w)                              # sorted by priority: the first of equal weight keeps the slot
            stop = np.where(active, np.where(ok, s_stop[safe], np.nan), stop)
            tp = np.where(active, np.where(ok, s_tp[safe], np.nan), tp)
            best_w = np.where(active, w, best_w)
        if not loaded:
            from app.strategy.base import StrategyError
            raise StrategyError("None of this bot's strategies could be loaded for this instrument.")
        side = np.sign(net).astype(int)
        mult = np.where(side != 0, np.abs(net), 1.0)
        mult = np.where(np.isfinite(mult) & (mult > 0), mult, 1.0)
        return side, mult, stop, tp, bool(not np.allclose(mult, 1.0))


def build_bot_strategy(bot_id: str, symbol: str | None = None) -> BotStrategy:
    return BotStrategy(bot_config(bot_id), symbol=symbol)
