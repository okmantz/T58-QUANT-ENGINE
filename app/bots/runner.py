"""BotRunner: starts, pauses and stops bots on background threads and persists every step.

Two run modes, one engine (``app.bots.engine.BotEngine``):

  simulation  A fast, honest replay of the bundled 1-minute history: the bot trades the most recent N months of real NQ bars as if they were
              arriving live (signals, fills, costs, risk governor, account rules all identical to a live run). Trades are booked into the
              T58 demo account when the bot is attached to it. This is what the shipped bots do out of the box: no data feed or broker needed.
  feed        Real-time: poll the connected broker account for completed 1-minute bars and trade them (paper / demo / live account).

Threads are daemons; ``stop`` sets an event the loop checks every chunk. State is saved after every chunk, so a restart resumes from the last
bar. Live (broker) runs additionally refuse to start unless the caller passes ``live_ok=True`` (the web layer ties that to the existing
Deploy Live access guard).
"""
from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from app.bots import store
from app.bots.engine import BotEngine, rules_for_account
from app.bots.models import BotConfig, BotRuntime, now_iso
from app.bots.signals import PrecomputedSignals, RollingSignals, load_strategy, strategy_timeframe_minutes
from app.bots.venues import BrokerVenue, venue_for

ROOT = Path(__file__).resolve().parents[2]
DATA_FILES = {"NQ": "data/raw/NQ1!/futures_NQ.F_1m.parquet", "ES": "data/raw/ES1!/futures_ES.F_1m.parquet", "GC": "data/raw/GC1!/futures_GC.F_1m.parquet"}
SIM_SPEEDS = {"instant": 0.0, "fast": 0.12, "watch": 0.6}
_DATA_CACHE: dict = {}
_LOCK = threading.RLock()
_THREADS: dict = {}
_STOPS: dict = {}


def load_history(symbol: str) -> pd.DataFrame:
    with _LOCK:
        if symbol in _DATA_CACHE:
            return _DATA_CACHE[symbol]
        rel = DATA_FILES.get(symbol)
        if not rel or not (ROOT / rel).exists():
            raise FileNotFoundError(f"no 1-minute history bundled for {symbol}")
        from app.data.importer import import_csv
        df = import_csv(str(ROOT / rel)).dataframe.reset_index(drop=True)
        ts = pd.to_datetime(df["timestamp"])
        if ts.dt.tz is None:
            df["timestamp"] = ts.dt.tz_localize("UTC")
        _DATA_CACHE[symbol] = df
        return df


def history_span(symbol: str = "NQ") -> tuple[pd.Timestamp, pd.Timestamp]:
    df = load_history(symbol)
    return pd.Timestamp(df["timestamp"].iloc[0]), pd.Timestamp(df["timestamp"].iloc[-1])


def _persist(bot_id: str, cfg: BotConfig, rt: BotRuntime, trades: list, events: list) -> None:
    def fn(rec):
        rec["runtime"], rec["trades"], rec["events"] = rt.to_dict(), trades, events
    store.update_bot(bot_id, fn)


def is_running(bot_id: str) -> bool:
    t = _THREADS.get(bot_id)
    return bool(t and t.is_alive())


# --------------------------------------------------------------------------------------------------------------------- simulation
def _build_sim_sources(cfg: BotConfig, start: pd.Timestamp, end: pd.Timestamp, events: list) -> tuple[dict, pd.DataFrame]:
    sources, primary = {}, None
    sym0 = cfg.legs[0].symbol
    for lg in cfg.legs:
        if lg.symbol != sym0:
            events.append({"t": now_iso(), "kind": "warn", "text": f"{lg.label}: multi-instrument bots are not supported yet; leg skipped."})
            continue
        df = load_history(lg.symbol)
        w0 = start - pd.Timedelta(days=int(lg.lookback_days))
        seg = df[(df["timestamp"] >= w0) & (df["timestamp"] <= end)].reset_index(drop=True)
        strat = load_strategy(lg.strategy)
        tf = strategy_timeframe_minutes(strat)
        sources[lg.label] = PrecomputedSignals(strat, seg, tf)
        if primary is None:
            primary = df
    bars = primary[(primary["timestamp"] >= start) & (primary["timestamp"] <= end)].reset_index(drop=True)
    return sources, bars


def start_simulation(bot_id: str, *, months: float = 3.0, speed: str = "fast", from_date: Optional[str] = None) -> dict:
    """Begin (or resume) a simulation. Returns {'ok': bool, 'message': str}."""
    with _LOCK:
        if is_running(bot_id):
            return {"ok": False, "message": "This bot is already running."}
        rec = store.get_bot(bot_id)
        if rec is None:
            return {"ok": False, "message": "Unknown bot."}
        cfg = BotConfig.from_dict(rec["config"])
        rt = BotRuntime.from_dict(rec["runtime"])
        if rt.status in ("halted", "complete"):
            return {"ok": False, "message": "This run has finished. Reset the bot to start a fresh run."}
        if not cfg.legs:
            return {"ok": False, "message": "Add at least one strategy to this bot."}
        if cfg.account.venue == "broker":
            return {"ok": False, "message": "Simulation runs on the T58 demo account or the bot sandbox; use Start live for a broker account."}
        if cfg.account.venue == "demo":
            from app.demo_account import account as demo
            a = demo.load()
            if a.status != "active":
                return {"ok": False, "message": f"The T58 demo account is {a.status}. Start a new attempt on the demo account first."}
        lo, hi = history_span(cfg.legs[0].symbol)
        if rt.replay_cursor:
            start = max(pd.Timestamp(rt.replay_cursor) + pd.Timedelta(minutes=1), lo)
        elif from_date:
            start = max(pd.Timestamp(from_date, tz="UTC"), lo)
        else:
            start = max(hi - pd.Timedelta(days=int(30.4 * months)), lo)
        if start >= hi:
            return {"ok": False, "message": "The bundled history has been fully replayed. Reset the bot to replay again."}
        rt.status, rt.mode, rt.started_at, rt.message = "running", "simulation", now_iso(), "Simulation running."
        stop = threading.Event()
        _STOPS[bot_id] = stop
        _persist(bot_id, cfg, rt, rec["trades"], rec["events"])
        th = threading.Thread(target=_sim_loop, args=(bot_id, start, hi, SIM_SPEEDS.get(speed, 0.12), stop), daemon=True, name=f"t58-bot-{bot_id}")
        _THREADS[bot_id] = th
        th.start()
    return {"ok": True, "message": "Simulation started."}


def _sim_loop(bot_id: str, start: pd.Timestamp, end: pd.Timestamp, pause: float, stop: threading.Event) -> None:
    rec = store.get_bot(bot_id)
    cfg, rt = BotConfig.from_dict(rec["config"]), BotRuntime.from_dict(rec["runtime"])
    trades, events = rec["trades"], rec["events"]
    try:
        sources, bars = _build_sim_sources(cfg, start, end, events)
        venue = venue_for(cfg.account)
        rules, mx, mm = rules_for_account(cfg.account)
        eng = BotEngine(cfg, rt, trades, events, venue, sources, rules=rules, max_minis=mx, max_micros=mm)
        ts = pd.DatetimeIndex(bars["timestamp"])
        o, h, l, c = (bars[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        n, chunk, i = len(bars), 1380, 0
        while i < n and not stop.is_set() and rt.status == "running":
            j = min(n, i + chunk)
            for k in range(i, j):
                eng.on_bar(ts[k], o[k], h[k], l[k], c[k])
                rt.replay_cursor = ts[k].isoformat()
                if rt.status != "running":
                    break
            i = j
            _persist(bot_id, cfg, rt, trades, events)
            if pause:
                time.sleep(pause)
        if rt.status == "running":
            if stop.is_set():
                rt.status, rt.message = "stopped", "Stopped. Press Start to continue from here."
            else:
                rt.status, rt.message = "stopped", "Replay reached the end of the bundled data. Reset to run again, or connect a live feed to continue in real time."
        if eng.pos is not None and rt.status != "running":
            eng._close_position(float(rt.last_price), pd.Timestamp(rt.last_bar_time), "bot stopped: flattened")
        eng._persist_state()
        rt.stopped_at = now_iso()
    except Exception as e:  # noqa: BLE001
        rt.status, rt.halted_reason, rt.message = "halted", f"{type(e).__name__}: {e}", f"Halted: {e}"
        events.append({"t": now_iso(), "kind": "error", "text": traceback.format_exc(limit=3)})
    finally:
        _persist(bot_id, cfg, rt, trades, events)


# ------------------------------------------------------------------------------------------------------------------------- feed
def start_feed(bot_id: str, adapter, *, live_ok: bool, poll_seconds: float = 15.0) -> dict:
    """Real-time loop on a connected broker adapter. ``adapter`` must already be connected."""
    with _LOCK:
        if is_running(bot_id):
            return {"ok": False, "message": "This bot is already running."}
        rec = store.get_bot(bot_id)
        if rec is None:
            return {"ok": False, "message": "Unknown bot."}
        cfg = BotConfig.from_dict(rec["config"])
        rt = BotRuntime.from_dict(rec["runtime"])
        if cfg.account.venue == "broker" and not live_ok:
            return {"ok": False, "message": "Live trading is locked. Unlock Deploy Live first (password and enable phrase)."}
        if rt.status in ("halted", "complete"):
            return {"ok": False, "message": "This run has finished. Reset the bot to start a fresh run."}
        rt.status, rt.mode, rt.started_at, rt.message = "running", "feed", now_iso(), "Connected: waiting for the next completed bar."
        stop = threading.Event()
        _STOPS[bot_id] = stop
        _persist(bot_id, cfg, rt, rec["trades"], rec["events"])
        th = threading.Thread(target=_feed_loop, args=(bot_id, adapter, poll_seconds, stop), daemon=True, name=f"t58-bot-{bot_id}")
        _THREADS[bot_id] = th
        th.start()
    return {"ok": True, "message": "Bot started on the live feed."}


def _feed_loop(bot_id: str, adapter, poll_seconds: float, stop: threading.Event) -> None:
    rec = store.get_bot(bot_id)
    cfg, rt = BotConfig.from_dict(rec["config"]), BotRuntime.from_dict(rec["runtime"])
    trades, events = rec["trades"], rec["events"]
    window = {"df": None}
    try:
        sym = cfg.account.broker_symbol
        sources = {}
        for lg in cfg.legs:
            strat = load_strategy(lg.strategy)
            tf = strategy_timeframe_minutes(strat)
            sources[lg.label] = RollingSignals(strat, tf, lambda: window["df"])
        venue = venue_for(cfg.account, adapter=adapter) if cfg.account.venue == "broker" else venue_for(cfg.account)
        rules, mx, mm = rules_for_account(cfg.account)
        eng = BotEngine(cfg, rt, trades, events, venue, sources, rules=rules, max_minis=mx, max_micros=mm)
        need = max(lg.lookback_days for lg in cfg.legs) * 1440
        last_t = pd.Timestamp(rt.last_bar_time) if rt.last_bar_time else None
        failures = 0
        while not stop.is_set() and rt.status == "running":
            try:
                df = adapter.fetch_completed_bars(sym, 1, min(need, 50_000))
                failures = 0
            except Exception as e:  # noqa: BLE001
                failures += 1
                events.append({"t": now_iso(), "kind": "warn", "text": f"Data fetch failed ({failures}): {e}"})
                if failures >= 5:
                    rt.status, rt.halted_reason = "halted", "Lost the data feed 5 times in a row."
                    venue.flatten_all()
                    break
                time.sleep(poll_seconds)
                continue
            if df is not None and len(df):
                df = df.reset_index(drop=True)
                ts = pd.to_datetime(df["timestamp"])
                if ts.dt.tz is None:
                    df["timestamp"] = ts.dt.tz_localize("UTC")
                window["df"] = df
                new = df if last_t is None else df[df["timestamp"] > last_t]
                if last_t is None:
                    new = df.tail(1)       # first connect: arm on the latest bar, never replay old bars into live orders
                for r in new.itertuples():
                    eng.on_bar(pd.Timestamp(r.timestamp), float(r.open), float(r.high), float(r.low), float(r.close))
                    last_t = pd.Timestamp(r.timestamp)
                    if rt.status != "running":
                        break
                _persist(bot_id, cfg, rt, trades, events)
            stop.wait(poll_seconds)
        if rt.status == "running":
            rt.status, rt.message = "stopped", "Stopped."
        if eng.pos is not None and rt.status != "running":
            venue.flatten_all()
            eng._close_position(float(rt.last_price), pd.Timestamp(rt.last_bar_time or pd.Timestamp.utcnow()), "bot stopped: flattened", broker_closed=True)
        rt.stopped_at = now_iso()
    except Exception as e:  # noqa: BLE001
        rt.status, rt.halted_reason, rt.message = "halted", f"{type(e).__name__}: {e}", f"Halted: {e}"
        events.append({"t": now_iso(), "kind": "error", "text": traceback.format_exc(limit=3)})
        try:
            adapter.close_all(cfg.account.broker_symbol)
        except Exception:  # noqa: BLE001
            pass
    finally:
        _persist(bot_id, cfg, rt, trades, events)


# ----------------------------------------------------------------------------------------------------------------------- control
def stop_bot(bot_id: str, *, wait: float = 5.0) -> dict:
    ev = _STOPS.get(bot_id)
    th = _THREADS.get(bot_id)
    if ev is not None:
        ev.set()
    if th is not None and th.is_alive():
        th.join(timeout=wait)
    rec = store.get_bot(bot_id)
    if rec and rec["runtime"].get("status") == "running" and not (th and th.is_alive()):
        def fn(r):
            r["runtime"]["status"] = "stopped"
        store.update_bot(bot_id, fn)
    return {"ok": True, "message": "Stopped."}


def kill_all() -> int:
    n = 0
    for bid in list(_THREADS):
        if is_running(bid):
            stop_bot(bid, wait=2.0)
            n += 1
    return n


def heal_stale_running() -> None:
    """After an app restart a bot saved as 'running' has no thread: mark it stopped so the page never shows a ghost."""
    for rec in store.list_bots():
        bid = rec["config"]["id"]
        if rec["runtime"].get("status") == "running" and not is_running(bid):
            def fn(r):
                r["runtime"]["status"] = "stopped"
                r["runtime"]["message"] = "Stopped (the app restarted). Press Start to resume."
            store.update_bot(bid, fn)
