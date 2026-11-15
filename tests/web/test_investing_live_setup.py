"""Live investing: picking Live now leads to a guided setup instead of a bare 'tick the box' error."""
import pytest

import app.web.investing_routes as ir
from app.web.server import app


@pytest.fixture()
def client(monkeypatch):
    import app.web.server as srv
    srv._license_ok_cached = True
    return app.test_client()


def test_live_without_keys_says_what_to_do_next(client, monkeypatch):
    monkeypatch.setattr("app.data.alpaca_credentials.has_saved_credentials", lambda: False)
    j = client.get("/investing/api/account?mode=live").get_json()
    assert j["ok"] is False and j["needs"] == "keys"
    assert client.get("/investing/api/live/status").get_json() == {"ok": True, "has_keys": False, "needs": "keys"}


def test_live_with_keys_but_not_armed_asks_for_the_confirmation_step(client, monkeypatch):
    monkeypatch.setattr("app.data.alpaca_credentials.has_saved_credentials", lambda: True)
    j = client.get("/investing/api/account?mode=live").get_json()
    assert j["needs"] == "confirm"
    # an order is refused the same way -- the guided panel is the only way to arm live mode
    r = client.post("/investing/api/order", json={"mode": "live", "symbol": "AAPL", "side": "buy", "dollars": 100})
    assert r.get_json()["needs"] == "confirm"


def test_connect_rejects_empty_keys_and_never_touches_paper(client):
    assert client.post("/investing/api/live/connect", json={"api_key": "", "secret_key": ""}).get_json()["ok"] is False
    assert client.get("/investing/api/account?mode=paper").get_json()["ok"] is True


def test_failed_key_test_restores_previous_working_keys(client, monkeypatch):
    from app.data import alpaca_credentials as ac
    saved = {}
    class C:  # noqa: D401
        is_usable = True
        api_key, secret_key = "OLDKEYOLDKEY", "OLDSECRETOLD"
    monkeypatch.setattr(ac, "load_credentials", lambda: C())
    monkeypatch.setattr(ac, "save_credentials", lambda k, s: saved.update(last=(k, s)))
    monkeypatch.setattr(ac, "clear_credentials", lambda: saved.update(cleared=True))
    import app.investing.broker_alpaca as ba
    monkeypatch.setattr(ba.AlpacaBroker, "state", lambda self, prices=None: (_ for _ in ()).throw(ba.BrokerError("401")))
    j = client.post("/investing/api/live/connect", json={"api_key": "NEWKEYNEWKEY", "secret_key": "NEWSECRETNEW"}).get_json()
    assert j["ok"] is False and saved["last"] == ("OLDKEYOLDKEY", "OLDSECRETOLD") and "cleared" not in saved


def test_page_renders_the_setup_panel(client):
    body = client.get("/investing").get_data(as_text=True)
    assert 'id="livesetup"' in body and "Turn on live trading" in body
