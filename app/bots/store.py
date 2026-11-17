"""Persistence for Trading Bots: one JSON file under data/config/ (atomic write, thread-safe), same pattern as the demo account.

Each bot record: {config, runtime, trades[<=MAX_TRADES], events[<=MAX_EVENTS]}. The three shipped presets are seeded on first load and
can be reset to their calibrated defaults at any time without touching a user's custom bots."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from app.bots.models import BotConfig, BotRuntime, now_iso
from app.data.storage import get_app_base_dir

MAX_TRADES = 5000
MAX_EVENTS = 300
_FILE = "trading_bots.json"
_LOCK = threading.RLock()


def _path() -> Path:
    d = get_app_base_dir() / "data" / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d / _FILE


def _read() -> dict:
    try:
        d = json.loads(_path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001 - missing or corrupt file: start clean, never crash the page
        return {}


def _write(d: dict) -> None:
    p = _path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d), encoding="utf-8")
    tmp.replace(p)


def _seed(d: dict) -> dict:
    from app.bots.presets import preset_configs
    bots = d.setdefault("bots", {})
    for cfg in preset_configs():
        if cfg.id not in bots:
            bots[cfg.id] = {"config": cfg.to_dict(), "runtime": BotRuntime().to_dict(), "trades": [], "events": []}
    return d


def _load() -> dict:
    return _seed(_read())


def list_bots() -> list[dict]:
    with _LOCK:
        d = _load()
        order = {"A": 0, "B": 1, "NET": 2}
        rows = list(d["bots"].values())
        rows.sort(key=lambda r: (0 if r["config"].get("preset_key") else 1, order.get(r["config"].get("objective"), 9), r["config"].get("created_at", "")))
        return rows


def get_bot(bot_id: str) -> Optional[dict]:
    with _LOCK:
        return _load()["bots"].get(bot_id)


def save_bot(rec: dict) -> None:
    with _LOCK:
        d = _load()
        rec["trades"] = rec.get("trades", [])[-MAX_TRADES:]
        rec["events"] = rec.get("events", [])[-MAX_EVENTS:]
        d["bots"][rec["config"]["id"]] = rec
        _write(d)


def update_bot(bot_id: str, fn) -> Optional[dict]:
    """Read-modify-write under the lock: ``fn(rec)`` mutates the record in place."""
    with _LOCK:
        d = _load()
        rec = d["bots"].get(bot_id)
        if rec is None:
            return None
        fn(rec)
        rec["trades"] = rec.get("trades", [])[-MAX_TRADES:]
        rec["events"] = rec.get("events", [])[-MAX_EVENTS:]
        _write(d)
        return rec


def add_event(rec: dict, kind: str, text: str, time: str = "") -> None:
    rec.setdefault("events", []).append({"t": time or now_iso(), "kind": kind, "text": text})


def create_bot(cfg: BotConfig) -> dict:
    with _LOCK:
        d = _load()
        rec = {"config": cfg.to_dict(), "runtime": BotRuntime().to_dict(), "trades": [], "events": []}
        d["bots"][cfg.id] = rec
        _write(d)
        return rec


def delete_bot(bot_id: str) -> bool:
    """Custom bots can be deleted; the three shipped presets can only be reset (they are re-seeded)."""
    with _LOCK:
        d = _load()
        rec = d["bots"].get(bot_id)
        if rec is None or rec["config"].get("preset_key"):
            return False
        del d["bots"][bot_id]
        _write(d)
        return True


def reset_bot(bot_id: str, *, keep_config: bool = True) -> Optional[dict]:
    """Clear trades/runtime/events (a fresh run). With keep_config=False a preset also returns to its shipped calibration."""
    from app.bots.presets import preset_configs
    with _LOCK:
        d = _load()
        rec = d["bots"].get(bot_id)
        if rec is None:
            return None
        cfg = rec["config"]
        if not keep_config and cfg.get("preset_key"):
            fresh = next((c for c in preset_configs() if c.id == bot_id), None)
            if fresh is not None:
                cfg = fresh.to_dict()
        d["bots"][bot_id] = {"config": cfg, "runtime": BotRuntime().to_dict(), "trades": [], "events": []}
        _write(d)
        return d["bots"][bot_id]
