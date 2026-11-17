from __future__ import annotations

import pytest

from app.web.server import app


@pytest.fixture()
def client():
    return app.test_client()


def _ok(r):
    j = r.get_json()
    assert r.status_code == 200 and j["ok"], j
    return j


def test_page_renders(client):
    r = client.get("/trading-bots", follow_redirects=True)
    assert r.status_code == 200


def test_lists_three_bots_on_demo(client):
    j = _ok(client.get("/trading-bots/api/bots"))
    assert len(j["bots"]) >= 3
    assert all(b["config"]["account"]["venue"] == "demo" for b in j["bots"] if b["config"].get("preset_key"))


def test_accounts_include_demo_first(client):
    j = _ok(client.get("/trading-bots/api/accounts"))
    assert j["accounts"][0]["id"] == "t58-demo"


def test_settings_clamped_and_saved(client):
    j = _ok(client.post("/trading-bots/api/bot/bot-pass/settings", json={"base_risk_pct": 99, "name": "Fast passer"}))
    assert j["bot"]["config"]["governor"]["base_risk_pct"] == 3.0
    assert j["bot"]["config"]["name"] == "Fast passer"


def test_broker_requires_account_and_guard(client):
    r = client.post("/trading-bots/api/bot/bot-pass/settings", json={"account": {"venue": "broker"}})
    assert r.status_code == 400
    _ok(client.post("/trading-bots/api/bot/bot-pass/settings", json={"account": {"venue": "broker", "account_id": "acct1"}}))
    r = client.post("/trading-bots/api/bot/bot-pass/start", json={})
    assert r.status_code in (401, 403, 404, 409) and not r.get_json()["ok"]


def test_cannot_delete_preset(client):
    r = client.post("/trading-bots/api/bot/bot-pass/delete", json={})
    assert r.status_code == 400


def test_duplicate_then_delete_custom(client):
    j = _ok(client.post("/trading-bots/api/bot/bot-profit/duplicate", json={}))
    bid = j["bot"]["config"]["id"]
    _ok(client.post(f"/trading-bots/api/bot/{bid}/delete", json={}))


def test_unknown_bot_404(client):
    assert client.get("/trading-bots/api/bot/zzz").status_code == 404
