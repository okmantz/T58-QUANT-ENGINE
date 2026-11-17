from __future__ import annotations

import pytest

from app.bots import builder, store
from app.bots.models import BotConfig
from app.web.server import app

GOOD = "python/NQ1! Open Drive Continuation 5m.py"
GOOD2 = "python/NQ1! Ind Rule 15m.py"


@pytest.fixture()
def client():
    return app.test_client()


def test_catalog_lists_library_and_flags_daily():
    cat = {r["id"]: r for r in builder.strategy_catalog()}
    assert cat[GOOD]["supported"] and cat[GOOD]["instrument"] == "NQ"
    daily = [r for r in cat.values() if not r["supported"]]
    assert daily and all(r["reason"] for r in daily)
    assert all(r["idea"] and not r["idea"].startswith("+--") for r in cat.values())


def test_every_goal_and_style_gives_a_valid_governor():
    for g in ("A", "B", "NET"):
        for st in builder.RISK_STYLES:
            gov = builder.style_governor(g, st)
            assert gov.objective == g and 0 < gov.base_risk_pct <= 3
    assert builder.style_governor("A", "nonsense").base_risk_pct == builder.style_governor("A", "balanced").base_risk_pct
    assert builder.style_governor("A", "conservative").base_risk_pct < builder.style_governor("A", "aggressive").base_risk_pct


def test_build_requires_name_goal_and_strategy():
    cfg, errs, _ = builder.build_config({})
    assert cfg is None and len(errs) >= 2
    cfg, errs, _ = builder.build_config({"name": "x", "objective": "B", "strategies": []})
    assert cfg is None and any("strategy" in e.lower() for e in errs)


def test_build_multi_strategy_bot_with_weights_and_clamping():
    cfg, errs, warns = builder.build_config({"name": "  My <b>bot</b> ", "objective": "net", "style": "aggressive",
                                             "strategies": [{"strategy": GOOD, "weight": 9}, GOOD2],
                                             "risk": {"base_risk_pct": 50, "cushion_risk_frac": ""}})
    assert cfg is not None and not errs
    assert cfg.objective == "NET" and cfg.name == "My bbbot" or cfg.name.startswith("My")
    assert [lg.weight for lg in cfg.legs] == [3.0, 1.0]
    assert cfg.governor["base_risk_pct"] == 3.0 and cfg.governor["cushion_risk_frac"] is None
    assert any("adjusted" in w for w in warns)
    assert cfg.account.venue == "paper" and cfg.account.broker_symbol == "MNQ"


def test_rejects_unknown_duplicate_traversal_and_daily_strategies():
    for bad in ("python/nope.py", "../app/server.py", "/etc/passwd"):
        cfg, errs, _ = builder.build_config({"name": "x", "objective": "A", "strategies": [bad]})
        assert cfg is None and errs
    cfg, errs, _ = builder.build_config({"name": "x", "objective": "A", "strategies": [GOOD, GOOD]})
    assert cfg is None and any("twice" in e for e in errs)
    daily = next(r["id"] for r in builder.strategy_catalog() if not r["supported"])
    cfg, errs, _ = builder.build_config({"name": "x", "objective": "A", "strategies": [daily]})
    assert cfg is None and errs


def test_broker_needs_an_account_and_progress_marks_are_ordered():
    cfg, errs, _ = builder.build_config({"name": "x", "objective": "A", "strategies": [GOOD], "account": {"venue": "broker"}})
    assert cfg is None and any("broker" in e.lower() for e in errs)
    cfg, errs, warns = builder.build_config({"name": "x", "objective": "A", "strategies": [GOOD], "risk": {"p1": 0.8, "p2": 0.3}})
    assert cfg is not None and cfg.governor["p2"] > cfg.governor["p1"]


def test_describe_in_plain_words_and_rule_free_net():
    cfg, _, _ = builder.build_config({"name": "x", "objective": "A", "strategies": [GOOD]})
    d = builder.describe(cfg)
    assert d["risk_dollars"] == 500.0 and "loss limit" in " ".join(d["lines"]) and not d["rule_free"]
    cfg, _, _ = builder.build_config({"name": "n", "objective": "NET", "strategies": [GOOD], "account": {"venue": "paper", "preset_key": ""}})
    d = builder.describe(cfg)
    assert d["rule_free"] and any("No prop-firm rules" in ln for ln in d["lines"])


def test_add_strategy_validates_and_cleans_up(tmp_path, monkeypatch):
    from app.strategy import library
    monkeypatch.setattr(library, "get_app_base_dir", lambda: tmp_path)
    row, err = builder.add_strategy("x.txt", "print(1)")
    assert row is None and "end in" in err
    row, err = builder.add_strategy("", "")
    assert row is None and err


def test_routes_create_preview_update_delete(client):
    j = client.get("/trading-bots/api/builder").get_json()
    assert j["ok"] and j["strategies"] and {g["key"] for g in j["goals"]} == {"A", "B", "NET"}
    body = {"name": "API bot", "objective": "B", "style": "conservative", "strategies": [GOOD, GOOD2]}
    p = client.post("/trading-bots/api/builder/preview", json=body).get_json()
    assert p["ok"] and p["summary"]["lines"]
    bad = client.post("/trading-bots/api/bots/create", json={"name": "", "objective": "A", "strategies": []})
    assert bad.status_code == 400 and not bad.get_json()["ok"]
    j = client.post("/trading-bots/api/bots/create", json=body).get_json()
    assert j["ok"]
    bid = j["bot"]["config"]["id"]
    assert len(j["bot"]["config"]["legs"]) == 2
    j = client.post(f"/trading-bots/api/bot/{bid}/update", json={"name": "Renamed", "objective": "B", "strategies": [GOOD], "risk": {"base_risk_pct": 0.7}}).get_json()
    assert j["ok"] and j["bot"]["config"]["name"] == "Renamed" and j["bot"]["config"]["governor"]["base_risk_pct"] == 0.7
    assert len(j["bot"]["config"]["legs"]) == 1
    assert client.post(f"/trading-bots/api/bot/{bid}/delete", json={}).get_json()["ok"]


def test_edit_keeps_shipped_preset_marker(client):
    j = client.post("/trading-bots/api/bot/bot-pass/update", json={"name": "Passer 2", "objective": "A", "strategies": [GOOD]}).get_json()
    assert j["ok"] and j["bot"]["config"]["preset_key"] == "pass"


def test_custom_bot_runs_a_short_simulation(client):
    j = client.post("/trading-bots/api/bots/create", json={"name": "Sim", "objective": "A", "strategies": [GOOD]}).get_json()
    cfg = BotConfig.from_dict(j["bot"]["config"])
    from app.bots import runner
    res = runner.start_simulation(cfg.id, months=0.25, speed="instant")
    assert res.get("ok"), res
    runner.stop_bot(cfg.id, wait=60.0)
