"""The Research Integrity page must never go blank: the API degrades per block and the page script is null-safe."""
import pytest

from app.validation import research_integrity as ri


@pytest.fixture
def client():
    from app.web.server import app
    return app.test_client()


def test_dashboard_survives_a_malformed_saved_report(client, monkeypatch):
    from app.discovery_engine import surrogate as sg
    bad = {"schema": sg.GATE_SCHEMA, "created_at": 1.0, "n_null": 70, "planted": [{"target_r": 0.2, "found": 5, "runs": 10}], "power": {"0.20": 0.5}}
    monkeypatch.setattr(sg, "load_report", lambda *a, **k: bad)
    d = ri.dashboard()
    assert d["detection"]["by_size"][0]["measured_r"] is None      # null measured_r is data, not a crash
    r = client.get("/api/research-integrity")
    assert r.status_code == 200 and r.json["ok"] is True


def test_dashboard_isolates_a_failing_block(monkeypatch):
    from app.discovery_engine import surrogate as sg
    monkeypatch.setattr(sg, "combined_false_positive", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    d = ri.dashboard()
    assert d["false_positive"]["measured"] is False
    assert any("boom" in w for w in d["warnings"])


def test_page_script_is_null_safe(client):
    body = client.get("/research-integrity").get_data(as_text=True)
    assert "function section(" in body and "isNum(" in body
    assert "p.measured_r.toFixed" not in body
