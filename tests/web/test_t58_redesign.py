"""Redesign: funded demo choice, dashboard top three + bots, Create a Bot, Options in the Quant Lab, Deploy bot-or-strategy."""
import pytest

import app.web.server as server
from app.demo_account import account as D


@pytest.fixture()
def client():
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def _pass_the_evaluation():
    D.reset(50_000.0)
    D.record_trade(2_000.0, root="NQ", side="long", why="test")
    D.record_trade(1_100.0, root="NQ", side="long", why="test")
    return D.load()


def test_passed_account_offers_funded_or_reset(client):
    a = _pass_the_evaluation()
    assert a.status == "passed" and a.to_dict()["next_step"]["kind"] == "choose"
    html = client.get("/forward-test?view=demo").get_data(as_text=True)
    assert "Move to the funded demo account" in html and "Start the evaluation again" in html
    assert 'id="da-strategy"' in html and 'id="da-bots"' in html and 'id="da-kind"' in html


def test_funded_route_moves_on_and_reset_starts_over(client):
    _pass_the_evaluation()
    assert client.post("/demo-account/funded", json={}).get_json()["account"]["phase"] == "funded"
    a = D.load()
    assert a.phase == "funded" and a.status == "active"
    assert client.post("/demo-account/funded", json={}).status_code == 409      # only valid right after a pass
    assert client.post("/demo-account/reset", json={}).get_json()["account"]["phase"] == "evaluation"
    assert D.load().status == "active"


def test_payout_needs_the_rule_to_be_met(client):
    _pass_the_evaluation()
    client.post("/demo-account/funded", json={})
    r = client.post("/demo-account/payout", json={})
    assert r.status_code == 409 and r.get_json()["ok"] is False


def test_dashboard_shows_top_three_and_the_default_bots(client):
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'id="db-bots"' in html and "db-libbtn" in html
    assert html.count('<article class="sc ') <= 3


def test_create_tab_has_a_create_a_bot_card(client):
    html = client.get("/start-here/create").get_data(as_text=True)
    assert "Create a Bot" in html and "/trading-bots?new=1" in html


def test_options_outlook_lives_in_the_quant_lab(client):
    html = client.get("/quant-lab/").get_data(as_text=True)
    assert "Options Outlook" in html


def test_lifecycle_stepper_only_inside_lifecycle_pages():
    js = open("app/web/static/t58-chrome.js", encoding="utf-8").read()
    assert "if (current < 0) return;" in js


def test_deploy_pages_use_the_shared_deploy_styles(client):
    assert "t58-deploy.css" in client.get("/forward-test").get_data(as_text=True)
    assert "t58-deploy.css" in open("app/web/templates/deploy_live.html", encoding="utf-8").read()   # /deploy-live itself is access-gated
    assert 'data-kind="bot"' in client.get("/forward-test").get_data(as_text=True)


def test_bot_settings_accept_leg_tuning_and_demo_venue(client):
    bots = client.get("/trading-bots/api/bots").get_json()["bots"]
    assert len(bots) >= 3
    bid = bots[0]["config"]["id"]
    leg = bots[0]["config"]["legs"][0]["label"]
    r = client.post(f"/trading-bots/api/bot/{bid}/settings", json={"legs": [{"label": leg, "weight": 0.5}], "account": {"venue": "demo"}})
    assert r.get_json()["ok"] is True
