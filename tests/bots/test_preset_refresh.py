"""Shipped bots follow their recipe revision: an old, idle copy is refreshed once; a running one is left alone; Objective B ships the round-4 twelve-leg book."""
from __future__ import annotations

import json

from app.bots import store
from app.bots.presets import PRESET_REV, preset_configs


def test_payout_hunter_is_the_twelve_leg_flex_book():
    b = next(c for c in preset_configs() if c.id == "bot-payout")
    assert len(b.legs) == 12 and b.legs[0].label == "Context Drive Long" and b.legs[-1].label == "Gap with trend GC"
    assert b.preset_rev == PRESET_REV and "five days of $150" in b.description


def _age(bot_id: str, status: str) -> None:
    def fn(rec):
        rec["config"]["preset_rev"] = 0
        rec["config"]["legs"] = rec["config"]["legs"][:1]
        rec["runtime"]["status"] = status
        rec["trades"] = [{"pnl": 1.0}]
    store.update_bot(bot_id, fn)


def test_old_idle_copy_is_refreshed_and_history_cleared():
    store.list_bots()
    _age("bot-payout", "stopped")
    rec = next(r for r in store.list_bots() if r["config"]["id"] == "bot-payout")
    assert rec["config"]["preset_rev"] == PRESET_REV and len(rec["config"]["legs"]) == 12
    assert rec["trades"] == [] and any("newest recipe" in e["text"] for e in rec["events"])


def test_running_copy_is_never_swapped_under_it():
    store.list_bots()
    _age("bot-payout", "running")
    rec = next(r for r in store.list_bots() if r["config"]["id"] == "bot-payout")
    assert rec["config"]["preset_rev"] == 0 and len(rec["config"]["legs"]) == 1
