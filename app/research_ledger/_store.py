"""Tiny append-only JSON Lines store shared by the ledgers. Reading never creates a folder; writing creates it on demand."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

_LOCK = threading.RLock()


def ledger_dir() -> Path:
    """``T58_RESEARCH_LEDGER_DIR`` (tests) or ``<app base>/data/research_ledger``. The folder is NOT created here."""
    env = os.environ.get("T58_RESEARCH_LEDGER_DIR", "").strip()
    if env:
        return Path(env)
    from app.data.storage import get_app_base_dir
    return Path(get_app_base_dir()) / "data" / "research_ledger"


def read_rows(name: str, base: Path | None = None) -> list[dict]:
    p = (base or ledger_dir()) / f"{name}.jsonl"
    if not p.exists():
        return []
    rows: list[dict] = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows


def append_row(name: str, row: dict, base: Path | None = None) -> dict:
    out = {"id": uuid.uuid4().hex[:12], "ts": round(time.time(), 3), **row}
    d = base or ledger_dir()
    with _LOCK:
        d.mkdir(parents=True, exist_ok=True)
        with (d / f"{name}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(out, default=str) + "\n")
    return out
