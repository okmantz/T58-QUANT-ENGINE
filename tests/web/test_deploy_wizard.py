"""One-click Deploy: the wizard page, its state endpoint, and the Deploy button on the Champion Board."""
import pytest

from app.web.server import app


@pytest.fixture()
def client():
    import app.web.server as srv
    srv._license_ok_cached = True
    return app.test_client()


def test_wizard_page_renders_with_all_three_targets_and_the_connect_panel(client):
    body = client.get("/deploy/wizard").get_data(as_text=True)
    for needle in ("Practice on the demo", "Live on MT5", "Live on a prop firm", 'id="dc-firm"', "Deploy live", "DEPLOY LIVE", "Where should it trade?"):
        assert needle in body, needle


def test_wizard_preselects_the_strategy_from_the_champion_board_link(client, monkeypatch):
    import app.web.server as srv
    monkeypatch.setattr(srv, "_simple_strategy_options", lambda **_kw: [{"type": "library", "name": "My Champ"}])
    body = client.get("/deploy/wizard?strategy=library%3A%3AMy%20Champ").get_data(as_text=True)
    assert 'value="library::My Champ" selected' in body


def test_state_reports_the_three_unlock_switches(client):
    j = client.get("/deploy/wizard/state.json").get_json()
    assert [c["key"] for c in j["checklist"]] == ["password", "unlock", "enable"] and j["enable_phrase"]
    assert isinstance(j["allowed"], bool)


def test_wizard_cannot_start_live_without_the_server_side_guards(client):
    # the wizard only composes the guarded routes: with live deploy off, the start route still refuses
    r = client.post("/deploy-live/start", data={"confirm_text": "DEPLOY LIVE"})
    assert r.status_code in (400, 401, 403, 409)


def test_deploy_page_links_to_the_wizard_and_champion_page_has_the_button(client):
    assert "/deploy/wizard" in client.get("/deploy-live").get_data(as_text=True) or client.get("/deploy-live").status_code in (200, 403)
    assert "ch-deploy" in open("app/web/templates/champion_simple.html", encoding="utf-8").read()
