"""Validate page, a bot picked: the job starts and the checks run on the bot like on any strategy (slow lane: it runs a real Monte Carlo)."""
from __future__ import annotations

import time

import pytest

from app.web.server import app


@pytest.fixture(autouse=True)
def _isolated_bot_store(monkeypatch, tmp_path):
    from app.bots import store
    monkeypatch.setattr(store, "get_app_base_dir", lambda: tmp_path)


def test_validate_runs_on_a_bot():
    c = app.test_client()
    r = c.post("/validate-simple/start", data={
        "existing_dataset": "NQ1!/futures_NQ.F_1m.parquet", "strategy_pick": "bot::bot-payout", "prop_preset": "lucid_50k",
        "initial_balance": "50000", "check_monte_carlo": "on", "mc_sims": "100"})
    assert r.status_code == 302, r.get_data(as_text=True)[:300]
    jid = r.headers["Location"].rsplit("/", 1)[-1]
    j = {}
    for _ in range(280):
        j = c.get(f"/validate-simple/job/{jid}/status.json").get_json()
        if j["done"]:
            break
        time.sleep(1)
    assert j["done"], "\n".join((j.get("log") or [])[-10:])
    assert not j["error"], j["error"]
