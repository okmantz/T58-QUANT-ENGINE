"""Test page (Full Pipeline), a bot picked: the job starts and runs the bot through the same pipeline as a strategy (slow lane)."""
from __future__ import annotations

import time

import pytest

from app.web.server import app


@pytest.fixture(autouse=True)
def _isolated_bot_store(monkeypatch, tmp_path):
    from app.bots import store
    monkeypatch.setattr(store, "get_app_base_dir", lambda: tmp_path)


def test_full_pipeline_starts_and_finishes_on_a_bot():
    c = app.test_client()
    r = c.post("/full-pipeline/start", data={
        "existing_dataset": "NQ1!/futures_NQ.F_1m.parquet", "strategy_mode": "bot", "existing_strategy_bot": "bot-payout",
        "prop_preset": "lucid_50k", "account_size": "50000", "initial_balance": "50000", "skip_optimization": "on", "n_sims": "100",
        "mc_sims": "100", "risk_mode": "percent", "risk_value": "1.0"})
    assert r.status_code in (200, 302), r.get_data(as_text=True)[:500]
    loc = r.headers.get("Location", "")
    assert "/full-pipeline" in loc or r.status_code == 200
    jid = loc.rsplit("/", 1)[-1] if loc else None
    if not jid:
        pytest.skip("page rendered inline")
    j = {}
    for _ in range(500):
        j = c.get(f"/full-pipeline/job/{jid}/status.json").get_json() or {}
        if j.get("done"):
            break
        time.sleep(1)
    assert j.get("done"), "\n".join((j.get("log") or [])[-10:])
    assert not j.get("error"), j.get("error")
