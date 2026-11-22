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

from app.bots import gate27 as g27
from app.bots import store
from app.bots.arbiter import Arbiter, account_key
from app.bots.reconcile import reconcile
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


def bot_symbols(cfg: BotConfig) -> list:
    """Every instrument the bot's legs use, first-use order."""
    out: list = []
    for lg in cfg.legs:
        if lg.symbol not in out:
            out.append(lg.symbol)
    return out


def bot_span(cfg: BotConfig) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The stretch of history every one of the bot's instruments has."""
    spans = [history_span(s) for s in bot_symbols(cfg)]
    return max(a for a, _ in spans), min(b for _, b in spans)


def _flush_journal(cfg: BotConfig, rt: BotRuntime, trades: list) -> None:
    """Copy the trades booked since the last flush into the Trading Journal's trade log (every bot, on every account).
    Runs at every persist point, so a fill or a close reaches the journal as it happens on a live feed and in chunks in a replay."""
    pending = int(rt.trades_total) - int(rt.journal_cursor)
    if pending <= 0 or not trades:
        return
    try:
        from app.journal.capture import capture_bot_trades
        capture_bot_trades(cfg.to_dict(), trades[-pending:], mode=rt.mode or "simulation")
        rt.journal_cursor = int(rt.trades_total)
    except Exception:  # noqa: BLE001 -- the journal must never stop a bot; the next persist (or the journal's own sync) retries
        pass


def _persist(bot_id: str, cfg: BotConfig, rt: BotRuntime, trades: list, events: list) -> None:
    _flush_journal(cfg, rt, trades)

    def fn(rec):
        rec["runtime"], rec["trades"], rec["events"] = rt.to_dict(), trades, events
    store.update_bot(bot_id, fn)


def is_running(bot_id: str) -> bool:
    t = _THREADS.get(bot_id)
    return bool(t and t.is_alive())


# --------------------------------------------------------------------------------------------------------------------- simulation
def _build_sim_sources(cfg: BotConfig, start: pd.Timestamp, end: pd.Timestamp, events: list) -> tuple[dict, dict]:
    """(sources by leg label, {symbol: 1-minute bars inside [start, end]}) for every instrument the bot trades."""
    sources, frames = {}, {}
    g27_closes: dict = {}
    for lg in cfg.legs:
        try:
            df = load_history(lg.symbol)
        except FileNotFoundError:
            events.append({"t": now_iso(), "kind": "warn", "text": f"{lg.label}: no history bundled for {lg.symbol}; leg skipped."})
            continue
        if lg.kind == "gate27":
            g27_closes[lg.symbol] = g27.session_closes(df[df["timestamp"] <= end])
            continue
        w0 = start - pd.Timedelta(days=int(lg.lookback_days))
        seg = df[(df["timestamp"] >= w0) & (df["timestamp"] <= end)].reset_index(drop=True)
        try:
            strat = load_strategy(lg.strategy)
        except FileNotFoundError as exc:      # a strategy file was renamed or deleted: run the bot on the rest instead of halting it
            events.append({"t": now_iso(), "kind": "warn", "text": f"{lg.label}: strategy file not found ({exc}); leg skipped."})
            continue
        tf = strategy_timeframe_minutes(strat)
        sources[lg.label] = PrecomputedSignals(strat, seg, tf)
        frames.setdefault(lg.symbol, df)
    if g27_closes:
        shared = g27.Gate27Source(g27_closes, g27.config_from_params(next((lg.params for lg in cfg.legs if lg.kind == "gate27" and lg.params), None)))
        for lg in cfg.legs:
            if lg.kind == "gate27" and lg.symbol in g27_closes:
                sources[lg.label] = shared
                frames.setdefault(lg.symbol, load_history(lg.symbol))
    if not sources:
        raise ValueError("None of this bot's strategies could be loaded. Open Settings and pick strategies that exist in the library.")
    bars = {sym: df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].reset_index(drop=True) for sym, df in frames.items()}
    return sources, bars


def _merged_bars(bars: dict):
    """Yield (timestamp, {symbol: (o, h, l, c)}) over the union of the instruments' minutes, in time order."""
    syms = list(bars)
    if len(syms) == 1:
        sym = syms[0]
        b = bars[sym]
        ts = pd.DatetimeIndex(b["timestamp"])
        o, h, l, c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        for k in range(len(b)):
            yield ts[k], {sym: (o[k], h[k], l[k], c[k])}
        return
    def _ns(col) -> np.ndarray:                                   # epoch nanoseconds whatever unit pandas stored the timestamps in
        ix = pd.DatetimeIndex(col)
        ix = ix.tz_localize("UTC") if ix.tz is None else ix.tz_convert("UTC")
        return ix.as_unit("ns").asi8
    ns = {s: _ns(bars[s]["timestamp"]) for s in syms}
    allts = np.unique(np.concatenate(list(ns.values())))
    pos = {s: np.searchsorted(ns[s], allts) for s in syms}
    arr = {s: tuple(bars[s][k].to_numpy(float) for k in ("open", "high", "low", "close")) for s in syms}
    for k, tns in enumerate(allts):
        d = {}
        for s in syms:
            j = pos[s][k]
            if j < len(ns[s]) and ns[s][j] == tns:
                d[s] = (arr[s][0][j], arr[s][1][j], arr[s][2][j], arr[s][3][j])
        yield pd.Timestamp(int(tns), tz="UTC"), d


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
        lo, hi = bot_span(cfg)
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
        rules, mx, mm = rules_for_account(cfg.account, objective=cfg.objective)
        eng = BotEngine(cfg, rt, trades, events, venue, sources, rules=rules, max_minis=mx, max_micros=mm)
        chunk, i, since = 1380, 0, 0
        for ts, dbars in _merged_bars(bars):
            if stop.is_set() or rt.status != "running":
                break
            eng.on_bars(ts, dbars)
            rt.replay_cursor = ts.isoformat()
            i += 1
            if i % chunk == 0:
                _persist(bot_id, cfg, rt, trades, events)
                if pause:
                    time.sleep(pause)
        if rt.status == "running":
            if stop.is_set():
                rt.status, rt.message = "stopped", "Stopped. Press Start to continue from here."
            else:
                rt.status, rt.message = "stopped", "Replay reached the end of the bundled data. Reset to run again, or connect a live feed to continue in real time."
        if eng.open_positions() and rt.status != "running":
            eng.close_all("bot stopped: flattened")
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


def _broker_symbol(cfg: BotConfig, sym: str) -> str:
    """The broker's contract symbol for a research instrument: the account's own symbol for the primary instrument, the micro for the others."""
    from app.bots.builder import INSTRUMENTS
    prim = cfg.legs[0].symbol if cfg.legs else "NQ"
    return cfg.account.broker_symbol if sym == prim else INSTRUMENTS.get(sym, {}).get("micro", sym)


def _daily_closes_from_adapter(adapter, broker_sym: str) -> Optional[pd.DataFrame]:
    """Daily history for the Gate 27 legs from the broker (None when the adapter cannot provide it)."""
    try:
        df = adapter.fetch_completed_bars(broker_sym, 1440, 400)
    except Exception:  # noqa: BLE001
        return None
    if df is None or len(df) < g27.SMA_WINDOW:
        return None
    ts = pd.to_datetime(df["timestamp"])
    ts = ts.dt.tz_localize(None) if ts.dt.tz is None else ts.dt.tz_convert("UTC").dt.tz_localize(None)
    c = df["close"].astype(float).to_numpy()
    return pd.DataFrame({"close": c, "raw": c}, index=pd.DatetimeIndex(ts.dt.normalize()))


def _feed_loop(bot_id: str, adapter, poll_seconds: float, stop: threading.Event) -> None:
    rec = store.get_bot(bot_id)
    cfg, rt = BotConfig.from_dict(rec["config"]), BotRuntime.from_dict(rec["runtime"])
    trades, events = rec["trades"], rec["events"]
    windows: dict = {}
    try:
        prim = cfg.legs[0].symbol
        sources, g27_legs = {}, []
        for lg in cfg.legs:
            if lg.kind == "gate27":
                g27_legs.append(lg)
                continue
            try:
                strat = load_strategy(lg.strategy)
            except FileNotFoundError as exc:
                events.append({"t": now_iso(), "kind": "warn", "text": f"{lg.label}: strategy file not found ({exc}); leg skipped."})
                continue
            tf = strategy_timeframe_minutes(strat)
            sources[lg.label] = RollingSignals(strat, tf, (lambda s=lg.symbol: windows.get(s)))
        g27_src = None
        if g27_legs:
            closes = {}
            for lg in g27_legs:
                fr = _daily_closes_from_adapter(adapter, _broker_symbol(cfg, lg.symbol))
                if fr is None:
                    events.append({"t": now_iso(), "kind": "warn", "text": f"{lg.label}: the broker gave no daily history (210+ sessions needed); leg skipped."})
                else:
                    closes[lg.symbol] = fr
            if closes:
                g27_src = g27.Gate27Source(closes, g27.config_from_params(next((lg.params for lg in g27_legs if lg.params), None)))
                for lg in g27_legs:
                    if lg.symbol in closes:
                        sources[lg.label] = g27_src
        if not sources:
            raise ValueError("None of this bot's strategies could be loaded. Open Settings and pick strategies that exist in the library.")
        venue = venue_for(cfg.account, adapter=adapter) if cfg.account.venue == "broker" else venue_for(cfg.account)
        if hasattr(venue, "symbol_map"):
            venue.symbol_map = {sym: _broker_symbol(cfg, sym) for sym in bot_symbols(cfg)}
        rules, mx, mm = rules_for_account(cfg.account, objective=cfg.objective)
        eng = BotEngine(cfg, rt, trades, events, venue, sources, rules=rules, max_minis=mx, max_micros=mm,
                        arbiter=Arbiter.persistent(account_key(cfg.account)))
        reconcile(eng, venue)                       # a restart must not forget open positions or today's trades, and must trust the broker over its memory
        _persist(bot_id, cfg, rt, trades, events)
        need = max([lg.lookback_days for lg in cfg.legs if lg.kind != "gate27"] or [30]) * 1440
        last_t: dict = {prim: pd.Timestamp(rt.last_bar_time) if rt.last_bar_time else None}
        syms = [s for s in bot_symbols(cfg) if any(lg.symbol == s and lg.label in sources for lg in cfg.legs)]
        failures = 0
        while not stop.is_set() and rt.status == "running":
            try:
                fetched = {}
                for sym in syms:
                    try:
                        fetched[sym] = adapter.fetch_completed_bars(_broker_symbol(cfg, sym), 1, min(need, 50_000))
                    except Exception:  # noqa: BLE001
                        if sym == prim:
                            raise
                        events.append({"t": now_iso(), "kind": "warn", "text": f"No bars for {sym} from the broker this poll."})
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
            merged: dict = {}
            for sym, df in fetched.items():
                if df is None or not len(df):
                    continue
                df = df.reset_index(drop=True)
                ts = pd.to_datetime(df["timestamp"])
                if ts.dt.tz is None:
                    df["timestamp"] = ts.dt.tz_localize("UTC")
                windows[sym] = df
                lt = last_t.get(sym)
                new = df if lt is not None else df.tail(1)       # first connect: arm on the latest bar, never replay old bars into live orders
                if lt is not None:
                    new = df[df["timestamp"] > lt]
                for r in new.itertuples():
                    merged.setdefault(pd.Timestamp(r.timestamp), {})[sym] = (float(r.open), float(r.high), float(r.low), float(r.close))
                    last_t[sym] = pd.Timestamp(r.timestamp)
            for t in sorted(merged):
                before = (len(trades), tuple(sorted((x.symbol, x.ticket) for x in eng.open_positions())))
                eng.on_bars(t, merged[t])
                if (len(trades), tuple(sorted((x.symbol, x.ticket) for x in eng.open_positions()))) != before:
                    _persist(bot_id, cfg, rt, trades, events)      # a fill or a close hits the database at once, not at the end of the poll
                if rt.status != "running":
                    break
            if merged:
                _persist(bot_id, cfg, rt, trades, events)
            stop.wait(poll_seconds)
        if rt.status == "running":
            rt.status, rt.message = "stopped", "Stopped."
        if eng.open_positions() and rt.status != "running":
            venue.flatten_all()
            for ln in eng.lanes.values():
                if ln.pos is not None:
                    eng._lane = ln
                    eng._close_position(ln.last_price or float(rt.last_price), pd.Timestamp(ln.last_time or rt.last_bar_time or pd.Timestamp.utcnow()), "bot stopped: flattened", broker_closed=True)
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
