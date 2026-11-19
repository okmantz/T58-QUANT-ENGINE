"""Shipped bots follow their recipe revision: an old, idle copy is refreshed once; a running one is left alone; Objective B ships the 5-winning-days book."""
from __future__ import annotations

import json

from app.bots import store
from app.bots.presets import PRESET_REV, preset_configs


def test_payout_hunter_is_the_three_leg_winning_days_book():
    b = next(c for c in preset_configs() if c.id == "bot-payout")
    assert [(lg.label, lg.weight) for lg in b.legs] == [("Ind Rule", 1.0), ("Compression ORB", 0.25), ("Open Drive", 0.25)]
    assert b.preset_rev == PRESET_REV and "5-winning-days" in b.description


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
    assert rec["config"]["preset_rev"] == PRESET_REV and len(rec["config"]["legs"]) == 3
    assert rec["trades"] == [] and any("newest recipe" in e["text"] for e in rec["events"])


def test_running_copy_is_never_swapped_under_it():
    store.list_bots()
    _age("bot-payout", "running")
    rec = next(r for r in store.list_bots() if r["config"]["id"] == "bot-payout")
    assert rec["config"]["preset_rev"] == 0 and len(rec["config"]["legs"]) == 1
