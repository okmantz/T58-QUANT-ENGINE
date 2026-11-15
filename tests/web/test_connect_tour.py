"""The quick 'connect a prop firm / MT5 and go live' tour sits beside the 60-second tour and never touches the first-run flag."""
import re
from pathlib import Path

import pytest

from app.web.server import app

JS = Path("app/web/static/t58-tour.js").read_text(encoding="utf-8")


@pytest.fixture()
def dash():
    import app.web.server as srv
    srv._license_ok_cached = True
    return app.test_client().get("/dashboard").get_data(as_text=True)


def test_button_sits_next_to_the_60_second_tour(dash):
    i, j = dash.index("60-second tour"), dash.index('data-t58-tour-start="connect"')
    assert 0 < j - i < 400 and "data-t58-tour-start>" in dash[:i + 40] or "data-t58-tour-start" in dash[:i]


def test_connect_tour_steps_and_deep_link():
    assert "var CONNECT_STEPS" in JS and 'start("connect")' in JS and "_connectSteps" in JS
    assert JS.count("/deploy/wizard") >= 2 and "/settings/account" in JS


def test_connect_tour_does_not_mark_the_main_tour_as_seen():
    assert re.search(r'if \(state\.kind !== "connect"\) markSeen\(how\)', JS)


def test_main_tour_is_unchanged_by_default():
    assert "var STEPS = MAIN_STEPS" in JS and "kind = (typeof kind === \"string\") ? kind : \"main\"" in JS
