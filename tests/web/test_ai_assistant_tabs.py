"""AI assistant page: three tabs (Assistant / Research / Analysis), every element the page's JS needs is still present."""
import pytest

from app.web.server import app


@pytest.fixture()
def body():
    import app.web.server as srv
    srv._license_ok_cached = True
    return app.test_client().get("/assistant/").get_data(as_text=True)


def test_three_tabs_and_their_panes(body):
    for tab in ("assistant", "research", "analysis"):
        assert f'data-tab="{tab}"' in body and f'id="ai-pane-{tab}"' in body
    assert body.count('role="tab"') == 3


def test_every_id_the_page_script_uses_still_exists(body):
    for el in ("chat-log", "chat-input", "send-btn", "news-panel", "rankings-panel", "director-panel", "director-reply", "outlook-reply",
               "symbol-picker-input", "symbol-picker-reply", "shot-file", "shot-notes", "ollama-dot", "mode-personal", "ai-enabled", "settings-status"):
        assert f'id="{el}"' in body, el


def test_old_tab_names_still_deep_link(body):
    assert "ask:'research'" in body and "analyze:'analysis'" in body
