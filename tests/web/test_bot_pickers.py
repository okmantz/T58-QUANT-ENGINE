"""Bots are selectable wherever a strategy is: Test (Full Pipeline), Optimize, Validate and Replay, and they run through the same chokepoints."""
from __future__ import annotations

import io
import json

import pytest

from app.web import server
from app.web.server import app


@pytest.fixture(autouse=True)
def _isolated_bot_store(monkeypatch, tmp_path):
    from app.bots import store
    monkeypatch.setattr(store, "get_app_base_dir", lambda: tmp_path)


def test_saved_strategies_json_carries_the_bots():
    data = json.loads(server._saved_strategies_json())
    ids = {b["name"] for b in data["bot"]}
    assert {"bot-pass", "bot-payout", "bot-profit"} <= ids
    assert all(b["label"] for b in data["bot"])


@pytest.mark.parametrize("url", ["/optimize-simple", "/validate-simple"])
def test_optimize_and_validate_pickers_list_bots(url):
    r = app.test_client().get(url)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'optgroup label="Bots"' in body and 'value="bot::bot-pass"' in body


def test_full_pipeline_and_replay_pickers_offer_bots():
    c = app.test_client()
    fp = c.get("/full-pipeline").get_data(as_text=True)
    assert "['bot', 'Bots']" in fp
    rp = c.get("/replay").get_data(as_text=True)
    assert "bot" in rp and "SAVED_STRATEGIES" in rp


def test_deploy_pages_never_list_bots_as_library_strategies():
    assert all(s["type"] != "bot" for s in server._simple_strategy_options())
    assert any(s["type"] == "bot" for s in server._simple_strategy_options(include_bots=True))


def test_build_strategy_resolves_a_bot_pick():
    with app.test_request_context("/"):
        form = {"strategy_mode": "bot", "existing_strategy_bot": "bot-payout"}
        strat, ref = server._build_strategy("bot", form, {})
    assert ref is None and strat.source_type == "bot" and strat.bot_id == "bot-payout"


def test_simple_load_strategy_accepts_bot_pick():
    with app.test_request_context("/", method="POST", data={"strategy_pick": "bot::bot-pass"}):
        strat, _ref = server._simple_load_strategy(server.request.form)
    assert strat.bot_id == "bot-pass"


def test_bot_is_loadable_for_replay_and_batch():
    strat = server._load_library_strategy_for_batch("bot", "bot-pass")
    assert strat.source_type == "bot"


def test_replay_runs_a_bot_on_stored_nq_data():
    r = app.test_client().post("/replay/prepare", data={
        "existing_dataset": "NQ1!/futures_NQ.F_1m.parquet", "strategy_mode": "library",
        "library_strategy_type": "bot", "library_strategy_name": "bot-pass", "max_bars": "6000",
        "initial_balance": "50000", "risk_mode": "percent", "risk_value": "1.0", "account_size": "50000"})
    assert r.status_code == 302 and "/replay/view/" in r.headers["Location"], r.get_data(as_text=True)[:400]
    data = app.test_client().get(r.headers["Location"].replace("/replay/view/", "/replay/data/") + ".json")
    assert data.status_code == 200 and data.get_json()["strategy_info"]["source_type"] == "bot"


def test_optimize_job_runs_the_bot_optimizer(monkeypatch):
    """A bot picked on the Optimize page is searched by the bot optimizer, not by the single-strategy engines."""
    import threading
    from app.optimize import bot_optimizer
    from app.strategy.bot_strategy import build_bot_strategy
    seen = {}

    def fake(df, cfg, risk, **kw):
        seen["bot"] = cfg.id
        return bot_optimizer.BotOptResult("B", False, "No change", {"Ind Rule": 1.0}, {"Ind Rule": 1.0}, None, {}, {"current": {}, "optimized": {}})

    monkeypatch.setattr(bot_optimizer, "optimize_bot", fake)
    job = server.JOB_MANAGER.create(tool="t", page_template="/x/{job_id}", log=[], progress={"percent": 0.0, "step": None, "step_total": 1, "step_label": "", "label": "", "elapsed_seconds": 0.0, "done": False})
    server._run_optimize_simple_job(job, None, build_bot_strategy("bot-payout"), None, None, ["quick_optimize"], {}, cancel_event=threading.Event())
    assert seen["bot"] == "bot-payout"
    assert server.JOB_MANAGER.get(job)["summary"]["bot_optimizer"]["improved"] is False
