"""Persistence for Trading Bots: SQLite (WAL, one file under data/config/trading_bots.sqlite), thread-safe.

A restart must not forget an open position, a pending order or the day's trades, so every mutation is committed to disk in one transaction:

    bots(id, config, runtime, updated)       runtime carries the open position, the pending order, the day's trade count and realised P&L
    trades(bot_id, seq, body)                the closed-trade ledger (last MAX_TRADES kept)
    events(bot_id, seq, body)                the activity log (last MAX_EVENTS kept)
    day_ledger(account_key, day, ...)        the shared per-account, per-day counters used by the risk arbiter (app/bots/arbiter.py)

The public API is unchanged from the old JSON store (a record is still {config, runtime, trades, events}); an existing trading_bots.json is imported
once and renamed ``.migrated``. The three shipped presets are seeded on first load and can be reset to their calibrated defaults at any time."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from app.bots.models import BotConfig, BotRuntime, now_iso
from app.data.storage import get_app_base_dir

MAX_TRADES = 5000
MAX_EVENTS = 300
_FILE = "trading_bots.sqlite"
_LEGACY = "trading_bots.json"
_LOCK = threading.RLock()


def _dir() -> Path:
    d = get_app_base_dir() / "data" / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path() -> Path:
    return _dir() / _FILE


_SCHEMA = """
CREATE TABLE IF NOT EXISTS bots(id TEXT PRIMARY KEY, config TEXT NOT NULL, runtime TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trades(bot_id TEXT NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(bot_id, seq));
CREATE TABLE IF NOT EXISTS events(bot_id TEXT NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(bot_id, seq));
CREATE TABLE IF NOT EXISTS day_ledger(account_key TEXT NOT NULL, day TEXT NOT NULL, trades INTEGER NOT NULL DEFAULT 0,
    realised REAL NOT NULL DEFAULT 0, PRIMARY KEY(account_key, day));
CREATE TABLE IF NOT EXISTS arbiter_positions(account_key TEXT NOT NULL, bot_id TEXT NOT NULL, leg TEXT NOT NULL, symbol TEXT NOT NULL,
    direction INTEGER NOT NULL, qty REAL NOT NULL, risk_dollars REAL NOT NULL, opened TEXT NOT NULL, PRIMARY KEY(account_key, bot_id, leg));
"""


def connect() -> sqlite3.Connection:
    """A new connection (cheap) to the bots database, schema ensured. Callers use it as a context manager so a mutation commits atomically."""
    cx = sqlite3.connect(str(_path()), timeout=30, isolation_level=None)
    cx.row_factory = sqlite3.Row
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("PRAGMA synchronous=NORMAL")
    cx.executescript(_SCHEMA)
    return cx


class _Tx:
    def __init__(self):
        self.cx = connect()

    def __enter__(self):
        self.cx.execute("BEGIN IMMEDIATE")
        return self.cx

    def __exit__(self, et, ev, tb):
        try:
            self.cx.execute("ROLLBACK" if et else "COMMIT")
        finally:
            self.cx.close()
        return False


def _migrate_legacy(cx: sqlite3.Connection) -> None:
    legacy = _dir() / _LEGACY
    if not legacy.exists() or cx.execute("SELECT 1 FROM bots LIMIT 1").fetchone():
        return
    try:
        d = json.loads(legacy.read_text(encoding="utf-8"))
        for rec in (d.get("bots") or {}).values():
            _put(cx, rec)
        legacy.replace(legacy.with_suffix(".json.migrated"))
    except Exception:  # noqa: BLE001 - a corrupt legacy file must never stop the app; presets are seeded instead
        pass


def _put(cx: sqlite3.Connection, rec: dict) -> None:
    bid = rec["config"]["id"]
    trades = rec.get("trades", [])[-MAX_TRADES:]
    events = rec.get("events", [])[-MAX_EVENTS:]
    cx.execute("INSERT OR REPLACE INTO bots(id, config, runtime, updated) VALUES(?,?,?,?)",
               (bid, json.dumps(rec["config"]), json.dumps(rec.get("runtime") or {}), now_iso()))
    for table, rows in (("trades", trades), ("events", events)):
        cx.execute(f"DELETE FROM {table} WHERE bot_id=?", (bid,))
        cx.executemany(f"INSERT INTO {table}(bot_id, seq, body) VALUES(?,?,?)", [(bid, i, json.dumps(r)) for i, r in enumerate(rows)])


def _rec(cx: sqlite3.Connection, row: sqlite3.Row) -> dict:
    bid = row["id"]
    return {"config": json.loads(row["config"]), "runtime": json.loads(row["runtime"]),
            "trades": [json.loads(r["body"]) for r in cx.execute("SELECT body FROM trades WHERE bot_id=? ORDER BY seq", (bid,))],
            "events": [json.loads(r["body"]) for r in cx.execute("SELECT body FROM events WHERE bot_id=? ORDER BY seq", (bid,))]}


def _seed(cx: sqlite3.Connection) -> None:
    from app.bots.presets import preset_configs
    _migrate_legacy(cx)
    have = {r["id"]: r for r in cx.execute("SELECT id, config, runtime FROM bots")}
    for cfg in preset_configs():
        if cfg.id not in have:
            _put(cx, {"config": cfg.to_dict(), "runtime": BotRuntime().to_dict(), "trades": [], "events": []})
            continue
        # A shipped bot whose recipe changed (a newer preset_rev) replaces an OLDER, idle copy: its history belongs to the old recipe, so the copy starts clean.
        try:
            old_cfg, old_rt = json.loads(have[cfg.id]["config"]), json.loads(have[cfg.id]["runtime"] or "{}")
        except Exception:  # noqa: BLE001 -- a corrupt row is left for the user to reset
            continue
        if int(old_cfg.get("preset_rev", 0) or 0) < int(cfg.preset_rev) and old_cfg.get("preset_key") == cfg.preset_key \
                and (old_rt.get("status") or "stopped") in ("stopped", "complete", "halted"):
            rec = {"config": cfg.to_dict(), "runtime": BotRuntime().to_dict(), "trades": [],
                   "events": [{"t": now_iso(), "kind": "info", "text": f"{cfg.name} was updated to the newest recipe (revision {cfg.preset_rev}); its earlier run history was cleared."}]}
            _put(cx, rec)


def _open() -> sqlite3.Connection:
    cx = connect()
    _seed(cx)
    return cx


def list_bots() -> list[dict]:
    with _LOCK:
        cx = _open()
        try:
            rows = [_rec(cx, r) for r in cx.execute("SELECT * FROM bots")]
        finally:
            cx.close()
        order = {"A": 0, "B": 1, "NET": 2}
        rows.sort(key=lambda r: (0 if r["config"].get("preset_key") else 1, order.get(r["config"].get("objective"), 9), r["config"].get("created_at", "")))
        return rows


def get_bot(bot_id: str) -> Optional[dict]:
    with _LOCK:
        cx = _open()
        try:
            row = cx.execute("SELECT * FROM bots WHERE id=?", (bot_id,)).fetchone()
            return _rec(cx, row) if row else None
        finally:
            cx.close()


def save_bot(rec: dict) -> None:
    with _LOCK:
        _open().close()
        with _Tx() as cx:
            _put(cx, rec)


def update_bot(bot_id: str, fn) -> Optional[dict]:
    """Read-modify-write in one transaction: ``fn(rec)`` mutates the record in place; the result is on disk before this returns."""
    with _LOCK:
        _open().close()
        with _Tx() as cx:
            row = cx.execute("SELECT * FROM bots WHERE id=?", (bot_id,)).fetchone()
            if row is None:
                return None
            rec = _rec(cx, row)
            fn(rec)
            rec["trades"] = rec.get("trades", [])[-MAX_TRADES:]
            rec["events"] = rec.get("events", [])[-MAX_EVENTS:]
            _put(cx, rec)
            return rec


def add_event(rec: dict, kind: str, text: str, time: str = "") -> None:
    rec.setdefault("events", []).append({"t": time or now_iso(), "kind": kind, "text": text})


def create_bot(cfg: BotConfig) -> dict:
    with _LOCK:
        _open().close()
        rec = {"config": cfg.to_dict(), "runtime": BotRuntime().to_dict(), "trades": [], "events": []}
        with _Tx() as cx:
            _put(cx, rec)
        return rec


def delete_bot(bot_id: str) -> bool:
    """Custom bots can be deleted; the three shipped presets can only be reset (they are re-seeded)."""
    with _LOCK:
        _open().close()
        with _Tx() as cx:
            row = cx.execute("SELECT config FROM bots WHERE id=?", (bot_id,)).fetchone()
            if row is None or json.loads(row["config"]).get("preset_key"):
                return False
            for t in ("bots", "trades", "events"):
                cx.execute(f"DELETE FROM {t} WHERE {'id' if t == 'bots' else 'bot_id'}=?", (bot_id,))
            cx.execute("DELETE FROM arbiter_positions WHERE bot_id=?", (bot_id,))
            return True


def reset_bot(bot_id: str, *, keep_config: bool = True) -> Optional[dict]:
    """Clear trades/runtime/events (a fresh run). With keep_config=False a preset also returns to its shipped calibration."""
    from app.bots.presets import preset_configs
    with _LOCK:
        _open().close()
        with _Tx() as cx:
            row = cx.execute("SELECT config FROM bots WHERE id=?", (bot_id,)).fetchone()
            if row is None:
                return None
            cfg = json.loads(row["config"])
            if not keep_config and cfg.get("preset_key"):
                fresh = next((c for c in preset_configs() if c.id == bot_id), None)
                if fresh is not None:
                    cfg = fresh.to_dict()
            rec = {"config": cfg, "runtime": BotRuntime().to_dict(), "trades": [], "events": []}
            _put(cx, rec)
            cx.execute("DELETE FROM arbiter_positions WHERE bot_id=?", (bot_id,))
            return rec
