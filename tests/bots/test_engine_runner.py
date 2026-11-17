from __future__ import annotations

import time

import pytest

from app.bots import runner, store


def test_simulation_runs_and_books_to_runtime():
    store.list_bots()
    res = runner.start_simulation("bot-pass", months=1, speed="instant")
    assert res["ok"]
    t0 = time.time()
    while runner.is_running("bot-pass") and time.time() - t0 < 120:
        time.sleep(0.5)
    rec = store.get_bot("bot-pass")
    assert rec["runtime"]["status"] in ("stopped", "halted", "complete")
    assert rec["runtime"]["replay_cursor"]
    for t in rec["trades"]:
        assert {"leg", "side", "pnl", "entry", "exit"} <= set(t)


def test_live_feed_refused_without_unlock():
    store.list_bots()
    store.update_bot("bot-pass", lambda r: r["config"]["account"].update(venue="broker", account_id="x"))
    res = runner.start_feed("bot-pass", object(), live_ok=False)
    assert not res["ok"]


def test_unknown_bot():
    assert not runner.start_simulation("nope")["ok"]


def test_skip_events_are_deduplicated():
    from app.bots.engine import BotEngine
    from app.bots.models import BotConfig, BotRuntime
    from app.bots.venues import PaperVenue
    eng = BotEngine(BotConfig(name="t"), BotRuntime(status="running"), [], [], PaperVenue(), {})
    for _ in range(5):
        eng._event("skip", "Open Drive signal skipped: day stop: down $506")
    assert len(eng.events) == 1
